from flask import Flask, request, jsonify
import sqlite3
import uuid
import hashlib
import secrets
from flask_cors import CORS
from flask import render_template_string
from functools import wraps

app = Flask(__name__)
CORS(app) 
DB = "timetable.db"

# Simple authentication decorator (disabled for demo)
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # For demo purposes, we'll allow all requests
        return f(*args, **kwargs)
    return decorated_function

# -------------------------
# Database Setup
# -------------------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        role TEXT CHECK(role IN ('admin','faculty','student')),
        password TEXT
    )
    """)

    # Classrooms
    c.execute("""
    CREATE TABLE IF NOT EXISTS classrooms (
        id TEXT PRIMARY KEY,
        name TEXT,
        capacity INTEGER,
        type TEXT CHECK(type IN ('lecture','lab'))
    )
    """)

    # Subjects
    c.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id TEXT PRIMARY KEY,
        name TEXT,
        credits INTEGER,
        weekly_hours INTEGER,
        department TEXT
    )
    """)

    # Faculty-Subject Map
    c.execute("""
    CREATE TABLE IF NOT EXISTS faculty_subject_map (
        faculty_id TEXT,
        subject_id TEXT,
        max_hours_per_week INTEGER,
        avg_leaves_per_month INTEGER,
        PRIMARY KEY (faculty_id, subject_id),
        FOREIGN KEY(faculty_id) REFERENCES users(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id)
    )
    """)

    # Batches
    c.execute("""
    CREATE TABLE IF NOT EXISTS batches (
        id TEXT PRIMARY KEY,
        name TEXT,
        size INTEGER,
        type TEXT,
        department TEXT
    )
    """)

    # Timetable Slots
    c.execute("""
    CREATE TABLE IF NOT EXISTS timetable_slots (
        id TEXT PRIMARY KEY,
        day TEXT,
        time TEXT,
        classroom_id TEXT,
        subject_id TEXT,
        faculty_id TEXT,
        batch_id TEXT,
        FOREIGN KEY(classroom_id) REFERENCES classrooms(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id),
        FOREIGN KEY(faculty_id) REFERENCES users(id),
        FOREIGN KEY(batch_id) REFERENCES batches(id)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------
# Helper
# -------------------------
def execute_query(query, params=(), fetch=False, many=False):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        if many:
            c.executemany(query, params)
        else:
            c.execute(query, params)
        conn.commit()
        if fetch:
            rows = c.fetchall()
            cols = [col[0] for col in c.description]
            conn.close()
            return [dict(zip(cols, row)) for row in rows]
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return {"error": str(e)}

# -------------------------
# Root Route
# -------------------------
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "message": "Smart Classroom & Timetable Scheduler API",
        "version": "1.0.0",
        "endpoints": {
            "authentication": ["/login", "/register"],
            "crud": ["/create/<table>", "/read/<table>", "/update/<table>/<id>", "/delete/<table>/<id>"],
            "data": ["/show_all", "/table_all"]
        },
        "status": "running"
    })

# -------------------------
# CRUD Routes
# -------------------------
@app.route("/create/<table>", methods=["POST"])
def create(table):
    data = request.get_json()
    keys = ",".join(data.keys())
    placeholders = ",".join(["?"] * len(data))
    values = tuple(data.values())
    query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
    result = execute_query(query, values)
    if result is True:
        return jsonify({"status": "success", "table": table, "data": data}), 201
    return jsonify({"status": "error", "message": result}), 400


@app.route("/read/<table>", methods=["GET"])
@require_auth
def read(table):
    query = f"SELECT * FROM {table}"
    result = execute_query(query, fetch=True)
    if isinstance(result, list):
        return jsonify(result)
    return jsonify({"status": "error", "message": result}), 400


@app.route("/update/<table>/<id>", methods=["PUT"])
def update(table, id):
    data = request.get_json()
    updates = ",".join([f"{k}=?" for k in data.keys()])
    values = tuple(data.values()) + (id,)
    query = f"UPDATE {table} SET {updates} WHERE id=?"
    result = execute_query(query, values)
    if result is True:
        return jsonify({"status": "updated", "table": table, "id": id})
    return jsonify({"status": "error", "message": result}), 400


@app.route("/delete/<table>/<id>", methods=["DELETE"])
def delete(table, id):
    query = f"DELETE FROM {table} WHERE id=?"
    result = execute_query(query, (id,))
    if result is True:
        return jsonify({"status": "deleted", "table": table, "id": id})
    return jsonify({"status": "error", "message": result}), 400


@app.route("/show_all", methods=["GET"])
def show_all():
    tables = ["users", "classrooms", "subjects", "faculty_subject_map", "batches", "timetable_slots"]
    all_data = {}
    for table in tables:
        result = execute_query(f"SELECT * FROM {table}", fetch=True)
        all_data[table] = result if isinstance(result, list) else {"error": result}
    return jsonify(all_data)

@app.route("/table_all", methods=["GET"])
def table_all():
    tables = ["users", "classrooms", "subjects", "faculty_subject_map", "batches", "timetable_slots"]
    html = "<h1>All Tables</h1>"
    for table in tables:
        result = execute_query(f"SELECT * FROM {table}", fetch=True)
        if isinstance(result, list) and result:
            cols = result[0].keys()
            html += f"<h2>{table}</h2><table border='1' cellpadding='5'><tr>"
            html += "".join(f"<th>{col}</th>" for col in cols)
            html += "</tr>"
            for row in result:
                html += "<tr>" + "".join(f"<td>{row[col]}</td>" for col in cols) + "</tr>"
            html += "</table><br>"
        else:
            html += f"<h2>{table}</h2><p>No data</p>"
    return html

# -------------------------
# Authentication Routes
# -------------------------
def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    """Generate a simple token"""
    return secrets.token_urlsafe(32)

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({"status": "error", "message": "Email and password are required"}), 400
        
        # Hash the provided password
        hashed_password = hash_password(password)
        
        # Query user from database
        query = "SELECT * FROM users WHERE email = ? AND password = ?"
        result = execute_query(query, (email, hashed_password), fetch=True)
        
        if isinstance(result, list) and len(result) > 0:
            user = result[0]
            # Remove password from response
            user_data = {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
            
            # Generate token (in production, use JWT)
            token = generate_token()
            
            return jsonify({
                "status": "success",
                "message": "Login successful",
                "user": user_data,
                "token": token
            }), 200
        else:
            return jsonify({"status": "error", "message": "Invalid email or password"}), 401
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'student')
        
        if not name or not email or not password:
            return jsonify({"status": "error", "message": "Name, email, and password are required"}), 400
        
        # Check if user already exists
        query = "SELECT * FROM users WHERE email = ?"
        existing_user = execute_query(query, (email,), fetch=True)
        
        if isinstance(existing_user, list) and len(existing_user) > 0:
            return jsonify({"status": "error", "message": "User with this email already exists"}), 400
        
        # Hash password
        hashed_password = hash_password(password)
        
        # Generate user ID
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        
        # Insert new user
        insert_query = "INSERT INTO users (id, name, email, role, password) VALUES (?, ?, ?, ?, ?)"
        result = execute_query(insert_query, (user_id, name, email, role, hashed_password))
        
        if result is True:
            user_data = {
                "id": user_id,
                "name": name,
                "email": email,
                "role": role
            }
            
            return jsonify({
                "status": "success",
                "message": "User created successfully",
                "user": user_data
            }), 201
        else:
            return jsonify({"status": "error", "message": "Failed to create user"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
# -------------------------
# Faculty API Endpoints
# -------------------------

@app.route('/faculty/profile', methods=['GET'])
@require_auth
def get_faculty_profile():
    """Get faculty profile information"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get faculty ID from token (for demo, use first faculty)
        c.execute("SELECT * FROM users WHERE role = 'faculty' LIMIT 1")
        faculty = c.fetchone()
        
        if faculty:
            faculty_data = {
                'id': faculty[0],
                'name': faculty[1],
                'email': faculty[2],
                'role': faculty[3],
                'department': 'Computer Science',  # Default for demo
                'weekly_hours': 25,  # Default for demo
                'leave_balance': 15  # Default for demo
            }
            conn.close()
            return jsonify(faculty_data)
        else:
            conn.close()
            return jsonify({'error': 'Faculty not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/faculty/subjects-batches', methods=['GET'])
@require_auth
def get_faculty_subjects_batches():
    """Get subjects and batches assigned to faculty"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get subjects
        c.execute("SELECT * FROM subjects")
        subjects = c.fetchall()
        subjects_data = []
        for subject in subjects:
            subjects_data.append({
                'id': subject[0],
                'name': subject[1],
                'code': subject[2],
                'credits': subject[3],
                'weekly_hours': subject[4] if len(subject) > 4 else 4,
                'type': subject[5] if len(subject) > 5 else 'theory'
            })
        
        # Get batches
        c.execute("SELECT * FROM batches")
        batches = c.fetchall()
        batches_data = []
        for batch in batches:
            batches_data.append({
                'id': batch[0],
                'name': batch[1],
                'strength': batch[2],
                'semester': batch[3] if len(batch) > 3 else 3,
                'department': batch[4] if len(batch) > 4 else 'Computer Science'
            })
        
        conn.close()
        return jsonify({
            'subjects': subjects_data,
            'batches': batches_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/faculty/timetable', methods=['GET'])
@require_auth
def get_faculty_timetable():
    """Get faculty timetable"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get timetable slots for faculty
        c.execute("""
            SELECT ts.day, ts.time_slot, s.name as subject, b.name as batch, c.name as classroom
            FROM timetable_slots ts
            JOIN subjects s ON ts.subject_id = s.id
            JOIN batches b ON ts.batch_id = b.id
            JOIN classrooms c ON ts.classroom_id = c.id
            WHERE ts.faculty_id = (SELECT id FROM users WHERE role = 'faculty' LIMIT 1)
            ORDER BY ts.day, ts.time_slot
        """)
        
        timetable = c.fetchall()
        timetable_data = []
        for slot in timetable:
            timetable_data.append({
                'day': slot[0],
                'time': slot[1],
                'subject': slot[2],
                'batch': slot[3],
                'classroom': slot[4]
            })
        
        conn.close()
        return jsonify(timetable_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/faculty/leave-request', methods=['POST'])
@require_auth
def submit_leave_request():
    """Submit a leave request"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['type', 'start_date', 'end_date', 'reason']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # For demo purposes, just return success
        # In a real application, you would save this to a leave_requests table
        return jsonify({
            'message': 'Leave request submitted successfully',
            'request_id': str(uuid.uuid4()),
            'status': 'pending'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/faculty/availability', methods=['GET', 'POST'])
@require_auth
def manage_faculty_availability():
    """Get or update faculty availability"""
    if request.method == 'GET':
        try:
            # For demo purposes, return default availability
            availability = {
                'Monday': ['09:00-10:00', '10:00-11:00', '11:00-12:00', '14:00-15:00', '15:00-16:00'],
                'Tuesday': ['09:00-10:00', '10:00-11:00', '11:00-12:00', '14:00-15:00', '15:00-16:00'],
                'Wednesday': ['09:00-10:00', '10:00-11:00', '11:00-12:00', '14:00-15:00', '15:00-16:00'],
                'Thursday': ['09:00-10:00', '10:00-11:00', '11:00-12:00', '14:00-15:00', '15:00-16:00'],
                'Friday': ['09:00-10:00', '10:00-11:00', '11:00-12:00', '14:00-15:00', '15:00-16:00'],
                'Saturday': ['09:00-10:00', '10:00-11:00', '11:00-12:00'],
                'Sunday': []
            }
            return jsonify(availability)
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            # For demo purposes, just return success
            # In a real application, you would save this to a faculty_availability table
            return jsonify({
                'message': 'Availability updated successfully',
                'availability': data
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# -------------------------
# Error Handlers
# -------------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Route not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"status": "error", "message": "Method not allowed"}), 405

@app.errorhandler(500)
def server_error(e):
    return jsonify({"status": "error", "message": "Server error"}), 500

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
