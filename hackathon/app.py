from flask import Flask, render_template, request, redirect, session, url_for, flash,g, jsonify
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor
import joblib
import pandas as pd
import sqlite3
import math
from flask_socketio import SocketIO, emit,join_room,leave_room
from flask_cors import CORS
import json

app = Flask(__name__)
socketio = SocketIO(app, 
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True
)
app.config['SECRET_KEY'] = 'khwaabonauts-lifelink-2024'
app.config['SESSION_TYPE'] = 'filesystem'
CORS(app)

# Load pre-trained model, scaler, and label encoder
model = joblib.load('organ_matching_model.pkl')
scaler = joblib.load('scaler.pkl')
label_encoder = joblib.load('label_encoder.pkl')

# SQLite database file name
DB_FILE = 'organ_donation.db'

DATABASE = DB_FILE  # Replace with the name of your database file


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Allows dict-like access to rows
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Function to fetch notifications for a user
def fetch_notifications_for_user(user_id):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute("SELECT message, type FROM notifications WHERE user_id = ?", (user_id,))
    notifications = cursor.fetchall()
    connection.close()
    return [{'message': msg, 'type': notif_type} for msg, notif_type in notifications]

@app.route('/notifications/<int:user_id>', methods=['GET'])
def get_notifications(user_id):
    notifications = fetch_notifications_for_user(user_id)
    return jsonify(notifications)

@app.route('/')
def index():
    return render_template('home.html')




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        connection = get_db()
        cursor = connection.cursor()
        
        cursor.execute('SELECT password FROM users WHERE email = ?', (email,))
        stored_password = cursor.fetchone()
        
        if stored_password and stored_password[0] == password:  # Plain text comparison
            cursor.execute('SELECT id FROM donors WHERE email = ?', (email,))
            donor = cursor.fetchone()
            
            if donor:
                session['user_id'] = donor[0] 
                session['user_type'] = 'donor'
                connection.close()
                return redirect(f'/card/{donor[0]}')
            else:
                cursor.execute('SELECT id FROM recipients WHERE email = ?', (email,))
                recipient = cursor.fetchone()
                connection.close()
                if recipient:
                    return redirect(f'/match/{recipient[0]}')
                return redirect(url_for('form'))
        else:
            connection.close()
            return "Invalid credentials"
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        connection = sqlite3.connect(DB_FILE)
        cursor = connection.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            email TEXT UNIQUE,
                            password TEXT,
                            user_type TEXT
                        )''')
        
        try:
            cursor.execute('INSERT INTO users (email, password, user_type) VALUES (?, ?, ?)',
                           (email, password, user_type))
            connection.commit()
            
            session['email'] = email
            session['user_type'] = user_type
            session['logged_in'] = True
            session['user_id'] = cursor.lastrowid  # Store the user ID
            
            return redirect(url_for('form'))
        except sqlite3.IntegrityError:
            return "Email already exists"
        finally:
            connection.close()
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/form')
def form():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_type = session.get('user_type')
    return render_template('form.html', user_type=user_type)


def notify_recipients(organ, donor_name):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    # Fetch all recipients who need the specified organ
    cursor.execute("SELECT id FROM recipients WHERE needed_organ = ?", (organ,))
    recipients = cursor.fetchall()

    for recipient in recipients:
        recipient_id = recipient[0]
        message = f"New donor available: {donor_name} for organ: {organ}"

        # Insert notification into the notifications table
        cursor.execute("INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
                       (recipient_id, message, 'new_donor'))

    connection.commit()
    cursor.close()
    connection.close()

@app.route('/submit', methods=['POST'])
def submit():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    form_type = request.form.get('form_type')
    full_name = request.form.get('fullName')
    blood_type = request.form.get('bloodType')
    age = int(request.form.get('age'))
    email = session['email']

    longitude = float(request.form.get(f'longitude_{form_type}'))
    latitude = float(request.form.get(f'latitude_{form_type}'))

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    if form_type == 'donor':
        organ = request.form.get('organs')
        query = """INSERT INTO pre_donors (full_name, email, blood_type, organ, age, longitude, latitude)
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        data = (full_name, email, blood_type, organ, age, longitude, latitude)
        cursor.execute(query, data)        
        connection.commit()
        cursor.close()
        connection.close()

        # Notify recipients about the new donor
        notify_recipients(organ, full_name)  # Implement this function to notify recipients

        return render_template('confirmation_card.html', user_type='donor', full_name=full_name, 
                               email=email, blood_type=blood_type, organ=organ, age=age,
                               longitude=longitude, latitude=latitude, user_id=session['user_id'])
    elif form_type == 'recipient':
        needed_organ = request.form.get('neededOrgan')
        urgency_level = int(request.form.get('urgencyLevel'))
        query = """INSERT INTO pre_recipients (full_name, email, blood_type, needed_organ, urgency_level, age, longitude, latitude)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        data = (full_name, email, blood_type, needed_organ, urgency_level, age, longitude, latitude)
        cursor.execute(query, data)

        recipient_id = cursor.lastrowid
        connection.commit()
        cursor.close()
        connection.close()

        return redirect(f'/match/{recipient_id}')

@app.route('/map-matches/<int:recipient_id>')
def map_matches(recipient_id):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    
    recipient_query = """
        SELECT full_name, latitude, longitude, needed_organ
        FROM recipients
        WHERE id = ?
    """
    cursor.execute(recipient_query, (recipient_id,))
    recipient = cursor.fetchone()

    if not recipient:
        return "Recipient not found", 404

    recipient_data = {
        'full_name': recipient[0],
        'latitude': float(recipient[1]),
        'longitude': float(recipient[2]),
        'needed_organ': recipient[3]
    }

    # Fetch donors matching the needed organ
    donor_query = """
        SELECT id,full_name, latitude, longitude, organ
        FROM donors
        WHERE organ = ?
    """
    cursor.execute(donor_query, (recipient_data['needed_organ'],))
    donors = cursor.fetchall()
    cursor.close()
    connection.close()

    if not donors:
        return "No matching donors found", 404

    # Prepare data for map rendering
    matches = [
        {
            'name': donor[1],
            'latitude': float(donor[2]),
            'longitude': float(donor[3]),
            'organ': donor[4]
        }
        for donor in donors
    ]

    return render_template('map_matches.html', 
                           recipient=recipient_data, 
                           matches=matches)

@app.route('/handle_request', methods=['POST'])
def handle_request():
    data = request.json
    request_id = data['request_id']
    action = data['action']
    status = 'accepted' if action == 'accept' else 'declined'

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    
    try:
        if status == 'accepted':
            # Get request details
            cursor.execute('''
                SELECT r.recipient_id, r.donor_id, d.full_name, rec.full_name, d.organ,
                       d.email as donor_email, rec.email as recipient_email
                FROM requests r
                JOIN donors d ON r.donor_id = d.id
                JOIN recipients rec ON r.recipient_id = rec.id
                WHERE r.id = ?
            ''', (request_id,))
            
            result = cursor.fetchone()
            if result:
                recipient_id, donor_id, donor_name, recipient_name, organ, donor_email, recipient_email = result
                
                # Store in matches
                cursor.execute('''
                    INSERT INTO matches (donor_id, recipient_id, donor_name, recipient_name, organ)
                    VALUES (?, ?, ?, ?, ?)
                ''', (donor_id, recipient_id, donor_name, recipient_name, organ))
                
                # Emit socket events
                socketio.emit('request_update', {
                    'status': 'accepted',
                    'donor_name': donor_name,
                    'recipient_name': recipient_name,
                    'organ': organ
                }, room=donor_email)
                
                socketio.emit('request_update', {
                    'status': 'accepted',
                    'donor_name': donor_name,
                    'recipient_name': recipient_name,
                    'organ': organ
                }, room=recipient_email)
        
        # Update request status
        cursor.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
        connection.commit()
        
        return jsonify({"success": True})

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"success": False, "error": str(e)})
        
    finally:
        connection.close()

@app.route('/send_request', methods=['POST'])
def send_request():
    try:
        data = request.json
        donor_id = data['donor_id']
        recipient_id = data['recipient_id']

        db = get_db()
        cursor = db.cursor()
        
        # Add transaction management
        try:
            cursor.execute("BEGIN")
            
            # Verify donor and recipient exist
            cursor.execute("SELECT id FROM donors WHERE id = ?", (donor_id,))
            if not cursor.fetchone():
                cursor.execute("ROLLBACK")
                return jsonify({"success": False, "message": "Donor not found"})
                
            cursor.execute("SELECT id FROM recipients WHERE id = ?", (recipient_id,))
            if not cursor.fetchone():
                cursor.execute("ROLLBACK")
                return jsonify({"success": False, "message": "Recipient not found"})
            
            # Check if request already exists
            cursor.execute(
                "SELECT id, status FROM requests WHERE donor_id = ? AND recipient_id = ?",
                (donor_id, recipient_id)
            )
            existing_request = cursor.fetchone()
            if existing_request:
                cursor.execute("ROLLBACK")
                return jsonify({
                    "success": False, 
                    "message": f"Request already exists with status: {existing_request[1]}"
                })

            # Insert new request
            cursor.execute(
                "INSERT INTO requests (donor_id, recipient_id, status) VALUES (?, ?, 'pending')",
                (donor_id, recipient_id)
            )
            
            cursor.execute("COMMIT")
            
            # Emit socket event to donor's room
            socketio.emit('new_request', {
                'type': 'new_request',
                'donor_id': donor_id,
                'recipient_id': recipient_id,
                'status': 'pending'
            }, room=str(donor_id))
            
            return jsonify({
                "success": True, 
                "message": "Request sent successfully"
            })

        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

    except Exception as e:
        print(f"Error in send_request: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Server error occurred"
        }), 500
    

@app.route('/requests/<donor_id>', methods=['GET'])
def get_requests(donor_id):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('''
        SELECT r.id, r.status, r.recipient_id, rec.full_name as recipient_name 
        FROM requests r
        JOIN recipients rec ON r.recipient_id = rec.id
        WHERE r.donor_id = ? AND r.status = 'pending'
    ''', (donor_id,))
    
    requests = cursor.fetchall()
    return jsonify([{
        'id': row[0],
        'status': row[1],
        'recipient_id': row[2],
        'recipient_name': row[3]
    } for row in requests])

@app.route('/accepted_requests/<recipient_id>', methods=['GET'])
def get_accepted_requests(recipient_id):
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT d.full_name AS donor_name, d.organ 
            FROM requests r
            JOIN donors d ON r.donor_id = d.id 
            WHERE r.recipient_id = ? AND r.status = 'accepted'
        """, (recipient_id,))
        
        requests = cursor.fetchall()
        return jsonify([{
            'donor_name': row[0],
            'organ': row[1]
        } for row in requests])
    except Exception as e:
        print(f"Error getting accepted requests: {str(e)}")
        return jsonify([])

@app.route('/match/<int:recipient_id>', methods=['GET', 'POST'])
def match(recipient_id):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    # Get recipient information
    recipient_query = """SELECT full_name, blood_type, needed_organ, urgency_level, age, latitude, longitude
                         FROM recipients WHERE id = ?"""
    cursor.execute(recipient_query, (recipient_id,))
    recipient = cursor.fetchone()

    if not recipient:
        return "Recipient not found", 404

    recipient_data = {
        'full_name': recipient[0],
        'blood_type': recipient[1],
        'needed_organ': recipient[2],
        'urgency_score': recipient[3],
        'age': recipient[4],
        'latitude': float(recipient[5]),
        'longitude': float(recipient[6])
    }

    # Get matching donors
    donor_query = """SELECT id, full_name, blood_type, organ, age, latitude, longitude
                     FROM donors WHERE organ = ?"""
    cursor.execute(donor_query, (recipient_data['needed_organ'],))
    donors = cursor.fetchall()

    if not donors:
        return "No matching donors found", 404

    results = []
    for donor in donors:
        donor_data = {
            'donor_id': donor[0],
            'full_name': donor[1],
            'blood_type': donor[2],
            'organ': donor[3],
            'age': donor[4],
            'latitude': float(donor[5]),
            'longitude': float(donor[6])
        }

        # Calculate compatibility scores
        donor_blood_type_encoded = label_encoder.transform([donor_data['blood_type']])[0]
        receiver_blood_type_encoded = label_encoder.transform([recipient_data['blood_type']])[0]
        location_distance = haversine(recipient_data['latitude'], recipient_data['longitude'],
                                      donor_data['latitude'], donor_data['longitude'])
        age_similarity = 1 / (1 + abs(donor_data['age'] - recipient_data['age']))

        input_data = pd.DataFrame([{
            'age_similarity': age_similarity,
            'distance_score': 1 / (1 + location_distance),
            'urgency_level': recipient_data['urgency_score']
        }])

        input_data_scaled = scaler.transform(input_data)
        compatibility_score = model.predict(input_data_scaled)[0]

        # Get the latest request status for this donor-recipient pair
        request_status_query = """
            SELECT status 
            FROM requests 
            WHERE donor_id = ? AND recipient_id = ? 
            ORDER BY id DESC LIMIT 1
        """
        cursor.execute(request_status_query, (donor_data['donor_id'], recipient_id))
        request_status_result = cursor.fetchone()
        request_status = request_status_result[0] if request_status_result else None

        results.append({
            'donor_id': donor_data['donor_id'],
            'donor_name': donor_data['full_name'],
            'organ': donor_data['organ'],
            'distance': round(location_distance, 2),
            'urgency_score': recipient_data['urgency_score'],
            'compatibility_score': round(compatibility_score, 2),
            'request_status': request_status  # Add request status to results
        })

    if request.method == 'POST':
        # Handle filtering and sorting
        sort_by = request.form.get('sort_by', 'compatibility_score')
        min_score_str = request.form.get('min_score', '')
        max_distance_str = request.form.get('max_distance', '')

        min_score = float(min_score_str) if min_score_str else 0
        max_distance = float(max_distance_str) if max_distance_str else float('inf')

        # Apply filters
        results = [result for result in results 
                  if result['compatibility_score'] >= min_score 
                  and result['distance'] <= max_distance]
        
        # Sort results
        results.sort(key=lambda x: x[sort_by], reverse=(sort_by != 'distance'))

    cursor.close()
    connection.close()

    return render_template('match.html', 
                         recipient_id=recipient_id, 
                         recipient_name=recipient_data['full_name'], 
                         results=results)

@app.route('/card/<int:donor_id>')
def donor_card(donor_id):
    if 'user_id' not in session or session['user_type'] != 'donor':
        return redirect(url_for('login'))
        
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute('SELECT full_name, email, blood_type, organ, age FROM donors WHERE id = ?', (donor_id,))
    donor = cursor.fetchone()
    connection.close()
    
    if not donor:
        return "Donor not found", 404
        
    return render_template('confirmation_card.html',
                         donor_id=donor_id,
                         full_name=donor[0],
                         email=donor[1],
                         blood_type=donor[2],
                         organ=donor[3],
                         age=donor[4])

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Radius of Earth in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon1 - lon2)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c  # in kilometers
    return distance

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == "admin" and password == "admin123":  # Hardcoded credentials
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return "Invalid credentials"
            
    return render_template('admin_login.html')

@app.route('/admin', methods=['GET'])
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    
    # Fetch pre-donors
    cursor.execute("SELECT * FROM pre_donors")
    pre_donors = cursor.fetchall()
    
    # Fetch pre-recipients
    cursor.execute("SELECT * FROM pre_recipients") 
    pre_recipients = cursor.fetchall()
    
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.execute("""
            SELECT id, donor_name, recipient_name, organ, match_date 
            FROM matches 
            ORDER BY match_date DESC
        """)
    matches = cursor.fetchall()
    connection.close()
    
    return render_template('admin.html', 
                         pre_donors=pre_donors,
                         pre_recipients=pre_recipients,users=users,matches=matches)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    
    try:
        # Start transaction
        cursor.execute("BEGIN")
        
        # Get user email first
        cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
        user_email = cursor.fetchone()
        
        if user_email:
            # Delete from donors if exists
            cursor.execute("DELETE FROM donors WHERE email = ?", (user_email[0],))
            
            # Delete from recipients if exists
            cursor.execute("DELETE FROM recipients WHERE email = ?", (user_email[0],))
            
            # Delete from pre_donors if exists
            cursor.execute("DELETE FROM pre_donors WHERE email = ?", (user_email[0],))
            
            # Delete from pre_recipients if exists
            cursor.execute("DELETE FROM pre_recipients WHERE email = ?", (user_email[0],))
            
            # Finally delete from users table
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            
            connection.commit()
            print(f"User {user_email[0]} deleted from all tables")
        
    except sqlite3.Error as e:
        connection.rollback()
        print(f"Error: {e}")
        
    finally:
        connection.close()
        
    return redirect(url_for('admin_panel'))

@app.route('/approve_donor/<int:donor_id>', methods=['POST'])
def approve_donor(donor_id):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    
    # Get donor data
    cursor.execute("SELECT * FROM pre_donors WHERE id = ?", (donor_id,))
    donor = cursor.fetchone()
    
    if donor:
        # Insert into main donors table
        cursor.execute("""
            INSERT INTO donors 
            (full_name, email, blood_type, organ, age, longitude, latitude)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, donor[1:])  # Exclude ID
        
        # Delete from pre_donors
        cursor.execute("DELETE FROM pre_donors WHERE id = ?", (donor_id,))
        connection.commit()
        
    connection.close()
    return redirect(url_for('admin_panel'))

@app.route('/approve_recipient/<int:recipient_id>', methods=['POST']) 
def approve_recipient(recipient_id):
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    
    cursor.execute("SELECT * FROM pre_recipients WHERE id = ?", (recipient_id,))
    recipient = cursor.fetchone()
    
    if recipient:
        cursor.execute("""
            INSERT INTO recipients
            (full_name, email, blood_type, needed_organ, urgency_level, age, longitude, latitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, recipient[1:])
        
        cursor.execute("DELETE FROM pre_recipients WHERE id = ?", (recipient_id,))
        connection.commit()
        
    connection.close()
    return redirect(url_for('admin_panel'))

def create_matches_table():
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS matches
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         donor_id INTEGER,
         recipient_id INTEGER,
         match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
         donor_name TEXT,
         recipient_name TEXT,
         organ TEXT,
         FOREIGN KEY (donor_id) REFERENCES donors (id),
         FOREIGN KEY (recipient_id) REFERENCES recipients (id))
    ''')
    connection.commit()
    connection.close()

# Define a WebSocket route
@socketio.on('connect', namespace='/ws')
def handle_connect():
    print('Client connected')
    emit('connected', {'data': 'Connected successfully'})

@socketio.on('disconnect', namespace='/ws')
def handle_disconnect():
    print('Client disconnected')

# In app.py, add room management:
@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    
@socketio.on('leave')
def on_leave(data):
    room = data['room'] 
    leave_room(room)

if __name__ == '__main__':
    create_matches_table()
    socketio.run(app, debug=True)
