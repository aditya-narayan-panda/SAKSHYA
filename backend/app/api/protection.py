import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.auth import require_officer
from app.core.database import get_db
from app.services.protection_service import protect_document, ProtectionError

router = APIRouter(prefix="/api/protect", tags=["protection"])


@router.post("")
async def protect(
    document: UploadFile = File(...),
    recipient_ids: str = Form(..., description='JSON array, e.g. ["REC-001","REC-002"]'),
    db: Session = Depends(get_db),
    _authed: str = Depends(require_officer),
):
    try:
        ids = json.loads(recipient_ids)
        if not isinstance(ids, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="recipient_ids must be a JSON array of strings")

    file_bytes = await document.read()
    try:
        result = protect_document(db, document.filename, file_bytes, ids)
    except ProtectionError as e:
        # e.g. {"code": "UNSUPPORTED_WATERMARK_TYPE", "message": "..."} for .txt/.xlsx
        raise HTTPException(status_code=400, detail={"code": e.code, "message": str(e)})
    return result
