"""Append-only audit writes."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent

#: Constant salt: the goal is unlinkability from the raw IP in a DB dump, while
#: keeping events from one origin correlatable. A per-deployment secret would be
#: stronger; that arrives with the auth work in Phase 2.
_ACTOR_SALT = b"voice-studio-audit-v1"


def hash_actor(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(_ACTOR_SALT + value.encode("utf-8")).hexdigest()[:32]


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        event: str,
        *,
        subject_id: str | None = None,
        actor: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        row = AuditEvent(
            event=event,
            subject_id=subject_id,
            actor_hash=hash_actor(actor),
            detail=json.dumps(detail, default=str) if detail else None,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list(self, *, limit: int = 100) -> list[AuditEvent]:
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))
