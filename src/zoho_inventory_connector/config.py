from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

READ_ONLY_SCOPES = (
    "ZohoInventory.settings.READ",
    "ZohoInventory.items.READ",
    "ZohoInventory.salesorders.READ",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    zoho_client_id: str | None = None
    zoho_client_secret: str | None = None
    zoho_refresh_token: str | None = None
    zoho_access_token: str | None = None
    zoho_redirect_uri: str = "http://localhost:8080/callback"
    zoho_organization_id: str | None = None

    zoho_accounts_base_url: str = "https://accounts.zoho.com"
    zoho_api_base_url: str = "https://www.zohoapis.com"

    zoho_request_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    zoho_max_retries: int = Field(default=4, ge=1, le=8)
    zoho_max_scan_pages: int = Field(default=3, ge=1, le=20)
    zoho_max_correlation_orders: int = Field(default=40, ge=1, le=200)

    @model_validator(mode="after")
    def normalize_urls(self) -> "Settings":
        self.zoho_accounts_base_url = self.zoho_accounts_base_url.rstrip("/")
        self.zoho_api_base_url = self.zoho_api_base_url.rstrip("/")
        return self

    def validate_runtime_auth(self) -> None:
        if self.zoho_access_token:
            return
        required = {
            "ZOHO_CLIENT_ID": self.zoho_client_id,
            "ZOHO_CLIENT_SECRET": self.zoho_client_secret,
            "ZOHO_REFRESH_TOKEN": self.zoho_refresh_token,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                "Missing Zoho OAuth configuration: "
                + ", ".join(missing)
                + ". Configure refresh-token auth or ZOHO_ACCESS_TOKEN."
            )

    def require_organization_id(self) -> str:
        if not self.zoho_organization_id:
            raise ValueError(
                "ZOHO_ORGANIZATION_ID is required for organization-scoped Inventory calls."
            )
        return self.zoho_organization_id


@lru_cache
def get_settings() -> Settings:
    return Settings()
