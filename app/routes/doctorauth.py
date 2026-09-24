from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.services.userService import generate_display_id
from app.models.user import User
from datetime import date, timezone, datetime, timedelta
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.extensions import db
from app.models.prescription import Prescription
from app.models.diagnosis import Diagnosis
from app.models.auditLog import AuditLog
from app.models.prescriptionDetail import PrescriptionDetails

from app.models.diagnosis import DiagnosisSeverity

doctor_bp = Blueprint("doctor", __name__, url_prefix="/doctor")

# DOCTOR DASH
@doctor_bp.route("/doctor_dash")
@login_required
def doctor_dash():
    if current_user.role != "DOCTOR":
        flash("Access denied.", "danger")
        return redirect("/")

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    week_start = today_start - timedelta(days=today_start.weekday())
    week_end = week_start + timedelta(days=7)

    recent_appointments = Appointment.query.filter_by(
        doctorID=current_user.id
    ).filter(
        Appointment.appointmentDateTime >= today_start,
        Appointment.appointmentDateTime < today_end
    ).count()

    week_appointments = Appointment.query.filter_by(
        doctorID=current_user.id
    ).filter(
        Appointment.appointmentDateTime >= week_start,
        Appointment.appointmentDateTime < week_end
    ).count()

    appointments = Appointment.query.filter_by(
        doctorID=current_user.id
    ).order_by(Appointment.appointmentDateTime.asc()).all()

    return render_template(
        "doctor/doctorDash.html",
        recent_appointments=recent_appointments,
        week_appointments=week_appointments,
        appointments=appointments
    )










# SHOW ALL PATIENTS
@doctor_bp.route("/doctor_patients")
@login_required
def doctor_patients():

    if current_user.role != "DOCTOR":
        flash("Access denied.", "danger")
        return redirect("/")

    center_id = current_user.centerID
    page = request.args.get("page", 1, type=int)
    per_page = 10


    patients= (
        Patient.query
        .join(User)
        .filter(User.centerID == center_id)
        .order_by(User.lastname.asc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    # Audit log
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED PATIENT LIST",
            entity=f"All patients in CenterID: {center_id}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except:
        db.session.rollback()

    return render_template(
        "doctor/searchPatient.html",
        patients=patients
    )



# CREATE DIAGNOSIS
@doctor_bp.route("/create_diagnosis/<int:appointmentID>", methods=["GET", "POST"])
@login_required
def create_diagnosis(appointmentID):
    # Fetch the appointment and patient
    appointment = Appointment.query.get_or_404(appointmentID)
    patient = appointment.patient

    # Debugging: Print the request method and form data
    if request.method == "POST":
        print("Form data received:", request.form)  # Log form data
        summary = request.form.get("summary")
        notes = request.form.get("notes", "")
        severity = request.form.get("severity")

        print(f"summary: '{summary}'")
        print(f"notes: '{notes}'")
        print(f"severity: '{severity}'")

        # Validate required fields
        if not summary or not severity:
            flash("Please fill in all required fields.", "danger")
            return redirect(request.referrer)

        # Create the Diagnosis and associate it with the appointment
        diagnosis = Diagnosis(
            patientID=patient.patientID,
            doctorID=current_user.id,
            diagnosisSummary=summary,
            diagnosisDetails=notes,
            severity=severity,
            appointmentID=appointment.appointmentID  # Set the appointment ID
        )

        try:
            # Commit the diagnosis
            db.session.add(diagnosis)
            db.session.commit()

            # Audit log
            audit_log = AuditLog(
                userID=current_user.id,
                action="CREATED DIAGNOSIS",
                entity=f"DiagnosisID: {diagnosis.diagnosisID} for {patient.user.firstname} {patient.user.lastname}",
                timestamp=datetime.now(timezone.utc),
                initiated_by=current_user.id
            )
            db.session.add(audit_log)
            db.session.commit()

            flash("Diagnosis created successfully.", "success")
            return redirect(url_for("doctor.view_diagnosis", diagnosisID=diagnosis.diagnosisID))

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to create diagnosis. Error: {str(e)}", "danger")
            return redirect(request.referrer)

    return render_template(
        "doctor/createDiagnosis.html",
        appointment=appointment
    )




# EDIT DIAGNOSIS

@doctor_bp.route("/edit_diagnosis/<int:diagnosisID>", methods=["GET", "POST"])
@login_required
def edit_diagnosis(diagnosisID):
    # Fetch the diagnosis record or return a 404 if not found
    diagnosis = Diagnosis.query.get_or_404(diagnosisID)
    patient = diagnosis.patient

    # Ensure the 'created_at' field is timezone-aware
    if diagnosis.created_at.tzinfo is None:
        diagnosis.created_at = diagnosis.created_at.replace(tzinfo=timezone.utc)

    # Restrict editing if the diagnosis was created more than 24 hours ago
    if datetime.now(timezone.utc) - diagnosis.created_at > timedelta(hours=24):
        flash("You cannot edit this diagnosis after 24 hours.", "danger")
        return redirect(url_for("doctor.view_diagnosis", diagnosisID=diagnosisID))

    if request.method == "POST":
        # Storing the old values for audit log
        old_summary = diagnosis.diagnosisSummary
        old_details = diagnosis.diagnosisDetails
        old_severity = diagnosis.severity

        # Get the new values from the form
        diagnosis.diagnosisSummary = request.form.get("diagnosisSummary")
        diagnosis.diagnosisDetails = request.form.get("diagnosisDetails", "")
        diagnosis.severity = request.form.get("severity")

        # Validate the severity value (ensure it's one of the defined enum values)
        if diagnosis.severity not in [e.value for e in DiagnosisSeverity]:
            flash("Invalid severity value.", "danger")
            return redirect(request.referrer)

        try:
            # Add the diagnosis changes and commit the transaction
            db.session.commit()

            # Create an audit log entry for the diagnosis update
            audit_log = AuditLog(
                userID=current_user.id,
                action="EDITED DIAGNOSIS",
                entity=f"DiagnosisID: {diagnosis.diagnosisID}, "
                       f"Old: [{old_summary}, {old_details}, {old_severity}], "
                       f"New: [{diagnosis.diagnosisSummary}, {diagnosis.diagnosisDetails}, {diagnosis.severity}]",
                timestamp=datetime.now(timezone.utc),
                initiated_by=current_user.id
            )
            db.session.add(audit_log)
            db.session.commit()  # Commit audit log

            flash("Diagnosis updated successfully.", "success")
            return redirect(url_for("doctor.view_diagnosis", diagnosisID=diagnosisID))

        except Exception as e:
            db.session.rollback()  # Rollback on any error to keep data consistent
            flash(f"Failed to update diagnosis. Error: {str(e)}", "danger")
            return redirect(request.referrer)

    # If GET request, render the edit form with current diagnosis data
    return render_template(
        "doctor/editDiagnosis.html",  # Adjust the template path if necessary
        diagnosis=diagnosis,
        patient=patient
    )





# VIEW DIAGNOSIS
@doctor_bp.route("/view_diagnosis/<int:diagnosisID>")
@login_required
def view_diagnosis(diagnosisID):
    diagnosis = Diagnosis.query.get_or_404(diagnosisID)
    patient = diagnosis.patient

    # Audit log
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED DIAGNOSIS",
            entity=f"DiagnosisID: {diagnosis.diagnosisID} for {patient.user.firstname} {patient.user.lastname}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except:
        db.session.rollback()

    return render_template(
        "doctor/doctorViewDiagnosis.html",
        diagnosis=diagnosis,
        patient=patient
    )


# SHOW ALL DIAGNOSIS
# LIST DIAGNOSES
#@doctor_bp.route("/diagnoses", defaults={"patientID": None})
#@doctor_bp.route("/diagnoses/<int:patientID>")
#@login_required
#def diagnosis_list(patientID):
#    search_query = request.args.get("q", "").strip()

    # Base query
#    diagnoses = Diagnosis.query.join(Patient).order_by(Diagnosis.diagnosisDate.desc())

    # Filter by patientID if provided
#    if patientID:
#        diagnoses = diagnoses.filter(Patient.patientID == patientID)

    # Search filter
#    if search_query:
#        diagnoses = diagnoses.filter(
#            (Patient.user.has(firstname=search_query)) |
#            (Patient.user.has(lastname=search_query)) |
#            (Diagnosis.diagnosisSummary.ilike(f"%{search_query}%"))
#        )

#    diagnoses = diagnoses.all()

    # --- Audit Log ---
#    try:
#        audit_log = AuditLog(
#            userID=current_user.userID,
#            action="VIEWED DIAGNOSIS LIST",
#            entity=f"PatientID: {patientID or 'All'} | Search: {search_query or 'None'}",
#            timestamp=datetime.now(timezone.utc),
#            initiated_by=current_user.userID
#        )
#        db.session.add(audit_log)
#        db.session.commit()
#    except:
#        db.session.rollback()

#    return render_template(
#        "doctor/searchDiagnosis.html",
#        diagnoses=diagnoses,
#        search_query=search_query,
#        patientID=patientID
#    )

# LIST DIAGNOSES
@doctor_bp.route("/diagnoses", defaults={"patientID": None})
@doctor_bp.route("/diagnoses/<int:patientID>")
@login_required
def diagnosis_list(patientID):
    search_query = request.args.get("q", "").strip()
    center_id = current_user.centerID
    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Base diagnoses query
    diagnoses_query = Diagnosis.query.join(Patient).join(User).filter(User.centerID == center_id).order_by(Diagnosis.diagnosisDate.desc())

    # Filter by patientID if provided
    if patientID:
        diagnoses_query = diagnoses_query.filter(Patient.patientID == patientID)

    # Search filter
    if search_query:
        diagnoses_query = diagnoses_query.filter(
            (Patient.user.has(firstname=search_query)) |
            (Patient.user.has(lastname=search_query)) |
            (Diagnosis.diagnosisSummary.ilike(f"%{search_query}%"))
        )

    # Apply pagination instead of .all()
    diagnoses = diagnoses_query.paginate(page=page, per_page=per_page, error_out=False)

    # --- Audit Log ---
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED DIAGNOSIS LIST",
            entity=f"PatientID: {patientID or 'All'} | Search: {search_query or 'None'}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except:
        db.session.rollback()

    return render_template(
        "doctor/searchDiagnosis.html",
        diagnoses=diagnoses,       # now a Pagination object
        search_query=search_query,
        patientID=patientID
    )






# CREATE PRESCRIPTION

@doctor_bp.route("/create_prescription/<int:appointmentID>", methods=["GET", "POST"])
@login_required
def create_prescription(appointmentID):
    # Fetch the appointment and patient
    appointment = Appointment.query.get_or_404(appointmentID)
    patient = appointment.patient

    # Ensure there's a diagnosis linked to the appointment
    diagnosis = appointment.diagnosis
    if not diagnosis:
        flash("No diagnosis found for this appointment. Prescription cannot be created.", "danger")
        return redirect(url_for('doctor.doctor_patient_view', patientID=patient.patientID))

    # Check if a prescription already exists for the appointment
    prescription = Prescription.query.filter_by(appointmentID=appointment.appointmentID).first()
    print(f"Prescription exists: {prescription}")

    if request.method == "POST":
        # Fetch form data for medicines
        medicines = request.form.getlist("medicine_name[]")
        dosages_amount = request.form.getlist("dosage[]")
        frequencies = request.form.getlist("frequency[]")
        durations = request.form.getlist("duration[]")
        instructions = request.form.getlist("instructions[]")

        # Debugging: Log the form data to check if it's coming correctly
        print(f"Medicines: {medicines}")
        print(f"Dosage Amount: {dosages_amount}")
        print(f"Frequencies: {frequencies}")
        print(f"Durations: {durations}")
        print(f"Instructions: {instructions}")

        # If no medications were provided, show an error
        if not medicines or not all(medicines):  
            flash("Please add at least one medication.", "danger")
            return redirect(request.referrer)

        # Create a new prescription if one does not already exist
        if not prescription:
            prescription = Prescription(
                patientID=patient.patientID,
                doctorID=current_user.id,
                diagnosisID=diagnosis.diagnosisID,
                dateIssued=datetime.now(timezone.utc),
                appointmentID=appointment.appointmentID
            )
            db.session.add(prescription)
            try:
                db.session.commit()  # Commit to create the prescription
                print(f"Prescription created with ID {prescription.prescriptionID}")
            except Exception as e:
                db.session.rollback()
                flash(f"Failed to create prescription. Error: {e}", "danger")
                return redirect(request.referrer)

        # Add medications to the prescription details
        for i in range(len(medicines)):
            if medicines[i] and dosages_amount[i]:  # Ensure that both medicine and dosage are provided
                med = PrescriptionDetails(
                    prescriptionID=prescription.prescriptionID,
                    medicineName=medicines[i],
                    dosage=dosages_amount[i],
                    frequency=frequencies[i],
                    duration=durations[i],
                    instructions=instructions[i]
                    #quantity=1
                )
                db.session.add(med)

        # Commit all the medications to the prescription
        try:
            db.session.commit()
            flash("Prescription created successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to add medications to prescription. Error: {e}", "danger")
            return redirect(request.referrer)

        # Redirect to the prescription view page
        return redirect(url_for("doctor.view_prescription", prescriptionID=prescription.prescriptionID))

    # If method is GET, just render the form
    return render_template("doctor/createPrescription.html", appointment=appointment, prescription=prescription)










# EDIT PRESCRIPTION
@doctor_bp.route("/edit_prescription/<int:prescriptionID>", methods=["GET", "POST"])
@login_required
def edit_prescription(prescriptionID):

    prescription = Prescription.query.get_or_404(prescriptionID)
    patient = prescription.patient

    # Ensure timezone aware
    if prescription.dateIssued.tzinfo is None:
        prescription.dateIssued = prescription.dateIssued.replace(tzinfo=timezone.utc)

    # 24 hour lock
    if datetime.now(timezone.utc) - prescription.dateIssued > timedelta(hours=24):
        flash("You cannot edit this prescription after 24 hours.", "danger")
        return redirect(url_for("doctor.view_prescription", prescriptionID=prescriptionID))

    if request.method == "POST":

        medicines = request.form.getlist("medicine_name[]")
        dosages = request.form.getlist("dosage[]")
        frequencies = request.form.getlist("frequency[]")
        durations = request.form.getlist("duration[]")
        instructions_list = request.form.getlist("instructions[]")

        if not medicines:
            flash("You must have at least one medication.", "danger")
            return redirect(request.referrer)

        if not (len(medicines) == len(dosages) == len(frequencies) == len(durations) == len(instructions_list)):
            flash("Medication fields mismatch.", "danger")
            return redirect(request.referrer)

        try:
          
            old_meds = PrescriptionDetails.query.filter_by(
                prescriptionID=prescription.prescriptionID
            ).all()

            old_list = [
                f"{m.medicineName}|{m.dosage}|{m.frequency}|{m.duration}|{m.instructions}"
                for m in old_meds
            ]

           
            PrescriptionDetails.query.filter_by(
                prescriptionID=prescription.prescriptionID
            ).delete(synchronize_session=False)

          
            new_list = []

            for i in range(len(medicines)):
                med = PrescriptionDetails(
                    prescriptionID=prescription.prescriptionID,
                    medicineName=medicines[i],
                    dosage=dosages[i],
                    frequency=frequencies[i],
                    duration=durations[i],
                    instructions=instructions_list[i],
                )
                db.session.add(med)

                new_list.append(
                    f"{medicines[i]}|{dosages[i]}|{frequencies[i]}|{durations[i]}|{instructions_list[i]}"
                )

            db.session.commit()  
          
            audit_log = AuditLog(
                userID=current_user.id,
                action="EDITED PRESCRIPTION",
                entity=f"PrescriptionID: {prescription.prescriptionID}, "
                       f"Old: {old_list}, "
                       f"New: {new_list}",
                timestamp=datetime.now(timezone.utc),
                initiated_by=current_user.id
            )
            db.session.add(audit_log)
            db.session.commit()

            flash("Prescription updated successfully.", "success")
            return redirect(url_for("doctor.view_prescription", prescriptionID=prescriptionID))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating prescription: {e}", "danger")
            return redirect(request.referrer)

    return render_template(
        "doctor/editPrescription.html",
        prescription=prescription,
        patient=patient
    )










#VIEW PRESCRIPTION
@doctor_bp.route("/prescription/<int:prescriptionID>")
@login_required
def view_prescription(prescriptionID):
    prescription = Prescription.query.get_or_404(prescriptionID)
    patient = prescription.patient

    # Audit log
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED PRESCRIPTION",
            entity=f"PrescriptionID: {prescription.prescriptionID} for {patient.user.firstname} {patient.user.lastname}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except:
        db.session.rollback()

    return render_template(
        "doctor/viewPrescription.html",
        prescription=prescription,
        patient=patient
    )



#LIST PRESCRIPTION
# LIST PRESCRIPTIONS
@doctor_bp.route("/prescriptions", defaults={"patientID": None})
@doctor_bp.route("/prescriptions/<int:patientID>")
@login_required
def doctor_prescriptions(patientID):
    search_query = request.args.get("q", "").strip()
    center_id = current_user.centerID
    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Filter by patientID if provided
    if patientID:
        diagnoses_query = diagnoses_query.filter(Patient.patientID == patientID)

    search_query = request.args.get("q", "").strip()

    # Base query
    prescriptions = Prescription.query.join(Patient).filter(User.centerID == center_id).order_by(Prescription.dateIssued.desc())

    # Filter by patientID if provided
    if patientID:
        prescriptions = prescriptions.filter(Patient.patientID == patientID)

    # Search filter
    if search_query:
        prescriptions = prescriptions.filter(
            (Patient.user.has(firstname=search_query)) |
            (Patient.user.has(lastname=search_query)) |
            (Prescription.prescriptiondetails.any(
                PrescriptionDetails.medicineName.ilike(f"%{search_query}%")
            ))
        )

    prescriptions = prescriptions.paginate(page=page, per_page=per_page, error_out=False)

    # --- Audit Log ---
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED PRESCRIPTION LIST",
            entity=f"PatientID: {patientID or 'All'} | Search: {search_query or 'None'}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except:
        db.session.rollback()

    return render_template(
        "doctor/searchPrescriptions.html",
        prescriptions=prescriptions,
        search_query=search_query,
        patientID=patientID
    )













# DOCTOR PATIENT VIEW
@doctor_bp.route("/patient/<int:patientID>", methods=["GET", "POST"])
@login_required
def doctor_patient_view(patientID):
    # Fetch patient or 404
    patient = Patient.query.get_or_404(patientID)

    # Last and upcoming visits
    last_visit_obj = Appointment.query.filter_by(patientID=patient.patientID)\
        .filter(Appointment.appointmentDateTime <= datetime.now(timezone.utc).date())\
        .order_by(Appointment.appointmentDateTime.desc()).first()

    next_visit_obj = Appointment.query.filter_by(patientID=patient.patientID)\
        .filter(Appointment.appointmentDateTime >= datetime.now(timezone.utc).date())\
        .order_by(Appointment.appointmentDateTime.asc()).first()

    last_visit = last_visit_obj.appointmentDateTime if last_visit_obj else None
    next_visit = next_visit_obj.appointmentDateTime if next_visit_obj else None

    # Recent appointments (last 5)
    appointments = Appointment.query.filter_by(patientID=patient.patientID)\
        .order_by(Appointment.appointmentDateTime.desc()).limit(5).all()

    # Audit log for viewing patient profile
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED PATIENT PROFILE",
            entity=f"PatientID: {patient.patientID} - {patient.user.firstname} {patient.user.lastname}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return render_template(
        "doctor/viewPatientProfile.html",
        patient=patient,
        last_visit=last_visit,
        next_visit=next_visit,
        appointments=appointments
    )


