import requests
import hashlib

BASE_URL = "http://127.0.0.1:5000"

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

# Data to populate
data = {
  "classrooms": [
    { "id": "C1", "name": "SPS1", "capacity": 60, "type": "lecture" },
    { "id": "C2", "name": "SPS2", "capacity": 60, "type": "lecture" },
    { "id": "C3", "name": "SPS3", "capacity": 50, "type": "lab" },
    { "id": "C4", "name": "SPS4", "capacity": 50, "type": "lecture" }
  ],
  "batches": [
    { "id": "B1", "name": "ME1", "department": "Mechanical", "size": 55, "type": "UG" },
    { "id": "B2", "name": "ME2", "department": "Mechanical", "size": 52, "type": "UG" },
    { "id": "B3", "name": "ME3", "department": "Mechanical", "size": 58, "type": "UG" },
    { "id": "B4", "name": "ME4", "department": "Mechanical", "size": 60, "type": "UG" }
  ],
  "teachers": [
    { "id": "T1", "name": "Dr. Arjun Mehta" },
    { "id": "T2", "name": "Prof. Kavita Sharma" },
    { "id": "T3", "name": "Dr. Rakesh Verma" },
    { "id": "T4", "name": "Prof. Neha Singh" },
    { "id": "T5", "name": "Dr. Aman Kapoor" },
    { "id": "T6", "name": "Prof. Sunita Rao" },
    { "id": "T7", "name": "Dr. Rajesh Kumar" },
    { "id": "T8", "name": "Prof. Meera Joshi" },
    { "id": "T9", "name": "Dr. Vikas Nair" },
    { "id": "T10", "name": "Prof. Pooja Malhotra" }
  ],
  "subjects": [
    { "id": "S1", "name": "Thermodynamics", "credits": 4, "weekly_hours": 4, "department": "Mechanical" },
    { "id": "S2", "name": "Fluid Mechanics", "credits": 4, "weekly_hours": 3, "department": "Mechanical" },
    { "id": "S3", "name": "Machine Design", "credits": 4, "weekly_hours": 3, "department": "Mechanical" },
    { "id": "S4", "name": "Engineering Mathematics", "credits": 4, "weekly_hours": 4, "department": "Mathematics" },
    { "id": "S5", "name": "Material Science", "credits": 3, "weekly_hours": 2, "department": "Mechanical" }
  ],
  "faculty_subject_map": [
    { "faculty_id": "T1", "subject_id": "S1", "max_hours_per_week": 8, "avg_leaves_per_month": 2 },
    { "faculty_id": "T2", "subject_id": "S2", "max_hours_per_week": 6, "avg_leaves_per_month": 2 },
    { "faculty_id": "T3", "subject_id": "S3", "max_hours_per_week": 6, "avg_leaves_per_month": 2 },
    { "faculty_id": "T4", "subject_id": "S4", "max_hours_per_week": 8, "avg_leaves_per_month": 2 },
    { "faculty_id": "T5", "subject_id": "S5", "max_hours_per_week": 4, "avg_leaves_per_month": 1 },
    { "faculty_id": "T6", "subject_id": "S1", "max_hours_per_week": 6, "avg_leaves_per_month": 2 },
    { "faculty_id": "T7", "subject_id": "S2", "max_hours_per_week": 6, "avg_leaves_per_month": 2 },
    { "faculty_id": "T8", "subject_id": "S3", "max_hours_per_week": 6, "avg_leaves_per_month": 2 },
    { "faculty_id": "T9", "subject_id": "S4", "max_hours_per_week": 6, "avg_leaves_per_month": 2 },
    { "faculty_id": "T10", "subject_id": "S5", "max_hours_per_week": 4, "avg_leaves_per_month": 1 }
  ]
}
def safe_print(label, response):
    try:
        print(label, response.json())
    except Exception:
        print(label, "RAW:", response.status_code, response.text)

def populate():
    # Classrooms
    for c in data["classrooms"]:
        r = requests.post(f"{BASE_URL}/create/classrooms", json=c)
        safe_print("Classroom:", r)

    # Batches
    for b in data["batches"]:
        r = requests.post(f"{BASE_URL}/create/batches", json=b)
        safe_print("Batch:", r)

    # Teachers -> insert into Users with role=faculty
    for t in data["teachers"]:
        payload = {
            "id": t["id"],
            "name": t["name"],
            "email": f"{t['id'].lower()}@univ.edu",
            "role": "faculty",
            "password": hash_password("password123")  # Default password for all teachers
        }
        r = requests.post(f"{BASE_URL}/create/users", json=payload)
        safe_print("Teacher (User):", r)

    # Subjects
    for s in data["subjects"]:
        r = requests.post(f"{BASE_URL}/create/subjects", json=s)
        safe_print("Subject:", r)

    # Faculty-Subject Map
    for fs in data["faculty_subject_map"]:
        r = requests.post(f"{BASE_URL}/create/faculty_subject_map", json=fs)
        safe_print("Faculty-Subject Map:", r)

    # Add demo admin user
    admin_payload = {
        "id": "admin_001",
        "name": "Admin User",
        "email": "admin@univ.edu",
        "role": "admin",
        "password": hash_password("admin123")
    }
    r = requests.post(f"{BASE_URL}/create/users", json=admin_payload)
    safe_print("Admin User:", r)

    # Add demo student user
    student_payload = {
        "id": "student_001",
        "name": "Demo Student",
        "email": "student@univ.edu",
        "role": "student",
        "password": hash_password("student123")
    }
    r = requests.post(f"{BASE_URL}/create/users", json=student_payload)
    safe_print("Student User:", r)

    # Add demo faculty user
    faculty_payload = {
        "id": "faculty_001",
        "name": "Dr. John Smith",
        "email": "faculty@univ.edu",
        "role": "faculty",
        "password": hash_password("faculty123")
    }
    r = requests.post(f"{BASE_URL}/create/users", json=faculty_payload)
    safe_print("Faculty User:", r)

populate()