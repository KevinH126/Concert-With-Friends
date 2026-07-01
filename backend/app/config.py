from pydantic_settings import BaseSettings, SettingsConfigDict


def _with_driver(url: str, driver: str) -> str:
    """Normalize a Postgres URL to use an explicit SQLAlchemy driver.

    Render's managed Postgres hands out `postgresql://...` (and older Heroku-style
    `postgres://...`) URLs. asyncpg needs `postgresql+asyncpg://` and Alembic's sync
    engine needs `postgresql+psycopg2://`, so we rewrite the scheme rather than
    depend on whatever form the environment happens to provide. Idempotent.
    """
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
        "postgresql://",
        "postgres://",
    ):
        if url.startswith(prefix):
            return f"postgresql+{driver}://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    # Ops token for /admin routes. Deliberately separate from secret_key so a leaked
    # admin token can't be used to forge JWTs.
    admin_token: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days
    ticketmaster_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    # Public origin for links we hand out (invite landing pages). Falls back to the
    # request's own base URL when unset, which can be http:// behind Render's proxy.
    public_base_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def async_database_url(self) -> str:
        return _with_driver(self.database_url, "asyncpg")

    @property
    def sync_database_url(self) -> str:
        return _with_driver(self.database_url, "psycopg2")


settings = Settings()
