# app.py

from flask import Flask, request, jsonify, render_template, send_file
import sqlite3
import pandas as pd
import io

app = Flask(__name__)

# --- Database Helper Functions ---
def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect('khata.db')
    conn.row_factory = sqlite3.Row # This allows accessing columns by name
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

# --- Main Routes ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Customer Routes ---
@app.route('/customers', methods=['GET'])
def get_customers():
    conn = get_db_connection()
    customers = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in customers])

@app.route('/add_customer', methods=['POST'])
def add_customer():
    data = request.json
    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", (data['name'], data['phone']))
        conn.commit()
        conn.close()
        return jsonify({'message': 'ग्राहक सफलतापूर्वक जोड़ा गया!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'इस फोन नंबर वाला ग्राहक पहले से मौजूद है'}), 400

# ✨ NEW: ग्राहक को सर्च करने के लिए रूट ✨
@app.route('/search_customers', methods=['GET'])
def search_customers():
    query = request.args.get('query', '')
    conn = get_db_connection()
    # Search by name or phone number
    customers = conn.execute(
        "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name",
        ('%' + query + '%', '%' + query + '%')
    ).fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in customers])


# --- Transaction Routes ---
@app.route('/customer/<int:customer_id>/transactions', methods=['GET'])
def get_transactions(customer_id):
    conn = get_db_connection()
    transactions = conn.execute(
        "SELECT * FROM transactions WHERE customer_id = ? ORDER BY timestamp DESC", (customer_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(ix) for ix in transactions])

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    data = request.json
    conn = get_db_connection()
    conn.execute("INSERT INTO transactions (customer_id, amount, type, description) VALUES (?, ?, ?, ?)",
                   (data['customer_id'], data['amount'], data['type'], data['description']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'लेन-देन सफलतापूर्वक रिकॉर्ड किया गया!'}), 201

# ✨ NEW: लेन-देन डिलीट करने के लिए रूट ✨
@app.route('/transaction/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'लेन-देन सफलतापूर्वक डिलीट किया गया!'})

# ✨ NEW: लेन-देन एडिट करने के लिए रूट ✨
@app.route('/transaction/<int:transaction_id>', methods=['PUT'])
def update_transaction(transaction_id):
    data = request.json
    conn = get_db_connection()
    conn.execute("UPDATE transactions SET amount = ?, type = ?, description = ? WHERE id = ?",
                   (data['amount'], data['type'], data['description'], transaction_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'लेन-देन सफलतापूर्वक अपडेट किया गया!'})


# --- Excel Export Route ---
@app.route('/export_excel', methods=['GET'])
def export_excel():
    # This function remains the same as before
    conn = get_db_connection()
    query = """SELECT c.name, c.phone, t.amount, t.type, t.description, t.timestamp FROM transactions t JOIN customers c ON c.id = t.customer_id ORDER BY c.name, t.timestamp"""
    df = pd.read_sql_query(query, conn)
    conn.close()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Khata_Data')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='khata_data.xlsx')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
