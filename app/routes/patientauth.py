from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from app.extensions import db
from app.models.user import User
from app.models.patient import Patient
from app.models.center import Center
from flask_login import current_user
from flask_login import login_required
from flask import abort
from app.services.userService import generate_display_id
from datetime import date, datetime, timezone
from app.models.appointment import Appointment
from app.models.diagnosis import Diagnosis
from app.models.prescription import Prescription
from app.models.auditLog import AuditLog

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")
 
#PATIENT DASH
@patient_bp.route("/patient_dash")
@login_required
def patient_dash():
    today = date.today()

    # Ensure logged-in user is a patient
    if not current_user.patient:
        flash("Patient profile not found.", "danger")
        return redirect(url_for("auth.login"))

    # Fetch today's appointments for this patient
    appointments_today = Appointment.query.filter(
        Appointment.patientID == current_user.patient.patientID,
        Appointment.appointmentDateTime == today
    ).order_by(Appointment.appointmentDateTime).limit(10).all()

    # Count for stats
    appointment_count = len(appointments_today)

    return render_template(
        "patient/patientDash.html",
        appointments=appointments_today,
        appointments_today=appointment_count
    )



# PATIENT VIEW ACCOUNT

@patient_bp.route("/patient_account")
@login_required
def patient_account():
    # Ensure the user is a patient
    if current_user.role != "PATIENT" or not current_user.patient:
        flash("Access denied or patient profile not found.", "danger")
        return redirect(url_for("auth.login"))

    patient = current_user.patient

    # Optional: preload hospital and pharmacy if not eager-loaded
    hospital = getattr(patient, "hospital", None)
    pharmacy = getattr(patient, "pharmacy", None)

    # Audit log: patient viewed their profile
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED PROFILE",
            entity=f"Patient profile viewed: {current_user.userID}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return render_template(
        "patient/patientProfile.html",
        patient=patient,
        hospital=hospital,
        pharmacy=pharmacy
    )



#ENFORCE ONBOARDING
@patient_bp.before_request
@login_required
def enforce_profile_completion():

    # Only enforce for patients
    if current_user.role != "PATIENT":
        return

    # Allow these endpoints
    allowed_routes = [
        "patient.complete_profile",
        "auth.logout",
        "static"
    ]

    if request.endpoint in allowed_routes:
        return

    # If no patient record OR profile incomplete → redirect
    if not current_user.patient or not current_user.patient.profile_completed:
        return redirect(url_for("patient.complete_profile"))



# COMPLETE PROFILE
@patient_bp.route("/complete_profile", methods=["GET", "POST"])
@login_required
def complete_profile():
    # Only patients allowed
    if current_user.role != "PATIENT":
        abort(403)

    patient = current_user.patient

    # Redirect if already completed
    if patient and patient.profile_completed:
        return redirect(url_for("patient.patient_dash"))

    # Fetch active hospitals/clinics and pharmacies
    hospitals = Center.query.filter(
        Center.centerType.in_(["Hospital", "Clinic"]),
        Center.isActive == True
    ).order_by(Center.centerName).all()

    pharmacies = Center.query.filter(
        Center.centerType == "Pharmacy",
        Center.isActive == True
    ).order_by(Center.centerName).all()

    if request.method == "POST":
        dob = request.form.get("dob")
        sex = request.form.get("sex")
        hospital_id = request.form.get("center")
        pharmacy_id = request.form.get("pharmacy")
        allergies = request.form.get("allergies")

        # Required fields check
        if not all([dob, sex, hospital_id, pharmacy_id]):
            flash("Please complete all required fields.", "danger")
            return redirect(url_for("patient.complete_profile"))

        try:
            # --- Update Patient ---
            patient.dob = datetime.strptime(dob, "%Y-%m-%d").date()
            patient.sex = sex
            patient.allergies = allergies
            patient.hospitalID = int(hospital_id)
            patient.pharmacyID = int(pharmacy_id)
            patient.profile_completed = True
            patient.updated_at = datetime.now(timezone.utc)

            # --- Update User default center to hospital ---
            current_user.centerID = int(hospital_id)
            current_user.updated_at = datetime.now(timezone.utc)

            # Commit changes
            db.session.commit()

            # --- Audit Logging ---
            audit_log = AuditLog(
                userID=current_user.id,
                action="COMPLETED PROFILE",
                entity=f"Patient {current_user.userID} set hospital {hospital_id} and pharmacy {pharmacy_id}",
                timestamp=datetime.now(timezone.utc),
                initiated_by=current_user.id
            )
            db.session.add(audit_log)
            db.session.commit()

            flash("Profile completed successfully!", "success")
            return redirect(url_for("patient.patient_dash"))

        except Exception as e:
            db.session.rollback()
            flash("An error occurred. Please try again.", "danger")
            print("Profile completion failed:", e)
            return redirect(url_for("patient.complete_profile"))

    return render_template(
        "patient/complete_profile.html",
        hospitals=hospitals,
        pharmacies=pharmacies,
        patient=patient
    )


# PATIENTS APPOINTMENTS
@patient_bp.route("/patient_appointments")
@login_required
def patient_appointments():
    # Ensure the current user is a patient
    if not current_user.patient:
        flash("Patient profile not found.", "danger")
        return redirect(url_for("auth.login"))

   
    page = request.args.get("page", 1, type=int)
    per_page = 10


   
    patient_id = current_user.patient.patientID
    today = datetime.now(timezone.utc)

    appointments = (
        Appointment.query
        .filter(Appointment.patientID == patient_id)
        .order_by(Appointment.appointmentDateTime.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
  

    # Audit logging
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED APPOINTMENT HISTORY",
            entity=f"PatientID: {patient_id} viewed appointment history",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Do not block user if audit fails
        print("Audit log failed for patient appointments view.")

    return render_template(
        "patient/patientAppointments.html",
        appointments=appointments
    )




# PATIENT DIAGNOSIS
@patient_bp.route("/patient_diagnoses")
@login_required
def patient_diagnoses():
    # Ensure the user is a patient
    if not hasattr(current_user, "patient") or current_user.patient is None:
        flash("Patient profile not found.", "danger")
        return redirect(url_for("auth.login"))
    
    page = request.args.get("page", 1, type=int)
    per_page = 10
   
    patient_id = current_user.patient.patientID

    diagnoses = (
        Diagnosis.query
        .filter(Diagnosis.patientID == patient_id)
        .order_by(Diagnosis.diagnosisDate.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Audit logging
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED DIAGNOSIS HISTORY",
            entity=f"Viewed all diagnoses for patient {current_user.patient.user.firstname} {current_user.patient.user.lastname}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception:
        db.session.rollback()  # Fail silently for audit errors

    return render_template(
        "patient/patientDiagnosis.html",  
        diagnoses=diagnoses
    )


# PATIENT PRESCRIPTIONS
@patient_bp.route("/patient_prescriptions")
@login_required
def patient_prescriptions():
    # Ensure the user has a patient profile
    if not getattr(current_user, "patient", None):
        flash("Patient profile not found.", "danger")
        return redirect(url_for("auth.login"))
    
    page = request.args.get("page", 1, type=int)
    per_page = 10
   
    patient_id = current_user.patient.patientID

    prescriptions = (
        Prescription.query
        .filter(Prescription.patientID == patient_id)
        .order_by(Prescription.dateIssued.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Audit log: patient viewed prescriptions
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED PRESCRIPTIONS",
            entity=f"PatientID: {patient_id} viewed all prescriptions",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Optional: you could log to server logs here

    return render_template(
        "patient/patientPrescriptions.html",
        prescriptions=prescriptions
    )


#EDIT ACCOUNT 
@patient_bp.route("/edit_account/<user_id>", methods=["GET", "POST"])
@login_required
def edit_account(user_id):
    # Ensure the logged-in user matches the user_id
    if current_user.userID != user_id:
        flash("Access denied.", "danger")
        return redirect(url_for("patient.patient_account"))

    user = current_user
    patient = user.patient

    if not patient:
        flash("Patient profile not found.", "danger")
        return redirect(url_for("auth.login"))

    # Fetch hospitals and pharmacies for selection
    hospitals = Center.query.filter(Center.centerType.in_(["Hospital", "Clinic"]), Center.isActive==True).all()
    pharmacies = Center.query.filter_by(centerType="Pharmacy", isActive=True).all()

    # Check if patient has upcoming appointments
    today = date.today()
    has_upcoming_appointments = Appointment.query.filter(
        Appointment.patientID == patient.patientID,
        Appointment.appointmentDateTime >= today
    ).count() > 0

    if request.method == "POST":
        new_hospital_id = request.form.get("center")
        new_pharmacy_id = request.form.get("pharmacy")

        changes_made = []

        try:
            # Hospital change allowed only if no upcoming appointments
            if not has_upcoming_appointments and new_hospital_id:
                if str(patient.centerID) != new_hospital_id:
                    old_hospital = patient.center.centerName if patient.center else "N/A"
                    new_hospital = Center.query.get(new_hospital_id).centerName
                    patient.centerID = new_hospital_id
                    changes_made.append(f"Hospital changed from '{old_hospital}' to '{new_hospital}'")

            # Pharmacy can always be changed
            if new_pharmacy_id and str(patient.pharmacyID) != new_pharmacy_id:
                old_pharmacy = patient.pharmacy.centerName if patient.pharmacy else "N/A"
                new_pharmacy = Center.query.get(new_pharmacy_id).centerName
                patient.pharmacyID = new_pharmacy_id
                changes_made.append(f"Pharmacy changed from '{old_pharmacy}' to '{new_pharmacy}'")

            if changes_made:
                # Update updated_at in user model
                user.updated_at = datetime.now(timezone.utc)
                db.session.commit()

                # Audit log
                audit_log = AuditLog(
                    userID=user.userID,
                    action="EDITED ACCOUNT",
                    entity="; ".join(changes_made),
                    timestamp=datetime.now(timezone.utc),
                    initiated_by=user.userID
                )
                db.session.add(audit_log)
                db.session.commit()

                flash("Account updated successfully.", "success")
            else:
                flash("No changes detected.", "info")

            return redirect(url_for("patient.patient_account"))

        except Exception as e:
            db.session.rollback()
            flash("Failed to update account. Please try again.", "warning")
            return redirect(request.referrer)

    return render_template(
        "patient/editAccount.html",
        user=user,
        patient=patient,
        hospitals=hospitals,
        pharmacies=pharmacies,
        has_upcoming_appointments=has_upcoming_appointments
    )

