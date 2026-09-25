from collections.abc import Generator
from pathlib import Path
import ssl

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    database_url: str
    docker_database_url: str | None = None
    math_brain_docker: bool = False
    xingce_docker: bool = False
    teacher_invite_code: str = ""
    upload_dir: str = str(BACKEND_DIR / "uploads")
    max_answer_image_bytes: int = 8 * 1024 * 1024
    storage_backend: str = "local"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_bucket: str = "math-brain-uploads"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 30
    db_pool_recycle: int = 300
    db_ssl_ca_cert: str = ""
    static_dir: str = ""
    cors_origins: str = ""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def resolve_database_url(config: Settings) -> str:
    if config.docker_database_url:
        return config.docker_database_url

    if config.math_brain_docker or config.xingce_docker:
        url = make_url(config.database_url)
        if url.host in {"localhost", "127.0.0.1"}:
            return url.set(host="host.docker.internal").render_as_string(hide_password=False)

    return config.database_url


database_url = resolve_database_url(settings)

connect_args = {}
if settings.db_ssl_ca_cert.strip():
    ssl_context = ssl.create_default_context(cadata=settings.db_ssl_ca_cert)
    ssl_context.check_hostname = True
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    connect_args["ssl"] = ssl_context

engine_options = {
    "pool_pre_ping": True,
    "pool_recycle": settings.db_pool_recycle,
    "connect_args": connect_args,
}
if make_url(database_url).get_backend_name() != "sqlite":
    engine_options.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
    )

engine = create_engine(database_url, **engine_options)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
