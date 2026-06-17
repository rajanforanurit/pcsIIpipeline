# PCS-II Question Ingestion Platform v2.0

Production backend for UPSC/UPPCS exam question ingestion via Google Drive ETL pipeline.

## Architecture

```
Google Drive (Unprocessed Folder)
    ↓  Changes API watcher
Download PDF  →  TEMP_DIR
    ↓
OCR (PaddleOCR)
    ↓
DeepSeek V3.2 (Azure AI Foundry)
    ↓  Detects: language, document_type, year, exam, paper
Generate JSON (canonical schema)
    ↓
Validate JSON
    ↓
Upload to Pending JSON Folder (Drive)
    ↓
Admin Review Panel (/api/v1/pending-review)
    ↓ approve / reject
Approve:
  → Insert into MongoDB (englishquestions / hindiquestions)
  → Move JSON: pending → processed_json
  → Move PDF: unprocessed → processed_pdf
  → Upload processing log
Reject:
  → Move JSON: pending → failed
  → No MongoDB insert
```

## New Endpoints (v2.0)

### Pending Review Panel
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/pending-review | List pending reviews |
| GET | /api/v1/pending-review/{id} | Get full review with questions |
| PUT | /api/v1/pending-review/{id} | Edit questions |
| POST | /api/v1/pending-review/{id}/approve | Approve → MongoDB |
| POST | /api/v1/pending-review/{id}/reject | Reject |
| GET | /api/v1/pending-review/{id}/preview | JSON preview |

### Drive Pipeline Management
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/drive-pipeline/jobs | List Drive ingestion jobs |
| GET | /api/v1/drive-pipeline/jobs/{id} | Get single job |
| POST | /api/v1/drive-pipeline/trigger | Manually trigger pipeline |
| GET | /api/v1/drive-pipeline/status | Pipeline config status |

### Health / Readiness
| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness probe |
| GET | /readiness | Readiness probe (checks MongoDB) |

## Environment Variables

See `.env.example` for all required variables.

Key new variables:
- `GOOGLE_SERVICE_ACCOUNT_JSON` – full service account JSON (loaded from env)
- `GOOGLE_DRIVE_UNPROCESSED_FOLDER_ID` – source folder watched for new PDFs
- `GOOGLE_DRIVE_PENDING_JSON_FOLDER_ID` – where AI JSON goes before admin review
- `GOOGLE_DRIVE_PROCESSED_JSON_FOLDER_ID` – approved JSONs
- `GOOGLE_DRIVE_PROCESSED_PDF_FOLDER_ID` – approved PDFs
- `GOOGLE_DRIVE_PROCESSED_LOG_FOLDER_ID` – processing logs
- `GOOGLE_DRIVE_FAILED_FOLDER_ID` – failed PDFs / rejected JSONs
- `CHECK_INTERVAL_SECONDS` – Drive polling interval (default 60)
- `MAX_CONCURRENT_WORKERS` – parallel pipeline workers (default 2)
- `PIPELINE_MODE` – `auto` (background watcher) or `manual` (API-triggered only)
- `ENABLE_DUPLICATE_CHECK` – skip already-processed Drive file IDs

## JSON Schema (canonical)

```json
{
  "id": 1,
  "year": 2023,
  "exam": "UPSC Prelims",
  "paper": "GS Paper 1",
  "language": "English",
  "question": "Which of the following...?",
  "options": {
    "A": "Option A",
    "B": "Option B",
    "C": "Option C",
    "D": "Option D"
  },
  "correct_answer": "B"
}
```

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in values
uvicorn app.main:app --reload
```

## Docker

```bash
docker build -t pcsii-pipeline .
docker run -p 8000:8000 --env-file .env pcsii-pipeline
```
