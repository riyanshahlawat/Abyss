# Smart Classroom & Timetable Scheduler

A comprehensive web-based platform for efficient class scheduling in higher education institutions. Built with HTML, JavaScript, TailwindCSS, and Flask backend with SQLite database.

## 🎯 Project Overview

This system addresses the challenges faced by higher education institutions in efficient class scheduling due to limited infrastructure, faculty constraints, elective courses, and overlapping departmental requirements. It provides an intelligent and adaptive solution for timetable management.

## ✨ Key Features

### 🔐 Authentication System
- **Role-based access control** (Admin, Faculty, Student)
- **Secure login/signup** with password hashing
- **Session management** with JWT tokens

### 👨‍💼 Admin Dashboard
- **Complete CRUD operations** for Users, Classrooms, Subjects, and Batches
- **Advanced filtering and search** functionality
- **Bulk operations** (select multiple items, bulk delete)
- **Comprehensive export** (CSV, Excel, JSON, PDF formats)
- **Real-time statistics** and dashboard analytics

### 🎓 Faculty Dashboard
- **Personal timetable viewing** with weekly selector
- **Subjects and batches management**
- **Leave request system** with approval workflow
- **Availability management** with time slot selection
- **Export functionality** for personal schedules

### 📊 Timetable Management
- **Dynamic timetable generation** with constraint-based scheduling
- **Conflict detection and resolution**
- **Multi-department and multi-shift support**
- **Resource optimization** (classrooms, faculty, batches)

## 🛠️ Technology Stack

### Frontend
- **HTML5** - Semantic markup
- **JavaScript (ES6+)** - Modern JavaScript features
- **TailwindCSS** - Utility-first CSS framework
- **Font Awesome** - Icon library
- **Google Fonts (Inter)** - Typography

### Backend
- **Flask (Python)** - Web framework
- **SQLite3** - Database
- **Flask-CORS** - Cross-origin resource sharing

### UI/UX Features
- **Responsive Design** - Mobile-first approach
- **Glassmorphism** - Modern glass-like effects
- **Gradient Backgrounds** - Beautiful visual design
- **Animations** - Smooth transitions and hover effects
- **Toast Notifications** - User feedback system

## 🚀 Getting Started

### Prerequisites
- Python 3.7+
- Modern web browser
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/riyanshahlawat/Abyss.git
   cd Abyss
   ```

2. **Install Python dependencies**
   ```bash
   cd backend
   pip install flask flask-cors
   ```

3. **Start the backend server**
   ```bash
   python api.py
   ```

4. **Populate the database**
   ```bash
   python populate.py
   ```

5. **Open the frontend**
   - Navigate to `frontend/index.html` in your browser
   - Or open `frontend/login.html` to start with authentication

### Demo Credentials

#### Admin Access
- **Email:** `admin@univ.edu`
- **Password:** `admin123`

#### Faculty Access
- **Email:** `faculty@univ.edu`
- **Password:** `faculty123`

#### Student Access
- **Email:** `student@univ.edu`
- **Password:** `student123`

## 📁 Project Structure

```
Smart-Classroom-Timetable-Scheduler/
├── frontend/
│   ├── index.html              # Landing page
│   ├── login.html              # Login page
│   ├── signup.html             # Registration page
│   ├── admin-dashboard.html    # Admin interface
│   ├── faculty-dashboard.html  # Faculty interface
│   ├── test-faculty.html       # Faculty testing page
│   └── table.html              # Timetable display
├── backend/
│   ├── api.py                  # Flask API server
│   ├── populate.py             # Database population script
│   ├── readme.md               # Backend documentation
│   └── timetable.db            # SQLite database
└── README.md                   # Project documentation
```

## 🔧 API Endpoints

### Authentication
- `POST /login` - User login
- `POST /register` - User registration

### CRUD Operations
- `GET /read/<table>` - Read data from any table
- `POST /create/<table>` - Create new records
- `PUT /update/<table>/<id>` - Update existing records
- `DELETE /delete/<table>/<id>` - Delete records

### Faculty Specific
- `GET /faculty/profile` - Faculty profile information
- `GET /faculty/subjects-batches` - Assigned subjects and batches
- `GET /faculty/timetable` - Faculty timetable
- `POST /faculty/leave-request` - Submit leave requests
- `GET/POST /faculty/availability` - Manage availability

## 🎨 Features in Detail

### Admin Dashboard Features
- **User Management:** Create, edit, delete users with role assignment
- **Classroom Management:** Manage lecture halls and labs with capacity tracking
- **Subject Management:** Handle course information with credits and weekly hours
- **Batch Management:** Organize student groups with department and type classification
- **Export System:** Export data in multiple formats with filtering options
- **Search & Filter:** Advanced filtering across all entities
- **Bulk Operations:** Select and manage multiple items simultaneously

### Faculty Dashboard Features
- **Timetable Viewing:** Interactive weekly timetable with export options
- **Subject Management:** View assigned subjects with detailed information
- **Batch Management:** See teaching batches with student counts
- **Leave System:** Request leave with different types and approval workflow
- **Availability:** Set weekly availability preferences
- **Statistics:** Personal teaching statistics and workload tracking

## 🔒 Security Features

- **Password Hashing:** SHA-256 encryption for user passwords
- **Session Management:** Secure token-based authentication
- **Input Validation:** Client and server-side validation
- **CORS Protection:** Cross-origin request security
- **Role-based Access:** Different permissions for different user types

## 📊 Database Schema

### Tables
- **users:** User accounts with roles and authentication
- **classrooms:** Lecture halls and labs with capacity
- **subjects:** Course information with credits and hours
- **batches:** Student groups with department classification
- **faculty_subject_map:** Faculty-subject assignments
- **timetable_slots:** Generated timetable data

## 🚀 Future Enhancements

- **Student Dashboard:** Student-specific interface
- **Timetable Generation Engine:** AI-powered scheduling algorithm
- **Mobile App:** React Native mobile application
- **Analytics Dashboard:** Advanced reporting and insights
- **Notification System:** Real-time updates and alerts
- **Integration APIs:** Connect with existing university systems

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Team

- **Developer:** Riyansh Ahlawat
- **Project:** Smart Classroom & Timetable Scheduler
- **Hackathon:** Educational Technology Innovation

## 📞 Support

For support, email support@university.edu or create an issue in this repository.

---

**Built with ❤️ for educational institutions worldwide**
