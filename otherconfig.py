import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


class BaseConfig:
    """
    Base configuration shared across all environments
    """

    #  Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-secret")

    #  Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    #  Email (Flask-Mail)
    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    #  Session & auth
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Can be overridden in production
    SESSION_COOKIE_SECURE = False


class DevelopmentConfig(BaseConfig):
    """
    Development environment configuration
    """

    DEBUG = True
    ENV = "development"

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///dev.db"
    )


class TestingConfig(BaseConfig):
    """
    Testing configuration
    """

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    """
    Production environment configuration
    """

    DEBUG = False
    ENV = "production"

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    # Stronger cookie security
    SESSION_COOKIE_SECURE = True


# Mapping used by create_app()
config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig
}
