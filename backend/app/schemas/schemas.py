from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class RecipientCreate(BaseModel):
    name: str
    organization: str = ""
    department: str = ""
    role: str = ""                     # free-text job title
    email: str = ""
    access_role: str = "officer"       # RBAC: "officer" | "auditor"


class RecipientOut(BaseModel):
    recipient_id: str
    name: str
    organization: str | None = None
    department: str | None = None
    role: str | None = None
    email: str | None = None
    status: str
    key_status: str
    created_at: str

    class Config:
        from_attributes = True


class ProtectRequestMeta(BaseModel):
    recipient_ids: list[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    recipient_id: str
    password: str


class LoginResponse(BaseModel):
    token: str
    recipient_id: str
    name: str
    organization: str = ""
    role: str = ""
    access_role: str = "officer"


class DecryptRequest(BaseModel):
    # The recipient's ML-DSA-65 signing PRIVATE key (contents of <id>.sig.private, or bare base64).
    # Held in memory for this request only; never written to disk or logged.
    signing_private_key_b64: str = ""
    apply_visible: bool = False        # visible stamp is OPT-IN; invisible watermark is always on


class RenderRequest(BaseModel):
    signing_private_key_b64: str = ""


class InvestigationOut(BaseModel):
    investigation_id: str
    status: str
    document_id: str | None = None
    event_id: str | None = None
    watermark_id: str | None = None
    recipient_id: str | None = None
    signature_valid: bool | None = None
    ledger_verified: bool | None = None
