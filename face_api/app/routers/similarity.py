from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional # <--- Important
import time
import logging
from app.models.schemas import SearchResponse, FaceMatch
from app.services.face_service import face_service
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/similarity", tags=["similarity"])

@router.post("/search", response_model=SearchResponse)
async def search_faces(
    file: UploadFile = File(..., description="Upload the photo you want to find"),
    
    # --- CHANGED: Optional Directory ---
    directory: Optional[str] = Form(None, description="Leave empty to search ALL folders. Or type a folder name."),
    # -----------------------------------
    
    limit: int = Form(5, description="Max matches to return"),
    threshold: float = Form(0.40, description="Sensitivity (Lower is stricter)")
):
    """
    Search for a person.
    - Provide 'directory' to filter search.
    - Leave 'directory' empty to search entire database.
    """
    start_time = time.time()
    temp_file_path = None
    
    try:
        # 1. Validation
        if not file.filename: raise HTTPException(status_code=400, detail="No filename")
        file_extension = None
        for ext in settings.allowed_extensions:
            if file.filename.lower().endswith(ext):
                file_extension = ext
                break
        if not file_extension: raise HTTPException(status_code=400, detail="Invalid file type")

        # 2. Process Image (Stream)
        temp_file_path = await face_service.process_image_file(file.file, file_extension)

        # 3. Perform Search
        matches = await face_service.search_similar_faces(
            query_image_path=temp_file_path, 
            directory_name=directory, # Can be None now
            threshold=threshold
        )

        # 4. Format Results
        formatted_matches = []
        for match in matches[:limit]:
            formatted_matches.append(FaceMatch(
                image_path=match[0],
                s3_url=match[1],
                similarity_score=float(match[2])
            ))

        return SearchResponse(
            total_matches=len(formatted_matches),
            matches=formatted_matches,
            processing_time=time.time() - start_time,
            error=None
        )

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return SearchResponse(
            total_matches=0, matches=[], processing_time=time.time() - start_time, error=str(e)
        )
        
    finally:
        await file.close()
        if temp_file_path:
            face_service.cleanup_temp_file(temp_file_path)

@router.get("/stats")
async def get_database_stats():
    try:
        faces = await face_service.get_all_faces()
        return {
            "total_faces": len(faces),
            "status": "healthy"
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to get stats")