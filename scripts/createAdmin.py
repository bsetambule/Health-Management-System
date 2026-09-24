import sys
import os
from datetime import datetime, timezone
from flask_login import current_user

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash
import getpass
from app.services.userService import generate_display_id  # Import the user service
from app.models.auditLog import AuditLog  # Import AuditLog model

app = create_app("development")

with app.app_context():
    # Ask for username
    username = input("Username: ")
    
    # Check if admin already exists
    if User.query.filter_by(username=username).first():
        print("Admin already exists")
        exit()

    # Prompt for password
    password = getpass.getpass("Password: ")

    # Generate unique userID for admin using the user service
    admin_user_id = generate_display_id("ADMIN")

    # Create the admin user instance
    admin = User(
        userID=admin_user_id,
        firstname="Admin",
        lastname="User",
        username=username,
        email="keyboardcypher@gmail.com",
        phonenumber="00000000",
        role="ADMIN",
        password_hash=generate_password_hash(password),
        isActive=True,
        isDeleted=False,
        deactivated_at=None,
        last_login=None,  # New admin will not have logged in yet
        created_at=datetime.now(timezone.utc),  # Set creation timestamp
        updated_at=datetime.now(timezone.utc),   # Set initial update timestamp
        original_role="ADMIN"
    )

    # Add the user to the session
    db.session.add(admin)
    
    # Commit the user to the database to generate the ID
    db.session.commit()

    # Now that the user has been committed and has a valid 'id', create the audit log
    audit_log = AuditLog(
        userID=admin.id,  # Admin performing the action
        action="CREATE NEW ADMIN ACCOUNT",
        entity=f"User {admin.userID}",  # Make entity more descriptive
        timestamp=datetime.now(timezone.utc),
        initiated_by=admin.userID
    )
    db.session.add(audit_log)

    # Commit the audit log
    db.session.commit()

    print(f"System created successfully Admin Account with userID: {admin_user_id}")
