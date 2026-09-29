from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import require_auditor
from app.core.database import get_db
from app.models.models import Report
from app.services.report_service import build_forensic_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    _authed: str = Depends(require_auditor),
):
    reports = db.query(Report).order_by(Report.id.desc()).all()
    return {
        "items": [
            {
                "report_id": r.report_id,
                "report_type": r.report_type,
                "document_id": r.document_id,
                "event_id": r.event_id,
                "investigation_id": r.investigation_id,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "status": r.status,
            }
            for r in reports
        ],
        "total": len(reports),
    }


@router.post("")
def create_report(
    investigation_id: str,
    db: Session = Depends(get_db),
    _authed: str = Depends(require_auditor),
):
    try:
        result = build_forensic_report(db, investigation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.get("/{report_id}/download")
def download_report(
    report_id: str,
    format: str = "pdf",
    db: Session = Depends(get_db),
    _authed: str = Depends(require_auditor),
):
    report = db.query(Report).filter(Report.report_id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    path = report.pdf_path if format == "pdf" else report.json_path
    if not path:
        raise HTTPException(status_code=404, detail=f"No {format} artifact for this report")
    return FileResponse(path, filename=f"{report_id}.{format}")
