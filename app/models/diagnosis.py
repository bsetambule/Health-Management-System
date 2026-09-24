from app.extensions import db
from datetime import datetime, timezone
from enum import Enum as PyEnum


class DiagnosisSeverity(PyEnum):
    MILD = "Mild"
    MODERATE = "Moderate"
    SEVERE = "Severe"
    CRITICAL = "Critical"


class Diagnosis(db.Model):
    __tablename__ = "diagnosis"

    diagnosisID = db.Column(db.Integer, primary_key=True)

    patientID = db.Column(
        db.Integer,
        db.ForeignKey("patients.patientID"),
        nullable=False,
        index=True
    )

    doctorID = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    diagnosisSummary = db.Column(
        db.String(250),
        nullable=False
    )

    diagnosisDetails = db.Column(
        db.Text,
        nullable=False
    )

    severity = db.Column(
        db.Enum(
            DiagnosisSeverity,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False
    )

    diagnosisDate = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    appointmentID = db.Column(db.Integer, db.ForeignKey('appointments.appointmentID'), nullable=True, index=True)

    # Relationships
    patient = db.relationship("Patient", back_populates="diagnoses")
    doctor = db.relationship("User", foreign_keys=[doctorID])
    prescriptions = db.relationship("Prescription", back_populates="diagnosis", cascade="all, delete-orphan")

    appointment = db.relationship("Appointment", back_populates="diagnosis", uselist=False)