import boto3
import uuid
from typing import Optional, List, Dict, BinaryIO
from fastapi import HTTPException
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class AWSService:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_id,
            aws_secret_access_key=settings.aws_secret,
            region_name=settings.region
        )
        self.bucket_name = settings.aws_s3_bucket

    # --- CHANGED: Accepts bytes OR BinaryIO (Stream) for large files ---
    async def upload_file(self, file_content: bytes | BinaryIO, file_extension: str, folder_path: str = "face-images") -> str:
        """Upload file (or stream) to S3 in a specific folder"""
        try:
            filename = f"{uuid.uuid4()}{file_extension}"
            clean_folder = folder_path.strip("/")
            s3_key = f"{clean_folder}/{filename}"
            
            # boto3 'Body' accepts bytes or a read()able file-like object (Stream)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content, 
                ContentType=f"image/{file_extension[1:]}"
            )
            
            s3_url = f"https://{self.bucket_name}.s3.{settings.region}.amazonaws.com/{s3_key}"
            logger.info(f"Successfully uploaded file to S3: {s3_url}")
            return s3_url
            
        except Exception as e:
            logger.error(f"Failed to upload file to S3: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

    async def delete_multiple_files(self, s3_keys: List[str]) -> int:
        """Delete a list of specific files from S3."""
        try:
            if not s3_keys: return 0
            objects_to_delete = [{'Key': key} for key in s3_keys]
            self.s3_client.delete_objects(Bucket=self.bucket_name, Delete={'Objects': objects_to_delete})
            logger.info(f"Deleted {len(objects_to_delete)} files from S3")
            return len(objects_to_delete)
        except Exception as e:
            logger.error(f"Failed to delete files from S3: {str(e)}")
            return 0

    async def list_files_in_folder(self, folder_path: str) -> List[Dict[str, str]]:
        """List all files inside a specific S3 folder (Requires ListBucket permission)."""
        try:
            clean_prefix = folder_path.strip("/") + "/"
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=clean_prefix)
            if 'Contents' not in response: return []
            files = []
            for obj in response['Contents']:
                key = obj['Key']
                if key == clean_prefix: continue
                url = f"https://{self.bucket_name}.s3.{settings.region}.amazonaws.com/{key}"
                files.append({
                    "filename": key.split("/")[-1],
                    "full_path": key,
                    "s3_url": url,
                    "size": obj['Size']
                })
            return files
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

    async def delete_folder(self, folder_path: str) -> int:
        """Delete all files inside a folder (Requires ListBucket permission)."""
        try:
            clean_prefix = folder_path.strip("/") + "/"
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=clean_prefix)
            if 'Contents' not in response: return 0
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
            if objects_to_delete:
                self.s3_client.delete_objects(Bucket=self.bucket_name, Delete={'Objects': objects_to_delete})
                return len(objects_to_delete)
            return 0
        except Exception as e:
            logger.error(f"Failed to delete folder: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete folder: {str(e)}")

aws_service = AWSService()