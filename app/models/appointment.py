from app.extensions import db
from datetime import datetime, timezone
from enum import Enum as PyEnum


class AppointmentStatus(PyEnum):
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    NO_SHOW = "No Show"


class Appointment(db.Model):
    __tablename__ = "appointments"

    appointmentID = db.Column(db.Integer, primary_key=True)

    patientID = db.Column(db.Integer, db.ForeignKey("patients.patientID"), nullable=False, index=True)
    doctorID = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    centerID = db.Column(db.Integer, db.ForeignKey("centers.centerID"), nullable=False, index=True)

    appointmentDateTime = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    appointmentNotes = db.Column(db.Text)

    status = db.Column(
        db.Enum(AppointmentStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AppointmentStatus.SCHEDULED.value,
        index=True
    )

    cancellation_reason = db.Column(db.Text)
    cancelled_at = db.Column(db.DateTime(timezone=True))

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships (explicit & clean)
    patient = db.relationship("Patient", back_populates="appointments")
    doctor = db.relationship("User", back_populates="appointments")
    center = db.relationship("Center", back_populates="appointments")

    diagnosis = db.relationship("Diagnosis", back_populates="appointment", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Appointment {self.appointmentID}>"
