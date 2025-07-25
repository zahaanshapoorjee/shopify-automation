from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    WHATSAPP_TOKEN: str
    WHATSAPP_PHONE_ID: str
    DATABASE_URL: str

    class Config:
        env_file = ".env"

settings = Settings()