import os
import shutil
import tempfile
import zipfile
import uuid
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.exceptions import ClientError
import mysql.connector
from mysql.connector import Error
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from main import generate_llm_analysis, create_word_doc, create_spider_chart
from src.data_loader import load_and_process_data
from auth import router as auth_router, get_current_user, get_db, init_db
from urllib.parse import urlparse

app = FastAPI(title="ByTE Report Generator API")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://byte-report-generator.netlify.app",
        "https://byte-report-generator.netlify.app/"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth_router)

@app.on_event("startup")
async def startup_event():
    print("🚀 App starting up... initializing database")
    init_db()

# Setup templates and static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
templates = Jinja2Templates(directory="templates")

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
AWS_REGION = os.getenv('AWS_REGION', 'eu-north-1')

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

# Ensure temporary directory exists
TEMP_BASE_DIR = os.path.join(tempfile.gettempdir(), "byte_reports")
os.makedirs(TEMP_BASE_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# IN-MEMORY JOB STORE  (job_id → job state)
# ─────────────────────────────────────────────
job_store: dict = {}

# Thread pool – max 3 concurrent generation jobs
executor = ThreadPoolExecutor(max_workers=3)


# ─────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────
def cleanup_files(*paths):
    """Cleanup temporary files and directories."""
    for path in paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            print(f"Error during cleanup of {path}: {e}")


def upload_to_s3(file_path, user_id, file_name):
    """Upload file to S3 and return the S3 key + URL."""
    try:
        s3_key = f"{user_id}/{file_name}"
        display_name = file_name.split("_", 2)[-1] if "_" in file_name else file_name

        s3_client.upload_file(
            file_path,
            AWS_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                'ContentType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'ContentDisposition': f'attachment; filename="{display_name}"'
            }
        )
        s3_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        return s3_key, s3_url
    except ClientError as e:
        print(f"Error uploading to S3: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file to S3: {str(e)}")


def delete_from_s3(s3_key):
    try:
        s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=s3_key)
    except ClientError as e:
        print(f"Error deleting from S3: {e}")


def get_s3_presigned_url(s3_key, expiration=3600):
    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': AWS_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expiration
        )
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None


# ─────────────────────────────────────────────
# BACKGROUND JOB FUNCTION  (runs in thread)
# ─────────────────────────────────────────────
def run_generation_job(
    job_id: str,
    students: list,
    final_class_name: str,
    class_avg: dict,
    consolidated_doc,          # already-created Document object
    docx_path: str,
    request_dir: str,
    current_user_id: int,
    docx_filename: str,
    unique_docx_name: str,
    db_conn_params: dict,
):
    """
    Runs entirely in a background thread so the HTTP request returns
    immediately.  Updates job_store[job_id] with live progress.
    """
    total = len(students)
    job_store[job_id].update({"total": total, "progress": 0, "current_name": ""})

    try:
        for idx, student in enumerate(students, 1):
            name = student.get('name', 'Unknown')
            job_store[job_id]["progress"] = idx
            job_store[job_id]["current_name"] = name
            print(f"[Job {job_id[:8]}] [{idx}/{total}] Processing: {name}")

            analysis, meta = generate_llm_analysis(student, name, final_class_name)
            if analysis:
                create_word_doc(
                    name, analysis, final_class_name, student, class_avg,
                    doc=consolidated_doc, save=False, is_first=(idx == 1)
                )
            else:
                print(f"  ⚠ Failed to generate analysis for: {name}")

        # ── Save consolidated DOCX ──
        consolidated_doc.save(docx_path)
        print(f"[Job {job_id[:8]}] ✅ Document saved: {docx_path}")

        # ── Upload to S3 ──
        s3_key, s3_url = upload_to_s3(docx_path, str(current_user_id), unique_docx_name)
        print(f"[Job {job_id[:8]}] ✅ Uploaded to S3: {s3_url}")

        # ── Persist to MySQL (fresh connection for thread safety) ──
        db = mysql.connector.connect(**db_conn_params)
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO reports (user_id, file_name, file_key, file_url) VALUES (%s, %s, %s, %s)",
            (current_user_id, docx_filename, s3_key, s3_url)
        )
        db.commit()
        report_id = cursor.lastrowid
        db.close()

        # ── Cleanup temp files ──
        cleanup_files(request_dir)

        # ── Mark job complete ──
        job_store[job_id]["status"] = "done"
        job_store[job_id]["result"] = {
            "message": "Reports generated successfully",
            "file_name": docx_filename,
            "download_url": s3_url,
            "report_id": report_id,
        }
        print(f"[Job {job_id[:8]}] 🎉 Done!")

    except Exception as e:
        import traceback
        traceback.print_exc()
        cleanup_files(request_dir)
        job_store[job_id]["status"] = "error"
        job_store[job_id]["error"] = str(e)
        print(f"[Job {job_id[:8]}] ❌ Error: {e}")


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "Backend is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/contact")
async def contact(request: Request):
    data = await request.json()
    name = data.get("name")
    email = data.get("email")
    message = data.get("message")
    print(f"Contact form submission:\n  Name: {name}\n  Email: {email}\n  Message: {message}")
    return {"status": "success", "message": "Your message has been received. Thank you!"}


@app.post("/generate-reports", status_code=202)
async def generate_reports(
    file: UploadFile = File(...),
    count: int = Form(None),
    current_user: dict = Depends(get_current_user),
    db: mysql.connector.MySQLConnection = Depends(get_db),
):
    """
    Accepts the uploaded Excel, kicks off a background generation job,
    and returns a job_id IMMEDIATELY (HTTP 202 Accepted).
    The frontend should poll /job-status/{job_id} for progress.
    """
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel or CSV file.")

    # ── Create unique workspace ──
    request_id = str(uuid.uuid4())
    request_dir = os.path.join(TEMP_BASE_DIR, request_id)
    input_dir = os.path.join(request_dir, "input")
    os.makedirs(input_dir, exist_ok=True)

    # ── Save uploaded file ──
    file_path = os.path.join(input_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # ── Load & validate student data (fast – no LLM calls yet) ──
    try:
        students, class_avg, internal_class = load_and_process_data(file_path)
    except Exception as e:
        cleanup_files(request_dir)
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    if not students:
        cleanup_files(request_dir)
        raise HTTPException(status_code=400, detail="No student data found in the uploaded file.")

    # ── Apply count limit ──
    if count is not None and count > 0:
        students = students[:count]

    final_class_name = internal_class if internal_class else os.path.splitext(file.filename)[0]

    # ── Build the Document skeleton (quick, no LLM) ──
    template_path = os.path.join(os.path.dirname(__file__), 'sample template to upload.docx')
    from docx import Document
    from docx.shared import Inches

    if os.path.exists(template_path):
        consolidated_doc = Document(template_path)
        body = consolidated_doc.element.body
        for child in list(body):
            if not child.tag.endswith('sectPr'):
                body.remove(child)
    else:
        consolidated_doc = Document()
        for section in consolidated_doc.sections:
            section.top_margin = Inches(0.5)
            section.bottom_margin = Inches(0.5)
            section.left_margin = Inches(0.6)
            section.right_margin = Inches(0.6)

    docx_filename = f"{final_class_name}_Reports.docx"
    unique_docx_name = f"{current_user['id']}_{request_id}_{docx_filename}"
    docx_path = os.path.join(request_dir, unique_docx_name)

    # ── DB connection params (safe to pass to thread) ──
    db_conn_params = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
    }

    # ── Initialise job entry BEFORE launching thread ──
    job_id = request_id
    job_store[job_id] = {
        "status": "running",
        "progress": 0,
        "total": len(students),
        "current_name": "",
        "result": None,
        "error": None,
    }

    # ── Launch background thread (non-blocking) ──
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor,
        run_generation_job,
        job_id,
        students,
        final_class_name,
        class_avg,
        consolidated_doc,
        docx_path,
        request_dir,
        current_user['id'],
        docx_filename,
        unique_docx_name,
        db_conn_params,
    )

    # ── Return immediately ──
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "total": len(students),
            "message": f"Generation started for {len(students)} students. Poll /job-status/{job_id} for progress.",
        }
    )


@app.get("/job-status/{job_id}")
async def job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    """
    Returns the current state of a generation job.
    Frontend should poll this every 3-5 seconds.

    Response shape:
    {
        "status":       "running" | "done" | "error",
        "progress":     <int>,      # students processed so far
        "total":        <int>,      # total students
        "current_name": <str>,      # name being processed right now
        "result":       <obj|null>, # populated when status == "done"
        "error":        <str|null>  # populated when status == "error"
    }
    """
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found. It may have expired.")
    return JSONResponse(content=job)


@app.get("/my-reports")
def my_reports(
    current_user: dict = Depends(get_current_user),
    db: mysql.connector.MySQLConnection = Depends(get_db)
):
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, file_name as filename, file_url, created_at FROM reports WHERE user_id=%s ORDER BY created_at DESC",
        (current_user['id'],)
    )
    records = cursor.fetchall()
    docs = []
    for r in records:
        docs.append({
            "id": r["id"],
            "filename": r["filename"],
            "created_at": r["created_at"],
            "download_url": r["file_url"],
        })
    return docs


@app.get("/download-report/{doc_id}")
def download_report(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
    db: mysql.connector.MySQLConnection = Depends(get_db)
):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM reports WHERE id=%s AND user_id=%s", (doc_id, current_user['id']))
    doc = cursor.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return JSONResponse(status_code=200, content={"file_name": doc["file_name"], "download_url": doc["file_url"]})


@app.delete("/delete-report/{doc_id}")
def delete_report(
    doc_id: int,
    current_user: dict = Depends(get_current_user),
    db: mysql.connector.MySQLConnection = Depends(get_db)
):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM reports WHERE id=%s AND user_id=%s", (doc_id, current_user['id']))
    doc = cursor.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    delete_from_s3(doc["file_key"])
    cursor.execute("DELETE FROM reports WHERE id=%s", (doc_id,))
    db.commit()
    return JSONResponse(status_code=200, content={"message": "Report deleted successfully"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)