from flask import Flask, request, jsonify
import sqlite3
import uuid
import hashlib
import secrets
from flask_cors import CORS
from flask import render_template_string
from functools import wraps
import requests
from typing import Dict, List, Optional
from collections import defaultdict

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

    # Attendance Records
    c.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id TEXT PRIMARY KEY,
        student_id TEXT,
        faculty_id TEXT,
        subject_id TEXT,
        batch_id TEXT,
        date TEXT,
        time_slot TEXT,
        status TEXT CHECK(status IN ('present','absent','late')),
        remarks TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(faculty_id) REFERENCES users(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id),
        FOREIGN KEY(batch_id) REFERENCES batches(id)
    )
    """)

    # Student-Batch Mapping
    c.execute("""
    CREATE TABLE IF NOT EXISTS student_batch_map (
        student_id TEXT,
        batch_id TEXT,
        roll_number TEXT,
        semester INTEGER,
        PRIMARY KEY (student_id, batch_id),
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(batch_id) REFERENCES batches(id)
    )
    """)

    # Student-Subject Mapping
    c.execute("""
    CREATE TABLE IF NOT EXISTS student_subject_map (
        student_id TEXT,
        subject_id TEXT,
        enrollment_date TEXT,
        PRIMARY KEY (student_id, subject_id),
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(subject_id) REFERENCES subjects(id)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------
# Timetable API Integration
# -------------------------
class TimetableAPI:
    def __init__(self, api_base_url="http://localhost:5000"):
        self.api_base_url = api_base_url
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        self.time_slots = [
            "9:00-10:00", "10:00-11:00", "11:00-12:00", "12:00-13:00", 
            "13:00-14:00", "14:00-15:00", "15:00-16:00"
        ]
        
        # Data storage
        self.users = {}
        self.classrooms = {}
        self.subjects = {}
        self.faculty_subject_map = {}
        self.batches = {}
        
    def fetch_data(self):
        """Fetch all necessary data from the API"""
        try:
            # Fetch users (filter for faculty)
            users_response = requests.get(f"{self.api_base_url}/read/users")
            if users_response.status_code == 200:
                for user in users_response.json():
                    if user['role'] == 'faculty':
                        self.users[user['id']] = user
            
            # Fetch classrooms
            classrooms_response = requests.get(f"{self.api_base_url}/read/classrooms")
            if classrooms_response.status_code == 200:
                for classroom in classrooms_response.json():
                    self.classrooms[classroom['id']] = classroom
            
            # Fetch subjects
            subjects_response = requests.get(f"{self.api_base_url}/read/subjects")
            if subjects_response.status_code == 200:
                for subject in subjects_response.json():
                    self.subjects[subject['id']] = subject
            
            # Fetch faculty-subject mapping
            faculty_subject_response = requests.get(f"{self.api_base_url}/read/faculty_subject_map")
            if faculty_subject_response.status_code == 200:
                for mapping in faculty_subject_response.json():
                    faculty_id = mapping['faculty_id']
                    if faculty_id not in self.faculty_subject_map:
                        self.faculty_subject_map[faculty_id] = []
                    self.faculty_subject_map[faculty_id].append(mapping)
            
            # Fetch batches
            batches_response = requests.get(f"{self.api_base_url}/read/batches")
            if batches_response.status_code == 200:
                for batch in batches_response.json():
                    self.batches[batch['id']] = batch
            
            return True
        except Exception as e:
            print(f"Error fetching data: {e}")
            return False
    
    def get_faculty_subjects(self, faculty_id: str) -> List[str]:
        if faculty_id in self.faculty_subject_map:
            return [mapping['subject_id'] for mapping in self.faculty_subject_map[faculty_id]]
        return []
    
    def get_subject_faculty(self, subject_id: str) -> List[str]:
        faculty_list: List[str] = []
        for faculty_id, mappings in self.faculty_subject_map.items():
            for mapping in mappings:
                if mapping['subject_id'] == subject_id:
                    faculty_list.append(faculty_id)
        return faculty_list
    
    def get_faculty_subject_max_hours(self, faculty_id: str, subject_id: str) -> int:
        """Return max_hours_per_week for given (faculty, subject) from faculty_subject_map if present, else a large number."""
        mappings = self.faculty_subject_map.get(faculty_id, [])
        for m in mappings:
            if m.get('subject_id') == subject_id:
                return int(m.get('max_hours_per_week', 10**6))
        return 10**6
    
    def get_subjects_for_batch(self, batch_id: str) -> List[str]:
        batch_dept = self.batches[batch_id]['department']
        return [subj_id for subj_id, subject in self.subjects.items() if subject['department'] == batch_dept]
    
    def _is_classroom_available_local(self, slots: List[Dict], classroom_id: str, day: str, time_slot: str) -> bool:
        for slot in slots:
            if slot['classroom_id'] == classroom_id and slot['day'] == day and slot['time'] == time_slot:
                return False
        return True
    
    def _is_faculty_available_local(self, slots: List[Dict], faculty_id: str, day: str, time_slot: str) -> bool:
        for slot in slots:
            if slot['faculty_id'] == faculty_id and slot['day'] == day and slot['time'] == time_slot:
                return False
        return True
    
    def _is_batch_available_local(self, slots: List[Dict], batch_id: str, day: str, time_slot: str) -> bool:
        for slot in slots:
            if slot['batch_id'] == batch_id and slot['day'] == day and slot['time'] == time_slot:
                return False
        return True
    
    def _get_available_classrooms_local(self, slots: List[Dict], day: str, time_slot: str, subject_type: str = None) -> List[str]:
        available: List[str] = []
        for classroom_id, classroom in self.classrooms.items():
            if subject_type and classroom['type'] != subject_type:
                continue
            if self._is_classroom_available_local(slots, classroom_id, day, time_slot):
                available.append(classroom_id)
        return available
    
    def generate_in_memory_timetable(self) -> List[Dict]:
        """Generate a full timetable in-memory without touching timetable_slots table."""
        # Ensure base data is loaded
        if not self.fetch_data():
            return []
        
        generated_slots: List[Dict] = []
        # Track scheduled hours per batch per subject
        scheduled_hours: Dict[str, Dict[str, int]] = {}
        # Track scheduled hours per (faculty, subject)
        faculty_subject_hours: Dict[str, int] = {}
        for batch_id in self.batches.keys():
            scheduled_hours[batch_id] = {subj_id: 0 for subj_id in self.subjects.keys()}
        
        # For each batch, schedule its subjects based on weekly_hours
        import random
        for batch_id, batch in self.batches.items():
            subject_ids = self.get_subjects_for_batch(batch_id)
            if not subject_ids:
                continue
            # Flat list with subject repeated weekly_hours times
            subjects_to_schedule: List[str] = []
            for subject_id in subject_ids:
                subjects_to_schedule.extend([subject_id] * self.subjects[subject_id]['weekly_hours'])
            random.shuffle(subjects_to_schedule)
            
            for subject_id in subjects_to_schedule:
                faculty_options = self.get_subject_faculty(subject_id)
                if not faculty_options:
                    continue
                scheduled = False
                attempts = 0
                max_attempts = 200
                while not scheduled and attempts < max_attempts:
                    attempts += 1
                    day = random.choice(self.days)
                    time_slot = random.choice(self.time_slots)
                    # batch availability
                    if not self._is_batch_available_local(generated_slots, batch_id, day, time_slot):
                        continue
                    # faculty availability
                    available_faculty = []
                    for faculty_id in faculty_options:
                        if not self._is_faculty_available_local(generated_slots, faculty_id, day, time_slot):
                            continue
                        # respect per (faculty, subject) max_hours_per_week
                        key = f"{faculty_id}::{subject_id}"
                        current_fs_hours = faculty_subject_hours.get(key, 0)
                        max_fs_hours = self.get_faculty_subject_max_hours(faculty_id, subject_id)
                        if current_fs_hours >= max_fs_hours:
                            continue
                        available_faculty.append(faculty_id)
                    if not available_faculty:
                        continue
                    # classroom availability
                    subject_obj = self.subjects[subject_id]
                    subject_type = 'lab' if 'lab' in subject_obj['name'].lower() else 'lecture'
                    available_classrooms = self._get_available_classrooms_local(generated_slots, day, time_slot, subject_type)
                    if not available_classrooms:
                        continue
                    # choose
                    faculty_id = random.choice(available_faculty)
                    classroom_id = random.choice(available_classrooms)
                    slot = {
                        'id': f"{batch_id}_{subject_id}_{day}_{time_slot.replace(':', '')}",
                        'day': day,
                        'time': time_slot,
                        'classroom_id': classroom_id,
                        'subject_id': subject_id,
                        'faculty_id': faculty_id,
                        'batch_id': batch_id
                    }
                    generated_slots.append(slot)
                    scheduled_hours[batch_id][subject_id] += 1
                    fs_key = f"{faculty_id}::{subject_id}"
                    faculty_subject_hours[fs_key] = faculty_subject_hours.get(fs_key, 0) + 1
                    scheduled = True
        return generated_slots

    def validate_generated_slots(self, generated_slots: List[Dict]) -> Dict:
        """Compute validation for batches, faculty, and classrooms based on generated slots."""
        # Constants
        max_daily_slots = len(self.time_slots)
        max_weekly_slots = len(self.days) * max_daily_slots
        max_faculty_hours = 30  # default policy

        # Precompute counters
        batch_subject_hours: Dict[str, Dict[str, int]] = {}
        batch_total_hours: Dict[str, int] = {}
        faculty_hours: Dict[str, int] = {}
        classroom_usage: Dict[str, int] = {}

        for batch_id in self.batches.keys():
            batch_subject_hours[batch_id] = {subj_id: 0 for subj_id in self.subjects.keys()}
            batch_total_hours[batch_id] = 0
        for faculty_id in self.users.keys():
            faculty_hours[faculty_id] = 0
        for classroom_id in self.classrooms.keys():
            classroom_usage[classroom_id] = 0

        for slot in generated_slots:
            b = slot['batch_id']
            s = slot['subject_id']
            f = slot['faculty_id']
            c = slot['classroom_id']
            if b in batch_subject_hours:
                if s in batch_subject_hours[b]:
                    batch_subject_hours[b][s] += 1
                batch_total_hours[b] += 1
            if f in faculty_hours:
                faculty_hours[f] += 1
            if c in classroom_usage:
                classroom_usage[c] += 1

        # Build validations
        validations = {
            'batches': {},
            'faculty': {},
            'classrooms': {}
        }

        # Precompute per (faculty, subject) assigned hours to estimate remaining capacity
        per_faculty_subject_assigned: Dict[str, Dict[str, int]] = {}
        for slot in generated_slots:
            f = slot['faculty_id']
            s = slot['subject_id']
            if f not in per_faculty_subject_assigned:
                per_faculty_subject_assigned[f] = {}
            per_faculty_subject_assigned[f][s] = per_faculty_subject_assigned[f].get(s, 0) + 1

        # Batch validations
        for batch_id, batch in self.batches.items():
            errors: List[str] = []
            suggestions: List[str] = []
            # Subject weekly requirements
            for subject_id in self.get_subjects_for_batch(batch_id):
                required = self.subjects[subject_id]['weekly_hours']
                scheduled = batch_subject_hours[batch_id][subject_id]
                if scheduled != required:
                    errors.append(f"Subject {self.subjects[subject_id]['name']}: {scheduled}/{required} hours")
                    if scheduled < required:
                        deficit = required - scheduled
                        # Estimate remaining qualified faculty capacity for this subject
                        qualified = [m['faculty_id'] for m in sum((self.faculty_subject_map.get(fid, []) for fid in self.faculty_subject_map.keys()), []) if m.get('subject_id') == subject_id]
                        # Fall back if above comprehension is too convoluted
                        if not qualified:
                            qualified = [fid for fid, maps in self.faculty_subject_map.items() for m in maps if m.get('subject_id') == subject_id]
                        remaining_capacity = 0
                        seen = set()
                        for fid, maps in self.faculty_subject_map.items():
                            for m in maps:
                                if m.get('subject_id') == subject_id and fid not in seen:
                                    seen.add(fid)
                                    max_h = int(m.get('max_hours_per_week', 0))
                                    assigned = per_faculty_subject_assigned.get(fid, {}).get(subject_id, 0)
                                    remaining_capacity += max(0, max_h - assigned)
                        subject_type = 'lab' if 'lab' in self.subjects[subject_id]['name'].lower() else 'lecture'
                        type_rooms = [cid for cid, c in self.classrooms.items() if c['type'] == subject_type]
                        suggestions.append(f"Schedule additional {deficit} hour(s) for {self.subjects[subject_id]['name']}.")
                        if remaining_capacity < deficit:
                            suggestions.append("Add new qualified faculty for this subject or increase max_hours_per_week for existing qualified faculty.")
                        else:
                            suggestions.append("Reassign this subject's hours to qualified faculty with remaining capacity.")
                        if not type_rooms:
                            suggestions.append(f"Add new {subject_type} classrooms to accommodate this subject.")
                        suggestions.append("Extend working hours or add time slots to fit remaining classes.")
                    else:
                        suggestions.extend([
                            f"Reduce allocation by {scheduled - required} hour(s) for {self.subjects[subject_id]['name']}.",
                            "Verify subject weekly_hours configuration.",
                            "Consolidate duplicate or conflicting entries."
                        ])
            # Capacity vs required total
            required_total = sum(self.subjects[sid]['weekly_hours'] for sid in self.get_subjects_for_batch(batch_id))
            if required_total > max_weekly_slots:
                errors.append(f"Required total hours {required_total} exceed available weekly slots {max_weekly_slots}")
                suggestions.extend([
                    "Reduce weekly_hours for some subjects or split across terms.",
                    "Add additional time slots per day or extend working hours.",
                    "Increase resource capacity (more classrooms or parallel sessions)."
                ])
            validations['batches'][batch_id] = {
                'status': 'OK' if not errors else 'ERROR',
                'errors': errors,
                'suggestions': suggestions,
                'scheduled_total_hours': batch_total_hours[batch_id],
                'required_total_hours': required_total,
                'max_weekly_slots': max_weekly_slots
            }

        # Faculty validations
        for faculty_id, user in self.users.items():
            if user.get('role') != 'faculty':
                continue
            errors: List[str] = []
            suggestions: List[str] = []
            hours = faculty_hours[faculty_id]
            if hours > max_faculty_hours:
                errors.append(f"Assigned {hours} hours exceeds max_weekly_hours {max_faculty_hours}")
                suggestions.extend([
                    "Reassign some classes to other qualified faculty.",
                    "Add new faculty for overloaded subjects.",
                    f"Increase this faculty's max_weekly_hours above {max_faculty_hours} if policy allows."
                ])
            # Per subject limits from faculty_subject_map
            # Compute actual per-subject hours for this faculty
            per_subject: Dict[str, int] = {}
            for slot in generated_slots:
                if slot['faculty_id'] == faculty_id:
                    sid = slot['subject_id']
                    per_subject[sid] = per_subject.get(sid, 0) + 1
            # Compare against mapping max_hours_per_week
            for m in self.faculty_subject_map.get(faculty_id, []):
                sid = m.get('subject_id')
                max_h = int(m.get('max_hours_per_week', 10**6))
                actual = per_subject.get(sid, 0)
                if actual > max_h:
                    errors.append(f"Subject {self.subjects.get(sid, {}).get('name', sid)}: {actual} exceeds max_hours_per_week {max_h}")
                    suggestions.extend([
                        "Reassign some hours of this subject to other qualified faculty.",
                        "Add new qualified faculty for this subject.",
                        "Increase max_hours_per_week for this faculty on this subject."
                    ])
            validations['faculty'][faculty_id] = {
                'status': 'OK' if not errors else 'ERROR',
                'errors': errors,
                'suggestions': suggestions,
                'assigned_hours': hours,
                'max_weekly_hours': max_faculty_hours
            }

        # Classroom validations
        for classroom_id, classroom in self.classrooms.items():
            errors: List[str] = []
            suggestions: List[str] = []
            usage = classroom_usage[classroom_id]
            if usage > max_weekly_slots:
                errors.append(f"Usage {usage} exceeds max weekly slots {max_weekly_slots}")
                suggestions.extend([
                    "Distribute classes to other available classrooms.",
                    "Add new classrooms of the required type.",
                    "Extend working hours or add time slots."
                ])
            validations['classrooms'][classroom_id] = {
                'status': 'OK' if not errors else 'ERROR',
                'errors': errors,
                'suggestions': suggestions,
                'usage_hours': usage,
                'max_weekly_slots': max_weekly_slots
            }

        return validations
    
    def fetch_timetable_slots(self):
        """Fetch fresh timetable slots from the API"""
        try:
            timetable_response = requests.get(f"{self.api_base_url}/read/timetable_slots")
            if timetable_response.status_code == 200:
                return timetable_response.json()
            return []
        except Exception as e:
            print(f"Error fetching timetable slots: {e}")
            return []

    def delete_all_timetable_slots(self) -> int:
        """Delete all timetable slots from the API. Returns number deleted."""
        deleted = 0
        try:
            existing = self.fetch_timetable_slots()
            for slot in existing:
                sid = slot.get('id')
                if not sid:
                    continue
                try:
                    resp = requests.delete(f"{self.api_base_url}/delete/timetable_slots/{sid}")
                    if resp.status_code in (200, 204):
                        deleted += 1
                except Exception:
                    pass
        except Exception as e:
            print(f"Error deleting timetable slots: {e}")
        return deleted

    def save_slots_to_db(self, slots: List[Dict]) -> int:
        """Save generated slots to the timetable_slots table. Returns number saved."""
        saved = 0
        for slot in slots:
            try:
                resp = requests.post(f"{self.api_base_url}/create/timetable_slots", json=slot)
                if resp.status_code in (200, 201):
                    saved += 1
            except Exception as e:
                print(f"Failed to save slot {slot.get('id')}: {e}")
        return saved
    
    def get_batch_timetable_json(self, batch_id: str) -> Dict:
        """Get timetable for a specific batch in JSON format"""
        if not self.fetch_data():
            return {"error": "Failed to fetch data from API"}
        
        if batch_id not in self.batches:
            return {"error": f"Batch with ID {batch_id} not found"}
        
        # Prefer locked DB timetable if present; fallback to generation
        db_slots = self.fetch_timetable_slots()
        timetable_slots = db_slots if db_slots else self.generate_in_memory_timetable()
        validations = self.validate_generated_slots(timetable_slots)
        
        batch = self.batches[batch_id]
        timetable = {day: {time_slot: [] for time_slot in self.time_slots} for day in self.days}
        
        # Find all classes for this batch
        for slot in timetable_slots:
            if slot['batch_id'] == batch_id:
                day = slot['day']
                time_slot = slot['time']
                
                class_info = {
                    "subject_id": slot['subject_id'],
                    "subject_name": self.subjects[slot['subject_id']]['name'],
                    "faculty_id": slot['faculty_id'],
                    "faculty_name": self.users[slot['faculty_id']]['name'],
                    "classroom_id": slot['classroom_id'],
                    "classroom_name": self.classrooms[slot['classroom_id']]['name'],
                    "classroom_type": self.classrooms[slot['classroom_id']]['type']
                }
                
                timetable[day][time_slot].append(class_info)
        
        return {
            "batch_id": batch_id,
            "batch_name": batch['name'],
            "department": batch['department'],
            "timetable": timetable,
            "days": self.days,
            "time_slots": self.time_slots,
            "validation": validations['batches'].get(batch_id, {})
        }
    
    def get_classroom_timetable_json(self, classroom_id: str) -> Dict:
        """Get timetable for a specific classroom in JSON format"""
        if not self.fetch_data():
            return {"error": "Failed to fetch data from API"}
        
        if classroom_id not in self.classrooms:
            return {"error": f"Classroom with ID {classroom_id} not found"}
        
        # Prefer locked DB timetable if present; fallback to generation
        db_slots = self.fetch_timetable_slots()
        timetable_slots = db_slots if db_slots else self.generate_in_memory_timetable()
        validations = self.validate_generated_slots(timetable_slots)
        
        classroom = self.classrooms[classroom_id]
        timetable = {day: {time_slot: [] for time_slot in self.time_slots} for day in self.days}
        
        # Find all classes in this classroom
        for slot in timetable_slots:
            if slot['classroom_id'] == classroom_id:
                day = slot['day']
                time_slot = slot['time']
                
                class_info = {
                    "subject_id": slot['subject_id'],
                    "subject_name": self.subjects[slot['subject_id']]['name'],
                    "faculty_id": slot['faculty_id'],
                    "faculty_name": self.users[slot['faculty_id']]['name'],
                    "batch_id": slot['batch_id'],
                    "batch_name": self.batches[slot['batch_id']]['name']
                }
                
                timetable[day][time_slot].append(class_info)
        
        return {
            "classroom_id": classroom_id,
            "classroom_name": classroom['name'],
            "classroom_type": classroom['type'],
            "timetable": timetable,
            "days": self.days,
            "time_slots": self.time_slots,
            "validation": validations['classrooms'].get(classroom_id, {})
        }
    
    def get_faculty_timetable_json(self, faculty_id: str) -> Dict:
        """Get timetable for a specific faculty in JSON format"""
        if not self.fetch_data():
            return {"error": "Failed to fetch data from API"}
        
        if faculty_id not in self.users or self.users[faculty_id]['role'] != 'faculty':
            return {"error": f"Faculty with ID {faculty_id} not found"}
        
        # Prefer locked DB timetable if present; fallback to generation
        db_slots = self.fetch_timetable_slots()
        timetable_slots = db_slots if db_slots else self.generate_in_memory_timetable()
        validations = self.validate_generated_slots(timetable_slots)
        
        faculty = self.users[faculty_id]
        timetable = {day: {time_slot: [] for time_slot in self.time_slots} for day in self.days}
        
        # Find all classes taught by this faculty
        for slot in timetable_slots:
            if slot['faculty_id'] == faculty_id:
                day = slot['day']
                time_slot = slot['time']
                
                class_info = {
                    "subject_id": slot['subject_id'],
                    "subject_name": self.subjects[slot['subject_id']]['name'],
                    "batch_id": slot['batch_id'],
                    "batch_name": self.batches[slot['batch_id']]['name'],
                    "classroom_id": slot['classroom_id'],
                    "classroom_name": self.classrooms[slot['classroom_id']]['name'],
                    "classroom_type": self.classrooms[slot['classroom_id']]['type']
                }
                
                timetable[day][time_slot].append(class_info)
        
        return {
            "faculty_id": faculty_id,
            "faculty_name": faculty['name'],
            "timetable": timetable,
            "days": self.days,
            "time_slots": self.time_slots,
            "validation": validations['faculty'].get(faculty_id, {})
        }
    
    def get_all_timetables_json(self) -> Dict:
        """Get all timetables in JSON format"""
        if not self.fetch_data():
            return {"error": "Failed to fetch data from API"}
        
        # Prefer locked DB timetable if present; fallback to generation
        db_slots = self.fetch_timetable_slots()
        timetable_slots = db_slots if db_slots else self.generate_in_memory_timetable()
        validations = self.validate_generated_slots(timetable_slots)
        
        result = {
            "batches": {},
            "classrooms": {},
            "faculty": {},
            "days": self.days,
            "time_slots": self.time_slots,
            "validation_summary": validations
        }
        
        # Build per-entity views from the one generated list
        # Batches
        for batch_id, batch in self.batches.items():
            timetable = {day: {time_slot: [] for time_slot in self.time_slots} for day in self.days}
            for slot in timetable_slots:
                if slot['batch_id'] == batch_id:
                    day = slot['day']
                    time_slot = slot['time']
                    timetable[day][time_slot].append({
                        "subject_id": slot['subject_id'],
                        "subject_name": self.subjects[slot['subject_id']]['name'],
                        "faculty_id": slot['faculty_id'],
                        "faculty_name": self.users[slot['faculty_id']]['name'],
                        "classroom_id": slot['classroom_id'],
                        "classroom_name": self.classrooms[slot['classroom_id']]['name'],
                        "classroom_type": self.classrooms[slot['classroom_id']]['type']
                    })
            result["batches"][batch_id] = {
                "batch_id": batch_id,
                "batch_name": batch['name'],
                "department": batch['department'],
                "timetable": timetable,
                "days": self.days,
                "time_slots": self.time_slots,
                "validation": validations['batches'].get(batch_id, {})
            }
        
        # Classrooms
        for classroom_id, classroom in self.classrooms.items():
            timetable = {day: {time_slot: [] for time_slot in self.time_slots} for day in self.days}
            for slot in timetable_slots:
                if slot['classroom_id'] == classroom_id:
                    day = slot['day']
                    time_slot = slot['time']
                    timetable[day][time_slot].append({
                        "subject_id": slot['subject_id'],
                        "subject_name": self.subjects[slot['subject_id']]['name'],
                        "faculty_id": slot['faculty_id'],
                        "faculty_name": self.users[slot['faculty_id']]['name'],
                        "batch_id": slot['batch_id'],
                        "batch_name": self.batches[slot['batch_id']]['name']
                    })
            result["classrooms"][classroom_id] = {
                "classroom_id": classroom_id,
                "classroom_name": classroom['name'],
                "classroom_type": classroom['type'],
                "timetable": timetable,
                "days": self.days,
                "time_slots": self.time_slots,
                "validation": validations['classrooms'].get(classroom_id, {})
            }
        
        # Faculty
        for faculty_id, faculty in self.users.items():
            if faculty['role'] != 'faculty':
                continue
            timetable = {day: {time_slot: [] for time_slot in self.time_slots} for day in self.days}
            for slot in timetable_slots:
                if slot['faculty_id'] == faculty_id:
                    day = slot['day']
                    time_slot = slot['time']
                    timetable[day][time_slot].append({
                        "subject_id": slot['subject_id'],
                        "subject_name": self.subjects[slot['subject_id']]['name'],
                        "batch_id": slot['batch_id'],
                        "batch_name": self.batches[slot['batch_id']]['name'],
                        "classroom_id": slot['classroom_id'],
                        "classroom_name": self.classrooms[slot['classroom_id']]['name'],
                        "classroom_type": self.classrooms[slot['classroom_id']]['type']
                    })
            result["faculty"][faculty_id] = {
                "faculty_id": faculty_id,
                "faculty_name": faculty['name'],
                "timetable": timetable,
                "days": self.days,
                "time_slots": self.time_slots,
                "validation": validations['faculty'].get(faculty_id, {})
            }
        
        return result

# Initialize timetable API
timetable_api = TimetableAPI()

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
        "version": "2.0.0",
        "endpoints": {
            "authentication": ["/login", "/register"],
            "crud": ["/create/<table>", "/read/<table>", "/update/<table>/<id>", "/delete/<table>/<id>"],
            "data": ["/show_all", "/table_all"],
            "student": ["/student/profile", "/student/timetable", "/student/attendance", "/student/assignments", "/student/grades", "/student/notifications", "/student/dashboard-stats"],
            "faculty": ["/faculty/profile", "/faculty/timetable", "/faculty/students", "/faculty/leave-request", "/faculty/availability"],
            "attendance": ["/attendance", "/attendance/bulk", "/attendance/history", "/attendance/analytics"],
            "timetable": ["/timetable/batch/<batch_id>", "/timetable/faculty/<faculty_id>", "/timetable/all", "/timetable/regenerate", "/timetable/validation", "/timetable/entities", "/timetable/health"]
        },
        "features": {
            "advanced_timetable_generation": True,
            "constraint_based_scheduling": True,
            "comprehensive_validation": True,
            "error_analysis_and_suggestions": True,
            "real_time_timetable_updates": True
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
    tables = ["users", "classrooms", "subjects", "faculty_subject_map", "batches", "timetable_slots", "attendance", "student_batch_map", "student_subject_map"]
    all_data = {}
    for table in tables:
        result = execute_query(f"SELECT * FROM {table}", fetch=True)
        all_data[table] = result if isinstance(result, list) else {"error": result}
    return jsonify(all_data)

@app.route("/table_all", methods=["GET"])
def table_all():
    tables = ["users", "classrooms", "subjects", "faculty_subject_map", "batches", "timetable_slots", "attendance", "student_batch_map", "student_subject_map"]
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
# Student Management API Endpoints
# -------------------------

@app.route('/faculty/students', methods=['GET'])
@require_auth
def get_faculty_students():
    """Get all students for faculty management"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get students with their batch and subject information
        c.execute("""
            SELECT 
                u.id, u.name, u.email, u.role,
                sbm.batch_id, b.name as batch_name, sbm.roll_number, sbm.semester,
                GROUP_CONCAT(s.name) as subjects,
                GROUP_CONCAT(s.id) as subject_ids
            FROM users u
            LEFT JOIN student_batch_map sbm ON u.id = sbm.student_id
            LEFT JOIN batches b ON sbm.batch_id = b.id
            LEFT JOIN student_subject_map ssm ON u.id = ssm.student_id
            LEFT JOIN subjects s ON ssm.subject_id = s.id
            WHERE u.role = 'student'
            GROUP BY u.id, sbm.batch_id
        """)
        
        students = c.fetchall()
        students_data = []
        
        for student in students:
            # Calculate attendance percentage
            c.execute("""
                SELECT 
                    COUNT(*) as total_classes,
                    SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_classes
                FROM attendance 
                WHERE student_id = ?
            """, (student[0],))
            
            attendance_data = c.fetchone()
            total_classes = attendance_data[0] if attendance_data[0] else 0
            present_classes = attendance_data[1] if attendance_data[1] else 0
            attendance_percentage = round((present_classes / total_classes * 100), 2) if total_classes > 0 else 0
            
            # Get latest status
            c.execute("""
                SELECT status FROM attendance 
                WHERE student_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (student[0],))
            
            latest_status = c.fetchone()
            current_status = latest_status[0] if latest_status else 'present'
            
            students_data.append({
                'id': student[0],
                'name': student[1],
                'email': student[2],
                'role': student[3],
                'batch': student[5] if student[5] else 'N/A',
                'rollNumber': student[6] if student[6] else 'N/A',
                'semester': student[7] if student[7] else 1,
                'subjects': student[8].split(',') if student[8] else [],
                'attendance': attendance_percentage,
                'status': current_status,
                'phone': f"+1-555-{student[0][-4:]}",  # Demo phone number
                'grade': 'A-' if attendance_percentage >= 90 else 'B+' if attendance_percentage >= 80 else 'B' if attendance_percentage >= 70 else 'C',
                'notes': 'Good student' if attendance_percentage >= 80 else 'Needs improvement'
            })
        
        conn.close()
        return jsonify({'students': students_data})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------
# Attendance API Endpoints
# -------------------------

@app.route('/attendance', methods=['POST'])
@require_auth
def create_attendance():
    """Create attendance record"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['student_id', 'faculty_id', 'subject_id', 'batch_id', 'date', 'time_slot', 'status']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Generate attendance ID
        attendance_id = f"att_{uuid.uuid4().hex[:8]}"
        
        # Insert attendance record
        query = """
            INSERT INTO attendance (id, student_id, faculty_id, subject_id, batch_id, date, time_slot, status, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        values = (
            attendance_id,
            data['student_id'],
            data['faculty_id'],
            data['subject_id'],
            data['batch_id'],
            data['date'],
            data['time_slot'],
            data['status'],
            data.get('remarks', '')
        )
        
        result = execute_query(query, values)
        
        if result is True:
            return jsonify({
                'status': 'success',
                'message': 'Attendance recorded successfully',
                'attendance_id': attendance_id
            }), 201
        else:
            return jsonify({'error': 'Failed to record attendance'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/attendance/bulk', methods=['POST'])
@require_auth
def create_bulk_attendance():
    """Create multiple attendance records at once"""
    try:
        data = request.get_json()
        
        if 'attendance_records' not in data:
            return jsonify({'error': 'Missing attendance_records field'}), 400
        
        attendance_records = data['attendance_records']
        if not isinstance(attendance_records, list):
            return jsonify({'error': 'attendance_records must be a list'}), 400
        
        # Prepare bulk insert data
        bulk_data = []
        for record in attendance_records:
            attendance_id = f"att_{uuid.uuid4().hex[:8]}"
            bulk_data.append((
                attendance_id,
                record['student_id'],
                record['faculty_id'],
                record['subject_id'],
                record['batch_id'],
                record['date'],
                record['time_slot'],
                record['status'],
                record.get('remarks', '')
            ))
        
        # Bulk insert
        query = """
            INSERT INTO attendance (id, student_id, faculty_id, subject_id, batch_id, date, time_slot, status, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        result = execute_query(query, bulk_data, many=True)
        
        if result is True:
            return jsonify({
                'status': 'success',
                'message': f'Bulk attendance recorded successfully for {len(attendance_records)} students',
                'count': len(attendance_records)
            }), 201
        else:
            return jsonify({'error': 'Failed to record bulk attendance'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/attendance/history', methods=['GET'])
@require_auth
def get_attendance_history():
    """Get attendance history with filters"""
    try:
        # Get query parameters
        student_id = request.args.get('student_id')
        subject_id = request.args.get('subject_id')
        batch_id = request.args.get('batch_id')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        
        # Build query
        query = """
            SELECT 
                a.id, a.student_id, a.faculty_id, a.subject_id, a.batch_id,
                a.date, a.time_slot, a.status, a.remarks, a.created_at,
                u.name as student_name, s.name as subject_name, b.name as batch_name
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            JOIN subjects s ON a.subject_id = s.id
            JOIN batches b ON a.batch_id = b.id
            WHERE 1=1
        """
        
        params = []
        
        if student_id:
            query += " AND a.student_id = ?"
            params.append(student_id)
        
        if subject_id:
            query += " AND a.subject_id = ?"
            params.append(subject_id)
            
        if batch_id:
            query += " AND a.batch_id = ?"
            params.append(batch_id)
            
        if from_date:
            query += " AND a.date >= ?"
            params.append(from_date)
            
        if to_date:
            query += " AND a.date <= ?"
            params.append(to_date)
        
        query += " ORDER BY a.date DESC, a.created_at DESC"
        
        result = execute_query(query, tuple(params), fetch=True)
        
        if isinstance(result, list):
            return jsonify({'attendance_history': result})
        else:
            return jsonify({'error': 'Failed to fetch attendance history'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/attendance/analytics', methods=['GET'])
@require_auth
def get_attendance_analytics():
    """Get attendance analytics"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get query parameters
        student_id = request.args.get('student_id')
        subject_id = request.args.get('subject_id')
        batch_id = request.args.get('batch_id')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        
        # Build base query
        base_query = "FROM attendance WHERE 1=1"
        params = []
        
        if student_id:
            base_query += " AND student_id = ?"
            params.append(student_id)
        
        if subject_id:
            base_query += " AND subject_id = ?"
            params.append(subject_id)
            
        if batch_id:
            base_query += " AND batch_id = ?"
            params.append(batch_id)
            
        if from_date:
            base_query += " AND date >= ?"
            params.append(from_date)
            
        if to_date:
            base_query += " AND date <= ?"
            params.append(to_date)
        
        # Get total records
        total_query = f"SELECT COUNT(*) {base_query}"
        c.execute(total_query, params)
        total_records = c.fetchone()[0]
        
        # Get present records
        present_query = f"SELECT COUNT(*) {base_query} AND status = 'present'"
        c.execute(present_query, params)
        present_records = c.fetchone()[0]
        
        # Get absent records
        absent_query = f"SELECT COUNT(*) {base_query} AND status = 'absent'"
        c.execute(absent_query, params)
        absent_records = c.fetchone()[0]
        
        # Get late records
        late_query = f"SELECT COUNT(*) {base_query} AND status = 'late'"
        c.execute(late_query, params)
        late_records = c.fetchone()[0]
        
        # Calculate percentages
        overall_attendance = round((present_records / total_records * 100), 2) if total_records > 0 else 0
        
        analytics = {
            'total_records': total_records,
            'present_records': present_records,
            'absent_records': absent_records,
            'late_records': late_records,
            'overall_attendance': overall_attendance
        }
        
        conn.close()
        return jsonify(analytics)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------
# Student API Endpoints
# -------------------------

@app.route('/student/profile', methods=['GET'])
@require_auth
def get_student_profile():
    """Get student profile information"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get student ID from token (for demo, use first student)
        c.execute("SELECT * FROM users WHERE role = 'student' LIMIT 1")
        student = c.fetchone()
        
        if student:
            # Get additional student information
            c.execute("""
                SELECT sbm.batch_id, b.name as batch_name, sbm.roll_number, sbm.semester
                FROM student_batch_map sbm
                JOIN batches b ON sbm.batch_id = b.id
                WHERE sbm.student_id = ?
            """, (student[0],))
            
            batch_info = c.fetchone()
            
            student_data = {
                'id': student[0],
                'name': student[1],
                'email': student[2],
                'role': student[3],
                'batch': batch_info[1] if batch_info else 'N/A',
                'rollNumber': batch_info[2] if batch_info else 'N/A',
                'semester': batch_info[3] if batch_info else 1,
                'department': 'Computer Science',  # Default for demo
                'phone': f"+1-555-{student[0][-4:]}",  # Demo phone number
                'address': '123 University Ave, Campus City'  # Default for demo
            }
            conn.close()
            return jsonify(student_data)
        else:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/student/attendance', methods=['GET'])
@require_auth
def get_student_attendance():
    """Get student attendance data"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get student ID (for demo, use first student)
        c.execute("SELECT id FROM users WHERE role = 'student' LIMIT 1")
        student_result = c.fetchone()
        
        if not student_result:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        student_id = student_result[0]
        
        # Get overall attendance statistics
        c.execute("""
            SELECT 
                COUNT(*) as total_classes,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_classes,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_classes,
                SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late_classes
            FROM attendance 
            WHERE student_id = ?
        """, (student_id,))
        
        overall_stats = c.fetchone()
        total_classes = overall_stats[0] if overall_stats[0] else 0
        present_classes = overall_stats[1] if overall_stats[1] else 0
        absent_classes = overall_stats[2] if overall_stats[2] else 0
        late_classes = overall_stats[3] if overall_stats[3] else 0
        overall_attendance = round((present_classes / total_classes * 100), 2) if total_classes > 0 else 0
        
        # Get subject-wise attendance
        c.execute("""
            SELECT 
                s.name as subject,
                COUNT(*) as total_classes,
                SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as present_classes
            FROM attendance a
            JOIN subjects s ON a.subject_id = s.id
            WHERE a.student_id = ?
            GROUP BY s.id, s.name
        """, (student_id,))
        
        subject_attendance = []
        for row in c.fetchall():
            subject_total = row[1]
            subject_present = row[2]
            subject_percentage = round((subject_present / subject_total * 100), 2) if subject_total > 0 else 0
            
            subject_attendance.append({
                'subject': row[0],
                'total': subject_total,
                'present': subject_present,
                'percentage': subject_percentage
            })
        
        # Get recent attendance history
        c.execute("""
            SELECT 
                a.date, a.time_slot, a.status, a.remarks,
                s.name as subject, f.name as faculty
            FROM attendance a
            JOIN subjects s ON a.subject_id = s.id
            JOIN users f ON a.faculty_id = f.id
            WHERE a.student_id = ?
            ORDER BY a.date DESC, a.created_at DESC
            LIMIT 10
        """, (student_id,))
        
        attendance_history = []
        for row in c.fetchall():
            attendance_history.append({
                'date': row[0],
                'time': row[1],
                'status': row[2],
                'remarks': row[3],
                'subject': row[4],
                'faculty': row[5]
            })
        
        conn.close()
        return jsonify({
            'overall': {
                'total_classes': total_classes,
                'present_classes': present_classes,
                'absent_classes': absent_classes,
                'late_classes': late_classes,
                'percentage': overall_attendance
            },
            'by_subject': subject_attendance,
            'history': attendance_history
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/student/assignments', methods=['GET'])
@require_auth
def get_student_assignments():
    """Get student assignments"""
    try:
        # For demo purposes, return mock assignment data
        # In a real application, this would fetch from an assignments table
        assignments = {
            'pending': [
                {
                    'id': 'assign_001',
                    'title': 'Math Assignment 3',
                    'subject': 'Mathematics',
                    'due_date': '2024-12-20',
                    'description': 'Solve calculus problems from chapter 5',
                    'status': 'pending',
                    'points': 100
                },
                {
                    'id': 'assign_002',
                    'title': 'Physics Lab Report',
                    'subject': 'Physics',
                    'due_date': '2024-12-22',
                    'description': 'Write lab report for experiment 3',
                    'status': 'pending',
                    'points': 50
                },
                {
                    'id': 'assign_003',
                    'title': 'Chemistry Project',
                    'subject': 'Chemistry',
                    'due_date': '2024-12-25',
                    'description': 'Research project on organic compounds',
                    'status': 'pending',
                    'points': 150
                }
            ],
            'completed': [
                {
                    'id': 'assign_004',
                    'title': 'Math Assignment 2',
                    'subject': 'Mathematics',
                    'submitted_date': '2024-12-15',
                    'grade': 'A-',
                    'points_earned': 92,
                    'total_points': 100,
                    'status': 'graded'
                },
                {
                    'id': 'assign_005',
                    'title': 'Physics Quiz',
                    'subject': 'Physics',
                    'submitted_date': '2024-12-14',
                    'grade': 'B+',
                    'points_earned': 42,
                    'total_points': 50,
                    'status': 'graded'
                },
                {
                    'id': 'assign_006',
                    'title': 'Chemistry Lab',
                    'subject': 'Chemistry',
                    'submitted_date': '2024-12-13',
                    'grade': 'A',
                    'points_earned': 48,
                    'total_points': 50,
                    'status': 'graded'
                }
            ]
        }
        
        return jsonify(assignments)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/student/grades', methods=['GET'])
@require_auth
def get_student_grades():
    """Get student grades and performance"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get student ID (for demo, use first student)
        c.execute("SELECT id FROM users WHERE role = 'student' LIMIT 1")
        student_result = c.fetchone()
        
        if not student_result:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        student_id = student_result[0]
        
        # Get subject grades (mock data for demo)
        subject_grades = [
            {'subject': 'Mathematics', 'grade': 'A-', 'gpa': 3.7, 'credits': 4},
            {'subject': 'Physics', 'grade': 'B+', 'gpa': 3.3, 'credits': 4},
            {'subject': 'Chemistry', 'grade': 'A', 'gpa': 4.0, 'credits': 3},
            {'subject': 'Computer Science', 'grade': 'A-', 'gpa': 3.7, 'credits': 4}
        ]
        
        # Calculate overall GPA
        total_points = sum(grade['gpa'] * grade['credits'] for grade in subject_grades)
        total_credits = sum(grade['credits'] for grade in subject_grades)
        overall_gpa = round(total_points / total_credits, 2) if total_credits > 0 else 0
        
        conn.close()
        return jsonify({
            'overall_gpa': overall_gpa,
            'subject_grades': subject_grades,
            'total_credits': total_credits
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/student/notifications', methods=['GET'])
@require_auth
def get_student_notifications():
    """Get student notifications"""
    try:
        # For demo purposes, return mock notification data
        # In a real application, this would fetch from a notifications table
        notifications = [
            {
                'id': 'notif_001',
                'type': 'assignment',
                'title': 'Assignment Due',
                'message': 'Math Assignment 3 is due tomorrow',
                'created_at': '2024-12-16T10:00:00Z',
                'urgent': True,
                'read': False
            },
            {
                'id': 'notif_002',
                'type': 'class',
                'title': 'Class Cancelled',
                'message': 'Chemistry lab cancelled today',
                'created_at': '2024-12-15T08:00:00Z',
                'urgent': False,
                'read': True
            },
            {
                'id': 'notif_003',
                'type': 'grade',
                'title': 'Grade Posted',
                'message': 'Physics quiz grades are now available',
                'created_at': '2024-12-14T16:30:00Z',
                'urgent': False,
                'read': True
            },
            {
                'id': 'notif_004',
                'type': 'announcement',
                'title': 'Holiday Notice',
                'message': 'University will be closed on Dec 25th',
                'created_at': '2024-12-13T12:00:00Z',
                'urgent': False,
                'read': True
            }
        ]
        
        return jsonify({'notifications': notifications})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/student/dashboard-stats', methods=['GET'])
@require_auth
def get_student_dashboard_stats():
    """Get student dashboard statistics"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get student ID (for demo, use first student)
        c.execute("SELECT id FROM users WHERE role = 'student' LIMIT 1")
        student_result = c.fetchone()
        
        if not student_result:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        student_id = student_result[0]
        
        # Get attendance percentage
        c.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present
            FROM attendance 
            WHERE student_id = ?
        """, (student_id,))
        
        attendance_data = c.fetchone()
        total_classes = attendance_data[0] if attendance_data[0] else 0
        present_classes = attendance_data[1] if attendance_data[1] else 0
        attendance_percentage = round((present_classes / total_classes * 100), 2) if total_classes > 0 else 0
        
        # Mock data for other stats
        stats = {
            'overall_attendance': attendance_percentage,
            'current_gpa': 3.7,
            'pending_assignments': 3,
            'next_class': {
                'subject': 'Mathematics',
                'time': '10:00 AM',
                'room': 'Room 101'
            },
            'todays_schedule': [
                {
                    'subject': 'Mathematics',
                    'time': '09:00-10:00',
                    'room': 'Room 101',
                    'status': 'completed'
                },
                {
                    'subject': 'Physics',
                    'time': '10:30-11:30',
                    'room': 'Lab 205',
                    'status': 'upcoming'
                }
            ]
        }
        
        conn.close()
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------
# Timetable API Endpoints
# -------------------------

@app.route('/student/timetable', methods=['GET'])
@require_auth
def get_student_timetable():
    """Get student timetable - convenience endpoint"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get student's batch
        c.execute("""
            SELECT sbm.batch_id FROM student_batch_map sbm
            JOIN users u ON sbm.student_id = u.id
            WHERE u.role = 'student'
            LIMIT 1
        """)
        
        batch_result = c.fetchone()
        if not batch_result:
            conn.close()
            return jsonify({'error': 'Student batch not found'}), 404
        
        batch_id = batch_result[0]
        conn.close()
        
        # Redirect to advanced batch timetable
        return get_batch_timetable(batch_id)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/faculty/timetable', methods=['GET'])
@require_auth
def get_faculty_timetable():
    """Get faculty timetable - convenience endpoint"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        
        # Get faculty ID
        c.execute("SELECT id FROM users WHERE role = 'faculty' LIMIT 1")
        faculty_result = c.fetchone()
        if not faculty_result:
            conn.close()
            return jsonify({'error': 'Faculty not found'}), 404
        
        faculty_id = faculty_result[0]
        conn.close()
        
        # Redirect to advanced faculty timetable
        return get_advanced_faculty_timetable(faculty_id)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------
# Advanced Timetable API Endpoints
# -------------------------

@app.route('/timetable/batch/<batch_id>', methods=['GET'])
def get_batch_timetable(batch_id):
    """Get timetable for a specific batch with advanced validation"""
    result = timetable_api.get_batch_timetable_json(batch_id)
    return jsonify(result)

@app.route('/timetable/faculty/<faculty_id>', methods=['GET'])
def get_advanced_faculty_timetable(faculty_id):
    """Get timetable for a specific faculty member with advanced validation"""
    result = timetable_api.get_faculty_timetable_json(faculty_id)
    return jsonify(result)

@app.route('/timetable/regenerate', methods=['POST'])
def regenerate_timetable():
    """Regenerate timetable, lock it by saving to timetable_slots (port 5000)."""
    # Generate new timetable
    slots = timetable_api.generate_in_memory_timetable()
    validations = timetable_api.validate_generated_slots(slots)
    # Save only if generation succeeded (optional: require all OK)
    # Strategy: clear old slots and persist new
    deleted = timetable_api.delete_all_timetable_slots()
    saved = timetable_api.save_slots_to_db(slots)
    return jsonify({
        'message': 'Timetable regenerated and saved.',
        'deleted_old_slots': deleted,
        'saved_new_slots': saved,
        'validation_summary': validations
    })

@app.route('/timetable/validation', methods=['GET'])
def get_timetable_validation():
    """Get comprehensive timetable validation report"""
    try:
        if not timetable_api.fetch_data():
            return jsonify({"error": "Failed to fetch data from API"}), 500
        
        # Get existing timetable slots
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT * FROM timetable_slots")
        db_slots = c.fetchall()
        conn.close()
        
        # Convert to expected format
        timetable_slots = []
        for slot in db_slots:
            timetable_slots.append({
                'id': slot[0],
                'day': slot[1],
                'time': slot[2],
                'classroom_id': slot[3],
                'subject_id': slot[4],
                'faculty_id': slot[5],
                'batch_id': slot[6]
            })
        
        # Generate validation
        validations = timetable_api.validate_generated_slots(timetable_slots)
        
        return jsonify({
            'validation_report': validations,
            'total_slots': len(timetable_slots),
            'generated_at': '2024-12-16T10:00:00Z'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/timetable/entities', methods=['GET'])
def get_available_entities():
    """Get list of available batches, classrooms, and faculty for timetable generation"""
    try:
        if not timetable_api.fetch_data():
            return jsonify({"error": "Failed to fetch data from API"}), 500
        
        result = {
            "batches": [
                {"id": batch_id, "name": batch['name'], "department": batch['department']}
                for batch_id, batch in timetable_api.batches.items()
            ],
            "classrooms": [
                {"id": classroom_id, "name": classroom['name'], "type": classroom['type']}
                for classroom_id, classroom in timetable_api.classrooms.items()
            ],
            "faculty": [
                {"id": faculty_id, "name": faculty['name']}
                for faculty_id, faculty in timetable_api.users.items()
                if faculty['role'] == 'faculty'
            ]
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/timetable/all', methods=['GET'])
def get_all_timetables():
    """Get all timetables"""
    result = timetable_api.get_all_timetables_json()
    return jsonify(result)

@app.route('/timetable/health', methods=['GET'])
def timetable_health_check():
    """Health check for timetable system"""
    try:
        # Test data fetching
        data_fetch_success = timetable_api.fetch_data()
        
        # Test database connection
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM timetable_slots")
        slot_count = c.fetchone()[0]
        conn.close()
        
        return jsonify({
            "status": "healthy" if data_fetch_success else "degraded",
            "data_fetch": data_fetch_success,
            "database_connected": True,
            "timetable_slots_count": slot_count,
            "available_entities": {
                "batches": len(timetable_api.batches),
                "classrooms": len(timetable_api.classrooms),
                "faculty": len([u for u in timetable_api.users.values() if u.get('role') == 'faculty']),
                "subjects": len(timetable_api.subjects)
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500

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
