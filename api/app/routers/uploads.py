"""CSV upload routes (charting or Hudl), scoped to one of the caller's teams.

Each upload is recorded so it can be listed and deleted (deleting removes its
plays), and the same file can't be imported twice into a team.
"""
from __future__ import annotations

import hashlib
import os
import tempfile

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, UploadFile, status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ratelimit import rate_limit
from app.db.models import Team, Upload
from app.deps import check_opponent, get_db, owned_team
from app.schemas.team import UploadOut
from app.schemas.tendency import UploadSummary
from app.services import tendencies as tendency_service

router = APIRouter(prefix="/teams/{team_id}", tags=["uploads"])

# Cap upload size so a single request can't exhaust memory.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post(
    "/uploads",
    response_model=UploadSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("upload", 30, 3600))],
)
def upload_csv(
    file: UploadFile = File(...),
    source: str = Form("auto"),
    team_label: str | None = Form(None, alias="team", max_length=40),
    opponent_id: int | None = Form(None),
    team: Team = Depends(owned_team),
    db: Session = Depends(get_db),
) -> UploadSummary:
    """Ingest a charting or Hudl CSV into this team's plays.

    ``source`` is auto|charting|hudl ("auto" sniffs the headers). ``team``
    labels offense_team on rows missing one (e.g. the opponent's name on a
    Hudl export). ``opponent_id`` optionally tags every play with one of this
    team's opponents. Re-uploading identical bytes returns 409.
    """
    if source not in tendency_service.VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source '{source}'. Use one of {list(tendency_service.VALID_SOURCES)}.",
        )
    check_opponent(db, team.id, opponent_id)
    # Read one byte past the limit to detect oversize without loading it all.
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large (max 5 MB).",
        )
    digest = hashlib.sha256(content).hexdigest()

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        summary = tendency_service.ingest_csv(
            db, team.id, tmp_path,
            filename=file.filename or "upload.csv", sha256=digest,
            source=source, default_team=team_label, opponent_id=opponent_id,
        )
    except tendency_service.DuplicateUpload as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - parse errors become a 400
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read this {source} file: {exc}",
        ) from exc
    finally:
        if tmp_path is not None and os.path.exists(tmp_path):
            os.remove(tmp_path)

    skipped = sum(summary["skipped"].values())
    message = (
        f"Imported {summary['inserted']} plays from the {summary['source']} export"
        + (f"; skipped {skipped} rows" if skipped else "") + "."
    )
    return UploadSummary(message=message, **summary)


@router.get("/uploads", response_model=list[UploadOut])
def list_uploads(team: Team = Depends(owned_team), db: Session = Depends(get_db)):
    return list(db.scalars(
        select(Upload).where(Upload.team_id == team.id).order_by(Upload.id.desc())
    ))


@router.delete("/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    upload_id: int,
    team: Team = Depends(owned_team),
    db: Session = Depends(get_db),
) -> None:
    """Delete an upload and every play imported from it."""
    upload = db.scalar(
        select(Upload).where(Upload.id == upload_id, Upload.team_id == team.id)
    )
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    db.delete(upload)
    db.commit()
