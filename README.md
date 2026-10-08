# FITCORE — Smart Gym Management & Real-Time Occupancy System

> A complete, production-grade full-stack Gym Management System built with **Python 3, Flask, PyMongo, MongoDB, Bootstrap 5, and Vanilla JavaScript**.

Designed specifically for commercial fitness clubs, gym administrators, and front-desk receptionists to streamline member enrollments, trainer assignments, attendance tracking, revenue accounting, and live floor density monitoring.

---

## 🌟 Key Features

### 1. 🟢 Real-Time Gym Occupancy & Traffic Density (NO CHARTS)
- **Live Occupancy Counter**: Displays members currently on the gym floor against maximum capacity (e.g., `47 / 100`).
- **Dynamic CSS Progress Gauge**: Visual percentage filled with color transitions (🟢 Normal $\le$ 50%, 🟡 Moderately Busy $\le$ 80%, 🟠 Crowded $\le$ 99%, 🔴 Full 100%).
- **Hard Capacity Protection**: Check-in is blocked on both frontend and backend when floor limit is reached.
- **Hourly Occupancy Timeline**: 2-hour interval traffic audit calculated dynamically from historical attendance timestamps without any charts or canvas dependencies.
- **Auto-Polling Engine**: Vanilla JS `fetch()` polling refreshes live floor stats every 15 seconds without full page reloads.

### 2. 👥 Complete Member Management (CRUD)
- Auto-generated sequential IDs (`GYM001`, `GYM002`, ...).
- Profile photos upload (JPG, PNG) with secure file storage.
- Intelligent Membership Renewal: Extends coverage from the existing end date if active, or from today if expired.
- Status management: `Active`, `Expired`, `Suspended`, `Inactive`.
- Safe Deactivation: Soft-deactivates members with financial/attendance history to protect audit trails.
- Multi-field search (ID, name, phone, email) and filtering by status, plan, and trainer.

### 3. 🏋️ Coach & Personal Trainer Management
- Trainer directory with readable IDs (`TRN001`, `TRN002`, ...).
- Specializations: Weight Training, Cardio, CrossFit, Yoga, Strength Training, Personal Training, Nutrition.
- Trainer profiles display assigned member rosters and active client counts.

### 4. 💳 Membership Plans & Pricing
- Seed plans: Monthly (30 days), Quarterly (90 days), Half-Yearly (180 days), Annual (365 days).
- Flexible price and duration configuration stored in MongoDB.
- Dedicated renewal management dashboard.

### 5. ⏱️ Attendance & Anti-Passback Check-In
- Quick check-in widget on the dashboard.
- Duplicate check-in protection prevents double entry while member is already inside.
- Automatic duration calculation upon check-out (e.g., `1h 45m`).

### 6. 💰 Payments & Revenue Ledger
- Receipts tracking with unique IDs (`PAY001`, `PAY002`, ...).
- Payment methods: Cash, UPI, Credit/Debit Card, Bank Transfer.
- Payment statuses: Paid, Pending, Failed.
- Revenue breakdown cards: Today, This Week, This Month, This Year, and All-Time.

### 7. 📊 Reports & Data Exports
- Dedicated audit reports for Members, Attendance, Revenue, and Occupancy.
- One-click CSV downloads (`fitcore_members_YYYY-MM-DD.csv`, etc.).
- Print-friendly CSS (`@media print`) that automatically formats clean printable paper reports.

### 8. 🔔 Dynamic System Notifications
- Automated alerts for memberships expiring within 3 days or expired today.
- Real-time logging of new registrations, payments, check-ins, and high gym density warnings.

### 9. ⚙️ Settings & Security
- Configurable gym details, opening/closing hours, floor capacity, and currency.
- Real-time calculation of gym status: `🟢 OPEN` or `🔴 CLOSED` based on current time in `Asia/Kolkata`.
- Admin credential management with password hashing (`Werkzeug` scrypt).

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.14+, Flask 3, Werkzeug, PyMongo, python-dotenv |
| **Database** | MongoDB (compatible with Local MongoDB & MongoDB Atlas) + MongoMock fallback |
| **Frontend** | HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons, Vanilla JavaScript |
| **Timezone** | `Asia/Kolkata` (IST) |
| **Currency** | Indian Rupee (`₹` / INR) |
| **Charts** | **ZERO CHARTS** (No Chart.js, no graphs; purely professional cards, tables, badges, and progress bars) |

---

## 📂 Project Architecture

```text
GYM/
├── app.py                      # Flask Application factory & server startup
├── config.py                   # Environment configuration loader
├── seed.py                     # Database seeder with realistic sample records
├── requirements.txt            # Python dependencies
├── .env                        # Local environment variables
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
│
├── database/
│   ├── __init__.py             # Database exports
│   └── db.py                   # MongoDB connection manager & index creator
│
├── routes/
│   ├── __init__.py             # Blueprint aggregator
│   ├── auth.py                 # Admin login & logout
│   ├── dashboard.py            # Summary metrics & live occupancy APIs
│   ├── members.py              # Member CRUD & renewal workflow
│   ├── trainers.py             # Trainer CRUD & client rosters
│   ├── memberships.py          # Membership plan tiers & renewal tracking
│   ├── attendance.py           # Check-in/out logic & hourly timeline
│   ├── payments.py             # Payment journal & revenue breakdowns
│   ├── reports.py              # Audit reports & CSV exports
│   ├── notifications.py        # System alerts & expiry notifications
│   └── settings.py             # Gym parameters & admin security
│
├── utils/
│   ├── __init__.py
│   ├── auth.py                 # Password hashing & verification
│   ├── validators.py           # Form validations
│   ├── helpers.py              # Timezone, date/currency formatters, occupancy status
│   ├── ids.py                  # Sequential ID generators (GYM001, TRN001, PAY001)
│   ├── notifier.py             # Notification logging & expiry sync
│   └── decorators.py           # @login_required session protection
│
├── templates/
│   ├── base.html               # Main layout with dark sidebar & topbar
│   ├── login.html              # Login screen with credentials box
│   ├── dashboard.html          # Operational dashboard (NO CHARTS)
│   ├── 404.html, 403.html, 500.html
│   ├── members/                # list.html, add.html, edit.html, view.html, renew.html
│   ├── trainers/               # list.html, add.html, edit.html, view.html
│   ├── memberships/            # list.html, add.html, edit.html, renewals.html
│   ├── attendance/             # list.html, checkin.html
│   ├── payments/               # list.html, add.html
│   ├── reports/                # dashboard.html, members.html, attendance.html, revenue.html, occupancy.html
│   ├── notifications/          # list.html
│   └── settings/               # index.html
│
├── static/
│   ├── css/
│   │   ├── style.css           # Core styling, cards, status badges & print CSS
│   │   └── responsive.css      # Mobile drawer menu & responsive tables
│   └── js/
│       ├── main.js             # Mobile toggles & confirm dialogs
│       ├── dashboard.js        # Live occupancy polling & quick check-in
│       ├── members.js          # Dynamic date calculation
│       └── attendance.js       # Live search & attendance actions
│
└── uploads/
    ├── members/                # Member profile photos
    └── trainers/               # Coach profile photos
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10 or higher
- Optional: MongoDB installed locally or a free cluster on [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)

### 2. Create Virtual Environment
```bash
python -m venv venv
```

Activate virtual environment:
- **Windows (Command Prompt / PowerShell)**:
  ```powershell
  .\venv\Scripts\activate
  ```
- **macOS / Linux**:
  ```bash
  source venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root:
```env
SECRET_KEY=fitcore-super-secret-key-development-2026
MONGO_URI=mongodb://localhost:27017/
DATABASE_NAME=gym_management
GYM_CAPACITY=100
TIMEZONE=Asia/Kolkata
```
> **Note**: If no live MongoDB instance is running, FITCORE will automatically and gracefully fall back to an internal MongoDB engine for testing and demonstration, ensuring 100% crash-free execution.

### 5. Seed the Database
Populate initial admin, membership plans, trainers, realistic members, attendance logs, and payments:
```bash
python seed.py
```

### 6. Run the Application
```bash
python app.py
```
Open your web browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 🔑 Default Administrator Login

| Credential | Value |
|---|---|
| **URL** | `http://127.0.0.1:5000/login` |
| **Username** | `admin` |
| **Password** | `admin123` |

> *Security Note*: Passwords are never stored in plaintext. They are salted and hashed using `Werkzeug` scrypt. You can change this password at any time from **Settings &rarr; Change Password**.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/occupancy` | Returns live headcount, capacity, %, and crowd status |
| `GET` | `/api/dashboard/stats` | Returns real-time dashboard summary metrics |
| `POST` | `/attendance/api/check-in` | Member check-in with capacity & duplicate checks |
| `POST` | `/attendance/api/check-out` | Member check-out with duration calculation |

---

## 🛡️ Production Deployment

For production deployments on Linux servers, run with Gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```
Make sure `debug=False` and set a strong `SECRET_KEY` in your `.env` file.

---

## 📜 License
Developed as a professional Python full-stack course project for FITCORE Smart Gym Management.
