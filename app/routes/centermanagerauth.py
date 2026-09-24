from flask import Blueprint, render_template, request,flash, redirect, url_for, abort
from flask_login import login_required, current_user
from app.services.userService import generate_display_id
from app.models.user import User
from app.models.center import Center
from app.extensions import db
from app.services.userService import generate_display_id
from werkzeug.security import generate_password_hash
from app.services.emailService import send_temp_password_email,send_password_reset_email
import random
import string
from app.models.auditLog import AuditLog
from datetime import datetime, date, timezone
from app.services.user_center_helpers import activate_user, deactivate_user
import re

centermanager_bp = Blueprint("centermanager", __name__, url_prefix="/centermanager")

@centermanager_bp.route("/centermanager_dash")
@login_required
def centermanager_dash():

    if current_user.role != "CENTER_MANAGER":
        abort(403)

    users_in_center = (
        User.query
        .filter(User.centerID == current_user.centerID)
        .order_by(User.created_at.desc())
        .all()
    )

    return render_template(
        "centerManager/centerManagerDash.html",
        total_users=len(users_in_center),
        recent_users=users_in_center[:10]
    )



#VIEW ALL USERS
@centermanager_bp.route("/centermanager_users")
@login_required
def centermanager_users():

    # Ensure only center managers can access
    if current_user.role != "CENTER_MANAGER":
        abort(403)

    page = request.args.get("page", 1, type=int)
    per_page = 10

    users = (User.query.filter_by(centerID=current_user.centerID).order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False))

    return render_template(
        "centerManager/centerManagerUsers.html",
        users=users
    )













# Function to generate a temporary password
def generate_temp_password(length=12):
    # Temporary password with a mix of letters, digits, and special characters
    characters = string.ascii_letters + string.digits + string.punctuation
    temp_password = ''.join(random.choice(characters) for i in range(length))
    return temp_password



# CREATE USER
@centermanager_bp.route("/create_user/<int:centerID>", methods=["GET", "POST"])
@login_required
def create_user(centerID):
    center = Center.query.get_or_404(centerID)  # Get the center by ID
    

    if request.method == "POST":
        # Get form data
        role = request.form["role"]
        firstname = request.form["first_name"]
        lastname = request.form["last_name"]
        phonenumber = request.form["phone"]
        #if not re.fullmatch(r"7\d{7}", phonenumber):
        #    flash("Phone number must start with 7 and be exactly 8 digits.", "danger")
        #    return redirect(request.referrer)  # or redirect(url_for("your_route"))
        email = request.form["email"]

        # Generate userID and username once
        userID = generate_display_id(role)
        username = userID

        # Generate and hash temporary password
        temp_password = generate_temp_password()
        hashed_temp_password = generate_password_hash(temp_password)

        # Create the new user
        new_user = User(
            userID=userID,
            username=username,
            firstname=firstname,
            lastname=lastname,
            phonenumber=phonenumber,
            email=email,
            role=role,
            centerID=centerID,
            password_hash=hashed_temp_password,
            password_set=False,
            password_reset_at=datetime.now(timezone.utc),
            original_role = role
        )

        db.session.add(new_user)

        # Audit log
        audit_log = AuditLog(
            userID=current_user.id,
            action="CREATE USER ACCOUNT",
            entity=f"User {new_user.userID}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)

        db.session.commit()

        # Send email with temp password
        send_temp_password_email(new_user.email, new_user.username, temp_password)

        # Flash success message
        flash(f"The user {firstname} {lastname} has been successfully created.", "success")

        return redirect(url_for('centermanager.centermanager_users'))

    # GET request → render form
    return render_template(
        "centermanager/createUser.html",
        center=center
    )



# EDIT USER
@centermanager_bp.route("/centermanager_editUser/<string:user_id>", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    # Security: only edit users in the same center
    if user.centerID != current_user.centerID:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("centermanager.centermanager_users"))

    if request.method == "POST":
        # Map form names to DB column names
        field_map = {
            "first_name": "firstname",
            "last_name": "lastname",
            "phone": "phonenumber",
            "email": "email",
            "role": "role"
        }

        # Get form values
        form_values = {form_field: request.form.get(form_field) for form_field in field_map.keys()}

        if not all(form_values.values()):
            flash("All fields are required.", "danger")
            return redirect(request.url)

        # Snapshot BEFORE
        old_values = {db_field: getattr(user, db_field) for db_field in field_map.values()}

        # Apply updates
        for form_field, db_field in field_map.items():
            setattr(user, db_field, form_values[form_field])
        user.updated_at = datetime.now(timezone.utc)

        # Detect changes
        changes = []
        for db_field, old in old_values.items():
            new = getattr(user, db_field)
            if str(old) != str(new):
                changes.append(f"{db_field}: {old} → {new}")

        # Audit log (only if something changed)
        if changes:
            db.session.add(AuditLog(
                userID=current_user.id,  # center manager who edited
                action="EDIT USER",
                entity=f"User {user.userID} | " + ", ".join(changes),
                timestamp=datetime.now(timezone.utc),
                initiated_by=current_user.userID
            ))

        db.session.commit()

        flash("User updated successfully.", "success")
        return redirect(url_for("centermanager.centermanager_users"))

    # GET request
    return render_template(
        "centermanager/editUser.html",
        user=user,
        center=user.center
    )











# VIEW USERS BY ID
@centermanager_bp.route("/users/<string:user_id>")
@login_required
def centermanager_user_view(user_id):
    user = User.query.get_or_404(user_id)  # Fetch the user by ID
    audit_logs = AuditLog.query.filter_by(userID=user.id).order_by(AuditLog.timestamp.desc()).limit(10).all()  

    # Create an audit log entry for viewing a user profile
    if current_user.is_authenticated:
        audit_log = AuditLog(
            userID=current_user.id,          # Admin/actor performing the action
            action="VIEW USER PROFILE",      # Action being done
            entity=f"User {user.userID}",    # Target of the action
            timestamp=datetime.now(timezone.utc) ,        # When it happened
            initiated_by=f"{current_user.userID}"  # Actor code
        )
        db.session.add(audit_log)
        db.session.commit()

    return render_template("centerManager/centerManagerViewUser.html", user=user, audit_logs=audit_logs)





# RESET PASSWORD
@centermanager_bp.route("/users/reset_password/<string:user_id>", methods=["GET", "POST"])
@login_required
def reset_password(user_id):
    if current_user.role != "CENTER_MANAGER":
        abort(403)

    user = User.query.get_or_404(user_id)

    temp_password = generate_temp_password()

    user.password_hash = generate_password_hash(temp_password)
    user.password_set = False
    user.password_reset_at = datetime.now(timezone.utc) 
    user.failed_attempts = 0
    user.last_failed_attempt = None
    user.updated_at = datetime.now(timezone.utc) 
    user.password_reset_at = datetime.now(timezone.utc) 

    db.session.add(AuditLog(
        userID=current_user.id,                     # actor (admin UUID)
        action="CENTER MANAGER PASSWORD RESET",
        entity=f"Password reset for {user.userID}", # target
        timestamp=datetime.now(timezone.utc) ,
        initiated_by=current_user.userID            # admin code (ADM001)
    ))

    db.session.commit()

    send_password_reset_email(user.email, temp_password, user)

    flash(f"{user.firstname} {user.lastname}'s password has been reset", "success")
    return redirect(url_for("centermanager.centermanager_user_view", user_id=user.id))




# DEACTIVATE USER
@centermanager_bp.route("/users/deactivate/<string:user_id>", methods=["POST"])
@login_required
def deactivate_user_route(user_id):
    user = User.query.get_or_404(user_id)
    if user.isActive:
        deactivate_user(user, current_user.id)
        db.session.commit()
        flash(f"User {user.firstname} {user.lastname} has been deactivated.", "success")
    else:
        flash("User account is already inactive.", "warning")
    return redirect(url_for('centermanager.centermanager_user_view', user_id=user.id))

# ACTIVATE USER
@centermanager_bp.route("/users/activate/<string:user_id>", methods=["POST"])
@login_required
def activate_user_route(user_id):
    user = User.query.get_or_404(user_id)
    if not user.isActive:
        activate_user(user, current_user.id)
        db.session.commit()
        flash(f"User {user.firstname} {user.lastname} has been reactivated.", "success")
    else:
        flash(f"User {user.firstname} {user.lastname} is already active.", "warning")
    return redirect(url_for('centermanager.centermanager_user_view', user_id=user.id))





