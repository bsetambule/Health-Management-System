from app.models.user import User
from app.extensions import db

ROLE_PREFIX = {
    "PATIENT": "PAT",
    "DOCTOR": "DOC",
    "RECEPTIONIST": "REC",
    "PHARMACIST": "PHM",
    "CENTER_MANAGER": "CM",
    "ADMIN": "ADM"
}

def generate_display_id(role: str) -> str:
    prefix = ROLE_PREFIX.get(role)

    if not prefix:
        raise ValueError("Invalid role")

    last_user = (
        User.query
        .filter(User.userID.like(f"{prefix}%"))
        .order_by(User.userID.desc())
        .first()
    )

    if not last_user:
        return f"{prefix}001"

    last_number = int(last_user.userID[len(prefix):])
    return f"{prefix}{last_number + 1:03d}"


def deactivate_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.deactivate()
        db.session.commit()
        return user
    return None

def restore_user(user_id):
    user = User.query.get(user_id)
    if user and user.isDeleted:
        user.isDeleted = False
        user.deactivated_at = None
        db.session.commit()
        return user
    return None