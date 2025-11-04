import os
import csv
from io import StringIO
from datetime import datetime as DateTime, time as Time, date as Date
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_, and_
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from flask_caching import Cache
from flask_mail import Mail, Message
from celery import Celery
from celery.schedules import crontab

# import your models
from models import db, User, Department, DoctorProfile, PatientProfile, Appointment, Treatment

# ---------------------------
# App & config
# ---------------------------
app = Flask(__name__, template_folder='../frontend', static_folder='../frontend', static_url_path='/static')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'change_this_to_a_real_secret'
# Celery / Redis
app.config['broker_url'] = 'redis://localhost:6379/0'
app.config['result_backend'] = 'redis://localhost:6379/0'
# Cache
app.config['CACHE_TYPE'] = 'RedisCache'
app.config['CACHE_REDIS_HOST'] = 'localhost'
app.config['CACHE_REDIS_PORT'] = 6379
app.config['CACHE_DEFAULT_TIMEOUT'] = 60
# Mail (configure for your provider)
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@example.com'
app.config['MAIL_PASSWORD'] = 'your_password'
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@example.com'

db.init_app(app)
jwt = JWTManager(app)
cache = Cache(app)
mail = Mail(app)
CORS(app)

# ---------------------------
# Celery
# ---------------------------
def make_celery(app):
    celery = Celery(app.import_name, backend=app.config['result_backend'], broker=app.config['broker_url'])
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# Ensure reports directory exists
REPORTS_DIR = os.path.join(app.root_path, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

# ---------------------------
# DB create + default admin
# ---------------------------
first_request = True

@app.before_request
def ensure_db():
    global first_request
    if first_request:
        db.create_all()
        # create default admin if missing
        if not User.query.filter_by(role='admin').first():
            admin = User(
                username='admin@hms.com',
                password=generate_password_hash('admin123'),
                role='admin',
                approve=True,
                blocked=False
            )
            db.session.add(admin)
            db.session.commit()
        os.makedirs(REPORTS_DIR, exist_ok=True)
        first_request = False

# ---------------------------
# Helpers
# ---------------------------
def is_admin_claims(claims):
    return claims.get('role') == 'admin'

def is_doctor_claims(claims):
    return claims.get('role') == 'doctor'

def is_patient_claims(claims):
    return claims.get('role') == 'patient'

# ---------------------------
# Home
# ---------------------------
@app.route('/')
def index():
    return render_template('index.html')

# ---------------------------
# AUTH: register / login
# ---------------------------
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    role = (data.get('role') or '').strip().lower()

    if not username or not password or role not in ('patient', 'doctor'):
        return jsonify({"category": "danger", "message": "username, password and role (patient|doctor) required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"category": "danger", "message": "User already exists"}), 400

    hashed = generate_password_hash(password)
    # patients auto-approved; doctors require admin approval
    approve = True if role == 'patient' else False
    user = User(username=username, password=hashed, role=role, approve=approve, blocked=False)
    db.session.add(user)
    db.session.commit()
    return jsonify({"category": "success", "message": "registered"}), 200 


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"category": "danger", "message": "username & password required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"category": "danger", "message": "Bad username or password"}), 401

    if user.blocked:
        return jsonify({"category": "danger", "message": "Account blocked"}), 401
    if not user.approve:
        return jsonify({"category": "danger", "message": "Account not approved"}), 401

    # check profile completion redirect
    redirect = None
    if user.role == 'patient':
        profile = PatientProfile.query.filter_by(user_id=user.id).first()
        redirect = 'patient_profile' if not profile else 'patient_dashboard'
    elif user.role == 'doctor':
        profile = DoctorProfile.query.filter_by(user_id=user.id).first()
        redirect = 'doctor_profile' if not profile else 'doctor_dashboard'

    token = create_access_token(identity=user.username, additional_claims={"user_id": user.id, "role": user.role, "redirect": redirect})
    return jsonify({"access_token": token}), 200

@app.route('/get-claims', methods=['GET'])
@jwt_required()
def get_claims():
    claims = get_jwt()
    return jsonify({"claims": claims}), 200


@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"category": "danger", "message": "username & password required"}), 400

    user = User.query.filter_by(username=username, role='admin').first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"category": "danger", "message": "Bad username or password"}), 401
    token = create_access_token(identity=user.username, additional_claims={"admin_user_id": user.id, "role": 'admin'})
    return jsonify({"access_token": token}), 200

# ---------------------------
# ADMIN endpoints
# ---------------------------
@app.route('/admin/dashboard', methods=['GET'])
@jwt_required()
def admin_dashboard():
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401

    total_doctors = User.query.filter_by(role='doctor').count()
    total_patients = User.query.filter_by(role='patient').count()
    total_appointments = Appointment.query.count()
    upcoming = Appointment.query.filter(Appointment.date >= DateTime.now().date()).count()
    return jsonify({
        "total_doctors": total_doctors,
        "total_patients": total_patients,
        "total_appointments": total_appointments,
        "upcoming_appointments": upcoming
    }), 200

@app.route('/admin/profile', methods=['GET'])
@jwt_required()
def admin_profile():
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"message": "Admins only", "category": "danger"}), 401

    user_id = claims.get("admin_user_id")
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Admin user not found", "category": "danger"}), 404

    return jsonify({
        "message": f"Welcome, {user.username}",
        "category": "success",
        "username": user.username,
        "role": user.role
    }), 200

# CRUD doctors (admin)
@app.route('/admin/doctors', methods=['GET', 'POST'])
@jwt_required()
def admin_doctors():
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401

    if request.method == 'GET':
        doctors = User.query.filter_by(role='doctor').all()
        return jsonify([{"id": d.id, "username": d.username, "approve": d.approve, "blocked": d.blocked} for d in doctors]), 200

    if request.method == 'POST':
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password', 'changeme123')
        if not username:
            return jsonify({"message": "username required"}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({"message": "already exists"}), 400
        user = User(username=username, password=generate_password_hash(password), role='doctor', approve=True, blocked=False)
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "doctor created", "id": user.id}), 201

@app.route('/admin/doctors/<int:user_id>', methods=['GET','PUT','DELETE'])
@jwt_required()
def admin_doctor_detail(user_id):
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401
    user = User.query.get_or_404(user_id)
    if user.role != 'doctor':
        return jsonify({"message": "User is not a doctor"}), 400
    if request.method == 'GET':
        profile = DoctorProfile.query.filter_by(user_id=user.id).first()
        return jsonify({
            "id": user.id,
            "username": user.username,
            "approve": user.approve,
            "blocked": user.blocked,
            "profile": profile.as_dict() if profile else None
        }), 200
    if request.method == 'PUT':
        data = request.get_json() or {}
        user.approve = data.get('approve', user.approve)
        user.blocked = data.get('blocked', user.blocked)
        db.session.commit()
        return jsonify({"message": "updated"}), 200
    if request.method == 'DELETE':
        # delete doctor user and profile
        prof = DoctorProfile.query.filter_by(user_id=user.id).first()
        if prof:
            db.session.delete(prof)
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "deleted"}), 200

@app.route('/admin/patients', methods=['GET'])
@jwt_required()
def admin_patients():
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401
    patients = User.query.filter_by(role='patient').all()
    return jsonify([{"id": p.id, "username": p.username} for p in patients]), 200

@app.route('/admin/appointments', methods=['GET'])
@jwt_required()
def admin_appointments():
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401
    appts = Appointment.query.order_by(Appointment.date.desc(), Appointment.time.desc()).all()
    result = []
    for a in appts:
        result.append({
            "id": a.id,
            "patient_id": a.patient_id,
            "doctor_id": a.doctor_id,
            "department_id": a.department_id,
            "date": str(a.date),
            "time": str(a.time),
            "status": a.status,
            "remarks": a.remarks
        })
    return jsonify(result), 200

@app.route('/admin/block_user/<int:user_id>', methods=['POST'])
@jwt_required()
def admin_block_user(user_id):
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401
    data = request.get_json() or {}
    action = data.get('action')
    user = User.query.get_or_404(user_id)
    if action == 'block':
        user.blocked = True
    elif action == 'unblock':
        user.blocked = False
    elif action == 'approve':
        user.approve = True
    elif action == 'reject':
        user.approve = False
    else:
        return jsonify({"message": "invalid action"}), 400
    db.session.commit()
    return jsonify({"message": "done"}), 200

# Admin export endpoints
@app.route('/admin/export/<int:professional_id>', methods=['GET'])
@jwt_required()
def export_service_requests(professional_id):
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401
    task = export_professional_service_requests.delay(professional_id)
    return jsonify({"message": f"Export started for professional ID {professional_id}.", "task_id": task.id}), 202

@app.route('/admin/reports/list', methods=['GET'])
@jwt_required()
def list_reports():
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401
    os.makedirs(REPORTS_DIR, exist_ok=True)
    files = [f for f in os.listdir(REPORTS_DIR) if f.endswith('.csv')]
    return jsonify({"downloads": files}), 200

@app.route('/admin/reports/download/<filename>', methods=['GET'])
@jwt_required()
def download_report(filename):
    claims = get_jwt()
    if not is_admin_claims(claims):
        return jsonify({"message": "Admin only"}), 401
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)

# ---------------------------
# DOCTOR endpoints
# ---------------------------
@app.route('/doctor/profile', methods=['GET','POST'])
@jwt_required()
def doctor_profile():
    claims = get_jwt()
    if not is_doctor_claims(claims):
        return jsonify({"message": "Doctor only"}), 401
    user_id = claims['user_id']
    profile = DoctorProfile.query.filter_by(user_id=user_id).first()

    if request.method == 'GET':
        if not profile:
            return jsonify({"message": "no profile"}), 200
        return jsonify(profile.as_dict()), 200

    # POST create/update
    data = request.get_json() or {}
    specialization_id = data.get('specialization_id')
    experience = data.get('experience')
    availability = data.get('availability')  # free-form or JSON string

    if profile:
        profile.specialization_id = specialization_id or profile.specialization_id
        profile.experience = experience or profile.experience
        profile.availability = availability or profile.availability
    else:
        profile = DoctorProfile(user_id=user_id, specialization_id=specialization_id, experience=experience, availability=availability)
        db.session.add(profile)
    db.session.commit()
    return jsonify({"message": "saved"}), 200

@app.route('/doctor/appointments', methods=['GET'])
@jwt_required()
def doctor_appointments():
    claims = get_jwt()
    if not is_doctor_claims(claims):
        return jsonify({"message": "Doctor only"}), 401
    doctor_id = claims['user_id']
    appts = Appointment.query.filter_by(doctor_id=doctor_id).order_by(Appointment.date.asc(), Appointment.time.asc()).all()
    result = []
    for a in appts:
        result.append({
            "id": a.id,
            "patient_id": a.patient_id,
            "date": str(a.date),
            "time": str(a.time),
            "status": a.status,
            "remarks": a.remarks
        })
    return jsonify(result), 200

@app.route('/doctor/appointments/<int:appointment_id>/complete', methods=['POST'])
@jwt_required()
def doctor_complete_appointment(appointment_id):
    claims = get_jwt()
    if not is_doctor_claims(claims):
        return jsonify({"message": "Doctor only"}), 401
    doctor_id = claims['user_id']
    appt = Appointment.query.get_or_404(appointment_id)
    if appt.doctor_id != doctor_id:
        return jsonify({"message": "Not your appointment"}), 401

    data = request.get_json() or {}
    diagnosis = data.get('diagnosis', '')
    prescription = data.get('prescription', '')
    notes = data.get('notes', '')

    appt.status = 'Completed'
    db.session.commit()

    treatment = Treatment(appointment_id=appt.id, diagnosis=diagnosis, prescription=prescription, notes=notes)
    db.session.add(treatment)
    db.session.commit()

    # optional: notify patient by email if patient.username is an email
    try:
        patient_user = User.query.get(appt.patient_id)
        if patient_user and '@' in patient_user.username:
            msg = Message(subject="Your visit summary", recipients=[patient_user.username],
                          body=f"Your appointment on {appt.date} with doctor id {appt.doctor_id} is completed.\nDiagnosis: {diagnosis}\nPrescription: {prescription}")
            mail.send(msg)
    except Exception:
        pass

    return jsonify({"message": "Appointment completed and treatment saved"}), 200

# ---------------------------
# PATIENT endpoints
# ---------------------------
@app.route('/patient/profile', methods=['GET','POST'])
@jwt_required()
def patient_profile():
    claims = get_jwt()
    if not is_patient_claims(claims):
        return jsonify({"message": "Patient only"}), 401
    user_id = claims['user_id']
    profile = PatientProfile.query.filter_by(user_id=user_id).first()
    if request.method == 'GET':
        if not profile:
            return jsonify({"message": "no profile"}), 200
        return jsonify(profile.as_dict()), 200

    data = request.get_json() or {}
    full_name = data.get('full_name')
    age = data.get('age')
    contact = data.get('contact')
    address = data.get('address')

    if profile:
        profile.full_name = full_name or profile.full_name
        profile.age = age or profile.age
        profile.contact = contact or profile.contact
        profile.address = address or profile.address
    else:
        profile = PatientProfile(user_id=user_id, full_name=full_name, age=age, contact=contact, address=address)
        db.session.add(profile)
    db.session.commit()
    return jsonify({"message": "saved"}), 200

@app.route('/patient/doctors', methods=['GET'])
@jwt_required()
def patient_doctors():
    claims = get_jwt()
    if not is_patient_claims(claims):
        return jsonify({"message": "Patient only"}), 401
    # search by specialization_id or q (name)
    specialization = request.args.get('specialization_id', type=int)
    q = request.args.get('q', type=str)
    query = DoctorProfile.query.join(User, DoctorProfile.user_id == User.id).filter(User.approve == True, User.blocked == False)
    if specialization:
        query = query.filter(DoctorProfile.specialization_id == specialization)
    if q:
        query = query.filter(DoctorProfile.user_id.in_(
            [u.id for u in User.query.filter(User.username.ilike(f"%{q}%")).all()]
        ))
    docs = query.all()
    return jsonify([d.as_dict() for d in docs]), 200

@app.route('/patient/appointments/book', methods=['POST'])
@jwt_required()
def patient_book_appointment():
    claims = get_jwt()
    if not is_patient_claims(claims):
        return jsonify({"message": "Patient only"}), 401
    user_id = claims['user_id']
    data = request.get_json() or {}
    doctor_id = data.get('doctor_id')
    dept_id = data.get('department_id')
    date_str = data.get('date')
    time_str = data.get('time')

    if not all([doctor_id, date_str, time_str]):
        return jsonify({"message": "doctor_id, date, time required"}), 400

    try:
        appt_date = Date.fromisoformat(date_str)
        appt_time = Time.fromisoformat(time_str)
    except Exception:
        return jsonify({"message": "date/time must be ISO format (YYYY-MM-DD / HH:MM:SS)"}), 400

    # check doctor exists and approved
    doctor_user = User.query.get(doctor_id)
    if not doctor_user or doctor_user.role != 'doctor' or not doctor_user.approve or doctor_user.blocked:
        return jsonify({"message": "doctor not available"}), 400

    # prevent double booking: same doctor, same date & time
    conflict = Appointment.query.filter_by(doctor_id=doctor_id, date=appt_date, time=appt_time).filter(Appointment.status == 'Booked').first()
    if conflict:
        return jsonify({"message": "Doctor already has an appointment at that slot"}), 409

    appointment = Appointment(patient_id=user_id, doctor_id=doctor_id, department_id=dept_id, date=appt_date, time=appt_time, status='Booked')
    db.session.add(appointment)
    db.session.commit()
    return jsonify({"message": "booked", "appointment_id": appointment.id}), 201
@app.route('/patient/appointments', methods=['GET'])
@jwt_required()
def patient_appointments():
    claims = get_jwt()  # ✅ Must call the function
    if claims.get('role') != 'patient':  # ✅ Ensure only patients can access
        return jsonify({"message": "Patient only"}), 401

    user_id = claims['user_id']  # Extract patient ID from JWT
    appts = Appointment.query.filter_by(patient_id=user_id)\
                             .order_by(Appointment.date.desc(), Appointment.time.desc())\
                             .all()  # ✅ Now appts is defined

    result = []
    for a in appts:
        result.append({
            "id": a.id,
            "doctor_id": a.doctor_id,
            "date": str(a.date),
            "time": str(a.time),
            "status": a.status,
            "remarks": a.remarks
        })
    return jsonify(result), 200


@app.route('/patient/appointments/<int:appointment_id>/cancel', methods=['POST'])
@jwt_required()
def patient_cancel_appointment(appointment_id):
    claims = get_jwt()
    if not is_patient_claims(claims):
        return jsonify({"message": "Patient only"}), 401
    user_id = claims['user_id']
    appt = Appointment.query.get_or_404(appointment_id)
    if appt.patient_id != user_id:
        return jsonify({"message": "Not your appointment"}), 401
    if appt.status != 'Booked':
        return jsonify({"message": "Only booked appointments can be cancelled"}), 400
    appt.status = 'Cancelled'
    db.session.commit()
    return jsonify({"message": "cancelled"}), 200


@app.route('/patient/treatments', methods=['GET'])
@jwt_required()
def patient_treatments():
    claims = get_jwt()
    if not is_patient_claims(claims):
        return jsonify({"message": "Patient only"}), 401
    user_id = claims['user_id']
    treatments = Treatment.query.join(Appointment, Treatment.appointment_id == Appointment.id)\
                                .filter(Appointment.patient_id == user_id).all()
    out = []
    for t in treatments:
        appt = Appointment.query.get(t.appointment_id)
        out.append({
            "treatment_id": t.id,
            "appointment_id": t.appointment_id,
            "appointment_date": str(appt.date) if appt else None,
            "diagnosis": t.diagnosis,
            "prescription": t.prescription,
            "notes": t.notes
        })
    return jsonify(out), 200


@app.route('/patient/export_treatments', methods=['GET'])
@jwt_required()
def patient_export_treatments():
    claims = get_jwt()
    if not is_patient_claims(claims):
        return jsonify({"message": "Patient only"}), 401
    patient_id = claims['user_id']
    task = export_treatments_csv.delay(patient_id)
    return jsonify({"task_id": task.id}), 202


@app.route('/reports/download/<path:filename>', methods=['GET'])
@jwt_required()
def reports_download(filename):
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


# ---------------------------
# CELERY tasks
# ---------------------------

@celery.task(name="tasks.daily_reminder")
def daily_reminder():
    today = DateTime.now().date()
    appts = Appointment.query.filter_by(date=today, status='Booked').all()
    for a in appts:
        patient = User.query.get(a.patient_id)
        doctor = User.query.get(a.doctor_id)
        if patient and '@' in patient.username:
            try:
                msg = Message(
                    subject="Appointment Reminder",
                    recipients=[patient.username],
                    body=f"Reminder: Appointment with Dr {doctor.username if doctor else 'N/A'} "
                         f"at {a.time} on {a.date}"
                )
                mail.send(msg)
            except Exception:
                pass
    return "done"


@celery.task(name="tasks.monthly_doctor_activity")
def monthly_doctor_activity():
    doctors = User.query.filter_by(role='doctor', approve=True).all()
    now = DateTime.now()
    month = now.month
    for d in doctors:
        appts = Appointment.query.filter(
            Appointment.doctor_id == d.id,
            func.strftime('%m', Appointment.date) == f"{month:02d}"
        ).all()
        html = f"<h2>Activity for {d.username} - {now.strftime('%B %Y')}</h2><ul>"
        for a in appts:
            html += f"<li>{a.date} {a.time} - {a.status}</li>"
        html += "</ul>"
        if '@' in d.username:
            try:
                msg = Message(
                    subject=f"Monthly Activity - {now.strftime('%B %Y')}",
                    recipients=[d.username],
                    html=html
                )
                mail.send(msg)
            except Exception:
                pass
    return "done"


@celery.task(name="tasks.export_treatments_csv")
def export_treatments_csv(patient_id):
    treatments = Treatment.query.join(Appointment).filter(Appointment.patient_id == patient_id).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['appointment_date', 'doctor_username', 'diagnosis', 'prescription', 'notes'])
    for t in treatments:
        appt = Appointment.query.get(t.appointment_id)
        doctor = User.query.get(appt.doctor_id) if appt else None
        writer.writerow([
            str(appt.date) if appt else '',
            doctor.username if doctor else '',
            t.diagnosis,
            t.prescription,
            t.notes
        ])
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"patient_{patient_id}_treatments.csv")
    with open(path, 'w', newline='') as f:
        f.write(output.getvalue())
    return path


@celery.task(name="tasks.export_professional_service_requests")
def export_professional_service_requests(professional_id):
    appts = Appointment.query.filter_by(doctor_id=professional_id).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['appointment_id', 'patient_id', 'date', 'time', 'status', 'remarks'])
    for a in appts:
        writer.writerow([a.id, a.patient_id, a.date, a.time, a.status, a.remarks])
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"doctor_{professional_id}_appointments.csv")
    with open(path, 'w', newline='') as f:
        f.write(output.getvalue())
    return path


celery.conf.beat_schedule = {
    'daily-reminder': {
        'task': 'tasks.daily_reminder',
        'schedule': crontab(hour=8, minute=0)
    },
    'monthly-doctor-activity': {
        'task': 'tasks.monthly_doctor_activity',
        'schedule': crontab(hour=7, minute=0, day_of_month=1)
    },
}

# ---------------------------
# Run
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
