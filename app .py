import os
import io
import pandas as pd
from flask import (Flask, request, jsonify, render_template, send_file, 
                   session, redirect, url_for, g, flash)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
# Render के Environment Variable से SECRET_KEY और DATABASE_URL प्राप्त करें
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Models (New way of defining tables) ---
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

# --- User Session Management ---
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

# --- Authentication Routes ---
@app.route('/register', methods=('GET', 'POST'))
def register():
    # ... (Register logic remains similar, but uses SQLAlchemy)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        
        if not username or not password:
            error = 'यूजरनेम और पासवर्ड जरूरी है।'
        elif User.query.filter_by(username=username).first() is not None:
            error = f"यूजरनेम '{username}' पहले से मौजूद है।"
        
        if error is None:
            new_user = User(username=username, password=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            flash('रजिस्ट्रेशन सफल! अब आप लॉगइन कर सकते हैं।', 'success')
            return redirect(url_for('login'))
        
        flash(error, 'error')
    return render_template('register.html')


@app.route('/login', methods=('GET', 'POST'))
def login():
    # ... (Login logic remains similar, but uses SQLAlchemy)
    if g.user:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        user = User.query.filter_by(username=username).first()

        if user is None or not check_password_hash(user.password, password):
            error = 'गलत यूजरनेम या पासवर्ड।'

        if error is None:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('index'))
        
        flash(error, 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- App Routes and API Endpoints (Now using SQLAlchemy) ---

# All routes need to be protected with @login_required
# Queries now use the SQLAlchemy ORM

@app.route('/')
@login_required
def index():
    return render_template('index.html')

# Add other routes like /all_transactions here, protected with @login_required

# Example of updated API route:
@app.route('/customers', methods=['GET'])
@login_required
def get_customers():
    customers = Customer.query.filter_by(user_id=g.user.id).order_by(Customer.name).all()
    return jsonify([{"id": c.id, "name": c.name, "phone": c.phone} for c in customers])

# You would continue to update all your routes (add_customer, search_customers, etc.)
# using the SQLAlchemy query syntax (e.g., Model.query.filter_by(...)).
# The rest of the routes are omitted here for brevity but would follow the same pattern.
# Make sure to create the database tables with a command.

if __name__ == '__main__':
    with app.app_context():
        db.create_all() # This creates tables based on models
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
