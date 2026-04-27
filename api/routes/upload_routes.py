"""
STEP 5 — Admin-Only Upload Routes
------------------------------------
POST /upload/json          → admin uploads a course JSON → triggers generation
GET  /upload/status/{id}   → poll job status
GET  /upload/list          → admin lists all uploads
GET  /upload/download/{id} → download the generated PDF

STEP-BY-STEP UPLOAD FLOW:
  1.  Client sends multipart/form-data with the JSON file
      + Authorization: Bearer <admin-JWT>
  2.  `require_admin` dependency:
        a. Extracts Bearer token from header
        b. Decodes + verifies JWT signature
        c. Loads user from DB
        d. Checks role == 'admin' → 403 if not
  3.  Validate file extension (.json only)
  4.  Read file bytes, parse JSON → validate CourseInput schema
  5.  Save file to uploads/ directory
  6.  Insert upload record in DB (status=pending)
  7.  Return job_id immediately (non-blocking)
  8.  BackgroundTasks runs the Gemini generation asynchronously:
        a. status → processing
        b. SyllabusAgent.generate(course)
        c. assemble_markdown + save full MD
        d. generate_pdf
        e. status → complete  (or failed + error_message)
"""

import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

# Ensure parent dir is on path so agent/pdf_generator are importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent import SyllabusAgent, assemble_markdown, save_full_markdown, _safe_filename
from api.auth import require_admin
from api.database import (
    create_upload_record,
    list_uploads,
    update_upload_status,
    get_user_by_id,
)
from api.schemas import JobStatusResponse, UploadListItem, UploadResponse
from models import CourseInput
from pdf_generator import generate_pdf
from api.database import get_db

router = APIRouter(prefix="/upload", tags=["Admin Upload"])

UPLOAD_DIR  = Path(__file__).parent.parent.parent / "uploads"
OUTPUT_DIR  = Path(__file__).parent.parent.parent / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".json"}
MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB guard


# ─────────────────────────────────────────────────────────────────
# Background worker: runs AFTER the HTTP response is sent
# ─────────────────────────────────────────────────────────────────
def _run_generation(upload_id: str, json_path: Path, course: CourseInput) -> None:
    """
    STEP 5B: Background generation task.
    Runs outside the request/response cycle — client gets job_id
    immediately and can poll /upload/status/{job_id}.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        update_upload_status(upload_id, "failed", error_message="GEMINI_API_KEY not set on server")
        return

    try:
        # Mark as processing
        update_upload_status(upload_id, "processing")

        # Generate all 15 sections
        agent    = SyllabusAgent(api_key=api_key)
        sections = agent.generate(course, output_dir=str(OUTPUT_DIR))

        # Assemble and save markdown
        md_path  = save_full_markdown(sections, course, str(OUTPUT_DIR))

        # Generate PDF
        slug     = _safe_filename(course.course_title)
        pdf_path = OUTPUT_DIR / f"{slug}_FULL_SYLLABUS.pdf"
        meta = {
            "Program"       : f"{course.program} — {course.discipline}",
            "Department"    : course.department,
            "Course Code"   : course.course_code,
            "Credits"       : str(course.total_credits),
            "L-T-P"         : course.ltp,
        }
        generate_pdf(md_path.read_text(), pdf_path, course_title=course.course_title, meta=meta)

        update_upload_status(
            upload_id,
            status="complete",
            output_md=str(md_path),
            output_pdf=str(pdf_path),
        )

    except Exception as exc:
        update_upload_status(upload_id, "failed", error_message=str(exc))


# ─────────────────────────────────────────────────────────────────
# ROUTE 1: Upload JSON file  (ADMIN ONLY)
# ─────────────────────────────────────────────────────────────────
@router.post(
    "/json",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[ADMIN] Upload course JSON and trigger syllabus generation",
)
async def upload_course_json(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Course configuration JSON file"),
    admin=Depends(require_admin),          # ← STEP 2F: only admins reach here
):
    """
    STEP 5A: Upload validation + record creation.

    Security checks (in order):
      1. require_admin dependency (JWT decode → role check)
      2. File extension must be .json
      3. File size must be under 1 MB
      4. Content must be valid JSON
      5. JSON must match CourseInput schema
    """
    # 1. Extension check
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only .json files are accepted. Got: {suffix}",
        )

    # 2. Read bytes with size guard
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 1 MB limit",
        )

    # 3. Parse JSON
    try:
        data = json.loads(contents.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON: {e}",
        )

    # 4. Validate against CourseInput schema
    try:
        course = CourseInput(**data)
    except TypeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"JSON does not match CourseInput schema: {e}",
        )

    if not course.course_title.strip():
        raise HTTPException(status_code=422, detail="course_title is required")

    # 5. Save file to disk
    save_path = UPLOAD_DIR / f"{admin['id']}_{file.filename}"
    save_path.write_bytes(contents)

    # 6. Insert DB record
    job_id = create_upload_record(
        filename=file.filename,
        uploaded_by=admin["id"],
    )

    # 7. Queue background generation (returns immediately)
    background_tasks.add_task(_run_generation, job_id, save_path, course)

    return UploadResponse(
        job_id=job_id,
        filename=file.filename,
        status="pending",
        message=f"Upload accepted. Syllabus generation queued. Poll /upload/status/{job_id}",
    )


# ─────────────────────────────────────────────────────────────────
# ROUTE 2: Poll job status  (ADMIN ONLY)
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    summary="[ADMIN] Poll syllabus generation status",
)
def job_status(job_id: str, admin=Depends(require_admin)):
    """
    STEP 5C: Poll to check if background generation is done.
    Status values: pending → processing → complete | failed
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM uploads WHERE id = ?", (job_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=row["id"],
        status=row["status"],
        output_md=row["output_md"],
        output_pdf=row["output_pdf"],
        error_message=row["error_message"],
    )


# ─────────────────────────────────────────────────────────────────
# ROUTE 3: List all uploads  (ADMIN ONLY)
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/list",
    response_model=list[UploadListItem],
    summary="[ADMIN] List all uploaded syllabi",
)
def list_all_uploads(admin=Depends(require_admin)):
    """STEP 5D: View history of all uploads by all admins."""
    rows = list_uploads(limit=100)
    return [
        UploadListItem(
            id=r["id"],
            filename=r["filename"],
            username=r["username"],
            status=r["status"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────
# ROUTE 4: Download generated PDF  (ADMIN ONLY)
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/download/{job_id}",
    summary="[ADMIN] Download the generated PDF for a completed job",
)
def download_pdf(job_id: str, admin=Depends(require_admin)):
    """STEP 5E: Serve the PDF file once generation is complete."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM uploads WHERE id = ?", (job_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    if row["status"] != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not complete yet. Current status: {row['status']}",
        )

    pdf_path = Path(row["output_pdf"])
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on server")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
    )
