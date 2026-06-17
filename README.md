# AI Question Ingestion Platform

Production-ready FastAPI backend for UPSC/PSC competitive exam question ingestion, OCR, AI generation, and admin review.

## Architecture

```
app/
├── api/v1/routes/          # FastAPI route handlers
├── core/                   # Config, security, logging, exceptions
├── db/                     # MongoDB connection and indexes
├── models/                 # Pydantic v2 models
├── repositories/           # Data access layer (Repository pattern)
└── services/
    ├── ai/                 # PCS-II model abstraction
    ├── ingestion/          # English / Hindi / Book pipelines
    ├── ocr/                # PaddleOCR scanned PDF processing
    ├── parsers/            # Deterministic question parsers
    └── validators/         # Rule-based question validators
```

## API Endpoints

### Authentication
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | Admin login, returns JWT |
| GET | `/api/v1/auth/me` | Get current admin info |
| POST | `/api/v1/auth/logout` | Logout |

### Dashboard
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/dashboard/stats` | Aggregated counts |

### Ingestion
| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/ingest/english` | Upload English exam PDF |
| POST | `/api/v1/ingest/hindi` | Upload Hindi exam PDF |
| POST | `/api/v1/ingest/book` | Upload book PDF for AI generation |

### Jobs
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/jobs` | List jobs (paginated, filtered) |
| GET | `/api/v1/jobs/{job_id}` | Get job details with logs |

### PCS Questions (English/Hindi)
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/questions/pcs` | List questions (paginated, filtered) |
| GET | `/api/v1/questions/pcs/{id}` | Get single question |
| PATCH | `/api/v1/questions/pcs/{id}` | Edit question/options/answer |
| DELETE | `/api/v1/questions/pcs/{id}` | Delete question |
| POST | `/api/v1/questions/pcs/{id}/approve` | Approve single question |
| POST | `/api/v1/questions/pcs/bulk/approve` | Bulk approve questions |

### Book Questions
| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/questions/book` | List questions (paginated, filtered) |
| GET | `/api/v1/questions/book/{id}` | Get single question |
| PATCH | `/api/v1/questions/book/{id}` | Edit question/options |
| DELETE | `/api/v1/questions/book/{id}` | Delete question |
| POST | `/api/v1/questions/book/{id}/approve` | Approve single question |
| POST | `/api/v1/questions/book/bulk/approve` | Bulk approve |
| GET | `/api/v1/questions/book/export/approved` | Export approved as JSON |
