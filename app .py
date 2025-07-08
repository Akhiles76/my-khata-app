import os
import io
import pandas as pd
from flask import (Flask, request, jsonify, render_template, send_file, 
                   session, redirect, url_for, g, flash)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-secret-key-for-local-dev')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ✨ NEW LOGIC: Use PostgreSQL on Render, but SQLite locally ✨
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # We are on Render, use the PostgreSQL database
    # The 'replace' is a common fix for SQLAlchemy compatibility
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
else:
    # We are running locally, use a simple SQLite database file
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///khata.db'


db = SQLAlchemy(app)

# --- Database Models (No changes here) ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    customers = db.relationship('Customer', backref='user', lazy=True, cascade="all, delete-orphan")

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transactions = db.relationship('Transaction', backref='customer', lazy=True, cascade="all, delete-orphan")

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

# --- User Session Management & Auth Routes (No changes here) ---
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = db.session.get(User, user_id) if user_id else None

def login_required(view):
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    wrapped_view.__name__ = view.__name__
    return wrapped_view

@app.route('/register', methods=('GET', 'POST'))
def register():
    if g.user: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('यूजरनेम और पासवर्ड जरूरी है।', 'error')
        elif User.query.filter_by(username=username).first() is not None:
            flash(f"यूजरनेम '{username}' पहले से मौजूद है।", 'error')
        else:
            new_user = User(username=username, password=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            flash('रजिस्ट्रेशन सफल! अब आप लॉगइन कर सकते हैं।', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.user: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user is None or not check_password_hash(user.password, password):
            flash('गलत यूजरनेम या पासवर्ड।', 'error')
        else:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- All App Routes and API Endpoints (No changes here) ---
# ... (The rest of your routes like @app.route('/'), @app.route('/customers'), etc. remain exactly the same)
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# --- Main execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    app.run(debug=True, host='0.0.0.0', port=5000)
