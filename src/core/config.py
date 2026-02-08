import os

class Config:
    APP_NAME = os.getenv("APP_NAME", "RepoPulse")
    DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "t")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", 8000))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")