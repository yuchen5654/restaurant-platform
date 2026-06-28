from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = 'postgresql://rp_user:localdevpassword@localhost/restaurant_platform'
    SECRET_KEY: str = 'change-this-in-production-use-secrets-manager'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REDIS_URL: str = 'redis://localhost:6379/0'
    ANTHROPIC_API_KEY: str = ''
    OPENAI_API_KEY: str = ''
    TOAST_CLIENT_ID: str = ''
    TOAST_CLIENT_SECRET: str = ''
    SENDGRID_API_KEY: str = ''

    class Config:
        env_file = '.env'


settings = Settings()
