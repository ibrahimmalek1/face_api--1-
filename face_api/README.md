# Face Detection and Similarity Search API

A FastAPI-based microservice for face detection, similarity search, and image processing using DeepFace and AWS S3.

## Features

- **Bulk Image Upload**: Upload multiple images at once for preprocessing
- **Single Image Upload**: Upload individual images for processing
- **Face Similarity Search**: Find similar faces by uploading a query image
- **AWS S3 Integration**: Automatic file storage and retrieval
- **Face Embedding Storage**: SQLite database for face embeddings
- **Configurable Thresholds**: Adjustable similarity thresholds

## API Endpoints

### Upload Endpoints
- `POST /upload/bulk` - Upload multiple images in bulk
- `POST /upload/single` - Upload a single image

### Similarity Search Endpoints
- `POST /similarity/search` - Find similar faces
- `GET /similarity/stats` - Get database statistics

### Health Check
- `GET /` - Basic health check
- `GET /health` - Detailed health check

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   ```bash
   cp env.example .env
   # Edit .env with your AWS credentials
   ```

3. **Run the Application**
   ```bash
   python -m app.main
   # or
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_ID` | AWS Access Key ID | Required |
| `AWS_SECRET` | AWS Secret Access Key | Required |
| `AWS_S3_BUCKET` | S3 Bucket Name | Required |
| `REGION` | AWS Region | us-east-1 |
| `SIMILARITY_THRESHOLD` | Face similarity threshold | 0.3 |
| `MODEL_NAME` | DeepFace model name | Facenet |
| `MAX_FILE_SIZE` | Maximum file size in bytes | 10485760 (10MB) |

## Usage Examples

### Bulk Upload
```bash
curl -X POST "http://localhost:8000/upload/bulk" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@image1.jpg" \
  -F "files=@image2.jpg"
```

### Single Upload
```bash
curl -X POST "http://localhost:8000/upload/single" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@image.jpg"
```

### Similarity Search
```bash
curl -X POST "http://localhost:8000/similarity/search?threshold=0.3&max_results=5" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@query_image.jpg"
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

- **FastAPI**: Web framework
- **DeepFace**: Face recognition and embedding extraction
- **AWS S3**: File storage
- **SQLite**: Local embedding storage
- **Pydantic**: Data validation and serialization
- **Boto3**: AWS SDK for Python

## Security Considerations

- Configure CORS properly for production
- Use environment variables for sensitive data
- Implement proper authentication/authorization
- Validate file types and sizes
- Use HTTPS in production