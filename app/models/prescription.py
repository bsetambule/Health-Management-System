from app.extensions import db
from enum import Enum as PyEnum
from datetime import date


class PrescriptionStatus(PyEnum):
    DRAFT = "Draft"
    PENDING = "Pending"
    PARTIALLY_FILLED = "Partially Filled"
    DISPENSED = "Dispensed"


class Prescription(db.Model):
    __tablename__ = "prescriptions"

    prescriptionID = db.Column(db.Integer, primary_key=True)

    patientID = db.Column(db.Integer, db.ForeignKey("patients.patientID"), nullable=False)
    doctorID = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    diagnosisID = db.Column(db.Integer, db.ForeignKey("diagnosis.diagnosisID"), nullable=False)
    appointmentID = db.Column(db.Integer, db.ForeignKey("appointments.appointmentID"), nullable=False)

    dateIssued = db.Column(db.DateTime(timezone=True), nullable=False)

    status = db.Column(
        db.Enum(PrescriptionStatus, values_callable=lambda x: [e.value for e in x]),
        default=PrescriptionStatus.PENDING.value,
        nullable=False
    )

    patient = db.relationship("Patient", back_populates="prescriptions")
    doctor = db.relationship("User", back_populates="doctor_prescriptions")
    diagnosis = db.relationship("Diagnosis", back_populates="prescriptions")
    appointment = db.relationship("Appointment")

    prescriptiondetails = db.relationship(
        "PrescriptionDetails",
        back_populates="prescription",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Prescription {self.prescriptionID}>"
