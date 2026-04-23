import mysql.connector
from mysql.connector import Error
import uuid
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from pydantic import BaseModel

load_dotenv()

# MySQL Configuration from environment variables
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_ADDON_HOST'),
    'database': os.getenv('MYSQL_ADDON_DB'),
    'user': os.getenv('MYSQL_ADDON_USER'),
    'password': os.getenv('MYSQL_ADDON_PASSWORD'),
    'port': int(os.getenv('MYSQL_ADDON_PORT', 3306))
}

SECRET_KEY = os.getenv('SECRET_KEY', "bytesecretkey_very_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 300

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

router = APIRouter()

# Database connection function
def get_db():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

# Initialize DB Tables
def init_db():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        
        # Create byte table (users)
        cursor.execute('''CREATE TABLE IF NOT EXISTS byte(
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE,
            email VARCHAR(150) UNIQUE,
            password VARCHAR(255),
            is_verified BOOLEAN DEFAULT FALSE,
            verification_token VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Create reports table
        cursor.execute('''CREATE TABLE IF NOT EXISTS reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            file_name VARCHAR(255),
            file_key VARCHAR(500),
            file_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES byte(id) ON DELETE CASCADE
        )''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database tables initialized successfully")
    except Error as e:
        print(f"Error initializing database: {e}")

# Run initialization (Removed from top-level to prevent startup timeout)
# init_db()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

class UserCreate(BaseModel):
    email: str
    password: str
    username: Optional[str] = None

def send_verification_email(recipient_email: str, token: str):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not smtp_username:
        print("❌ ERROR: SMTP_USERNAME is not set in environment variables.")
    if not smtp_password:
        print("❌ ERROR: SMTP_PASSWORD is not set in environment variables.")
        
    if not smtp_username or not smtp_password:
        return False
        
    msg = EmailMessage()
    msg['Subject'] = 'Verify Your ByTE Account'
    msg['From'] = smtp_username
    msg['To'] = recipient_email
    
    verify_link = f"https://byte-report-generator.netlify.app/verify?token={token}"
    msg.set_content(f"""\
Hello,

Thank you for registering with ByTE Report Generator! 
Please verify your email address by clicking the link below:

{verify_link}

If you did not request this, please ignore this email.
""")

    try:
        if smtp_port == 465:
            # For SSL (Port 465)
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
        else:
            # For TLS (Port 587)
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send real email: {e}")
        return False

@router.post("/register")
def register(
    user: UserCreate, 
    background_tasks: BackgroundTasks,
    db: mysql.connector.MySQLConnection = Depends(get_db)
):
    cursor = db.cursor()
    
    # Check if email already exists
    cursor.execute("SELECT * FROM byte WHERE email=%s", (user.email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists (if provided)
    if user.username:
        cursor.execute("SELECT * FROM byte WHERE username=%s", (user.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already taken")
    
    hashed_password = get_password_hash(user.password)
    verification_token = str(uuid.uuid4())
    
    # Use email as username if no username provided
    username = user.username if user.username else user.email.split('@')[0]
    
    # Make username unique by appending numbers if it already exists
    base_username = username
    counter = 1
    while True:
        cursor.execute("SELECT * FROM byte WHERE username=%s", (username,))
        if not cursor.fetchone():
            break
        username = f"{base_username}{counter}"
        counter += 1
    
    try:
        # Set is_verified=True (1) directly to bypass email verification
        cursor.execute(
            "INSERT INTO byte (email, username, password, is_verified, verification_token) VALUES (%s, %s, %s, %s, %s)", 
            (user.email, username, hashed_password, True, verification_token)
        )
        db.commit()
    except Error as e:
        db.rollback()
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")
    
    print(f"DEBUG: Registering user {user.email}. Verification bypassed (Auto-verified).")

    return {"message": "Registration successful! You can now log in."}

def send_verification_email_with_logging(email, token):
    print(f"DEBUG: Attempting to send verification email to {email}...")
    email_sent = send_verification_email(email, token)
    if email_sent:
        print(f"✅ SUCCESS: Verification email sent to {email}")
    else:
        print("\n" + "="*50)
        print("📧 MOCK EMAIL SENT (Add SMTP credentials to .env to send real ones!) 📧")
        print(f"To: {email}")
        print("Subject: Verify Your ByTE Account")
        print("\nPlease click the link below to verify your account:")
        print(f"https://byte-report-generator.netlify.app/verify?token={token}")
        print("="*50 + "\n")

@router.get("/verify-email")
def verify_email(token: str, db: mysql.connector.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM byte WHERE verification_token=%s", (token,))
    user = cursor.fetchone()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
        
    if user['is_verified']:
        return {"message": "Email already verified. You can log in now."}
        
    cursor.execute("UPDATE byte SET is_verified=1 WHERE id=%s", (user['id'],))
    db.commit()
    
    return {"message": "Email successfully verified. You can now log in!"}

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: mysql.connector.MySQLConnection = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    # Allow login with either email or username
    cursor.execute("SELECT * FROM byte WHERE email=%s OR username=%s", (form_data.username, form_data.username))
    user = cursor.fetchone()
    
    if not user or not verify_password(form_data.password, user['password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user['is_verified']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox for the verification link.",
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['email']}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

def get_current_user(token: str = Depends(oauth2_scheme), db: mysql.connector.MySQLConnection = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM byte WHERE email=%s", (email,))
    user = cursor.fetchone()
    if user is None:
        raise credentials_exception
    return user