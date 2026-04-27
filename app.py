import os
import shutil
import tempfile
import zipfile
import uuid
import sys
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
    """Upload file to S3 and return the S3 URL"""
    try:
        # Create S3 key with user_id folder structure
        s3_key = f"{user_id}/{file_name}"
        
        # Extract the original filename (without the user_id and request_id prefix) for the download header
        display_name = file_name.split("_", 2)[-1] if "_" in file_name else file_name
        
        # Upload file to S3
        s3_client.upload_file(
            file_path,
            AWS_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                'ContentType': 'application/zip',
                'ContentDisposition': f'attachment; filename="{display_name}"'
            }
        )
        
        # Generate S3 URL
        s3_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        
        return s3_key, s3_url
    except ClientError as e:
        print(f"Error uploading to S3: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file to S3: {str(e)}")

def delete_from_s3(s3_key):
    """Delete file from S3"""
    try:
        s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=s3_key)
    except ClientError as e:
        print(f"Error deleting from S3: {e}")

def get_s3_presigned_url(s3_key, expiration=3600):
    """Generate a presigned URL for temporary access"""
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': AWS_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return None

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
    
    # In a real app, you would send an email or save to a database here.
    # For now, we'll just log it to the console.
    print(f"Contact form submission received:")
    print(f"  Name: {name}")
    print(f"  Email: {email}")
    print(f"  Message: {message}")
    
    return {"status": "success", "message": "Your message has been received. Thank you!"}

@app.post("/generate-reports")
async def generate_reports(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    count: int = Form(None),
    current_user: dict = Depends(get_current_user),
    db: mysql.connector.MySQLConnection = Depends(get_db)
):
    if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel or CSV file.")

    # Create a unique request ID and temp folders
    request_id = str(uuid.uuid4())
    request_dir = os.path.join(TEMP_BASE_DIR, request_id)
    input_dir = os.path.join(request_dir, "input")
    output_dir = os.path.join(request_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Save uploaded file
    file_path = os.path.join(input_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Load and process data
        students, class_avg, internal_class = load_and_process_data(file_path)
        if not students:
            raise Exception("No student data found in the uploaded file.")

        # Apply report count limit if specified
        if count is not None and count > 0:
            students = students[:count]

        final_class_name = internal_class if internal_class else os.path.splitext(file.filename)[0]

        # Initialize a single consolidated document using the updated template
        template_path = os.path.join(os.path.dirname(__file__), 'sample template to upload.docx')
        from docx import Document
        from docx.shared import Inches
        
        if os.path.exists(template_path):
            consolidated_doc = Document(template_path)
            # Clear existing body content but keep section properties (headers/margins)
            body = consolidated_doc.element.body
            for child in list(body):
                if not child.tag.endswith('sectPr'):
                    body.remove(child)
        else:
            # Fallback if template is missing
            consolidated_doc = Document()
            # Set narrow margins once for the consolidated doc
            sections = consolidated_doc.sections
            for section in sections:
                section.top_margin = Inches(0.5)
                section.bottom_margin = Inches(0.5)
                section.left_margin = Inches(0.6)
                section.right_margin = Inches(0.6)

        # Generate reports into the single document
        for idx, student in enumerate(students, 1):
            name = student.get('name', 'Unknown')
            analysis, meta = generate_llm_analysis(student, name, final_class_name)
            if analysis:
                # Pass the consolidated_doc to be appended to
                create_word_doc(name, analysis, final_class_name, student, class_avg, 
                                doc=consolidated_doc, save=False, is_first=(idx==1))
            else:
                print(f"Failed to generate analysis for: {name}")

        # Save single consolidated document
        docx_filename = f"{final_class_name}_Reports.docx"
        unique_docx_name = f"{current_user['id']}_{request_id}_{docx_filename}"
        docx_path = os.path.join(request_dir, unique_docx_name)
        consolidated_doc.save(docx_path)

        # Upload DOCX to S3
        s3_key, s3_url = upload_to_s3(docx_path, str(current_user['id']), unique_docx_name)

        # Save report info to MySQL
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO reports (user_id, file_name, file_key, file_url) VALUES (%s, %s, %s, %s)", 
            (current_user['id'], docx_filename, s3_key, s3_url)
        )
        db.commit()

        # Schedule cleanup of temporary files
        background_tasks.add_task(cleanup_files, request_dir)

        # Return the S3 URL for immediate download
        return JSONResponse(
            status_code=200,
            content={
                "message": "Reports generated successfully",
                "file_name": docx_filename,
                "download_url": s3_url,
                "report_id": cursor.lastrowid
            }
        )

    except Exception as e:
        cleanup_files(request_dir)
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/my-reports")
def my_reports(current_user: dict = Depends(get_current_user), db: mysql.connector.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, file_name as filename, file_url, created_at FROM reports WHERE user_id=%s ORDER BY created_at DESC", 
        (current_user['id'],)
    )
    records = cursor.fetchall()
    
    # Add presigned URLs for each report (optional - if you want time-limited access)
    docs = []
    for r in records:
        doc = {
            "id": r["id"],
            "filename": r["filename"],
            "created_at": r["created_at"],
            "download_url": r["file_url"]  # Use permanent S3 URL
        }
        docs.append(doc)
    
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
    
    # Return the S3 URL directly
    # You can also generate a presigned URL for additional security
    return JSONResponse(
        status_code=200,
        content={
            "file_name": doc["file_name"],
            "download_url": doc["file_url"]
        }
    )

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
    
    # Delete from S3
    delete_from_s3(doc["file_key"])
    
    # Delete from database
    cursor.execute("DELETE FROM reports WHERE id=%s", (doc_id,))
    db.commit()
    
    return JSONResponse(
        status_code=200,
        content={"message": "Report deleted successfully"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)