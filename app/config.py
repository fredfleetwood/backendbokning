"""
Configuration Management - Environment-based settings for production deployment
"""
import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Environment-based configuration for VPS automation server
    """
    
    # Application Settings
    APP_NAME: str = "VPS Automation Server"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENVIRONMENT: str = Field(default="production", description="Environment: development/staging/production")
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", description="API host binding")
    API_PORT: int = Field(default=8000, description="API port")
    API_SECRET_TOKEN: str = Field(..., description="Secret token for API authentication")
    
    # Database Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    DATABASE_URL: Optional[str] = Field(default=None, description="PostgreSQL connection URL for local state")
    
    # External Services
    SUPABASE_WEBHOOK_URL: str = Field(..., description="Supabase webhook endpoint URL")
    SUPABASE_SECRET_KEY: str = Field(..., description="Supabase webhook secret key")
    WEBHOOK_SECRET: str = Field(..., description="Secret for webhook verification")
    
    # Browser Configuration
    BROWSER_HEADLESS: bool = Field(default=False, description="Run browsers in headless mode")
    BROWSER_TIMEOUT: int = Field(default=30000, description="Browser operation timeout in ms")
    BROWSER_VIEWPORT_WIDTH: int = Field(default=1920, description="Browser viewport width")
    BROWSER_VIEWPORT_HEIGHT: int = Field(default=1080, description="Browser viewport height")
    
    # VNC Monitoring Configuration
    VNC_MONITORING_ENABLED: bool = Field(default=False, description="Enable VNC monitoring for live job debugging")
    VNC_DISPLAY: str = Field(default=":99", description="VNC display to use for monitoring")
    
    # Queue System Configuration
    MAX_CONCURRENT_JOBS: int = Field(default=10, description="Maximum concurrent booking jobs")
    MAX_QUEUE_SIZE: int = Field(default=50, description="Maximum queue size")
    JOB_TIMEOUT: int = Field(default=1800, description="Job timeout in seconds (30 minutes)")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1", description="Celery broker URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2", description="Celery result backend")
    
    # Browser Resource Management
    MAX_BROWSER_INSTANCES: int = Field(default=10, description="Maximum browser instances")
    BROWSER_MEMORY_LIMIT: str = Field(default="512MB", description="Memory limit per browser instance")
    CLEANUP_INTERVAL: int = Field(default=300, description="Cleanup interval in seconds")
    
    # QR Code Configuration
    QR_CAPTURE_INTERVAL: int = Field(default=1, description="QR code capture interval in seconds - 1s for ultra-responsive BankID QR updates")
    QR_IMAGE_QUALITY: int = Field(default=95, description="QR code image quality (1-100)")
    QR_MAX_SIZE: int = Field(default=500, description="Maximum QR code image size in pixels")
    
    # Security Settings
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="Rate limit requests per minute")
    RATE_LIMIT_WINDOW: int = Field(default=60, description="Rate limit window in seconds")
    SESSION_SECRET_KEY: str = Field(..., description="Secret key for session management")
    
    # Monitoring & Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Log format: json or text")
    HEALTH_CHECK_INTERVAL: int = Field(default=60, description="Health check interval in seconds")
    METRICS_ENABLED: bool = Field(default=True, description="Enable Prometheus metrics")
    METRICS_PORT: int = Field(default=9090, description="Metrics server port")
    
    # Trafikverket Configuration
    TRAFIKVERKET_BASE_URL: str = Field(
        default="https://fp.trafikverket.se/boka/#/",
        description="Base URL for Trafikverket booking system"
    )
    TRAFIKVERKET_LOCALE: str = Field(default="sv-SE", description="Locale for Trafikverket site")
    TRAFIKVERKET_TIMEZONE: str = Field(default="Europe/Stockholm", description="Timezone for booking times")
    
    # BankID Configuration
    BANKID_TIMEOUT: int = Field(default=300, description="BankID authentication timeout in seconds")
    BANKID_QR_REFRESH_INTERVAL: int = Field(default=1, description="BankID QR refresh check interval - 1s for ultra-responsive updates")
    
    # Geolocation (Stockholm coordinates)
    DEFAULT_LATITUDE: float = Field(default=59.3293, description="Default latitude for geolocation")
    DEFAULT_LONGITUDE: float = Field(default=18.0686, description="Default longitude for geolocation")
    
    # File Storage
    UPLOAD_DIR: str = Field(default="/tmp/uploads", description="Directory for file uploads")
    MAX_UPLOAD_SIZE: int = Field(default=10485760, description="Maximum upload size in bytes (10MB)")
    
    # Performance Settings
    WORKER_CONCURRENCY: int = Field(default=5, description="Celery worker concurrency")
    WORKER_PREFETCH_MULTIPLIER: int = Field(default=1, description="Celery worker prefetch multiplier")
    CONNECTION_POOL_SIZE: int = Field(default=20, description="Database connection pool size")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


class BookingConfig:
    """
    Configuration for booking automation parameters
    """
    
    # License Types
    SUPPORTED_LICENSE_TYPES = [
        "B", "A1", "A2", "A", "C1", "C", "D1", "D", "BE", "C1E", "CE", "D1E", "DE"
    ]
    
    # Exam Types
    EXAM_TYPES = [
        "Körprov",
        "Kunskapsprov",
        "Riskutbildning",
        "Introduktionsutbildning"
    ]
    
    # Vehicle/Language Options
    VEHICLE_OPTIONS = [
        "Egen bil",
        "Trafikverkets bil",
        "Automatisk växellåda",
        "Manuell växellåda"
    ]
    
    # Default Locations (can be overridden by user)
    DEFAULT_LOCATIONS = [
        "Stockholm",
        "Göteborg", 
        "Malmö",
        "Uppsala",
        "Linköping"
    ]
    
    # Browser Selectors (multiple fallbacks)
    SELECTORS = {
        "cookie_accept": [
            "button.btn.btn-primary:has-text('Godkänn nödvändiga')",
            "button:has-text('Godkänn')",
            "button[data-accept-cookies]"
        ],
        "book_test_button": [
            "button[title='Boka prov']",
            "button:has-text('Boka prov')",
            ".booking-button"
        ],
        "continue_button": [
            "text='Fortsätt'",
            "button:has-text('Fortsätt')",
            ".continue-btn"
        ],
        "qr_code": [
            "img[alt*='QR']",
            "canvas[id*='qr']",
            ".qr-code img",
            "#qr-code",
            "img[src*='qr']"
        ],
        "license_selection": "button[title='{}']",
        "exam_type_dropdown": "#examination-type-select",
        "vehicle_select": "#vehicle-select",
        "location_search": "#select-location-search",
        "location_input": "#location-search-input",
        "confirm_location": "text=Bekräfta",
        "available_times": "text='Lediga provtider'",
        "select_time": "button.btn.btn-primary:has-text('Välj')",
        "continue_cart": "#cart-continue-button",
        "pay_later": "#pay-invoice-button"
    }


# Global settings instance
settings = Settings()
booking_config = BookingConfig()


def get_settings() -> Settings:
    """Get application settings"""
    return settings


def get_booking_config() -> BookingConfig:
    """Get booking configuration"""
    return booking_config 