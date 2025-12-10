import sqlite3
import numpy as np
import tempfile
import os
import shutil
from typing import List, Tuple, BinaryIO, Dict
from deepface import DeepFace
from scipy.spatial.distance import cosine
from fastapi import HTTPException
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class FaceService:
    def __init__(self):
        self.db_path = "faces.db"
        self._init_database()

    def _init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_path TEXT UNIQUE,
                    s3_url TEXT,
                    embedding BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise HTTPException(status_code=500, detail="Database initialization failed")

    async def get_and_delete_folder_records(self, directory_name: str) -> List[str]:
        """Finds files in DB matching folder, deletes rows, returns S3 keys."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            search_pattern = f"%/{directory_name}/%"
            
            c.execute("SELECT s3_url FROM faces WHERE s3_url LIKE ?", (search_pattern,))
            rows = c.fetchall()
            
            if not rows:
                conn.close()
                return []
                
            c.execute("DELETE FROM faces WHERE s3_url LIKE ?", (search_pattern,))
            conn.commit()
            conn.close()

            s3_keys = []
            for row in rows:
                url = row[0]
                if "amazonaws.com/" in url:
                    key = url.split("amazonaws.com/")[-1]
                    s3_keys.append(key)
            return s3_keys
        except Exception as e:
            logger.error(f"Failed to delete records: {str(e)}")
            return []

    async def list_files_in_directory(self, directory_name: str) -> List[Dict[str, str]]:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            search_pattern = f"%/{directory_name}/%"
            c.execute("SELECT image_path, s3_url, created_at FROM faces WHERE s3_url LIKE ?", (search_pattern,))
            rows = c.fetchall()
            conn.close()

            files = []
            for row in rows:
                files.append({"filename": row[0], "s3_url": row[1], "created_at": row[2]})
            return files
        except Exception:
            return []

    async def store_embedding(self, image_path: str, s3_url: str) -> bool:
        try:
            embedding_objs = DeepFace.represent(img_path=image_path, model_name=settings.face_model_name, enforce_detection=False)
            embedding = embedding_objs[0]["embedding"]
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()

            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO faces (image_path, s3_url, embedding) VALUES (?, ?, ?)", (image_path, s3_url, embedding_bytes))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to store embedding: {str(e)}")
            return False

    async def get_all_faces(self) -> List[Tuple[str, str, bytes]]:
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT image_path, s3_url, embedding FROM faces")
            results = c.fetchall()
            conn.close()
            return results
        except Exception:
            return []

    # --- UPDATED LOGIC HERE ---
    async def search_similar_faces(self, query_image_path: str, directory_name: str | None, threshold: float = 0.40) -> List[Tuple[str, str, float]]:
        """
        Search for similar faces.
        - If directory_name is provided: Search ONLY that folder.
        - If directory_name is None/Empty: Search EVERYTHING.
        """
        try:
            # 1. Generate Query Embedding
            query_embedding_objs = DeepFace.represent(
                img_path=query_image_path, 
                model_name=settings.face_model_name,
                enforce_detection=False
            )
            query_embedding = np.array(query_embedding_objs[0]["embedding"], dtype=np.float32)

            # 2. Prepare SQL
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if directory_name and directory_name.strip():
                # Specific Folder Search
                search_pattern = f"%/{directory_name}/%"
                c.execute("SELECT image_path, s3_url, embedding FROM faces WHERE s3_url LIKE ?", (search_pattern,))
            else:
                # Global Search (No WHERE clause)
                c.execute("SELECT image_path, s3_url, embedding FROM faces")
            
            stored_faces = c.fetchall()
            conn.close()
            
            if not stored_faces:
                return []

            results = []
            for image_path, s3_url, embedding_bytes in stored_faces:
                try:
                    db_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                    distance = cosine(query_embedding, db_embedding)
                    
                    if distance < threshold:
                        results.append((image_path, s3_url, 1 - distance))
                except Exception:
                    continue

            results.sort(key=lambda x: x[2], reverse=True)
            return results
            
        except Exception as e:
            logger.error(f"Failed to search: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Face search failed: {str(e)}")

    async def process_image_file(self, file_input: BinaryIO | bytes, file_extension: str) -> str:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                if isinstance(file_input, bytes):
                    tmp_file.write(file_input)
                else:
                    shutil.copyfileobj(file_input, tmp_file)
                return tmp_file.name
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to process image file")

    def cleanup_temp_file(self, file_path: str):
        if os.path.exists(file_path):
            os.unlink(file_path)

face_service = FaceService()