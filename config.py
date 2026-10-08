import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fitcore-secret-default-key-change-in-prod')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://24205036_db_user:Haamidh%40123@cluster0.qdjj9uz.mongodb.net/?appName=Cluster0')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'gym_management')
    DEFAULT_GYM_CAPACITY = int(os.getenv('GYM_CAPACITY', 100))
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Kolkata')
    
    # Uploads configuration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MEMBERS_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'members')
    TRAINERS_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'trainers')
    
    # Max file upload size: 5MB
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
