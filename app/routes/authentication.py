from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from app.extensions import db
from app.models.user import User
from app.models.patient import Patient

from flask_login import login_manager
from flask_login import login_user
from flask_login import login_required
from flask_login import logout_user
from flask_login import current_user
from werkzeug.security import generate_password_hash
from app.services.emailService import send_temp_password_email, send_otp_email 

from flask_mail import Message
from app.extensions import mail

import random
import string

from app.models.auditLog import AuditLog
from datetime import datetime, date, timedelta, timezone
from app.services.emailService import send_password_changes_email
from app.services.resetPasswordService import MAX_FAILED_ATTEMPTS, LOCK_TIME

import uuid
from random import randint

auth_bp = Blueprint("auth", __name__)

USERNAME_REGEX = r"^\d{9}$"
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{15,}$"


def generate_user_id(role):
    prefix = {"PATIENT": "PAT"}[role]
    count = User.query.filter_by(role=role).count() + 1
    return f"{prefix}{count:03d}"

@auth_bp.route("/")
def home():
    return render_template("account/landingPage.html")

#LOGIN
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash("Invalid username or password", "danger")
            return redirect(url_for("auth.login"))

        if not user.isActive or user.role == "DEACTIVATED":
            flash(
                "Your account has been deactivated or is no longer active. Please contact support.",
                "danger"
            )
            return redirect(url_for("auth.login"))

        # Temporary-password users
        if not user.password_set:
            login_user(user)
            user.last_login = datetime.now(timezone.utc) 
            db.session.commit()
            return redirect(url_for("auth.reset_password"))

        # Normal login
        login_user(user)

        # ✅ Capture last login
        user.last_login = datetime.now(timezone.utc) 
        db.session.commit()

        session["role"] = user.role
        session["firstname"] = user.firstname
        session["lastname"] = user.lastname

        if user.role == "PATIENT":
            return redirect(url_for("patient.patient_dash"))
        elif user.role == "DOCTOR":
            return redirect(url_for("doctor.doctor_dash"))
        elif user.role == "RECEPTIONIST":
            return redirect(url_for("reception.reception_dash"))
        elif user.role == "PHARMACIST":
            return redirect(url_for("pharmacy.pharmacy_dash"))
        elif user.role == "CENTER_MANAGER":
            return redirect(url_for("centermanager.centermanager_dash"))
        elif user.role == "ADMIN":
            return redirect(url_for("admin.admin_dash"))

        flash("Unauthorized role", "danger")
        return redirect(url_for("auth.login"))

    return render_template("account/login.html")


# GENERATE TEMPORARY PASSWORD
# Function to generate a temporary password
def generate_temp_password(length=12):
    # Temporary password with a mix of letters, digits, and special characters
    characters = string.ascii_letters + string.digits + string.punctuation
    temp_password = ''.join(random.choice(characters) for i in range(length))
    return temp_password


# CREATE ACCOUNT
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        firstname = request.form.get("firstName")
        lastname = request.form.get("lastName")
        phonenumber = request.form.get("phoneNumber")
        omangnumber = request.form.get("omangNumber")
        email = request.form.get("email")

        # Check if patient already exists
        if Patient.query.filter_by(omangnumber=omangnumber).first():
            flash("Account already exists. Please login.", "info")
            return redirect(url_for("auth.login"))

        temp_password = generate_temp_password()
        hashed_temp_password = generate_password_hash(temp_password)

        # Define role
        role = "PATIENT"

        # Create User
        user = User(
            userID=generate_user_id(role),
            firstname=firstname,
            lastname=lastname,
            phonenumber=phonenumber,
            email=email,
            username=omangnumber,
            role=role,
            original_role=role,
            password_hash=hashed_temp_password,
            password_set=False
        )

        # Create Patient and link to user
        patient = Patient(
            user=user,
            omangnumber=omangnumber
        )

        # Save to DB
        db.session.add(user)
        db.session.add(patient)
        db.session.commit()

        # 🔹 Audit Logging
        db.session.add(AuditLog(
            userID=user.id,  # the user that was just created
            action="USER REGISTERED",
            entity=f"Patient {patient.omangnumber} ({firstname} {lastname})",
            timestamp=datetime.now(timezone.utc),
            initiated_by=user.id  # self-registration
        ))
        db.session.commit()

        # Send temporary password via email
        send_temp_password_email(user.email, user.username, temp_password)

        # Flash success message
        flash(
            f"Account for {firstname} {lastname} created successfully. "
            f"Please check your email.",
            "success"
        )

        return redirect(url_for("auth.login"))

    return render_template("account/register.html")


#LOGOUT
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logging out.", "info")
    return redirect(url_for("auth.login"))


# password reset route
@auth_bp.route("/reset_password", methods=["GET", "POST"])
@login_required
def reset_password():
    if request.method == "POST":
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            flash("Passwords do not match", "danger")

            audit_log = AuditLog(
                userID=current_user.id,
                action="FAILED PASSWORD CHANGE",
                entity=f"User {current_user.userID}",
                timestamp=datetime.now(timezone.utc) ,
                initiated_by=current_user.userID
            )
            db.session.add(audit_log)
            db.session.commit()

            return redirect(url_for("auth.reset_password"))

        # Update password + metadata
        current_user.password_hash = generate_password_hash(new_password)
        current_user.password_set = True
        current_user.password_reset_at = datetime.now(timezone.utc) 
        current_user.updated_at = datetime.now(timezone.utc) 

        audit_log = AuditLog(
            userID=current_user.id,
            action="SUCCESSFUL PASSWORD CHANGE",
            entity=f"User {current_user.userID}",
            timestamp=datetime.now(timezone.utc) ,
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()

        send_password_changes_email(current_user)

        flash("Password updated successfully. Please log in again.", "success")

        logout_user()
        return redirect(url_for("auth.login"))

    return render_template("account/resetPassword.html")


# NEW RESET PASSWORD
@auth_bp.route("/reset_pass", methods=["GET", "POST"])
@login_required
def reset_pass():

    # 🔒 Lockout protection
    if current_user.failed_attempts >= MAX_FAILED_ATTEMPTS:
        if current_user.last_failed_attempt and \
           datetime.now(timezone.utc)  - current_user.last_failed_attempt < LOCK_TIME:
            flash("Too many failed attempts. Try again later.", "danger")
            logout_user()
            return redirect(url_for("auth.login"))
        else:
            current_user.failed_attempts = 0
            current_user.last_failed_attempt = None
            db.session.commit()

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            current_user.failed_attempts += 1
            current_user.last_failed_attempt = datetime.now(timezone.utc) 

            db.session.add(AuditLog(
                userID=current_user.id,
                action="FAILED PASSWORD CHANGE",
                entity=f"User {current_user.userID}",
                timestamp=datetime.now(timezone.utc) ,
                initiated_by=current_user.userID
            ))
            db.session.commit()

            flash("Passwords do not match", "danger")
            return redirect(url_for("auth.reset_pass"))

        # ✅ SUCCESS
        current_user.password_hash = generate_password_hash(new_password)
        current_user.password_set = True
        current_user.password_reset_at = None
        current_user.failed_attempts = 0
        current_user.last_failed_attempt = None
        current_user.updated_at = datetime.now(timezone.utc) 

        db.session.add(AuditLog(
            userID=current_user.id,
            action="SUCCESSFUL PASSWORD CHANGE",
            entity=f"User {current_user.userID}",
            timestamp=datetime.now(timezone.utc) ,
            initiated_by=current_user.userID
        ))

        db.session.commit()

        send_password_changes_email(current_user)

        flash("Password updated successfully. Please log in again.", "success")
        logout_user()
        return redirect(url_for("auth.login"))

    return render_template("account/resetPassword.html")


# send email


#def send_temp_password_email(user_email, temp_password):
#    msg = Message("Temporary Password", recipients=[user_email])
#    msg.body = f"Your temporary password is: {temp_password}. Please change it upon logging in."
#    try:
#        mail.send(msg)
#        print(f"Email sent to {user_email}")  # Debugging line
#    except Exception as e:
#        print(f"Error sending email: {str(e)}")


#FORGOT PASSWORD

@auth_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        phone = request.form.get("phoneNumber")
        
        user = User.query.filter_by(email=email).first()
        
        if not user or user.phonenumber != phone:
            flash("Email or phone number error.", "danger")
            return redirect(url_for("auth.forgot_password"))
        
        # Generate OTP
        otp = f"{randint(100000, 999999)}"
        user.otp_code = otp
        user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        db.session.commit()

        # Audit
        db.session.add(AuditLog(
            userID=user.id,
            action="GENERATED PASSWORD RESET OTP",
            entity=f"User {user.userID}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=user.userID
        ))
        db.session.commit()

        # Send OTP via email
        send_otp_email(user, otp)

        flash("OTP sent to your email. It will expire in 10 minutes.", "success")
        return redirect(url_for("auth.verify_otp", user_id=user.id))
    
    return render_template("account/forgotPassword.html")


# OTP

def ensure_utc(dt):
    """
    Ensures a datetime object is timezone-aware (UTC).
    Needed because SQLite may return naive datetimes.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@auth_bp.route("/verify_otp/<user_id>", methods=["GET", "POST"])
def verify_otp(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()

        # 🔒 Safety check: OTP must exist
        if not user.otp_code or not user.otp_expires_at:
            flash("Invalid or expired OTP. Please request a new one.", "danger")
            return redirect(url_for("auth.forgot_password"))

        # ❌ Incorrect OTP
        if user.otp_code != entered_otp:
            db.session.add(AuditLog(
                userID=user.id,
                action="FAILED OTP VERIFICATION",
                entity=f"User {user.userID}",
                timestamp=datetime.now(timezone.utc),
                initiated_by=user.userID
            ))
            db.session.commit()

            flash("Invalid OTP.", "danger")
            return redirect(url_for("auth.verify_otp", user_id=user.id))

        # ⏰ Expiry Check (SAFE)
        now = datetime.now(timezone.utc)
        otp_expiry = ensure_utc(user.otp_expires_at)

        if now > otp_expiry:
            user.otp_code = None
            user.otp_expires_at = None
            user.updated_at = datetime.now(timezone.utc)

            db.session.add(AuditLog(
                userID=user.id,
                action="EXPIRED OTP USED",
                entity=f"User {user.userID}",
                timestamp=datetime.now(timezone.utc),
                initiated_by=user.userID
            ))

            db.session.commit()

            flash("OTP has expired. Please request a new one.", "danger")
            return redirect(url_for("auth.forgot_password"))

        # ✅ OTP SUCCESS
        user.otp_code = None
        user.otp_expires_at = None
        user.updated_at = datetime.now(timezone.utc)

        db.session.add(AuditLog(
            userID=user.id,
            action="OTP VERIFIED SUCCESSFULLY",
            entity=f"User {user.userID}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=user.userID
        ))

        db.session.commit()

        return redirect(url_for("auth.otp_resetpassword", user_id=user.id))

    return render_template("account/verifyOTP.html")


# SET NEW PASSWORD


@auth_bp.route("/reset_password/<user_id>", methods=["GET", "POST"])
def otp_resetpassword(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_pass", user_id=user.id))

        # Update password
        user.password_hash = generate_password_hash(new_password)
        user.password_set = True
        user.password_reset_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Audit
        db.session.add(AuditLog(
            userID=user.id,
            action="PASSWORD RESET SUCCESSFUL",
            entity=f"User {user.userID}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=user.userID
        ))
        db.session.commit()

        flash("Password updated successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("account/confirmPassword.html")
