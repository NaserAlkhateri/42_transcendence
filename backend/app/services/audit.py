from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def record_audit(db: Session, actor: User, action: str, target_type: str, target_id: object, details: dict) -> None:
    """Append an audit event. actor_label snapshots the email so the trail survives the actor's deletion."""
    db.add(
        AuditEvent(
            actor_id=actor.id,
            actor_label=actor.email,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            details=details,
        )
    )
