"""Configuration management."""
import os
from pathlib import Path
from typing import Optional

class Config:
    """Application configuration."""
    
    # Base paths
    BASE_DIR = Path(__file__).parent.parent.parent  # project root
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"
    UPLOAD_DIR = DATA_DIR / "uploads"
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'c2.db'}")
    
    # Security
    SECRET_KEY = None  # Loaded from file
    ENCRYPTION_KEY = None  # From config
    AGENT_TOKEN = None  # From config
    
    # Flask
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "8443"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    # Session
    SESSION_LIFETIME_HOURS = 12
    PERMANENT_SESSION_LIFETIME_DAYS = 30
    
    # Rate limiting
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_DEFAULT = "60 per minute"
    RATE_LIMIT_LOGIN = "5 per 5 minutes"
    RATE_LIMIT_API = "100 per minute"
    
    # Agent health check
    AGENT_TIMEOUT_SECONDS = 30
    HEALTH_CHECK_INTERVAL = 10
    
    # Scheduled tasks
    SCHEDULED_TASK_INTERVAL = 30
    
    # Webhooks
    WEBHOOK_TIMEOUT = 5
    
    # Tunnel
    TUNNEL_ENABLED = True
    TUNNEL_TOOLS = ["cloudflared", "ngrok"]
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Kaggle
    KAGGLE_POLL_INTERVAL = 30
    KAGGLE_DEPLOY_TIMEOUT = 300
    
    # File upload
    MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'tar', 'gz'}
    
    @classmethod
    def init(cls):
        """Initialize configuration."""
        # Create directories
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load secret key
        secret_file = cls.DATA_DIR / ".secret_key"
        if secret_file.exists():
            cls.SECRET_KEY = secret_file.read_text().strip()
        else:
            import secrets
            cls.SECRET_KEY = secrets.token_hex(32)
            secret_file.write_text(cls.SECRET_KEY)
            os.chmod(secret_file, 0o600)
    
    @classmethod
    def get_database_url(cls) -> str:
        """Get database URL."""
        return cls.DATABASE_URL
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production."""
        return not cls.FLASK_DEBUG

# Initialize on import
Config.init()
