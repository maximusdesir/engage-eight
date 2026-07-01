"""Public charting-upload endpoint.

Accepts a manually charted opponent CSV, runs it through the ml charting
loader, and persists the resulting canonical plays.
"""
from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.deps import get_current_user, get_db
from app.schemas.tendency import UploadSummary
from app.services import tendencies as tendency_service

router = APIRouter(tags=["uploads"])

# Cap upload size so a single request can't exhaust memory.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/uploads", response_model=UploadSummary)
def upload_charting(
    file: UploadFile = File(...),
    source: str = Form("auto"),
    team: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadSummary:
    """Ingest a charting or Hudl CSV into the plays table.

    Requires authentication. ``source`` is auto|charting|hudl ("auto" sniffs the
    headers). ``team`` optionally labels offense_team on rows missing one (handy
    when tagging an opponent's Hudl export). The file is read with a size cap,
    written to a temp path, parsed by the matching ml loader, and removed
    afterward. Parse failures (including the loader's ``SystemExit``) become a
    400 with the underlying message.
    """
    if source not in tendency_service.VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source '{source}'. Use one of {list(tendency_service.VALID_SOURCES)}.",
        )
    # Read one byte past the limit to detect oversize without loading it all.
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Charting file too large (max 5 MB).",
        )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        summary = tendency_service.ingest_csv(
            db, tmp_path, source=source, default_team=team
        )
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not ingest {source} file: {exc}",
        ) from exc
    finally:
        if tmp_path is not None and os.path.exists(tmp_path):
            os.remove(tmp_path)

    teams = summary["teams"]
    inserted = summary["inserted"]
    resolved = summary["source"]
    message = f"Inserted {inserted} plays from {resolved} export for {len(teams)} team(s)."
    return UploadSummary(
        inserted=inserted,
        teams=teams,
        source=resolved,
        message=message,
        unmapped_formations=summary.get("unmapped_formations", []),
        unmapped_motions=summary.get("unmapped_motions", []),
    )
