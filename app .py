import sqlite3
import io
import pandas as pd
import os # ✨ यह नई लाइन है
from flask import (Flask, request, jsonify, render_template, send_file, 
                   session, redirect, url_for, g, flash)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Sessions को सुरक्षित रखने के लिए एक SECRET KEY जरूरी है
app.config['SECRET_KEY'] = 'a-very-random-and-secret-key-for-my-app'

# --- Database Setup ---

# ✨ DATABASE FUNCTION UPDATED FOR RENDER DEPLOYMENT ✨
def get_db_connection():
    """Establishes a connection to the database."""
    # Render पर डेटा को स्थायी रूप से सेव करने के लिए पाथ सेट करें
    db_folder = '/var/data'
    if not os.path.exists(db_folder):
        os.makedirs(db_folder)
    
    db_path = os.path.join(db_folder, 'khata.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db_connection()
    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Customers table with user_id foreign key
    conn.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    # Transactions table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

# --- User Session Management ---
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = None
    if user_id is not None:
        conn = get_db_connection()
        g.user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

def login_required(view):
    """Decorator to protect views that require login."""
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    wrapped_view.__name__ = view.__name__
    return wrapped_view

# --- Authentication Routes ---
@app.route('/register', methods=('GET', 'POST'))
def register():
    if g.user:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        error = None
        
        if not username or not password:
            error = 'यूजरनेम और पासवर्ड जरूरी है।'
        elif conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone() is not None:
            error = f"यूजरनेम '{username}' पहले से मौजूद है।"
        
        if error is None:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                         (username, generate_password_hash(password)))
            conn.commit()
            conn.close()
            flash('रजिस्ट्रेशन सफल! अब आप लॉगइन कर सकते हैं।', 'success')
            return redirect(url_for('login'))
        
        flash(error, 'error')
        conn.close()
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.user:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        error = None
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user['password'], password):
            error = 'गलत यूजरनेम या पासवर्ड।'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        
        flash(error, 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Protected App Routes ---
@app.route('/')
@login_required
def index():
    return render_template('index.html')
    
@app.route('/all_transactions')
@login_required
def all_transactions_page():
    return render_template('transactions.html')

# --- Protected API Endpoints ---
@app.route('/customers', methods=['GET'])
@login_required
def get_customers():
    conn = get_db_connection()
    customers = conn.execute("SELECT * FROM customers WHERE user_id = ? ORDER BY name", (g.user['id'],)).fetchall()
    conn.close()
    return jsonify([dict(c) for c in customers])

@app.route('/add_customer', methods=['POST'])
@login_required
def add_customer():
    data = request.json
    conn = get_db_connection()
    conn.execute("INSERT INTO customers (name, phone, user_id) VALUES (?, ?, ?)", 
                   (data['name'], data['phone'], g.user['id']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'ग्राहक सफलतापूर्वक जोड़ा गया!'}), 201

@app.route('/search_customers', methods=['GET'])
@login_required
def search_customers():
    query = request.args.get('query', '')
    conn = get_db_connection()
    customers = conn.execute(
        "SELECT * FROM customers WHERE user_id = ? AND (name LIKE ? OR phone LIKE ?)",
        (g.user['id'], f'%{query}%', f'%{query}%')
    ).fetchall()
    conn.close()
    return jsonify([dict(c) for c in customers])

@app.route('/customer/<int:customer_id>/transactions', methods=['GET'])
@login_required
def get_transactions(customer_id):
    conn = get_db_connection()
    customer = conn.execute("SELECT id FROM customers WHERE id = ? AND user_id = ?", (customer_id, g.user['id'])).fetchone()
    if customer is None:
        return jsonify({"error": "Unauthorized"}), 403
    
    transactions = conn.execute("SELECT * FROM transactions WHERE customer_id = ? ORDER BY timestamp DESC", (customer_id,)).fetchall()
    conn.close()
    return jsonify([dict(t) for t in transactions])

@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
    data = request.json
    conn = get_db_connection()
    conn.execute("INSERT INTO transactions (customer_id, amount, type, description) VALUES (?, ?, ?, ?)",
                   (data['customer_id'], data['amount'], data['type'], data['description']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'लेन-देन सफलतापूर्वक रिकॉर्ड किया गया!'}), 201

@app.route('/transaction/<int:transaction_id>', methods=['DELETE', 'PUT'])
@login_required
def modify_transaction(transaction_id):
    conn = get_db_connection()
    # Add security check here in a real app
    if request.method == 'DELETE':
        conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        message = 'लेन-देन सफलतापूर्वक डिलीट किया गया!'
    elif request.method == 'PUT':
        data = request.json
        conn.execute("UPDATE transactions SET amount = ?, type = ?, description = ? WHERE id = ?",
                       (data['amount'], data['type'], data['description'], transaction_id))
        message = 'लेन-देन सफलतापूर्वक अपडेट किया गया!'
    conn.commit()
    conn.close()
    return jsonify({'message': message})

@app.route('/get_all_transactions_data')
@login_required
def get_all_transactions_data():
    conn = get_db_connection()
    query = """
    SELECT t.*, c.name as customer_name, c.phone as customer_phone
    FROM transactions t JOIN customers c ON t.customer_id = c.id
    WHERE c.user_id = ? ORDER BY t.timestamp DESC
    """
    transactions = conn.execute(query, (g.user['id'],)).fetchall()
    conn.close()
    return jsonify([dict(t) for t in transactions])

@app.route('/export_excel', methods=['GET'])
@login_required
def export_excel():
    conn = get_db_connection()
    query = """
    SELECT c.name, c.phone, t.amount, t.type, t.description, t.timestamp 
    FROM transactions t JOIN customers c ON c.id = t.customer_id 
    WHERE c.user_id = ? ORDER BY c.name, t.timestamp
    """
    df = pd.read_sql_query(query, conn, params=(g.user['id'],))
    conn.close()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Khata_Data')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='khata_data.xlsx')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
```
