from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ===========================
# User Table (Admin/Doctor/Patient)
# ===========================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)  # email
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Admin / Doctor / Patient
    approve = db.Column(db.Boolean, default=False)  # doctor approved by admin
    blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    def as_dict(self):
        return {c.key: getattr(self, c.key) for c in self.__table__.columns}



# ===========================
# Department / Specialization
# ===========================
class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200))



# ===========================
# Doctor Profile
# ===========================
class DoctorProfile(db.Model):
    __tablename__ = 'doctor_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    specialization_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    experience = db.Column(db.String(100))
    availability = db.Column(db.String(200))  # can store JSON: slots for next 7 days

    user = db.relationship('User', foreign_keys=[user_id])
    specialization = db.relationship('Department')



# ===========================
# Patient Profile
# ===========================
class PatientProfile(db.Model):
    __tablename__ = 'patient_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    full_name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    contact = db.Column(db.String(15))
    address = db.Column(db.String(200))

    user = db.relationship('User', foreign_keys=[user_id])



# ===========================
# Appointment Table
# ===========================
class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    date = db.Column(db.Date)
    time = db.Column(db.Time)
    status = db.Column(db.String(20), default="Booked")  # Booked/Completed/Cancelled
    remarks = db.Column(db.String(200))

    patient = db.relationship('User', foreign_keys=[patient_id], backref="patient_appointments")
    doctor = db.relationship('User', foreign_keys=[doctor_id], backref="doctor_appointments")
    department = db.relationship('Department')



# ===========================
# Treatment Table
# ===========================
class Treatment(db.Model):
    __tablename__ = 'treatments'
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'))
    diagnosis = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)

    appointment = db.relationship('Appointment')
