import os
from datetime import datetime, timedelta
from database import init_db, get_db
from utils.auth import hash_password
from utils.helpers import get_now

def seed_database(target_db=None):
    print("[*] Initializing FITCORE database seed...")
    db = target_db if target_db is not None else init_db()
    
    # 1. Seed Admin
    existing_admin = db.admins.find_one({"username": "admin"})
    if not existing_admin:
        admin_doc = {
            "username": "admin",
            "password": hash_password("admin123"),
            "full_name": "Admin Manager",
            "email": "admin@fitcore.local",
            "role": "Super Admin",
            "created_at": get_now(),
            "last_login": None
        }
        db.admins.insert_one(admin_doc)
        print("  [+] Created default admin user (admin / admin123)")
    else:
        print("  [-] Default admin user already exists.")

    # 2. Seed Settings
    existing_settings = db.settings.find_one({"type": "general"})
    if not existing_settings:
        settings_doc = {
            "type": "general",
            "gym_name": "FITCORE",
            "gym_address": "42 Fitness Boulevard, Tech City, Bangalore",
            "gym_phone": "+91 98765 43210",
            "gym_email": "admin@fitcore.local",
            "gym_capacity": 100,
            "opening_time": "05:00 AM",
            "closing_time": "10:00 PM",
            "currency": "INR",
            "currency_symbol": "₹",
            "timezone": "Asia/Kolkata",
            "created_at": get_now()
        }
        db.settings.insert_one(settings_doc)
        print("  [+] Created default gym settings (Capacity: 100)")
    else:
        print("  [-] Gym settings already exist.")

    # 3. Seed Membership Plans
    default_plans = [
        {"plan_id": "PLAN001", "name": "Monthly", "duration_days": 30, "price": 1000.0, "description": "Standard 30-day gym floor access", "status": "Active"},
        {"plan_id": "PLAN002", "name": "Quarterly", "duration_days": 90, "price": 2500.0, "description": "3-month fitness membership with locker access", "status": "Active"},
        {"plan_id": "PLAN003", "name": "Half-Yearly", "duration_days": 180, "price": 4500.0, "description": "6-month fitness & cardio training program", "status": "Active"},
        {"plan_id": "PLAN004", "name": "Annual", "duration_days": 365, "price": 8000.0, "description": "12-month full VIP gym access & personal consultation", "status": "Active"}
    ]
    for p in default_plans:
        db.membership_plans.update_one(
            {"plan_id": p["plan_id"]},
            {"$setOnInsert": {**p, "created_at": get_now()}},
            upsert=True
        )
    print("  [+] Seeded 4 default membership plans (Monthly, Quarterly, Half-Yearly, Annual)")

    # 4. Seed Trainers
    default_trainers = [
        {"trainer_id": "TRN001", "name": "Vikram Singh", "age": 29, "gender": "Male", "phone": "+91 98765 11001", "email": "vikram.s@fitcore.local", "specialization": "Weight Training", "experience": "5 Years", "salary": 38000.0, "joining_date": "2024-01-10", "status": "Active"},
        {"trainer_id": "TRN002", "name": "Ananya Sharma", "age": 27, "gender": "Female", "phone": "+91 98765 11002", "email": "ananya.s@fitcore.local", "specialization": "Yoga", "experience": "4 Years", "salary": 34000.0, "joining_date": "2024-03-15", "status": "Active"},
        {"trainer_id": "TRN003", "name": "Rohit Verma", "age": 32, "gender": "Male", "phone": "+91 98765 11003", "email": "rohit.v@fitcore.local", "specialization": "CrossFit", "experience": "7 Years", "salary": 45000.0, "joining_date": "2023-08-01", "status": "Active"},
        {"trainer_id": "TRN004", "name": "Priya Nair", "age": 26, "gender": "Female", "phone": "+91 98765 11004", "email": "priya.n@fitcore.local", "specialization": "Cardio", "experience": "3 Years", "salary": 30000.0, "joining_date": "2024-06-20", "status": "Active"},
        {"trainer_id": "TRN005", "name": "David Miller", "age": 35, "gender": "Male", "phone": "+91 98765 11005", "email": "david.m@fitcore.local", "specialization": "Strength Training", "experience": "9 Years", "salary": 50000.0, "joining_date": "2023-02-10", "status": "Active"}
    ]
    for t in default_trainers:
        db.trainers.update_one(
            {"trainer_id": t["trainer_id"]},
            {"$setOnInsert": {**t, "photo": "", "created_at": get_now()}},
            upsert=True
        )
    print("  [+] Seeded 5 professional gym trainers")

    # 5. Seed Members (10 members with various plans, trainers, and statuses)
    now = get_now()
    today_str = now.strftime("%Y-%m-%d")
    
    # Dates
    start_recent = (now - timedelta(days=20)).strftime("%Y-%m-%d")
    end_future = (now + timedelta(days=70)).strftime("%Y-%m-%d")
    end_near_future = (now + timedelta(days=2)).strftime("%Y-%m-%d") # Expiring soon
    end_past = (now - timedelta(days=5)).strftime("%Y-%m-%d") # Expired
    
    sample_members = [
        {
            "member_id": "GYM001",
            "full_name": "Arun Kumar",
            "age": 28,
            "gender": "Male",
            "phone": "+91 98111 22331",
            "email": "arun.kumar@gmail.com",
            "address": "12 Richmond Road, Bangalore",
            "emergency_contact": "+91 98111 22330",
            "plan_id": "PLAN002",
            "plan_name": "Quarterly",
            "plan_price": 2500.0,
            "join_date": "2025-01-15",
            "start_date": start_recent,
            "end_date": end_future,
            "trainer_id": "TRN001",
            "trainer_name": "Vikram Singh",
            "payment_status": "Paid",
            "status": "Active"
        },
        {
            "member_id": "GYM002",
            "full_name": "Sneha Patel",
            "age": 25,
            "gender": "Female",
            "phone": "+91 98111 22332",
            "email": "sneha.p@gmail.com",
            "address": "45 Koramangala 4th Block, Bangalore",
            "emergency_contact": "+91 98111 22339",
            "plan_id": "PLAN004",
            "plan_name": "Annual",
            "plan_price": 8000.0,
            "join_date": "2024-11-01",
            "start_date": "2024-11-01",
            "end_date": (now + timedelta(days=200)).strftime("%Y-%m-%d"),
            "trainer_id": "TRN002",
            "trainer_name": "Ananya Sharma",
            "payment_status": "Paid",
            "status": "Active"
        },
        {
            "member_id": "GYM003",
            "full_name": "Karthik Rajan",
            "age": 31,
            "gender": "Male",
            "phone": "+91 98111 22333",
            "email": "karthik.r@yahoo.com",
            "address": "78 Indiranagar 100ft Road, Bangalore",
            "emergency_contact": "+91 98111 22338",
            "plan_id": "PLAN001",
            "plan_name": "Monthly",
            "plan_price": 1000.0,
            "join_date": "2025-02-01",
            "start_date": (now - timedelta(days=28)).strftime("%Y-%m-%d"),
            "end_date": end_near_future, # Expiring in 2 days!
            "trainer_id": "TRN003",
            "trainer_name": "Rohit Verma",
            "payment_status": "Paid",
            "status": "Active"
        },
        {
            "member_id": "GYM004",
            "full_name": "Meera Joshi",
            "age": 29,
            "gender": "Female",
            "phone": "+91 98111 22334",
            "email": "meera.j@gmail.com",
            "address": "15 HSR Layout Sector 2, Bangalore",
            "emergency_contact": "+91 98111 22337",
            "plan_id": "PLAN003",
            "plan_name": "Half-Yearly",
            "plan_price": 4500.0,
            "join_date": "2024-09-10",
            "start_date": (now - timedelta(days=190)).strftime("%Y-%m-%d"),
            "end_date": end_past, # Expired!
            "trainer_id": "TRN004",
            "trainer_name": "Priya Nair",
            "payment_status": "Paid",
            "status": "Expired"
        },
        {
            "member_id": "GYM005",
            "full_name": "Rohan Gupta",
            "age": 24,
            "gender": "Male",
            "phone": "+91 98111 22335",
            "email": "rohan.g@outlook.com",
            "address": "88 Whitefield Main Road, Bangalore",
            "emergency_contact": "+91 98111 22336",
            "plan_id": "PLAN001",
            "plan_name": "Monthly",
            "plan_price": 1000.0,
            "join_date": "2025-03-01",
            "start_date": start_recent,
            "end_date": (now + timedelta(days=10)).strftime("%Y-%m-%d"),
            "trainer_id": "TRN005",
            "trainer_name": "David Miller",
            "payment_status": "Paid",
            "status": "Active"
        },
        {
            "member_id": "GYM006",
            "full_name": "Divya Suresh",
            "age": 26,
            "gender": "Female",
            "phone": "+91 98111 22336",
            "email": "divya.s@gmail.com",
            "address": "23 Malleshwaram 8th Cross, Bangalore",
            "emergency_contact": "+91 98111 22335",
            "plan_id": "PLAN002",
            "plan_name": "Quarterly",
            "plan_price": 2500.0,
            "join_date": "2025-02-15",
            "start_date": (now - timedelta(days=15)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=75)).strftime("%Y-%m-%d"),
            "trainer_id": "TRN002",
            "trainer_name": "Ananya Sharma",
            "payment_status": "Paid",
            "status": "Active"
        },
        {
            "member_id": "GYM007",
            "full_name": "Varun Nair",
            "age": 33,
            "gender": "Male",
            "phone": "+91 98111 22337",
            "email": "varun.nair@hotmail.com",
            "address": "66 Jayanagar 4th T Block, Bangalore",
            "emergency_contact": "+91 98111 22334",
            "plan_id": "PLAN003",
            "plan_name": "Half-Yearly",
            "plan_price": 4500.0,
            "join_date": "2024-12-05",
            "start_date": (now - timedelta(days=40)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=140)).strftime("%Y-%m-%d"),
            "trainer_id": "TRN001",
            "trainer_name": "Vikram Singh",
            "payment_status": "Paid",
            "status": "Active"
        },
        {
            "member_id": "GYM008",
            "full_name": "Pooja Shah",
            "age": 27,
            "gender": "Female",
            "phone": "+91 98111 22338",
            "email": "pooja.shah@gmail.com",
            "address": "104 Basavanagudi, Bangalore",
            "emergency_contact": "+91 98111 22333",
            "plan_id": "PLAN001",
            "plan_name": "Monthly",
            "plan_price": 1000.0,
            "join_date": "2025-01-20",
            "start_date": (now - timedelta(days=60)).strftime("%Y-%m-%d"),
            "end_date": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
            "trainer_id": None,
            "trainer_name": "None",
            "payment_status": "Pending",
            "status": "Expired"
        },
        {
            "member_id": "GYM009",
            "full_name": "Amit Sengupta",
            "age": 36,
            "gender": "Male",
            "phone": "+91 98111 22339",
            "email": "amit.s@gmail.com",
            "address": "51 Bellandur Green Glen Layout, Bangalore",
            "emergency_contact": "+91 98111 22332",
            "plan_id": "PLAN004",
            "plan_name": "Annual",
            "plan_price": 8000.0,
            "join_date": "2025-01-10",
            "start_date": (now - timedelta(days=10)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=355)).strftime("%Y-%m-%d"),
            "trainer_id": "TRN005",
            "trainer_name": "David Miller",
            "payment_status": "Paid",
            "status": "Active"
        },
        {
            "member_id": "GYM010",
            "full_name": "Nisha Reddy",
            "age": 23,
            "gender": "Female",
            "phone": "+91 98111 22340",
            "email": "nisha.reddy@gmail.com",
            "address": "19 BTM Layout 2nd Stage, Bangalore",
            "emergency_contact": "+91 98111 22331",
            "plan_id": "PLAN001",
            "plan_name": "Monthly",
            "plan_price": 1000.0,
            "join_date": "2025-02-10",
            "start_date": (now - timedelta(days=5)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=25)).strftime("%Y-%m-%d"),
            "trainer_id": "TRN003",
            "trainer_name": "Rohit Verma",
            "payment_status": "Paid",
            "status": "Suspended"
        }
    ]

    for m in sample_members:
        db.members.update_one(
            {"member_id": m["member_id"]},
            {"$setOnInsert": {**m, "photo": "", "created_at": get_now(), "updated_at": get_now()}},
            upsert=True
        )
    print("  [+] Seeded 10 realistic members with varied statuses and plans")

    # 6. Seed Attendance Records
    # Crucial: 4 members are currently "Inside" (GYM001, GYM002, GYM005, GYM007)
    # Plus historical completed records for today & yesterday to calculate duration & hourly occupancy
    existing_att_count = db.attendance.count_documents({})
    if existing_att_count == 0:
        # Today's active checkins (Inside)
        inside_checkins = [
            {"member_id": "GYM001", "member_name": "Arun Kumar", "hours_ago": 1.2},
            {"member_id": "GYM002", "member_name": "Sneha Patel", "hours_ago": 0.8},
            {"member_id": "GYM005", "member_name": "Rohan Gupta", "hours_ago": 0.5},
            {"member_id": "GYM007", "member_name": "Varun Nair", "hours_ago": 0.2}
        ]
        
        for item in inside_checkins:
            cin_dt = now - timedelta(hours=item["hours_ago"])
            db.attendance.insert_one({
                "member_id": item["member_id"],
                "member_name": item["member_name"],
                "plan_name": "Standard",
                "check_in": cin_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "check_in_dt": cin_dt,
                "check_in_date": cin_dt.strftime("%Y-%m-%d"),
                "time_display": cin_dt.strftime("%I:%M %p"),
                "check_out": None,
                "check_out_dt": None,
                "duration_minutes": 0,
                "duration_display": "-",
                "status": "Inside",
                "created_at": cin_dt
            })
            
        # Completed checkins for today
        completed_today = [
            {"member_id": "GYM003", "member_name": "Karthik Rajan", "start_h": 6, "dur_m": 75},
            {"member_id": "GYM006", "member_name": "Divya Suresh", "start_h": 7, "dur_m": 60},
            {"member_id": "GYM009", "member_name": "Amit Sengupta", "start_h": 8, "dur_m": 90}
        ]
        for c in completed_today:
            c_in = datetime.combine(now.date(), datetime.min.time()).replace(tzinfo=now.tzinfo) + timedelta(hours=c["start_h"])
            c_out = c_in + timedelta(minutes=c["dur_m"])
            h_dur = c["dur_m"] // 60
            m_dur = c["dur_m"] % 60
            disp = f"{h_dur}h {m_dur}m" if h_dur > 0 else f"{m_dur}m"
            db.attendance.insert_one({
                "member_id": c["member_id"],
                "member_name": c["member_name"],
                "plan_name": "Standard",
                "check_in": c_in.strftime("%Y-%m-%d %H:%M:%S"),
                "check_in_dt": c_in,
                "check_in_date": c_in.strftime("%Y-%m-%d"),
                "time_display": c_in.strftime("%I:%M %p"),
                "check_out": c_out.strftime("%Y-%m-%d %H:%M:%S"),
                "check_out_dt": c_out,
                "duration_minutes": c["dur_m"],
                "duration_display": disp,
                "status": "Checked Out",
                "created_at": c_in
            })
        print("  [+] Seeded realistic attendance records (4 members currently Inside)")
    else:
        print("  [-] Attendance records already exist.")

    # 7. Seed Payments
    existing_pays = db.payments.count_documents({})
    if existing_pays == 0:
        sample_payments = [
            {"payment_id": "PAY001", "member_id": "GYM001", "member_name": "Arun Kumar", "plan_id": "PLAN002", "plan_name": "Quarterly", "amount": 2500.0, "days_ago": 0, "method": "UPI", "status": "Paid"},
            {"payment_id": "PAY002", "member_id": "GYM002", "member_name": "Sneha Patel", "plan_id": "PLAN004", "plan_name": "Annual", "amount": 8000.0, "days_ago": 0, "method": "Card", "status": "Paid"},
            {"payment_id": "PAY003", "member_id": "GYM005", "member_name": "Rohan Gupta", "plan_id": "PLAN001", "plan_name": "Monthly", "amount": 1000.0, "days_ago": 0, "method": "Cash", "status": "Paid"},
            {"payment_id": "PAY004", "member_id": "GYM006", "member_name": "Divya Suresh", "plan_id": "PLAN002", "plan_name": "Quarterly", "amount": 2500.0, "days_ago": 2, "method": "UPI", "status": "Paid"},
            {"payment_id": "PAY005", "member_id": "GYM007", "member_name": "Varun Nair", "plan_id": "PLAN003", "plan_name": "Half-Yearly", "amount": 4500.0, "days_ago": 5, "method": "Bank Transfer", "status": "Paid"},
            {"payment_id": "PAY006", "member_id": "GYM009", "member_name": "Amit Sengupta", "plan_id": "PLAN004", "plan_name": "Annual", "amount": 8000.0, "days_ago": 10, "method": "Card", "status": "Paid"},
            {"payment_id": "PAY007", "member_id": "GYM008", "member_name": "Pooja Shah", "plan_id": "PLAN001", "plan_name": "Monthly", "amount": 1000.0, "days_ago": 1, "method": "Cash", "status": "Pending"}
        ]
        for p in sample_payments:
            p_dt = now - timedelta(days=p["days_ago"], hours=2)
            db.payments.insert_one({
                "payment_id": p["payment_id"],
                "member_id": p["member_id"],
                "member_name": p["member_name"],
                "plan_id": p["plan_id"],
                "plan_name": p["plan_name"],
                "amount": p["amount"],
                "payment_date": p_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "payment_method": p["method"],
                "transaction_id": f"TXN-DEMO-{p['payment_id']}",
                "payment_status": p["status"],
                "remarks": f"Membership fee payment for {p['plan_name']}",
                "created_at": p_dt
            })
        print("  [+] Seeded realistic revenue & payment history")
    else:
        print("  [-] Payments already exist.")

    # 8. Seed Notifications
    existing_notifs = db.notifications.count_documents({})
    if existing_notifs == 0:
        db.notifications.insert_many([
            {
                "title": "Welcome to FITCORE",
                "message": "FITCORE Gym Management & Real-Time Occupancy System is ready.",
                "type": "success",
                "link": "/dashboard",
                "is_read": False,
                "created_at": now - timedelta(hours=5)
            },
            {
                "title": "Memberships Expiring Soon",
                "message": "Karthik Rajan (GYM003) membership expires in 2 days.",
                "type": "warning",
                "link": "/members?status=Active",
                "is_read": False,
                "created_at": now - timedelta(hours=3)
            },
            {
                "title": "Payment Received",
                "message": "Payment of Rs 8,000 received from Sneha Patel (Annual Plan).",
                "type": "info",
                "link": "/payments",
                "is_read": False,
                "created_at": now - timedelta(hours=1)
            }
        ])
        print("  [+] Seeded initial notifications")
    else:
        print("  [-] Notifications already exist.")

    # 9. Seed Unified Users for Role-Based Access Control
    demo_users = [
        {
            "user_id": "USR001",
            "username": "admin",
            "name": "Admin Manager",
            "email": "admin@fitcore.com",
            "phone": "+91 98765 43210",
            "password": hash_password("admin123"),
            "role": "admin",
            "status": "active",
            "created_at": now
        },
        {
            "user_id": "USR002",
            "trainer_id": "TRN001",
            "name": "Vikram Singh",
            "email": "trainer@fitcore.com",
            "phone": "+91 98765 11001",
            "password": hash_password("trainer123"),
            "role": "trainer",
            "status": "active",
            "created_at": now
        },
        {
            "user_id": "USR003",
            "member_id": "GYM001",
            "name": "Arun Kumar",
            "email": "member@fitcore.com",
            "phone": "+91 98111 22331",
            "password": hash_password("member123"),
            "role": "member",
            "status": "active",
            "created_at": now
        }
    ]
    for u in demo_users:
        db.users.update_one(
            {"email": u["email"]},
            {"$set": u},
            upsert=True
        )
    print("  [+] Seeded RBAC Demo Users (admin, trainer, member)")

    # 10. Seed Sample Workout Plans
    if db.workout_plans.count_documents({}) == 0:
        db.workout_plans.insert_many([
            {
                "workout_id": "WKT001",
                "trainer_id": "TRN001",
                "trainer_name": "Vikram Singh",
                "member_id": "GYM001",
                "member_name": "Arun Kumar",
                "workout_name": "Upper Body Hypertrophy",
                "goal": "Muscle Growth & Strength",
                "exercise": "Flat Barbell Bench Press, Incline DB Press, Cable Chest Flyes, Triceps Pushdowns",
                "sets": 4,
                "repetitions": "10-12",
                "duration": "50 mins",
                "notes": "Keep 90s rest interval between working sets. Progressive overload on compound lifts.",
                "created_at": now - timedelta(days=2)
            },
            {
                "workout_id": "WKT002",
                "trainer_id": "TRN001",
                "trainer_name": "Vikram Singh",
                "member_id": "GYM001",
                "member_name": "Arun Kumar",
                "workout_name": "Legs & Core Conditioning",
                "goal": "Lower Body Power",
                "exercise": "Barbell Back Squats, Romanian Deadlifts, Walking Lunges, Hanging Leg Raises",
                "sets": 3,
                "repetitions": "12-15",
                "duration": "45 mins",
                "notes": "Full depth on squats, focus on hamstrings stretch during RDLs.",
                "created_at": now - timedelta(days=1)
            }
        ])
        print("  [+] Seeded sample workout plans for member GYM001")

    # 11. Seed Sample Training Schedules
    if db.schedules.count_documents({}) == 0:
        today_date_str = now.strftime("%Y-%m-%d")
        tomorrow_date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        db.schedules.insert_many([
            {
                "schedule_id": "SCH001",
                "trainer_id": "TRN001",
                "trainer_name": "Vikram Singh",
                "member_id": "GYM001",
                "member_name": "Arun Kumar",
                "date": today_date_str,
                "time": "07:30 AM",
                "session_type": "Personal Training",
                "status": "Scheduled",
                "notes": "Form check on Bench Press & strength progression review.",
                "created_at": now
            },
            {
                "schedule_id": "SCH002",
                "trainer_id": "TRN001",
                "trainer_name": "Vikram Singh",
                "member_id": "GYM001",
                "member_name": "Arun Kumar",
                "date": tomorrow_date_str,
                "time": "08:00 AM",
                "session_type": "Form Assessment",
                "status": "Scheduled",
                "notes": "Squats technique review & core conditioning.",
                "created_at": now
            }
        ])
        print("  [+] Seeded sample trainer-member schedule sessions")

    print("\n[OK] FITCORE Database seeding completed successfully!")
    print("--------------------------------------------------")
    print("Role-Based Demo Credentials:")
    print("ADMIN   : admin / admin123  (or admin@fitcore.com)")
    print("TRAINER : trainer@fitcore.com / trainer123")
    print("MEMBER  : member@fitcore.com / member123")
    print("--------------------------------------------------")

if __name__ == '__main__':
    seed_database()
