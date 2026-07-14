from collections.abc import Generator
from pathlib import Path

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
    xingce_docker: bool = False

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def resolve_database_url(config: Settings) -> str:
    if config.docker_database_url:
        return config.docker_database_url

    if config.xingce_docker:
        url = make_url(config.database_url)
        if url.host in {"localhost", "127.0.0.1"}:
            return url.set(host="host.docker.internal").render_as_string(hide_password=False)

    return config.database_url


database_url = resolve_database_url(settings)

engine = create_engine(
    database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
)

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
