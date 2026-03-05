import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Development configuration"""
    # USING NOW - SQLite for local dev/collaboration
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///album_platform.db")
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration"""
    # IF WOULD LIKE BUT NOT IN COLLAB (set True and above set False, need futher configuation)
    # MySQL (or any DB) from environment variable
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    DEBUG = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
