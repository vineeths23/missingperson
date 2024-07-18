import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import face_recognition
from PIL import Image
import numpy as np
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:1234@localhost/missing_persons_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    contact_info = db.Column(db.String(255))

class MissingPerson(db.Model):
    __tablename__ = 'missing_persons'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    description = db.Column(db.Text)
    guardian_email = db.Column(db.String(100))
    image_path = db.Column(db.String(255))
    face_encoding = db.Column(db.LargeBinary)

def get_face_encoding(image_path):
    image = face_recognition.load_image_file(image_path)
    face_encodings = face_recognition.face_encodings(image)
    if face_encodings:
        return face_encodings[0]
    return None

def compare_faces(known_encoding, unknown_encoding):
    results = face_recognition.compare_faces([known_encoding], unknown_encoding)
    return results[0]

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        contact_info = request.form['contact_info']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        new_user = User(username=username, 
                        password=generate_password_hash(password),
                        email=email, 
                        contact_info=contact_info)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/update_missing', methods=['GET', 'POST'])
def update_missing():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        gender = request.form['gender']
        description = request.form['description']
        guardian_email = request.form['guardian_email']
        image = request.files['image']
        
        if image:
            filename = f"{name}_{age}.jpg"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            
            face_encoding = get_face_encoding(image_path)
            
            if face_encoding is not None:
                new_missing_person = MissingPerson(
                    name=name, age=age, gender=gender, description=description,
                    guardian_email=guardian_email, image_path=image_path,
                    face_encoding=face_encoding.tobytes()
                )
                db.session.add(new_missing_person)
                db.session.commit()
                flash('Missing person added successfully')
            else:
                flash('No face detected in the image. Please try again with a clear face image.')
        else:
            flash('No image uploaded. Please upload an image.')
        return redirect(url_for('home'))
    
    return render_template('update_missing.html')

@app.route('/search_missing', methods=['GET', 'POST'])
def search_missing():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        image = request.files['image']
        if image:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'search_image.jpg')
            image.save(image_path)
            
            search_encoding = get_face_encoding(image_path)
            
            if search_encoding is not None:
                missing_persons = MissingPerson.query.all()
                for person in missing_persons:
                    db_encoding = np.frombuffer(person.face_encoding, dtype=np.float64)
                    if compare_faces(db_encoding, search_encoding):
                        send_notification_email(person)
                        return render_template('search_result.html', person=person)
                
                flash('No matching person found')
            else:
                flash('No face detected in the image. Please try again with a clear face image.')
        else:
            flash('No image uploaded. Please upload an image.')
    
    return render_template('search_missing.html')

def send_notification_email(person):
    sender_email = "anudeepkkm5@gmail.com"
    sender_password = "gquy ixyv sslj zqbr"
    receiver_email = person.guardian_email
    
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = "Missing Person Found"
    
    body = f"Your missing person {person.name} has been found. Please contact the authorities for more information."
    message.attach(MIMEText(body, 'plain'))
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(message)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
