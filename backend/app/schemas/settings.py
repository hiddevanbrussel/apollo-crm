from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApolloSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    base_url: str
    enabled: bool
    configured: bool = False
    api_key_masked: str | None = None
    created_at: datetime
    updated_at: datetime


class ApolloSettingsUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    enabled: bool | None = None
    clear_api_key: bool = False


class ApolloTestResult(BaseModel):
    success: bool
    message: str
    status_code: int | None = None


class GroqSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    base_url: str
    model: str
    enabled: bool
    assistant_enabled: bool = True
    configured: bool = False
    api_key_masked: str | None = None
    created_at: datetime
    updated_at: datetime


class GroqSettingsUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    enabled: bool | None = None
    assistant_enabled: bool | None = None
    clear_api_key: bool = False


class GroqTestResult(BaseModel):
    success: bool
    message: str
    status_code: int | None = None


class LogokitSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    base_url: str
    enabled: bool
    configured: bool = False
    # Logokit publishable token is meant for client-side image URLs, so the full
    # value is returned to the frontend (not masked).
    token: str | None = None
    created_at: datetime
    updated_at: datetime


class LogokitSettingsUpdate(BaseModel):
    token: str | None = None
    base_url: str | None = None
    enabled: bool | None = None
    clear_token: bool = False


class LogokitTestResult(BaseModel):
    success: bool
    message: str
    status_code: int | None = None


class LogokitTestInput(BaseModel):
    token: str | None = None


class LogokitClientConfig(BaseModel):
    enabled: bool
    configured: bool = False
    token: str | None = None
    base_url: str = "https://img.logokit.com"


class IntegrationServiceStatus(BaseModel):
    enabled: bool
    configured: bool


class ProspeoTestResult(BaseModel):
    success: bool
    message: str
    status_code: int | None = None


class ProspeoSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    base_url: str
    enabled: bool
    configured: bool = False
    api_key_masked: str | None = None
    created_at: datetime
    updated_at: datetime


class ProspeoSettingsUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    enabled: bool | None = None
    clear_api_key: bool = False


class LushaTestResult(BaseModel):
    success: bool
    message: str
    status_code: int | None = None


class LushaSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    base_url: str
    enabled: bool
    configured: bool = False
    api_key_masked: str | None = None
    created_at: datetime
    updated_at: datetime


class LushaSettingsUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    enabled: bool | None = None
    clear_api_key: bool = False


class IntegrationsStatusOut(BaseModel):
    apollo: IntegrationServiceStatus
    groq: IntegrationServiceStatus
    logokit: IntegrationServiceStatus
    prospeo: IntegrationServiceStatus
    lusha: IntegrationServiceStatus
    azure_ad: IntegrationServiceStatus
