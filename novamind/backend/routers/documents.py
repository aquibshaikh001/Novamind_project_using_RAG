"""
routers/documents.py  -  upload, list and delete documents.

WHY THIS FILE EXISTS
    This is the door through which your files enter NovaMind. The browser
    sends a file here; we validate it, save it, and call the ingestion
    pipeline (services/ingestion.py).

NOTE: these are normal `def` (not `async def`) functions on purpose.
    Embedding a file is slow and blocking. FastAPI runs plain `def`
    endpoints in a worker thread, so the server stays responsive.
"""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from config import settings
from services import vector_store
from services.ingestion import ALLOWED_EXTENSIONS, ingest_file
from services.ollama_client import OllamaError

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
def upload(file: UploadFile = File(...)):
    # SECURITY: Path(...).name removes any folder part such as "../../x.pdf"
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="File has no name.")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(sorted(ALLOWED_EXTENSIONS))} files are supported.",
        )

    content = file.file.read()
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.MAX_UPLOAD_MB} MB.")

    saved_path = settings.DATA_DIR / filename
    saved_path.write_bytes(content)

    try:
        return ingest_file(saved_path)
    except OllamaError as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Could not process file: {exc}")


@router.get("")
def list_documents():
    """All uploaded files with their chunk counts."""
    return {"documents": vector_store.list_sources()}


@router.delete("/{name}")
def delete_document(name: str):
    """Remove a file from the database and from disk."""
    safe_name = Path(name).name
    vector_store.delete_source(safe_name)
    (settings.DATA_DIR / safe_name).unlink(missing_ok=True)
    return {"deleted": safe_name}
