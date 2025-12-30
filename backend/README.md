# Podcast Generation Backend

FastAPI backend for generating podcasts from text content.

## Setup

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export OPENAI_API_KEY=your_openai_api_key
export GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
export GOOGLE_CLOUD_PROJECT=your_project_id
```

Or create a `.env` file in the backend directory:
```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
GOOGLE_CLOUD_PROJECT=your_project_id
```

## Running

Start the server:
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## API Endpoints

- `POST /api/upload` - Upload text content and start podcast generation
- `GET /api/status/{task_id}` - Get task status
- `GET /api/download/{task_id}/audio` - Download audio file
- `GET /api/download/{task_id}/transcript` - Download transcript file
- `GET /api/stream/{task_id}` - SSE stream for progress updates

