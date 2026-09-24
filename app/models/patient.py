from app.extensions import db
from enum import Enum as PyEnum
from datetime import date, datetime, timezone


class SexType(PyEnum):
    MALE = "Male"
    FEMALE = "Female"


class Patient(db.Model):
    __tablename__ = "patients"

    patientID = db.Column(db.Integer, primary_key=True)
    userID = db.Column(db.String(36), db.ForeignKey("users.id"), unique=True, nullable=False, index=True)

    hospitalID = db.Column(db.Integer, db.ForeignKey("centers.centerID"))
    pharmacyID = db.Column(db.Integer, db.ForeignKey("centers.centerID"))

    omangnumber = db.Column(db.String(9), unique=True, nullable=False, index=True)
    dob = db.Column(db.Date)

    sex = db.Column(
        db.Enum(SexType, values_callable=lambda x: [e.value for e in x])
    )

    allergies = db.Column(db.Text)
    profile_completed = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship("User", back_populates="patient")
    appointments = db.relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    prescriptions = db.relationship("Prescription", back_populates="patient", cascade="all, delete-orphan")

    hospital = db.relationship("Center", foreign_keys=[hospitalID])
    pharmacy = db.relationship("Center", foreign_keys=[pharmacyID])

    diagnoses = db.relationship("Diagnosis", back_populates="patient")
    
    def __repr__(self):
        return f"<Patient {self.patientID}>"
