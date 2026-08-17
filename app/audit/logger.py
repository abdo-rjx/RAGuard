"""Audit logging — one row per decision point (plan Section 6, Phase 6).

Also hosts the non-ML anomaly flagging (feature A5): after each ACCESS_DENIED /
INJECTION_SUSPECTED_* event, if the same user has more than 5 such events in the
last 10 minutes, a lightweight SecurityAlert row is written so the admin dashboard
can surface the user as \"needs review\".
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

# Control characters (incl. CR/LF) that could be used to forge/fake log lines
# when the audit trail is exported to a SIEM or tailed in a terminal.
_CTRL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize(value: str | None) -> str | None:
    if value is None:
        return None
    return _CTRL_CHARS.sub(" ", value)

# Actions that count toward the anomaly threshold (feature A5).
ANOMALY_ACTIONS = {"ACCESS_DENIED", "INJECTION_SUSPECTED_QUERY", "INJECTION_SUSPECTED_CONTEXT"}
ANOMALY_THRESHOLD = 5  # more than this many events within the window triggers a flag
ANOMALY_WINDOW_MINUTES = 10


def write_audit_event(
    db: Session,
    action: str,
    *,
    user_id: int | None = None,
    username: str | None = None,
    role: str | None = None,
    query_text: str | None = None,
    decision: str | None = None,
    reason: str | None = None,
    details_json: dict[str, Any] | None = None,
) -> None:
    """Write an audit row. Never raises — logging must not break the request path."""
    try:
        # Strip control characters from free-text fields so a malicious query or
        # username can't inject fake lines into the exported audit trail.
        entry = AuditLog(
            user_id=user_id,
            username=_sanitize(username),
            role=role,
            action=action,
            query_text=_sanitize(query_text),
            decision=decision,
            reason=_sanitize(reason),
            details_json=details_json,
        )
        db.add(entry)
        db.commit()
        _check_anomaly(db, action=action, user_id=user_id, username=username)
    except Exception:
        db.rollback()


def _check_anomaly(db: Session, *, action: str, user_id: int | None, username: str | None) -> None:
    """Feature A5 — after an ACCESS_DENIED / INJECTION_SUSPECTED_* write, flag the
    user if they've tripped more than 5 such events in the last 10 minutes.
    Non-ML, never raises."""
    if user_id is None or action not in ANOMALY_ACTIONS:
        return
    try:
        from app.models.feature_models import SecurityAlert

        window_start = datetime.now(timezone.utc) - timedelta(minutes=ANOMALY_WINDOW_MINUTES)
        count = (
            db.query(AuditLog)
            .filter(
                AuditLog.user_id == user_id,
                AuditLog.action.in_(ANOMALY_ACTIONS),
                AuditLog.timestamp >= window_start,
            )
            .count()
        )
        if count <= ANOMALY_THRESHOLD:
            return
        # Dedupe: don't stack an alert for the same user inside the same window.
        existing = (
            db.query(SecurityAlert)
            .filter(
                SecurityAlert.user_id == user_id,
                SecurityAlert.created_at >= window_start,
            )
            .first()
        )
        if existing is not None:
            return
        db.add(
            SecurityAlert(
                user_id=user_id,
                username=username,
                event_action=action,
                event_count=count,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
