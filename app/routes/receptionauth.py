from flask import Blueprint, render_template, url_for, request, redirect, flash
from flask_login import login_required, current_user
from app.services.userService import generate_display_id
from app.models.user import User
from app.models.patient import Patient
from datetime import date, timedelta
from app.models.appointment import Appointment
#from app.models.doctor import Doctor
from app.extensions import db
from sqlalchemy.exc import IntegrityError
from app.models.auditLog import AuditLog
from datetime import datetime, timezone


reception_bp = Blueprint("reception", __name__, url_prefix="/reception")

# RECEPTION DASH
@reception_bp.route("/reception_dash")
@login_required
def reception_dash():
    center_id = current_user.centerID
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Query today's appointments in this center
    appointments_today = Appointment.query.join(Patient).join(User).filter(
        User.centerID == center_id,
        Appointment.appointmentDateTime >= today,
        Appointment.appointmentDateTime < tomorrow
    ).order_by(Appointment.appointmentDateTime.asc()).limit(10).all()

    return render_template(
        "receptionist/receptionDash.html",
        appointments=appointments_today,
        recent_appointments=len(appointments_today)
    )


# RECEPTION LIST ALL PATIENTS
@reception_bp.route("/reception_patients")
@login_required
def reception_patients():
    center_id = current_user.centerID
    page = request.args.get("page", 1, type=int)
    per_page = 10


    patients_in_center = (
        Patient.query
        .join(User)
        .filter(User.centerID == center_id)
        .order_by(User.lastname.asc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    
    return render_template(
        "receptionist/receptionPatients.html",
        patients=patients_in_center
    )


# VIEW PATIENTS BY ID
# VIEW USERS BY ID
@reception_bp.route("/reception_patientView/<int:patientID>")
@login_required
def reception_patientView(patientID):

    patient = Patient.query.get_or_404(patientID)

    # Get the linked User object
    patient_user = patient.user   # relationship

    # Get last 10 audit logs related to this patient
    audit_logs = AuditLog.query.filter_by(
        userID=patient_user.id    # UUID FK
    ).order_by(
        AuditLog.timestamp.desc()
    ).limit(10).all()

    # Log the view action
    audit_log = AuditLog(
        userID=current_user.id,   # UUID of actor
        action="VIEW PATIENT PROFILE",
        entity=f"PATIENT: {patient_user.userID}",  # readable ID (PAT001)
        timestamp=datetime.now(timezone.utc),
        initiated_by=current_user.userID
    )

    db.session.add(audit_log)
    db.session.commit()

    return render_template(
        "receptionist/receptionPatientView.html",
        patient=patient,
        audit_logs=audit_logs
    )


# VIEW APPOINTMENT BY ID
@reception_bp.route("/reception_appointmentView/<int:appointmentID>")
@login_required
def reception_appointmentView(appointmentID):

    # Fetch appointment
    appointment = Appointment.query.get_or_404(appointmentID)

    # Get patient from relationship
    patient = appointment.patient  # ✅ Corrected

    # Fetch last 10 audit logs for this patient
    audit_logs = AuditLog.query.filter_by(
        userID=patient.user.userID  # FK points to userID in AuditLog
    ).order_by(
        AuditLog.timestamp.desc()
    ).limit(10).all()

    # Create audit log entry for this view
    try:
        audit_log = AuditLog(
            userID=current_user.userID,   # Actor performing the action
            action="VIEWED APPOINTMENT",
            entity=f"AppointmentID: {appointment.appointmentID} for patient {patient.user.firstname} {patient.user.lastname}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Audit logging failed:", e)

    return render_template(
        "receptionist/receptionAppointmentView.html",
        appointment=appointment,
        patient=patient,
        audit_logs=audit_logs
    )



# EDIT APPOINTMENT DETAILS
@reception_bp.route("/reception_editAppointment/<int:appointmentID>", methods=["GET", "POST"])
@login_required
def reception_editAppointment(appointmentID):
    # Get the appointment
    appointment = Appointment.query.get_or_404(appointmentID)

    # Get the patient related to this appointment
    patient = appointment.patient  # Fetch the patient via the relationship

    # Get the doctors available in the same center
    doctors = User.query.filter_by(role="DOCTOR", isActive=True).all()

    if request.method == "POST":
        new_doctor_id = request.form.get("doctor_id")
        new_date = request.form.get("appDate")
        new_notes = request.form.get("appNotes")
        new_status = request.form.get("status")
        new_cancellation_reason = request.form.get("cancellation_reason") if new_status == "CANCELLED" else None

        changes = []

        # Doctor change
        doctor = User.query.get(new_doctor_id)  # Fetch the doctor by ID
        if not doctor or doctor.role != "DOCTOR" or not doctor.isActive:
            flash("Selected doctor is invalid or inactive.", "danger")
            return redirect(request.referrer)

        if new_doctor_id != appointment.doctorID:
            changes.append(f"Doctor: {appointment.doctorID} → {new_doctor_id}")
            appointment.doctorID = new_doctor_id

        # Date change
        if new_date:
            try:
                new_date_obj = datetime.strptime(new_date, "%Y-%m-%d").date()
                if new_date_obj != appointment.appointmentDateTime:
                    changes.append(f"Date: {appointment.appointmentDateTime} → {new_date_obj}")
                    appointment.appointmentDateTime = new_date_obj
            except ValueError:
                flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
                return redirect(request.referrer)

        # Notes change
        if new_notes != appointment.appointmentNotes:
            changes.append("Notes updated")
            appointment.appointmentNotes = new_notes

        # Status change
        if new_status != appointment.status:
            changes.append(f"Status: {appointment.status} → {new_status}")
            appointment.status = new_status
            # Update cancellation reason if status is CANCELLED
            appointment.cancellation_reason = new_cancellation_reason
        elif new_status == "CANCELLED" and new_cancellation_reason != appointment.cancellation_reason:
            changes.append("Cancellation reason updated")
            appointment.cancellation_reason = new_cancellation_reason

        if changes:
            # Updated at timestamp will be set automatically if using `onupdate`
            appointment.updated_at = datetime.now(timezone.utc)

            # Create an audit log entry
            audit_log = AuditLog(
                userID=current_user.id,  # UUID
                action="APPOINTMENT DETAILS CHANGED",
                entity=f"Appointment {appointment.appointmentID}",
                timestamp=datetime.now(timezone.utc),
                initiated_by=current_user.userID
            )
            db.session.add(audit_log)
            db.session.commit()

        return redirect(url_for(
            "reception.reception_patientView",  # Return to the patient's view page
            patientID=patient.patientID
        ))

    return render_template(
        "receptionist/editAppointment.html",
        appointment=appointment,
        patient=patient,
        doctors=doctors,
        min_date=datetime.today().strftime("%Y-%m-%d")
    )


# RECEPTION LIST ALL APPOINTMENTS


@reception_bp.route("/reception_appointments")
@login_required
def reception_appointments():
    center_id = current_user.centerID
    page = request.args.get("page", 1, type=int)
    per_page = 10
 
    # Fetch all appointments in this center, earliest first
    #appointments = (Appointment.query.filter_by(centerID=center_id).order_by(Appointment.appointmentDateTime.desc()).paginate(page=page, per_page=per_page, error_out=False))

    appointments = Appointment.query.filter_by(centerID=center_id) \
    .order_by(Appointment.appointmentDateTime.desc()) \
    .paginate(page=page, per_page=per_page, error_out=False)

    # --- Audit Log ---
    try:
        audit_log = AuditLog(
            userID=current_user.userID,
            action="VIEWED APPOINTMENTS LIST",
            entity=f"All appointments for centerID: {center_id}",
            timestamp=datetime.now(timezone.utc),
            initiated_by=current_user.userID
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Audit logging failed:", e)

    return render_template(
        "receptionist/receptionAppointments.html",
        appointments=appointments
    )






# RECEPTION BOOK APPOINTMENT
@reception_bp.route("/book_appointment/<int:patientID>", methods=["GET", "POST"])
@login_required
def book_appointment(patientID):
    # Fetch the patient
    patient = Patient.query.get_or_404(patientID)

    # Fetch doctors in the same center
    doctors = User.query.filter(
        User.role == "DOCTOR",
        User.centerID == current_user.centerID,
        User.isActive == True
    ).all()

    if request.method == "POST":
        # Get form values
        doctor_id = request.form.get("doctor_id")
        app_date_str = request.form.get("appDate")
        notes = request.form.get("appNotes", "")

        # Debugging print statements
        print(f"doctor_id: {doctor_id}")  # Debug: print doctor_id
        print(f"app_date_str: {app_date_str}")  # Debug: print raw date string
        print(f"appointmentDateTime: {app_date_str}")  # Debug: print final appointment date (string)
        print(f"patientID: {patient.patientID}")  # Debug: print patientID
        print(f"centerID: {current_user.centerID}")  # Debug: print current user's centerID

        # Validate doctor selection
        if not doctor_id:
            flash("Please select a doctor.", "danger")
            return redirect(request.referrer)

        # Ensure the doctor exists in the same center and is active
        doctor = User.query.filter_by(id=doctor_id, role="DOCTOR", centerID=current_user.centerID, isActive=True).first()
        if not doctor:
            flash("Doctor not found or not available in your center.", "danger")
            return redirect(request.referrer)

        # Validate appointment date
        try:
            app_date_obj = date.fromisoformat(app_date_str)
        except (ValueError, TypeError):
            flash("Invalid date format.", "danger")
            return redirect(request.referrer)

        if app_date_obj < date.today():
            flash("You cannot book an appointment for a past date.", "danger")
            return redirect(request.referrer)

        # Create appointment with default status "SCHEDULED"
        appointment = Appointment(
            patientID=patient.patientID,
            doctorID=doctor_id,  # doctor_id matches the doctor ID selected from form
            centerID=current_user.centerID,
            appointmentDateTime=app_date_obj,
            appointmentNotes=notes,
            status="SCHEDULED"
        )

        try:
            db.session.add(appointment)
            db.session.commit()

            # Create audit log
            audit_log = AuditLog(
                userID=current_user.id,
                action="BOOKED NEW APPOINTMENT",
                entity=f"Appointment for {patient.user.firstname} {patient.user.lastname}",
                timestamp=datetime.now(timezone.utc),
                initiated_by=current_user.userID
            )
            db.session.add(audit_log)
            db.session.commit()

            flash("Appointment booked successfully.", "success")
            return redirect(url_for("reception.reception_patientView", patientID=patient.patientID))

        except IntegrityError as e:
            db.session.rollback()
            print(f"IntegrityError: {e}")  # Debugging purpose
            flash("Failed to book appointment. Please check your inputs.", "danger")
            return redirect(request.referrer)

    min_date = date.today().isoformat()

    return render_template(
        "receptionist/bookAppointment.html",
        patient=patient,
        doctors=doctors,
        min_date=min_date
    )

