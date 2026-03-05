import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY                     = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """Development configuration — SQLite, debug on."""
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///album_platform.db")
    SPOTIFY_CLIENT_ID       = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET   = os.getenv("SPOTIFY_CLIENT_SECRET")
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration — set DATABASE_URL in environment."""
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SPOTIFY_CLIENT_ID       = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET   = os.getenv("SPOTIFY_CLIENT_SECRET")
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration — in-memory SQLite."""
    TESTING                 = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SPOTIFY_CLIENT_ID       = "test-client-id"
    SPOTIFY_CLIENT_SECRET   = "test-client-secret"