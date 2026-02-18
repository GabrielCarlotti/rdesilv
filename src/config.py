"""
Application configuration management.

This module handles all configuration settings for the application.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from google import genai

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


class GeminiSettings(BaseSettings):
    """
    Google Generative AI (Gemini) API configuration.

    Configures API keys and model identifiers for Google's AI services.
    Initializes the Genai client on instantiation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

    GOOGLE_API_KEY: str
    GEMINI_MODEL_2_5_FLASH: str

    def __init__(self, **data):
        super().__init__(**data)
        self.CLIENT = genai.Client(api_key=self.GOOGLE_API_KEY)


app_settings = AppSettings()  # type: ignore
gemini_settings = GeminiSettings()  # type: ignore