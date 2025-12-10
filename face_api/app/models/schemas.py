from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ImageUploadResponse(BaseModel):
    filename: str
    s3_url: str
    processed: bool
    embedding_stored: bool
    error: Optional[str] = None


class BulkUploadResponse(BaseModel):
    total_files: int
    successful_uploads: int
    failed_uploads: int
    results: List[ImageUploadResponse]
    processing_time: float


# --- NEW MODELS FOR SEARCH ROUTER ---
class FaceMatch(BaseModel):
    image_path: str
    s3_url: str
    similarity_score: float

class SearchResponse(BaseModel):
    total_matches: int
    matches: List[FaceMatch]
    processing_time: float
    error: Optional[str] = None
# -------------------------------------


# (Optional) You can keep these if you have older code using them, 
# but the new router uses the ones above.
class SimilarFaceResult(BaseModel):
    image_path: str
    s3_url: str
    similarity_score: float
    distance: float

class SimilaritySearchResponse(BaseModel):
    query_image: str
    similar_faces: List[SimilarFaceResult]
    total_matches: int
    search_time: float


class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str