from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API
    mindbase_api_host: str = "0.0.0.0"
    mindbase_api_port: int = 8080
    mindbase_api_key: str = "dev-key-change-me"
    mindbase_api_url: str = "http://localhost:8080"

    # Database
    database_url: str = "postgresql+asyncpg://mindbase:mindbase@localhost:5432/mindbase"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # S3
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "mindbase"
    s3_region: str = "us-east-1"

    # Embeddings
    embedding_api_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Worker
    worker_batch_size: int = 10
    worker_poll_interval_ms: int = 500

    # MCP
    mcp_server_port: int = 8090
    mcp_server_host: str = "0.0.0.0"

    # Queue
    stream_key: str = "mindbase:fragments"
    consumer_group: str = "mindbase-workers"

    # iCloud + Obsidian sync (macOS agent)
    icloud_mindbase_path: str = ""  # auto-detected if empty
    obsidian_vault_path: str = ""   # e.g. ~/Documents/MyVault
    sync_poll_interval_sec: int = 30
    sync_obsidian_enabled: bool = True
    sync_icloud_mirror: bool = True
