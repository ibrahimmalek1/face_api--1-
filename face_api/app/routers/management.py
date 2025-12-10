from fastapi import APIRouter, Form, HTTPException
from app.services.face_service import face_service
from app.services.aws_service import aws_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/management", tags=["management"])

@router.post("/list-files")
async def list_folder_contents(
    directory: str = Form(..., description="Folder name to list (e.g., 'class-10')")
):
    """
    Get a list of all images inside a specific folder (Using Local Database).
    """
    files = await face_service.list_files_in_directory(directory)
    
    return {
        "directory": directory,
        "total_files": len(files),
        "files": files
    }

@router.delete("/delete-folder")
async def delete_entire_folder(
    directory: str = Form(..., description="WARNING: This will delete the folder and ALL images inside it.")
):
    """
    Permanently delete a folder.
    1. Finds files in Local DB.
    2. Deletes them from S3.
    3. Removes records from Local DB.
    """
    try:
        # 1. Get keys and remove from DB
        s3_keys_to_delete = await face_service.get_and_delete_folder_records(directory)
        
        if not s3_keys_to_delete:
            return {
                "status": "success",
                "message": f"Folder '{directory}' was empty or didn't exist in database.",
                "deleted_count": 0
            }

        # 2. Delete from AWS S3
        # This bypasses the need for 'ListBucket' permission because we provide the exact keys.
        deleted_count = await aws_service.delete_multiple_files(s3_keys_to_delete)
        
        return {
            "status": "success",
            "message": f"Successfully deleted folder '{directory}'",
            "db_records_removed": len(s3_keys_to_delete),
            "s3_files_deleted": deleted_count
        }
    except Exception as e:
        logger.error(f"Delete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")