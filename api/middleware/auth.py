"""Demo RBAC claims. Header claims are intentionally demo-only, never production auth."""
import os
from typing import Literal

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

OfficerRole = Literal["STATION_OFFICER", "DISTRICT_SP", "STATE_DGP"]
JurisdictionType = Literal["STATION", "DISTRICT", "STATE"]


class OfficerContext(BaseModel):
    user_id: str
    role: OfficerRole
    jurisdiction_type: JurisdictionType
    jurisdiction_id: str

    @property
    def cache_key(self) -> str:
        return f"{self.role}:{self.jurisdiction_type}:{self.jurisdiction_id}"


_ROLE_SCOPE = {
    "STATION_OFFICER": "STATION",
    "DISTRICT_SP": "DISTRICT",
    "STATE_DGP": "STATE",
}


def get_current_officer(
    x_officer_id: str | None = Header(default=None),
    x_officer_role: OfficerRole | None = Header(default=None),
    x_officer_jurisdiction_type: JurisdictionType | None = Header(default=None),
    x_officer_jurisdiction_id: str | None = Header(default=None),
) -> OfficerContext:
    """Resolve demo claims. Production must inject verified JWT/SSO claims here."""
    if os.getenv("DEMO_AUTH_MODE", "true").lower() not in {"1", "true", "yes"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Production JWT/SSO officer authentication is not configured.",
        )
    if not all((x_officer_role, x_officer_jurisdiction_type, x_officer_jurisdiction_id)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Officer clearance headers are required.")
    if _ROLE_SCOPE[x_officer_role] != x_officer_jurisdiction_type:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role and jurisdiction scope do not match.")
    return OfficerContext(
        user_id=x_officer_id or f"demo:{x_officer_role.lower()}",
        role=x_officer_role,
        jurisdiction_type=x_officer_jurisdiction_type,
        jurisdiction_id=x_officer_jurisdiction_id.strip(),
    )
