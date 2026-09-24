# app/__init__.py
from flask import Flask, request, session
from .config import config
from .extensions import db, login_manager, mail
from flask_migrate import Migrate

migrate = Migrate()


from flask import Blueprint
from flask_mail import Message
from app.extensions import mail

from flask_login import current_user, logout_user, login_required 
from flask import flash, redirect, url_for

from datetime import datetime,timedelta, date

test_bp = Blueprint("test", __name__)

@test_bp.route("/send_test_email")
def send_test_email():
    try:
        msg = Message("Test Email", recipients=["httgeek@gmail.com"])
        msg.body = "This is a test email sent from Flask-Mail."
        mail.send(msg)
        return "Test email sent successfully!"
    except Exception as e:
        return f"Failed to send email: {str(e)}"




def create_app(env="development"):
    app = Flask(__name__)
    app.config.from_object(config[env])


# Session timeout (e.g., 10 minutes)
    app.permanent_session_lifetime = timedelta(minutes=10)  # 10 minutes timeout


    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app,db)

    # Import models here (after db is initialized) to avoid circular imports
    from .models.user import User
    from .models.patient import Patient
    from .models.auditLog import AuditLog
 
    from .models.diagnosis import Diagnosis
    from .models.center import Center
    from .models.appointment import Appointment
    from .models.prescription import Prescription
    from .models.prescriptionDetail import PrescriptionDetails
    

    # Register blueprints
    from .routes.authentication import auth_bp
    from .routes.patientauth import patient_bp
    from .routes.adminauth import admin_bp
    from .routes.doctorauth import doctor_bp
    from .routes.centermanagerauth import centermanager_bp
    from .routes.pharmacyauth import pharmacy_bp
    from .routes.receptionauth import reception_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(centermanager_bp)
    app.register_blueprint(pharmacy_bp)
    app.register_blueprint(reception_bp)
    
    # Register the test blueprint in your `create_app` function
    app.register_blueprint(test_bp)


    # User loader
    @login_manager.user_loader
    def load_user(userID):
        print(f"Loading user with ID: {userID}")
        user = User.query.get(userID)
        if user:
            #print(f"User found: {user.userID}, Active: {user.isActive}, Role: {user.role}")
            if user.isActive and user.role != "DEACTIVATED":
                return user
            #else:
                #print(f"User {user.userID} is deactivated or inactive.")
        #else:
            #print(f"User with ID {userID} not found.")
        return None

    # BEFORE REQUEST HOOK INSIDE CREATE_APP
   
    @app.before_request
    def global_user_checks():
        if current_user.is_authenticated:
        #  Block inactive or deactivated non-admin users
            if current_user.role != "ADMIN" and (not current_user.isActive or current_user.role == "DEACTIVATED"):
                logout_user()
                flash("Your account has been deactivated. Contact your admin.", "warning")
                return redirect(url_for("auth.login"))

        #  Force password reset if temporary password is set
            if not current_user.password_set:
                allowed = {"auth.reset_pass", "auth.logout", "static"}
                if request.endpoint not in allowed:
                    return redirect(url_for("auth.reset_pass"))

    @app.before_request
    def make_session_permanent():
        """ Mark the session as permanent to enable session lifetime management. """
        session.permanent = True

    @app.route("/keep_alive", methods=["GET"])
    @login_required
    def keep_alive():
        """ This route is used to update the session's expiration time. """
        session.modified = True  # Refresh session expiration
        return '', 204  # No content, just a response to reset the timeout



    return app
