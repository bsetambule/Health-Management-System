from app.extensions import db
from datetime import date, datetime, timezone
from app.models.user import User

class AuditLog(db.Model):
    __tablename__ = "auditlogs"
    logID = db.Column(db.Integer, primary_key=True)
    userID = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(300), nullable=True)
    entity = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(
    db.DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc)
)
    initiated_by = db.Column(db.String(100), nullable=False)

    user = db.relationship("User", back_populates="auditlogs")