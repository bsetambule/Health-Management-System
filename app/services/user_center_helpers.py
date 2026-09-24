from datetime import datetime, timezone
from app.extensions import db
from app.models.user import User
from app.models.center import Center
from app.models.auditLog import AuditLog

VALID_ROLES = ['CENTER_MANAGER', 'RECEPTIONIST', 'DOCTOR', 'PHARMACIST', 'PATIENT', 'ADMIN']

def deactivate_user(user: User, performed_by: str):
    """Deactivate a single user and store audit log"""
    if not user.original_role:
        user.original_role = user.role

    user.role = "DEACTIVATED"
    user.isActive = False
    user.deactivated_at = datetime.now(timezone.utc) 
    user.updated_at = datetime.now(timezone.utc) 
    db.session.add(user)

    # Audit log
    audit = AuditLog(
        userID=performed_by,
        action="DEACTIVATE USER",
        entity=f"User {user.userID}",
        timestamp=datetime.now(timezone.utc) ,
        initiated_by=performed_by
    )
    db.session.add(audit)

def activate_user(user: User, performed_by: str):
    """Activate a single user and restore their original role"""
    user.isActive = True
    user.deactivated_at = None
    user.updated_at = datetime.now(timezone.utc) 
    if user.original_role in VALID_ROLES:
        user.role = user.original_role
    db.session.add(user)

    # Audit log
    audit = AuditLog(
        userID=performed_by,
        action="ACTIVATE USER",
        entity=f"User {user.userID}",
        timestamp=datetime.now(timezone.utc) ,
        initiated_by=performed_by
    )
    db.session.add(audit)

def deactivate_center(center: Center, performed_by: str):
    """Deactivate center and all associated employees"""
    center.isActive = False
    center.deactivated_at = datetime.now(timezone.utc) 
    center.updated_at = datetime.now(timezone.utc) 
    db.session.add(center)

    users = User.query.filter_by(centerID=center.centerID).filter(User.role.in_(VALID_ROLES[:-1])).all()
    for user in users:
        deactivate_user(user, performed_by)

    db.session.commit()

    # Center audit log
    audit = AuditLog(
        userID=performed_by,
        action="DEACTIVATE CENTER",
        entity=f"Center {center.centerID}",
        timestamp=datetime.now(timezone.utc) ,
        initiated_by=performed_by
    )
    db.session.add(audit)
    db.session.commit()

def activate_center(center: Center, performed_by: str):
    """Activate center and all DEACTIVATED employees"""
    center.isActive = True
    center.deactivated_at = None
    center.updated_at = datetime.now(timezone.utc) 
    db.session.add(center)

    users = User.query.filter_by(centerID=center.centerID, role="DEACTIVATED").all()
    for user in users:
        activate_user(user, performed_by)

    db.session.commit()

    # Center audit log
    audit = AuditLog(
        userID=performed_by,
        action="ACTIVATE CENTER",
        entity=f"Center {center.centerID}",
        timestamp=datetime.now(timezone.utc) ,
        initiated_by=performed_by
    )
    db.session.add(audit)
    db.session.commit()
