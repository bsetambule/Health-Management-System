from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import uuid
from datetime import datetime, timezone


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    userID = db.Column(db.String(36), unique=True)

    centerID = db.Column(db.Integer, db.ForeignKey("centers.centerID"), nullable=True)

    firstname = db.Column(db.String(20), nullable=False)
    lastname = db.Column(db.String(20), nullable=False)
    phonenumber = db.Column(db.String(8), unique=True, nullable=False)
    email = db.Column(db.String(30), unique=True, nullable=False)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    isActive = db.Column(db.Boolean, default=True, nullable=False)
    isDeleted = db.Column(db.Boolean, default=False, nullable=False)
    password_set = db.Column(db.Boolean, default=False)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    deactivated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)

    failed_attempts = db.Column(db.Integer, default=0)
    last_failed_attempt = db.Column(db.DateTime(timezone=True), nullable=True)
    password_reset_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    original_role = db.Column(db.String(20), nullable=False)

    otp_code = db.Column(db.String(6), nullable=True) 
    otp_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    
    # Relationships
    doctor_prescriptions = db.relationship("Prescription", back_populates="doctor")

    patient = db.relationship("Patient", back_populates="user", uselist=False)
    center = db.relationship("Center", back_populates="users")
    auditlogs = db.relationship("AuditLog", back_populates="user")

    appointments = db.relationship("Appointment", back_populates="doctor")

    diagnoses = db.relationship("Diagnosis", back_populates="doctor")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def deactivate(self):
        self.isActive = False
        self.deactivated_at = datetime.now(timezone.utc)

    def soft_delete(self):
        self.isDeleted = True
        self.deleted_at = datetime.now(timezone.utc)

    # Flask-Login compatibility
    @property
    def is_active(self):
       
        return self.isActive and not self.isDeleted

    @property
    def is_authenticated(self):
        
        return True

    @property
    def is_anonymous(self):
        
        return False

    def get_id(self):
        
        return str(self.id)    