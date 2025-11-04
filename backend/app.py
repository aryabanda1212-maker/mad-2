import os
import csv
from io import StringIO
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, func, or_
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt
from werkzeug.security import generate_password_hash, check_password_hash
from models import User, Department, DoctorProfile, PatientProfile, Appointment, Treatment, db
from werkzeug.utils import secure_filename
from flask_cors import CORS
from flasgger import Swagger
from flask_caching import Cache
from datetime import datetime as DateTime
from celery import Celery
import requests
from celery.schedules import crontab
from flask_mail import Mail, Message

app = Flask(__name__, template_folder='../frontend', static_folder='../frontend', static_url_path='/static')

# --- (You should configure app.config here: SQLALCHEMY_DATABASE_URI, JWT settings, Mail, Celery, etc.) ---
# Example (set these appropriately in your real environment):
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
# app.config['JWT_SECRET_KEY'] = 'your-secret-key'
# db.init_app(app)
# jwt = JWTManager(app)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')
        role = (request.json.get('role') or "").strip().lower()

        if not username or not password or not role:
            return jsonify({"category": "danger", "message": "username, password and role are required"}), 400

        # allow only patient or doctor registration via this endpoint
        if role not in ['patient', 'doctor']:
            return jsonify({"category": "danger", "message": "Invalid role! Use 'patient' or 'doctor'."}), 401

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"category": "danger", "message": "User already exists!"}), 401

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Patients can be auto-approved; doctors must be approved by admin
        if role == 'patient':
            approve = True
            blocked = False
        else:  # doctor
            approve = False
            blocked = False

        new_user = User(username=username, password=hashed_password, role=role, approve=approve, blocked=blocked)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({"category": "success", "message": "Registration successful!"}), 200

    return jsonify({"category": "danger", "message": "Bad request"}), 400


@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')

        # only patient and doctor login here (admins use /admin/login)
        user = User.query.filter(User.username == username).filter(User.role.in_(['patient', 'doctor'])).first()
        if user and check_password_hash(user.password, password):
            # PATIENT flow
            if user.role == 'patient':
                # Patients are allowed to log in only if not blocked and approved
                if not user.approve:
                    return jsonify({"category": "danger", "message": "Your account is not approved yet! Please wait for the admin to approve."}), 401
                if user.blocked:
                    return jsonify({"category": "danger", "message": "Your account is blocked! Please contact the admin."}), 401

                patient_profile = PatientProfile.query.filter_by(user_id=user.id).first()
                if not patient_profile:
                    additional_claims = {"user_id": user.id, "role": user.role, "redirect": "patient_profile"}
                    access_token = create_access_token(identity=username, additional_claims=additional_claims)
                    return jsonify(access_token=access_token)

                additional_claims = {"user_id": user.id, "role": user.role, "redirect": "patient_dashboard"}
                access_token = create_access_token(identity=username, additional_claims=additional_claims)
                return jsonify(access_token=access_token)

            # DOCTOR flow
            elif user.role == 'doctor':
                doctor_profile = DoctorProfile.query.filter_by(user_id=user.id).first()
                if not doctor_profile:
                    additional_claims = {"user_id": user.id, "role": user.role, "redirect": "doctor_profile"}
                    access_token = create_access_token(identity=username, additional_claims=additional_claims)
                    return jsonify(access_token=access_token)

                # doctors require admin approval
                if not user.approve:
                    return jsonify({"category": "danger", "message": "Your account is not approved yet! Please wait for the admin to approve."}), 401
                if user.blocked:
                    return jsonify({"category": "danger", "message": "Your account is blocked! Please contact the admin."}), 401

                additional_claims = {"user_id": user.id, "role": user.role, "redirect": "doctor_dashboard"}
                access_token = create_access_token(identity=username, additional_claims=additional_claims)
                return jsonify(access_token=access_token)

        return jsonify({"category": "danger", "message": "Bad username or password"}), 401

    return jsonify({"category": "danger", "message": "Bad request"}), 400


@app.route('/admin/login', methods=['POST'])
def admin_login():
    if request.method == 'POST':
        username = request.json.get('username')
        password = request.json.get('password')

        # Admin login - ensure admin role is exactly 'admin'
        user = User.query.filter_by(username=username, role='admin').first()
        if user and check_password_hash(user.password, password):
            additional_claims = {"admin_user_id": user.id, "role": user.role}
            access_token = create_access_token(identity=username, additional_claims=additional_claims)
            return jsonify(access_token=access_token)

        return jsonify({"category": "danger", "message": "Bad username or password"}), 401

    return jsonify({"category": "danger", "message": "Bad request"}), 400


if __name__ == '__main__':
    # Only for local debugging; in prod use a WSGI server
    # Ensure DB is initialized before first run (e.g. call db.create_all() with app context)
    app.run(debug=True)
