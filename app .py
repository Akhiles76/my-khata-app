from flask import Flask, request, jsonify, render_template, send_file
import sqlite3
import pandas as pd
import io

app = Flask(__name__)

# डेटाबेस सेटअप (यह फंक्शन वैसा ही रहेगा)
def init_db():
    conn = sqlite3.connect('khata.db')
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
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    ''')
    conn.commit()
    conn.close()

# होम पेज दिखाने के लिए
@app.route('/')
def index():
    return render_template('index.html')

# नया ग्राहक जोड़ने के लिए
@app.route('/add_customer', methods=['POST'])
def add_customer():
    data = request.json
    try:
        conn = sqlite3.connect('khata.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", (data['name'], data['phone']))
        conn.commit()
        conn.close()
        return jsonify({'message': 'ग्राहक सफलतापूर्वक जोड़ा गया!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'इस फोन नंबर वाला ग्राहक पहले से मौजूद है'}), 400

# लेन-देन जोड़ने के लिए
@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    data = request.json
    conn = sqlite3.connect('khata.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO transactions (customer_id, amount, type, description) VALUES (?, ?, ?, ?)",
                   (data['customer_id'], data['amount'], data['type'], data['description']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'लेन-देन सफलतापूर्वक रिकॉर्ड किया गया!'}), 201

# सभी ग्राहकों की सूची पाने के लिए
@app.route('/get_customers', methods=['GET'])
def get_customers():
    conn = sqlite3.connect('khata.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers")
    customers = [{'id': row[0], 'name': row[1], 'phone': row[2]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(customers)

# डेटा को एक्सेल में एक्सपोर्ट करने के लिए
@app.route('/export_excel', methods=['GET'])
def export_excel():
    conn = sqlite3.connect('khata.db')
    
    # SQL क्वेरी से ग्राहकों और उनके लेन-देन का पूरा डेटा प्राप्त करें
    query = """
    SELECT 
        c.name AS CustomerName, 
        c.phone AS CustomerPhone, 
        t.amount AS Amount, 
        t.type AS TransactionType, 
        t.description AS Description
    FROM transactions t
    JOIN customers c ON c.id = t.customer_id
    ORDER BY c.name
    """
    
    # डेटा को Pandas DataFrame में पढ़ें
    df = pd.read_sql_query(query, conn)
    conn.close()

    # DataFrame को एक्सेल फाइल में बदलने के लिए एक इन-मेमोरी बफर बनाएं
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Khata_Data')
    
    output.seek(0) # बफर के शुरू में जाएं

    # फाइल को ब्राउज़र पर डाउनलोड के लिए भेजें
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='khata_data.xlsx'
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True)