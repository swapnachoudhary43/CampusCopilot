"""Runtime settings loaded from environment variables and backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Values that change between a developer laptop, tests, and a demo."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CampusCopilot"
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 480
    bcrypt_rounds: int = 12
    database_url: str | None = None
    storage_dir: str | None = None
    embedding_backend: str = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    similarity_threshold: float = 0.48
    retrieval_top_k: int = 4
    llm_provider: str = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    max_upload_mb: int = 15
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    chunk_size: int = 900
    chunk_overlap: int = 150

    @property
    def project_dir(self) -> Path:
        return PROJECT_DIR

    @property
    def storage_path(self) -> Path:
        if self.storage_dir:
            return Path(self.storage_dir)
        return BACKEND_DIR / "storage"

    @property
    def upload_path(self) -> Path:
        return self.storage_path / "uploads"

    @property
    def database_file_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.storage_path / "campuscopilot.db"
        return f"sqlite:///{db_path.as_posix()}"

    @property
    def faiss_index_path(self) -> Path:
        return self.storage_path / "faiss.index"

    @property
    def faiss_meta_path(self) -> Path:
        return self.storage_path / "faiss_meta.json"

    @property
    def model_dir(self) -> Path:
        return PROJECT_DIR / "models"

    @property
    def data_dir(self) -> Path:
        return PROJECT_DIR / "data"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    def resolved_llm_mode(self) -> str:
        """Decide whether answers may call Gemini.

        retrieval_only and gemini_missing never invent a generated answer.
        """
        provider = self.llm_provider.strip().lower()
        if provider == "retrieval_only":
            return "retrieval_only"
        if provider == "gemini":
            return "gemini" if self.gemini_configured else "gemini_missing"
        if self.gemini_configured:
            return "gemini"
        return "retrieval_only"


@lru_cache
def get_settings() -> Settings:
    return Settings()
