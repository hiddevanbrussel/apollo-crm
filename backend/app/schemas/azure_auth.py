from pydantic import BaseModel, Field


class AzureAuthPublicConfig(BaseModel):
    enabled: bool
    configured: bool


class AzureAdSettingsOut(BaseModel):
    enabled: bool
    configured: bool
    client_id: str | None = None
    client_secret_masked: str | None = None
    authority: str
    redirect_uri: str | None = None
    suggested_redirect_uri: str | None = None
    allowed_domains: list[str]


class AzureAdSettingsUpdate(BaseModel):
    enabled: bool | None = None
    client_id: str | None = None
    client_secret: str | None = None
    authority: str | None = None
    redirect_uri: str | None = None
    allowed_domains: list[str] | None = None
    clear_client_secret: bool = False
