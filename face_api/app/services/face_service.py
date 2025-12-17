import mysql.connector
from mysql.connector import pooling
import numpy as np
import tempfile
import os
import shutil
from typing import List, Tuple, BinaryIO, Dict, Optional
from deepface import DeepFace
from scipy.spatial.distance import cosine
from fastapi import HTTPException
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class FaceService:
    def __init__(self):
        # 1. Setup MySQL Connection Pool
        self.db_config = {
            "host": settings.mysql_host,
            "user": settings.mysql_user,
            "password": settings.mysql_password,
            "database": settings.mysql_db,
            "port": settings.mysql_port
        }
        # Create a pool to handle multiple connections efficiently
        self.pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=5,
            **self.db_config
        )
        self._init_database()

    def _get_connection(self):
        return self.pool.get_connection()

    def _init_database(self):
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            # MySQL Syntax: AUTO_INCREMENT instead of AUTOINCREMENT, LONGBLOB for embeddings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS faces (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    image_path VARCHAR(255) UNIQUE,
                    s3_url TEXT,
                    embedding LONGBLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            # We don't raise here to avoid crashing app on startup if DB is waking up
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    async def get_and_delete_folder_records(self, directory_name: str) -> List[str]:
        """Finds files in DB matching folder, deletes rows, returns S3 keys."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            search_pattern = f"%/{directory_name}/%"
            
            # MySQL uses %s placeholder, not ?
            cursor.execute("SELECT s3_url FROM faces WHERE s3_url LIKE %s", (search_pattern,))
            rows = cursor.fetchall()
            
            if not rows:
                return []
                
            cursor.execute("DELETE FROM faces WHERE s3_url LIKE %s", (search_pattern,))
            conn.commit()

            s3_keys = []
            for row in rows:
                url = row[0]
                # Extract key from URL
                if "amazonaws.com/" in url:
                    key = url.split("amazonaws.com/")[-1]
                    s3_keys.append(key)
            return s3_keys
        except Exception as e:
            logger.error(f"Failed to delete records: {str(e)}")
            return []
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    async def list_files_in_directory(self, directory_name: str) -> List[Dict[str, str]]:
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            search_pattern = f"%/{directory_name}/%"
            
            cursor.execute("SELECT image_path, s3_url, created_at FROM faces WHERE s3_url LIKE %s", (search_pattern,))
            rows = cursor.fetchall()

            files = []
            for row in rows:
                files.append({"filename": row[0], "s3_url": row[1], "created_at": str(row[2])})
            return files
        except Exception:
            return []
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    async def store_embedding(self, image_path: str, s3_url: str) -> bool:
        conn = None
        try:
            embedding_objs = DeepFace.represent(img_path=image_path, model_name=settings.face_model_name, enforce_detection=False)
            embedding = embedding_objs[0]["embedding"]
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()

            conn = self._get_connection()
            cursor = conn.cursor()
            
            # MySQL: INSERT ... ON DUPLICATE KEY UPDATE (instead of INSERT OR REPLACE)
            sql = """
                INSERT INTO faces (image_path, s3_url, embedding) 
                VALUES (%s, %s, %s) 
                ON DUPLICATE KEY UPDATE s3_url=%s, embedding=%s
            """
            val = (image_path, s3_url, embedding_bytes, s3_url, embedding_bytes)
            
            cursor.execute(sql, val)
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store embedding: {str(e)}")
            return False
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    async def get_all_faces(self) -> List[Tuple[str, str, bytes]]:
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT image_path, s3_url, embedding FROM faces")
            results = cursor.fetchall()
            return results
        except Exception:
            return []
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

    async def search_similar_faces(self, query_image_path: str, directory_name: str | None, threshold: float = 0.40) -> List[Tuple[str, str, float]]:
        conn = None
        try:
            # 1. Generate Query Embedding
            query_embedding_objs = DeepFace.represent(
                img_path=query_image_path, 
                model_name=settings.face_model_name,
                enforce_detection=False
            )
            query_embedding = np.array(query_embedding_objs[0]["embedding"], dtype=np.float32)

            # 2. Get Connection
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if directory_name and directory_name.strip():
                # Specific Folder Search
                search_pattern = f"%/{directory_name}/%"
                cursor.execute("SELECT image_path, s3_url, embedding FROM faces WHERE s3_url LIKE %s", (search_pattern,))
            else:
                # Global Search
                cursor.execute("SELECT image_path, s3_url, embedding FROM faces")
            
            stored_faces = cursor.fetchall()
            
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
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

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