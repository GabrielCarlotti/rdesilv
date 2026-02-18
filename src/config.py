"""
Application configuration management.

This module handles all configuration settings for the application.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    """
    Application environment settings.

    Loads configuration from .env file with strict validation.
    Settings:
        - APP_NAME: Application name
        - ENV: Environment (dev, prod, staging)
        - HOST: Server host address
        - PORT: Server port number
        - DEBUG: Debug mode flag
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    APP_NAME: str
    ENV: str
    HOST: str
    PORT: int
    DEBUG: bool


app_settings = AppSettings()  # type: ignore