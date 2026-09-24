from flask import Blueprint, render_template, redirect, url_for, flash, request, session, abort
from flask_login import login_required, current_user
from flask_login import logout_user
from app.models.user import User
from app.models.center import Center
from app.extensions import db
from app.services.userService import generate_display_id
from werkzeug.security import generate_password_hash
import random
import string
from app.services.emailService import send_temp_password_email,send_password_reset_email
from app.models.auditLog import AuditLog
from datetime import date, datetime, timezone
from app.models.patient import Patient
from app.services.user_center_helpers import deactivate_center, activate_center, deactivate_user, activate_user


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/admin_dash")
@login_required
def admin_dash():

    total_users = User.query.count()
    total_centers = Center.query.count()
    active_centers = Center.query.filter_by(isActive=True).count()
    active_users = User.query.filter_by(isActive=True).count()

    recent_users = (
        User.query
        .order_by(User.id.desc())
        .limit(15)
        .all()
    )

    return render_template("admin/adminDash.html", 
        total_users=total_users,
        total_centers=total_centers,
        active_centers=active_centers,
        recent_users=recent_users,
        active_users=active_users)


#ADMIN CENTERS
@admin_bp.route("/admin_centers")
@login_required
def admin_centers():
    page = request.args.get('page', 1, type=int)
    centers = Center.query.order_by(Center.centerID.desc()).paginate(page=page, per_page=15)  # Fetch all centers from the database
    return render_template("admin/adminCenters.html", centers=centers)


# CREATE CENTERS
# CREATE CENTERS
@admin_bp.route("/admin_createCenter", methods=["GET", "POST"])
@login_required
def admin_createCenter():
    if request.method == "POST":
        # Get the form data
        centerName = request.form["name"]
        centerType = request.form["type"]
        centerLocation = request.form["location"]

        # Create a new Center object
        new_center = Center(
            centerName=centerName,
            centerType=centerType,
            centerLocation=centerLocation
        )

        # Add the new center to the database
        db.session.add(new_center)
        db.session.commit()

        # Now, create an audit log entry to capture the creation of the center
        audit_log = AuditLog(
            userID=current_user.id,  # The admin who is creating the center
            action="CREATE CENTER",
            entity=f"Center {new_center.centerName}",
            timestamp=datetime.now(timezone.utc) ,  # Use UTC time for consistency
            initiated_by=f"{current_user.userID}"  # The user who initiated the action
        )

        # Add the audit log to the database
        db.session.add(audit_log)
        db.session.commit()

        # Flash success message and redirect
        flash(f"Center {centerName} created successfully!", "success")
        return redirect(url_for('admin.admin_centers'))  # Redirect to the center list view

    # Handle the GET request (default)
    return render_template("admin/createCenter.html")




#GENERATE TEMPORARY PASSWORD
# Function to generate a temporary password
def generate_temp_password(length=12):
    # Temporary password with a mix of letters, digits, and special characters
    characters = string.ascii_letters + string.digits + string.punctuation
    temp_password = ''.join(random.choice(characters) for i in range(length))
    return temp_password




# ASSIGN CENTER MANAGER
# ASSIGN CENTER MANAGER
@admin_bp.route("/admin_assignManager/<int:centerID>", methods=["GET", "POST"])
@login_required
def assign_manager(centerID):
    center = Center.query.get_or_404(centerID)  # Get the center by ID

    userID = generate_display_id("CENTER_MANAGER")  # Generate userID

    if request.method == "POST":
        firstname = request.form["first_name"]
        lastname = request.form["last_name"]
        phonenumber = request.form["phone"]
        email = request.form["email"]

        # Check if center already has a manager
        manager_exists = User.query.filter_by(
            centerID=center.centerID,
            role="CENTER_MANAGER"
        ).first()

        if manager_exists:
            flash("This center already has a manager.", "danger")
            return redirect(url_for('admin.admin_centers'))

        # Generate a temporary password
        temp_password = generate_temp_password()

        # Hash the temporary password before saving it to the database
        hashed_temp_password = generate_password_hash(temp_password)

        # Create a new center manager user
        new_manager = User(
            userID=userID,
            username=userID,  # Set username to userID (auto-generated)
            firstname=firstname,
            lastname=lastname,
            phonenumber=phonenumber,
            email=email,
            role="CENTER_MANAGER",  # Set role as center manager
            centerID=centerID,  # Assign this manager to the current center
            password_hash=hashed_temp_password,  # Set the temporary password hash
            password_set=False,  # Flag indicating password hasn't been set
            original_role="CENTER_MANAGER"  # Store the original role (CENTER_MANAGER)
        )

# Add the new manager to the session
        db.session.add(new_manager)
        db.session.commit()  # Commit first so new_manager.id is available

# Assign the new manager to the center
        center.centerManager = new_manager.id

# Update the timestamp for the center
        center.updated_at = datetime.now(timezone.utc)
        db.session.commit()

# Create an audit log for the action of creating the center manager account
        audit_log = AuditLog(
           userID=current_user.id,
           action="CREATE CENTER MANAGER ACCOUNT",
           entity=f"Center Manager {new_manager.userID}",
           timestamp=datetime.now(timezone.utc),
           initiated_by=f"{current_user.userID}"
        )

        db.session.add(audit_log)
        db.session.commit()


        # Send the temporary password email
        send_temp_password_email(new_manager.email, new_manager.username, temp_password)

        flash(f"Manager {firstname} {lastname} has been successfully assigned to {center.centerName}. "
              f"An email has been sent to them.", "success")

        return redirect(url_for('admin.admin_centers'))  # Redirect to the list of centers

    # If GET request, render the form with the center data and generated username
    return render_template("admin/createCenterManager.html", center=center, generated_username=userID)




# DEASSIGN CENTER MANAGER

@admin_bp.route("/admin_deassignManager/<int:centerID>", methods=["POST"])
@login_required
def deassign_manager(centerID):
    # Fetch the center to deassign the manager from
    center = Center.query.get_or_404(centerID)

    # Fetch the current manager for the center
    manager = User.query.filter_by(centerID=center.centerID, role="CENTER_MANAGER").first()

    if not manager:
        flash("This center doesn't have a manager assigned.", "warning")
        return redirect(url_for('admin.admin_centers', center_id=center.centerID))

    # Log the deassignment action
    audit_log = AuditLog(
        userID=current_user.id,  # Admin performing the action
        action="DEASSIGN CENTER MANAGER",  # Action performed
        entity=f"Center {center.centerID}",  # Center being affected
        timestamp=datetime.now(),
        initiated_by=f"{current_user.userID}"  # Admin who initiated the action
    )
    db.session.add(audit_log)

    # Deassign the manager from the center (remove the manager)
    center.centerManager = None
    center.updated_at = datetime.now(timezone.utc)  # Capture the update timestamp for the center
    db.session.commit()

    # Now, deactivate the manager's account and change their role
    manager.isActive = False  # Deactivate the account, user can no longer login
    manager.role = "DEACTIVATED"  # You could set another status or role
    manager.updated_at = datetime.now(timezone.utc)   # Update the timestamp for the manager's profile
    db.session.commit()

    # Flash message to notify admin of the deassignment
    flash(f"The manager for {center.centerName} has been deassigned and their account is now deactivated.", "success")

    # Optionally, force logout the user if they are logged in, or invalidate their session
    if current_user.id == manager.id:
        logout_user()  # If the admin is deassigning their own role

    # Redirect to the center's details page
    return redirect(url_for('admin.admin_centers', center_id=center.centerID))


#ADMIN USERS

#@admin_bp.route("/admin_users")
#@login_required
#def admin_users():
#    users = User.query.order_by(User.id.desc()).all()

#    return render_template("admin/adminUsers.html",
#
#                            users=users)

@admin_bp.route("/admin_users")
@login_required
def admin_users():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.id.desc()).paginate(page=page, per_page=15)

    return render_template("admin/adminUsers.html",
                           users=users)


def create_user():
    role = request.form["role"]

    user = User(
        userID=generate_display_id(role),
        firstname=request.form["firstname"],
        lastname=request.form["lastname"],
        username=request.form["username"],
        role=role,
        password_set=False
    )
    db.session.add(user)
    db.session.commit()

    flash("User created successfully", "success")
    return redirect(url_for("admin.admin_users"))



#ADMIN REPORTS
@admin_bp.route('/admin/admin_reports/audit_logs')
@login_required
def admin_reports():
   page = request.args.get('page', 1, type=int)
   auditlogs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=15)
    
   return render_template(
        "admin/adminReports.html",
        auditlogs=auditlogs
    )



#ADMIN LOGOUT
#@admin_bp.route("/logout")
#@login_required
#def admin_logout():
#    logout_user()
#    flash("You have been logged out.", "info")
#    return redirect(url_for("auth.login"))


#VIEW AUDIT LOGS
@admin_bp.route('/admin/users/<user_id>/audit_logs')
def view_audit_logs(user_id):
    # Query for audit logs specific to the user
    auditlogs = AuditLog.query.filter_by(userID=user_id).order_by(AuditLog.timestamp.desc()).limit(10).all()

    # Fetch the user profile to display their data
    user = User.query.get(user_id)

    # Pass the audit logs and user profile to the template
    return render_template('admin/adminViewUser.html', auditlogs=auditlogs, user=user)


# VIEW USERS BY ID
@admin_bp.route("/users/<string:user_id>")
@login_required
def admin_user_view(user_id):
    page = request.args.get("page", 1, type=int)  # get current page from query params
    per_page = 10  # number of audit logs per page

    user = User.query.get_or_404(user_id)  # Fetch the user by ID

    # Use paginate instead of limit().all()
    audit_logs = (
        AuditLog.query
        .filter_by(userID=user.id)
        .order_by(AuditLog.timestamp.desc())
        .paginate(page=page, per_page=per_page)
    )

    # Create an audit log entry for viewing a user profile
    if current_user.is_authenticated:
        audit_log = AuditLog(
            userID=current_user.id,
            action="VIEW USER PROFILE",
            entity=f"User {user.userID}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=f"{current_user.userID}"
        )
        db.session.add(audit_log)
        db.session.commit()

    return render_template("admin/adminViewUser.html", user=user, auditlogs=audit_logs)

# RESET PASSWORD
@admin_bp.route("/users/reset_password/<string:user_id>", methods=["POST"])
@login_required
def admin_reset_user_password(user_id):
    if current_user.role != "ADMIN":
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
        action="ADMIN PASSWORD RESET",
        entity=f"Password reset for {user.userID}", # target
        timestamp=datetime.now(timezone.utc) ,
        initiated_by=current_user.userID            # admin code (ADM001)
    ))

    db.session.commit()

    send_password_reset_email(user.email, temp_password, user)

    flash(f"{user.firstname} {user.lastname}'s password has been reset", "success")
    return redirect(url_for("admin.admin_user_view", user_id=user.id))



# VIEW CENTER BY ID
# VIEW CENTER BY ID
@admin_bp.route("/admin_center_view/<string:center_id>")
@login_required
def admin_center_view(center_id):
    # Fetch the center using centerID
    center = Center.query.get_or_404(center_id)

    # Fetch the last 10 audit logs for this center
    audit_logs = AuditLog.query.filter_by(entity=f"Center {center.centerName}") \
                               .order_by(AuditLog.timestamp.desc()) \
                               .limit(10).all()

    # Fetch the center manager user object (if assigned)
    center_manager = None
    if center.centerManager:  # centerManager stores user.id
        center_manager = User.query.get(center.centerManager)

    # Create an audit log entry for viewing the center profile
    if current_user.is_authenticated:
        audit_log = AuditLog(
            userID=current_user.id,  # User who performed the action
            action="VIEW CENTER PROFILE",  # What the user did
            entity=f"Center {center.centerName}",  # The center that was viewed
            timestamp=datetime.now(timezone.utc),  # When it was viewed
            initiated_by=current_user.userID  # User who initiated the action
        )
        db.session.add(audit_log)
        db.session.commit()

    # Render the template with center data, manager, and audit logs
    return render_template(
        "admin/adminViewCenter.html",
        center=center,
        center_manager=center_manager,
        audit_logs=audit_logs
    )




















# DEACTIVATE CENTERS
@admin_bp.route("/deactivate_center/<int:center_id>", methods=["POST"])
@login_required
def deactivate_center_route(center_id):
    center = Center.query.get_or_404(center_id)
    if center.isActive:
        deactivate_center(center, current_user.id)
        flash(f"Center {center.centerName} and all associated users have been deactivated.", "success")
    else:
        flash(f"Center {center.centerName} is already inactive.", "warning")
    return redirect(url_for('admin.admin_center_view', center_id=center.centerID))

# ACTIVATE CENTERS
@admin_bp.route("/activate_center/<int:center_id>", methods=["POST"])
@login_required
def activate_center_route(center_id):
    center = Center.query.get_or_404(center_id)
    if not center.isActive:
        activate_center(center, current_user.id)
        flash(f"Center {center.centerName} and associated users have been reactivated.", "success")
    else:
        flash(f"Center {center.centerName} is already active.", "warning")
    return redirect(url_for('admin.admin_center_view', center_id=center.centerID))


# DEACTIVATE USER
@admin_bp.route("/users/deactivate/<string:user_id>", methods=["POST"])
@login_required
def deactivate_user_route(user_id):
    user = User.query.get_or_404(user_id)
    if user.isActive:
        deactivate_user(user, current_user.id)
        db.session.commit()
        flash(f"User {user.firstname} {user.lastname} has been deactivated.", "success")
    else:
        flash("User account is already inactive.", "warning")
    return redirect(url_for('admin.admin_user_view', user_id=user.id))

# ACTIVATE USER
@admin_bp.route("/users/activate/<string:user_id>", methods=["POST"])
@login_required
def activate_user_route(user_id):
    user = User.query.get_or_404(user_id)
    if not user.isActive:
        activate_user(user, current_user.id)
        db.session.commit()
        flash(f"User {user.firstname} {user.lastname} has been reactivated.", "success")
    else:
        flash(f"User {user.firstname} {user.lastname} is already active.", "warning")
    return redirect(url_for('admin.admin_user_view', user_id=user.id))


# EDIT USER
# EDIT USER
@admin_bp.route("/editUser/<string:user_id>", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    # Only admins can access
    if current_user.role != "ADMIN":
        abort(403)

    user = User.query.get_or_404(user_id)
    centers = Center.query.filter_by(isActive=True).all()

    if request.method == "POST":
        # Get values from form
        firstname = request.form.get("first_name")
        lastname = request.form.get("last_name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        role = request.form.get("role")
        centerID = request.form.get("centerID")

        # Validate required fields
        if not all([firstname, lastname, phone, email, role, centerID]):
            flash("You can now edit the preferred fields.", "info")
            return redirect(request.url)

        # Snapshot of old values
        old_values = {
            "firstname": user.firstname,
            "lastname": user.lastname,
            "phonenumber": user.phonenumber,
            "email": user.email,
            "role": user.role,
            "centerID": user.centerID
        }

        # Track changes and apply them
        changes = []
        if old_values["firstname"] != firstname:
            changes.append(f"firstname: {old_values['firstname']} → {firstname}")
            user.firstname = firstname
        if old_values["lastname"] != lastname:
            changes.append(f"lastname: {old_values['lastname']} → {lastname}")
            user.lastname = lastname
        if old_values["phonenumber"] != phone:
            changes.append(f"phonenumber: {old_values['phonenumber']} → {phone}")
            user.phonenumber = phone
        if old_values["email"] != email:
            changes.append(f"email: {old_values['email']} → {email}")
            user.email = email
        if old_values["role"] != role:
            changes.append(f"role: {old_values['role']} → {role}")
            user.role = role
        if str(old_values["centerID"]) != str(centerID):
            changes.append(f"centerID: {old_values['centerID']} → {centerID}")
            user.centerID = centerID

        # If no changes
        if not changes:
            flash("No changes detected.", "info")
            return redirect(url_for("admin.admin_user_view", user_id=user.id))

        # Update timestamp
        user.updated_at = datetime.now(timezone.utc)

        # Create audit log
        db.session.add(AuditLog(
            userID=current_user.id,
            action="EDIT USER",
            entity=f"User {user.userID} | " + ", ".join(changes),
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        ))

        # Commit changes
        db.session.commit()

        flash("User updated successfully.", "success")
        return redirect(url_for("admin.admin_user_view", user_id=user.userID))

    # GET → render edit form
    return render_template(
        "admin/adminEditUser.html",
        user=user,
        centers=centers
    )




# EDIT CENTER
from uuid import UUID

@admin_bp.route("/admin_editCenter/<int:center_id>", methods=["GET", "POST"])
@login_required
def admin_editCenter(center_id):
    if current_user.role != "ADMIN":
        abort(403)

    # Get the center or 404
    center = Center.query.get_or_404(center_id)

    # Fetch all active users for this center
    active_users = User.query.filter_by(centerID=center.centerID, isActive=True).all()

    # Debugging: Check if center.centerManager is a UUID and fetch the manager
    print(f"Center Manager UUID: {center.centerManager}")  # Debugging: Check if it's a UUID

    center_manager_user = None
    if center.centerManager:
        try:
            # Fetch the user based on the UUID stored in center.centerManager
            center_manager_user = User.query.get(center.centerManager)
            print(f"Center Manager User: {center_manager_user}")  # Debugging: Check if user is found
        except Exception as e:
            print(f"Error fetching center manager: {e}")  # Catch any potential error

    if request.method == "POST":
        # Get new values from form
        new_name = request.form.get("name")
        new_type = request.form.get("type")
        new_location = request.form.get("location")
        new_manager_id = request.form.get("manager")  # This will be the userID (UUID)

        # Validate required fields
        if not all([new_name, new_type, new_location]):
            flash("Please fill in all required fields.", "info")
            return redirect(request.url)

        # Track changes
        changes = []

        if center.centerName != new_name:
            changes.append(f"centerName: {center.centerName} → {new_name}")
            center.centerName = new_name
        if center.centerType != new_type:
            changes.append(f"centerType: {center.centerType} → {new_type}")
            center.centerType = new_type
        if center.centerLocation != new_location:
            changes.append(f"centerLocation: {center.centerLocation} → {new_location}")
            center.centerLocation = new_location

        # Update manager if changed
        if new_manager_id and new_manager_id != str(center.centerManager):
            old_manager_name = f"{center_manager_user.firstname} {center_manager_user.lastname}" if center_manager_user else "No Manager Assigned"
            new_manager = User.query.get(new_manager_id)
            new_manager_name = f"{new_manager.firstname} {new_manager.lastname}"

            # Track the manager change
            changes.append(f"centerManager: {old_manager_name} → {new_manager_name}")

            # Store the user ID (UUID) of the new manager
            center.centerManager = new_manager.id

        if not changes:
            flash("No changes detected.", "info")
            return redirect(url_for("admin.admin_centers"))

        # Update timestamp
        center.updated_at = datetime.now(timezone.utc)

        # Create audit log
        db.session.add(AuditLog(
            userID=current_user.id,
            action="EDIT CENTER",
            entity=f"Center {center.centerName} | " + ", ".join(changes),
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        ))

        db.session.commit()
        flash("Center updated successfully.", "success")
        return redirect(url_for("admin.admin_centers"))

    # GET → render the edit form with current manager info
    return render_template(
        "admin/editCenter.html",
        center=center,
        active_users=active_users,  # Pass eligible users to template
        center_manager_user=center_manager_user  # Pass current manager's user object
    )
