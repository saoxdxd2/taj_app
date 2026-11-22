"""Core configuration and settings for the ERP system."""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Database
    database_url: str = "sqlite:///./erp_system.db"
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    
    # WebSocket Settings
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    
    # Backup & Maintenance
    backup_retention_days: int = 30
    log_rotation_size_mb: int = 10
    disk_space_threshold_percent: int = 90

    # WhatsApp Cloud API (Meta). Credentials come from the environment or
    # .env only — the access token is a secret and is never stored in the
    # database or written to logs.
    whatsapp_access_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_api_version: str = "v20.0"
    whatsapp_default_country_code: str = "212"
    
    # Environment
    environment: str = "development"  # development, testing, production
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
