from app.extensions import db
from datetime import datetime, timezone


class PrescriptionDetails(db.Model):
    __tablename__ = "prescriptiondetails"

    prescriptionDetailID = db.Column(db.Integer, primary_key=True)
    prescriptionID = db.Column(db.Integer, db.ForeignKey("prescriptions.prescriptionID"), nullable=False)

    medicineName = db.Column(db.String(50), nullable=False)
    dosage = db.Column(db.String(50), nullable=False)
    duration = db.Column(db.String(50), nullable=False)
    frequency = db.Column(db.String(30), nullable=False)
    instructions = db.Column(db.String(250))

    isDispensed = db.Column(db.Boolean, default=False)
    dispensed_at = db.Column(db.DateTime(timezone=True))
    dispensed_by = db.Column(db.String(36), db.ForeignKey("users.id"))

    prescription = db.relationship("Prescription", back_populates="prescriptiondetails")
    pharmacist = db.relationship("User", foreign_keys=[dispensed_by])

    def mark_as_dispensed(self, pharmacist_id):
        if not self.isDispensed:
            self.isDispensed = True
            self.dispensed_at = datetime.now(timezone.utc)
            self.dispensed_by = pharmacist_id
