"""
TAJ FROID ERP - Configuration Management
Enterprise-grade settings with environment support
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from typing import Optional
from pathlib import Path
import os


class SecuritySettings(BaseSettings):
    """Security configuration"""
    secret_key: str = Field(
        default="changeme-in-production-use-openssl-rand-hex-32",
        description="Secret key for JWT signing"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30
    
    @validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v):
        if v == "changeme-in-production-use-openssl-rand-hex-32":
            import warnings
            warnings.warn("Using default secret key! Change in production.")
        return v


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    database_url: Optional[str] = None
    database_path: Optional[Path] = None
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo_sql: bool = False
    
    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.database_path or Path("/workspace/data/erp.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_path}"


class APISettings(BaseSettings):
    """API configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list = ["*"]
    rate_limit_per_minute: int = 100
    max_request_size_mb: int = 10


class LogSettings(BaseSettings):
    """Logging configuration"""
    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
    rotation: str = "10 MB"
    retention: str = "30 days"
    compression: str = "zip"
    serialize: bool = False
    backtrace: bool = False
    diagnose: bool = False


class BackupSettings(BaseSettings):
    """Backup configuration"""
    enabled: bool = True
    directory: Optional[Path] = None
    max_backups: int = 10
    compress: bool = True
    schedule_hours: int = 24
    
    @property
    def effective_directory(self) -> Path:
        return self.directory or Path(__file__).parent.parent / "backups"


class Settings(BaseSettings):
    """Main application settings"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    app_name: str = "TAJ FROID ERP"
    version: str = "2.0.0"
    environment: str = Field(default="development", description="development|staging|production")
    
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    api: APISettings = Field(default_factory=APISettings)
    logging: LogSettings = Field(default_factory=LogSettings)
    backup: BackupSettings = Field(default_factory=BackupSettings)
    
    @validator('environment')
    @classmethod
    def validate_environment(cls, v):
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be 'development', 'staging', or 'production'")
        return v
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency to get settings"""
    return settings
