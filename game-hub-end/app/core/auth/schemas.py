"""Authentication value objects."""

from pydantic import BaseModel, ConfigDict, Field


class AuthenticatedUser(BaseModel):
    """User identity decoded from a valid short-lived access token."""

    model_config = ConfigDict(frozen=True)

    userId: str = Field(min_length=1)
    serviceId: str = Field(min_length=1)
    deviceId: str = Field(min_length=1)
    tokenId: str = Field(min_length=1)
    issuedAt: int = Field(ge=0)
    expiresAt: int = Field(ge=0)


class AccessTokenPayload(BaseModel):
    """Access token issue result."""

    model_config = ConfigDict(extra="forbid")

    accessToken: str = Field(min_length=1)
    expiresAt: int = Field(ge=0)
    tokenId: str = Field(min_length=1)
