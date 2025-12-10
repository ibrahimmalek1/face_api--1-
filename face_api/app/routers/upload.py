from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
import time
import asyncio
import logging
import os
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from app.models.schemas import BulkUploadResponse, ImageUploadResponse
from app.services.aws_service import aws_service
from app.services.face_service import face_service
from app.services.image_processing_service import image_processing_service
from app.core.config import settings

console = Console()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

CONCURRENCY_LIMIT = 5 
DEFAULT_WATERMARK_PATH = "app/assets/default_watermark.png"

# --- HELPER: Get Watermark ---
async def get_watermark_bytes(user_file: UploadFile | None) -> bytes | None:
    if user_file: return await user_file.read()
    if os.path.exists(DEFAULT_WATERMARK_PATH):
        with open(DEFAULT_WATERMARK_PATH, "rb") as f: return f.read()
    return None

# --- HELPER: Process Standard File (With Compress + Watermark) ---
async def process_standard_file(file: UploadFile, watermark_bytes, directory, progress, overall_task):
    task_id = progress.add_task(f"Waiting...", total=4, visible=False)
    try:
        progress.update(task_id, visible=True, description=f"🔄 Processing: {file.filename}")
        
        if not file.filename: raise Exception("No filename")
        file_extension = None
        for ext in settings.allowed_extensions:
            if file.filename.lower().endswith(ext):
                file_extension = ext; break
        if not file_extension: raise Exception("Invalid file type")
        
        progress.update(task_id, advance=1)

        # 1. Process Image (Compress + Watermark)
        loop = asyncio.get_event_loop()
        processed_content = await loop.run_in_executor(
            None, image_processing_service.process_image, file.file, watermark_bytes
        )
        final_extension = ".jpg" # Standard uploads become JPG
        
        progress.update(task_id, advance=1, description=f"☁️ Uploading...")
        
        # 2. Upload
        s3_url = await aws_service.upload_file(processed_content, final_extension, folder_path=directory)
        
        progress.update(task_id, advance=1, description=f"👤 Detecting Face...")
        
        # 3. Detect
        temp_file_path = await face_service.process_image_file(processed_content, final_extension)
        embedding_stored = await face_service.store_embedding(temp_file_path, s3_url)
        face_service.cleanup_temp_file(temp_file_path)
        
        progress.update(task_id, advance=1, visible=False)
        progress.advance(overall_task)
        
        return ImageUploadResponse(filename=file.filename, s3_url=s3_url, processed=True, embedding_stored=embedding_stored, error=None)
    except Exception as e:
        progress.update(task_id, visible=False)
        progress.advance(overall_task)
        return ImageUploadResponse(filename=file.filename, s3_url="", processed=False, embedding_stored=False, error=str(e))
    finally:
        await file.close()

# --- HELPER: Process Original File (NO Compress, NO Watermark) ---
async def process_original_file(file: UploadFile, directory, progress, overall_task):
    task_id = progress.add_task(f"Waiting...", total=3, visible=False)
    try:
        progress.update(task_id, visible=True, description=f"🔄 Reading: {file.filename}")
        
        if not file.filename: raise Exception("No filename")
        # Extract extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in settings.allowed_extensions: raise Exception("Invalid file type")
        
        progress.update(task_id, advance=1, description=f"☁️ Uploading Original...")
        
        # 1. Upload Stream DIRECTLY to AWS (Supports 100MB+)
        # We use file.file which is the stream
        s3_url = await aws_service.upload_file(file.file, file_extension, folder_path=directory)
        
        progress.update(task_id, advance=1, description=f"👤 Detecting Face...")
        
        # 2. Reset stream to start for Face Detection
        file.file.seek(0) 
        
        # 3. Detect
        temp_file_path = await face_service.process_image_file(file.file, file_extension)
        embedding_stored = await face_service.store_embedding(temp_file_path, s3_url)
        face_service.cleanup_temp_file(temp_file_path)
        
        progress.update(task_id, advance=1, visible=False)
        progress.advance(overall_task)
        
        return ImageUploadResponse(filename=file.filename, s3_url=s3_url, processed=False, embedding_stored=embedding_stored, error=None)
    except Exception as e:
        progress.update(task_id, visible=False)
        progress.advance(overall_task)
        console.print(f"[red]Failed {file.filename}: {e}[/red]")
        return ImageUploadResponse(filename=file.filename, s3_url="", processed=False, embedding_stored=False, error=str(e))
    finally:
        await file.close()

# ===================== STANDARD ENDPOINTS (Compress + Watermark) =====================

@router.post("/single", response_model=ImageUploadResponse)
async def upload_single_image(
    file: UploadFile = File(..., description="Select an image"),
    watermark_file: UploadFile = File(None, description="Upload a logo image (optional)"),
    directory: str = Form("face-images")
):
    watermark_bytes = await get_watermark_bytes(watermark_file)
    with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"), BarColumn(), console=console) as progress:
        task = progress.add_task("Single Upload", total=1)
        return await process_standard_file(file, watermark_bytes, directory, progress, task)

@router.post("/bulk", response_model=BulkUploadResponse)
async def bulk_upload_images(
    files: List[UploadFile] = File(..., description="Select multiple images"),
    watermark_file: UploadFile = File(None, description="Upload a logo image (optional)"),
    directory: str = Form("face-images")
):
    start_time = time.time()
    watermark_bytes = await get_watermark_bytes(watermark_file)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def sem_task(file):
        async with semaphore: return await process_standard_file(file, watermark_bytes, directory, progress, overall_task)

    with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), console=console) as progress:
        overall_task = progress.add_task(f"[green]Batch Processing...", total=len(files))
        tasks = [sem_task(file) for file in files]
        results = await asyncio.gather(*tasks)

    successful = sum(1 for r in results if r.embedding_stored)
    return BulkUploadResponse(total_files=len(files), successful_uploads=successful, failed_uploads=len(results)-successful, results=results, processing_time=time.time()-start_time)


# ===================== ORIGINAL ENDPOINTS (No Compress, No Watermark) =====================

@router.post("/original/single", response_model=ImageUploadResponse)
async def upload_original_single(
    file: UploadFile = File(..., description="Select an image (Original Quality, No Compression)"),
    directory: str = Form("face-images")
):
    with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"), BarColumn(), console=console) as progress:
        task = progress.add_task("Single Original Upload", total=1)
        return await process_original_file(file, directory, progress, task)

@router.post("/original/bulk", response_model=BulkUploadResponse)
async def upload_original_bulk(
    files: List[UploadFile] = File(..., description="Select multiple images (Original Quality)"),
    directory: str = Form("face-images")
):
    start_time = time.time()
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def sem_task(file):
        async with semaphore: return await process_original_file(file, directory, progress, overall_task)

    with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), console=console) as progress:
        overall_task = progress.add_task(f"[green]Original Batch...", total=len(files))
        tasks = [sem_task(file) for file in files]
        results = await asyncio.gather(*tasks)

    successful = sum(1 for r in results if r.embedding_stored)
    return BulkUploadResponse(total_files=len(files), successful_uploads=successful, failed_uploads=len(results)-successful, results=results, processing_time=time.time()-start_time)