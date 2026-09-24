from flask import Blueprint, render_template, redirect, flash, url_for, request
from flask_login import login_required, current_user
from app.services.userService import generate_display_id
from app.models.user import User
from app.models.prescription import Prescription
from datetime import date, datetime, timezone, timedelta
from app.extensions import db
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from app.models.patient import Patient
from app.models.auditLog import AuditLog

pharmacy_bp = Blueprint("pharmacy", __name__, url_prefix="/pharmacy")

#PHARMACY DASH
@pharmacy_bp.route("/pharmacy_dash")
@login_required
def pharmacy_dash():
    center_id = current_user.centerID

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    prescriptions_today = (
    db.session.query(Prescription)
    .join(Patient)
    .filter(Patient.pharmacyID == center_id)
    .filter(Prescription.dateIssued >= today_start)
    .filter(Prescription.dateIssued < today_end)
    .order_by(Prescription.dateIssued.desc())
    .limit(10)
    .all()
)

    return render_template(
        "pharmacy/pharmacyDash.html",
        prescriptions=prescriptions_today,
        recent_prescriptions=len(prescriptions_today)
    )




#LIST ALL PRESCRIPTIONS
@pharmacy_bp.route("/pharmacy_prescriptions")
@login_required
def pharmacy_prescriptions():
    center_id = current_user.centerID
    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Query prescriptions for patients in the same center
    prescriptions = (
    Prescription.query
    .join(Patient)
    .filter(Patient.pharmacyID == center_id)
    .options(
        joinedload(Prescription.patient).joinedload(Patient.user),
        joinedload(Prescription.doctor),
        joinedload(Prescription.prescriptiondetails)
    )
    .order_by(desc(Prescription.dateIssued))
    .paginate(page=page, per_page=per_page, error_out=False)
)


    return render_template(
        "pharmacy/pharmacyPrescriptions.html",
        prescriptions=prescriptions
    )





# VIEW PRESCRIPTION BY ID

@pharmacy_bp.route("/pharmacy/prescription/<int:prescription_id>")
@login_required
def pharmacy_prescriptionView(prescription_id):
    # Load prescription
    prescription = Prescription.query.get_or_404(prescription_id)

    # Security check: pharmacist only
    if current_user.role != "PHARMACIST" or prescription.patient.pharmacyID != current_user.centerID:

        flash("Unauthorized access.", "danger")
        return redirect(url_for("pharmacy.pharmacy_prescriptions"))

    # Log this view
    log = AuditLog(
        userID=current_user.id,
        action=f"Viewed prescription {prescription.prescriptionID}",
        entity=f"Prescription:{prescription.prescriptionID}",
        timestamp=datetime.now(timezone.utc),
        initiated_by=current_user.id  # optional for easier reporting
    )
    db.session.add(log)
    db.session.commit()

    return render_template(
        "pharmacy/pharmacyPrescriptionView.html",
        prescription=prescription
    )



#DISPENSE MEDICATIONS
@pharmacy_bp.route('/pharmacy/dispense/<int:prescription_id>', methods=['POST'])
@login_required
def dispense_prescription(prescription_id):

    prescription = Prescription.query.get_or_404(prescription_id)

    # 🔐 security
    if current_user.role != "PHARMACIST":
        flash("Unauthorized action.", "danger")
        return redirect(url_for("pharmacy.pharmacy_prescriptions"))

    if prescription.patient.pharmacyID != current_user.centerID:
        flash("You cannot access this prescription.", "danger")
        return redirect(url_for("pharmacy.pharmacy_prescriptions"))

    # status check
    if prescription.status == "Dispensed":
        flash("Already fully dispensed.", "warning")
        return redirect(url_for("pharmacy.pharmacy_prescriptions"))

    action = request.form.get("action")
    selected_ids = request.form.getlist("dispense_ids")

    updated = False

    # --- DISPENSE ALL ---
    if action == "all":
        for detail in prescription.prescriptiondetails:
            if not detail.isDispensed:
                detail.isDispensed = True
                db.session.add(detail)
                updated = True

    # --- DISPENSE SELECTED ---
    elif action == "selected":
        for detail in prescription.prescriptiondetails:
            if str(detail.id) in selected_ids and not detail.isDispensed:
                detail.isDispensed = True
                db.session.add(detail)
                updated = True

    if not updated:
        flash("No medications selected.", "warning")
        return redirect(url_for("pharmacy.pharmacy_prescriptionView", prescription_id=prescription_id))

    # --- UPDATE STATUS ---
    all_done = all(d.isDispensed for d in prescription.prescriptiondetails)

    previous_status = prescription.status

    if all_done:
        prescription.status = "Dispensed"
    else:
        prescription.status = "PartiallyFilled"

    prescription.dispensed_by = current_user.id
    prescription.dispensed_at = datetime.now(timezone.utc)

    db.session.add(prescription)

    # --- AUDIT LOG ---
    log = AuditLog(
        userID=current_user.id,
        action=f"Dispensed prescription {prescription.prescriptionID} "
               f"({previous_status} → {prescription.status})",
        entity=f"Prescription:{prescription.prescriptionID}",
        timestamp=datetime.now(timezone.utc),
        initiated_by=current_user.id
    )
    db.session.add(log)

    db.session.commit()

    flash("Dispensing updated.", "success")
    return redirect(url_for("pharmacy.pharmacy_prescriptionView", prescription_id=prescription_id))
