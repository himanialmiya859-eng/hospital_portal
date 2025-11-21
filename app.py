from flask import Flask, render_template, request, jsonify
import mysql.connector
import os, base64, re, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import cv2
import face_recognition
import numpy as np

# ---------------------------
# Flask App Initialization
# ---------------------------
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 80 * 1024 * 1024  # 80MB limit

# ---------------------------
# Upload Folders
# ---------------------------
UPLOAD_FOLDER = os.path.join('static', 'uploads')
PATIENTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'patients')
VISITORS_FOLDER = os.path.join(UPLOAD_FOLDER, 'visitors')
os.makedirs(PATIENTS_FOLDER, exist_ok=True)
os.makedirs(VISITORS_FOLDER, exist_ok=True)

# ---------------------------
# MySQL Connection
# ---------------------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Root@123",
    database="hospital_db"
)
cursor = db.cursor(dictionary=True)

# ---------------------------
# Home Routes
# ---------------------------
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/patient')
def patient():
    return render_template('patient.html')

@app.route('/visitor')
def visitor():
    return render_template('visitor.html')


# ---------------------------
# Patient Registration
# ---------------------------
@app.route('/register', methods=['POST'])
def register_patient():
    try:
        fullname = request.form['fullname']
        email = request.form['email']
        phone = request.form['phone']
        aadhaar = request.form['aadhaar']
        image = request.files['image']

        # Patient ID generate
        name_part = fullname[:2].upper()
        phone_part = phone[-3:]
        aadhaar_part = aadhaar[-3:]
        patient_code = f"{name_part}{aadhaar_part}{phone_part}"

        # Save image
        image_path = None
        if image and image.filename != "":
            image_filename = f"{fullname}_{phone}.png"
            image_path = os.path.join(PATIENTS_FOLDER, image_filename)
            image.save(image_path)

        # Save to database
        cursor.execute("""
            INSERT INTO patients (fullname, email, phone, aadhaar, image_path, patient_code)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (fullname, email, phone, aadhaar, image_path, patient_code))
        db.commit()

        # ---------------------------
        # Email Sending
        # ---------------------------
        try:
            sender_email = "hospital.portal.000@gmail.com"
            app_password = "havq logd tyel uvmz"
            receiver_email = email

            subject = "Your Patient ID - Hospital Registration"
            body = f"""
Hello {fullname},

Your registration is successful!

Your Patient ID is: {patient_code}

Please keep this ID safe for hospital visits.

Thank you,
Hospital Team
"""

            # Email format
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = receiver_email
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, app_password)
                server.send_message(message)

        except Exception as e:
            print("Email Error:", e)

        return render_template('success.html', name=fullname, patient_id=patient_code)

    except Exception as e:
        return f"Error: {str(e)}"


# ---------------------------
# Visitor Registration
# ---------------------------
@app.route("/register_visitor", methods=["POST"])
def register_visitor():
    try:
        name = request.form["name"]
        phone = request.form["phone"]
        patient_id = request.form["patient_id"]
        ward = request.form["ward"]
        image_data = request.form["visitor_image"]

        if not image_data.startswith("data:image"):
            return jsonify({"success": False, "error": "Invalid image data"})

        image_data = re.sub('^data:image/.+;base64,', '', image_data)
        image_bytes = base64.b64decode(image_data)

        filename = f"{name}_{phone}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        image_path = os.path.join(VISITORS_FOLDER, filename)
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        cursor.execute("""
            INSERT INTO visitors (name, phone, patient_id, ward, image_path)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, phone, patient_id, ward, image_path))
        db.commit()

        return jsonify({"success": True, "message": "Visitor registered successfully!"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------
# Check Patient ID (AJAX)
# ---------------------------
@app.route("/check_patient/<pid>")
def check_patient(pid):
    if len(pid) != 8:
        return jsonify({"exists": False, "error": "Invalid length"})

    cursor.execute("SELECT * FROM patients WHERE patient_code=%s", (pid,))
    patient = cursor.fetchone()
    return jsonify({"exists": bool(patient)})

@app.route("/check")
def check():
    return render_template("check_patient.html")

@app.route("/exit")
def exit_page():
    return render_template("exit.html")

@app.route("/verify_exit_face", methods=["POST"])
def verify_exit_face():
    try:
        data = request.get_json()
        face_base64 = data["face"]

        face_base64 = re.sub('^data:image/.+;base64,', '', face_base64)
        face_bytes = base64.b64decode(face_base64)

        np_img = np.frombuffer(face_bytes, np.uint8)
        frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

        live_face = face_recognition.face_encodings(frame)
        if len(live_face) == 0:
            return jsonify({"match": False})

        live_encoding = live_face[0]

        for file in os.listdir(VISITORS_FOLDER):
            file_path = os.path.join(VISITORS_FOLDER, file)
            known_img = face_recognition.load_image_file(file_path)

            known_faces = face_recognition.face_encodings(known_img)
            if len(known_faces) == 0:
                continue

            known_encoding = known_faces[0]
            match = face_recognition.compare_faces([known_encoding], live_encoding)[0]

            if match:
                return jsonify({"match": True})

        return jsonify({"match": False})

    except Exception as e:
        return jsonify({"match": False, "error": str(e)})


# ---------------------------
# Patients API (For Staff Dashboard)
# ---------------------------
@app.route("/patients")
def get_patients():
    cursor.execute("SELECT * FROM patients")
    data = cursor.fetchall()
    return jsonify(data)

@app.route("/staff")
def staff_login():
    return render_template("staff.html")




# ---------------------------
# Staff Dashboard
# ---------------------------
@app.route("/dashboard")
def dashboard():
    return render_template("staff_dashboard.html")


# ---------------------------
# Run App
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
