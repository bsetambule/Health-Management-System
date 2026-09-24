# app/services/email_service.py
from flask_mail import Message
from app.extensions import mail
from app.models.user import User
from datetime import datetime, timezone, timedelta

def send_temp_password_email(email, username, temp_password):
    msg = Message(
        subject="Account Creation",
        recipients=[email]
    )
    msg.body = f"""
Hello,

Your account has been created.

Username: {username}
Temporary password: {temp_password}

Please log in and change your password immediately.

If you did not expect this email, please contact support.
"""
    mail.send(msg)


def send_password_changes_email(user):
    msg = Message(
        subject="Password Update Notification",
        recipients=[user.email]  # Use user.email
    )
    msg.body = f"""
Hello {user.firstname} {user.lastname},

Your password has been changed.

You can now log in.

If you did not initiate this change, please contact support.
"""
    mail.send(msg)


def send_password_reset_email(email, temp_password, user):
    msg = Message(
        subject="Account Password Reset",
        recipients=[email]
    )
    msg.body = f"""
Hello {user.firstname} {user.lastname},

Your password has been reset.


Temporary password: {temp_password}

Please log in and change your password immediately.

If you did not expect this email, please contact support.
"""
    mail.send(msg)


def send_otp_email(user, otp):
    """
    Sends OTP to the user's email for password reset.
    """
    if not user.email:
        return  # Can't send email if not set

    msg = Message(
        subject="Your OTP for Password Reset",
        sender="no-reply@hospitalapp.com",
        recipients=[user.email]
    )

    expiry_time = (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime("%H:%M UTC")

    msg.body = f"""
    Hello {user.firstname},

    You requested to reset your password. 
    Use the following One-Time Password (OTP) to verify your identity:

    OTP: {otp}

    This OTP will expire at {expiry_time}. 

    If you did not request a password reset, please contact support immediately.

    Regards,
    Hospital System Team
    """

    try:
        mail.send(msg)
        print(f"OTP email sent to {user.email}")  # For debugging/logging
    except Exception as e:
        print(f"Failed to send OTP email to {user.email}: {e}")