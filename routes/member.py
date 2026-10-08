from datetime import datetime, timedelta
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db
from utils.decorators import login_required, role_required
from utils.auth import verify_password, hash_password
from utils.helpers import (
    get_now, get_tz, get_gym_settings, is_gym_open, 
    calculate_occupancy_status, format_currency
)

member_bp = Blueprint('member', __name__, url_prefix='/member')

def get_current_member(db):
    """
    Retrieves the current authenticated member document.
    """
    user_id = session.get('user_id')
    member_id = session.get('member_id')
    email = session.get('email')
    
    query = {}
    if member_id:
        query["member_id"] = member_id
    elif user_id:
        query["$or"] = [{"user_id": user_id}, {"member_id": user_id}]
    elif email:
        query["email"] = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
        
    member = db.members.find_one(query)
    if member and not session.get('member_id'):
        session['member_id'] = member.get('member_id')
    return member

@member_bp.route('/dashboard')
@login_required
@role_required('member')
def dashboard():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found. Please contact the administrator.", "danger")
        return redirect(url_for('auth.logout'))
        
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    gym_open = is_gym_open(settings)
    
    # 1. Real-time gym occupancy from actual attendance
    current_inside = db.attendance.count_documents({"status": "Inside"})
    occupancy_pct = round((current_inside / capacity * 100), 1) if capacity > 0 else 0
    available_spaces = max(0, capacity - current_inside)
    occ_status = calculate_occupancy_status(occupancy_pct)
    
    # 2. Membership status and dynamic days remaining
    now = get_now()
    now_date = now.date()
    end_date_str = member.get('end_date')
    days_remaining = 0
    membership_status = member.get('status', 'Active')
    
    if end_date_str:
        try:
            end_date = datetime.strptime(str(end_date_str)[:10], "%Y-%m-%d").date()
            delta = (end_date - now_date).days
            days_remaining = max(0, delta)
            if delta < 0:
                membership_status = "EXPIRED"
            elif delta <= 7:
                membership_status = "EXPIRING SOON"
            else:
                membership_status = "ACTIVE"
        except Exception:
            days_remaining = 0
            
    # 3. Attendance this month
    cur_year_month = now.strftime("%Y-%m")
    month_attendance_count = db.attendance.count_documents({
        "member_id": member["member_id"],
        "$or": [
            {"check_in_date": {"$regex": f"^{cur_year_month}"}},
            {"check_in": {"$regex": f"^{cur_year_month}"}}
        ]
    })
    
    # 4. Assigned Trainer details
    trainer = None
    if member.get('trainer_id'):
        trainer = db.trainers.find_one({"trainer_id": member['trainer_id']})
        
    # 5. Recent Payments
    recent_payments = list(db.payments.find({
        "member_id": member["member_id"]
    }).sort("created_at", -1).limit(3))
    
    last_payment = recent_payments[0] if recent_payments else None
    
    # 6. Notifications for member
    notifications = list(db.notifications.find({
        "$or": [
            {"member_id": member["member_id"]},
            {"type": {"$in": ["member", "general", "announcement"]}},
            {"member_id": {"$exists": False}}
        ]
    }).sort("created_at", -1).limit(4))
    
    # 7. Today's and assigned workout plans
    today_str = now.strftime("%Y-%m-%d")
    today_workout = db.workout_plans.find_one({
        "member_id": member["member_id"],
        "workout_date": today_str
    })
    if not today_workout:
        today_workout = db.workout_plans.find_one(
            {"member_id": member["member_id"]},
            sort=[("workout_date", -1), ("created_at", -1)]
        )
        
    workout_plans = list(db.workout_plans.find({
        "member_id": member["member_id"]
    }).sort("created_at", -1).limit(5))

    # Check if this member is currently inside the gym
    active_attendance = db.attendance.find_one({"member_id": member["member_id"], "status": "Inside"})
    currently_inside_member = bool(active_attendance)

    return render_template(
        'member/dashboard.html',
        member=member,
        gym_settings=settings,
        gym_open=gym_open,
        current_inside=current_inside,
        capacity=capacity,
        available_spaces=available_spaces,
        occupancy_pct=occupancy_pct,
        occupancy_status=occ_status,
        membership_status=membership_status,
        days_remaining=days_remaining,
        month_attendance_count=month_attendance_count,
        trainer=trainer,
        recent_payments=recent_payments,
        last_payment=last_payment,
        notifications=notifications,
        workout_plans=workout_plans,
        today_workout=today_workout,
        active_attendance=active_attendance,
        currently_inside_member=currently_inside_member
    )

@member_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@role_required('member')
def profile():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        gender = request.form.get('gender', member.get('gender', 'Other'))
        dob = request.form.get('date_of_birth', member.get('date_of_birth', ''))
        emergency_contact = request.form.get('emergency_contact', '').strip()
        
        update_data = {
            "phone": phone,
            "address": address,
            "gender": gender,
            "date_of_birth": dob,
            "emergency_contact": emergency_contact,
            "updated_at": get_now()
        }
        
        db.members.update_one({"member_id": member["member_id"]}, {"$set": update_data})
        db.users.update_one({"member_id": member["member_id"]}, {"$set": {"phone": phone}})
        
        flash("Your profile information has been updated successfully.", "success")
        return redirect(url_for('member.profile'))
        
    trainer = None
    if member.get('trainer_id'):
        trainer = db.trainers.find_one({"trainer_id": member['trainer_id']})
        
    return render_template('member/profile.html', member=member, trainer=trainer)

@member_bp.route('/membership')
@login_required
@role_required('member')
def membership():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    plan = db.membership_plans.find_one({"plan_id": member.get('plan_id')})
    
    # Calculate days remaining and status
    now = get_now()
    now_date = now.date()
    end_date_str = member.get('end_date')
    days_remaining = 0
    status_label = member.get('status', 'Active').upper()
    
    if end_date_str:
        try:
            end_date = datetime.strptime(str(end_date_str)[:10], "%Y-%m-%d").date()
            delta = (end_date - now_date).days
            days_remaining = delta
            if delta < 0:
                status_label = "EXPIRED"
            elif delta <= 7:
                status_label = "EXPIRING SOON"
            else:
                status_label = "ACTIVE"
        except Exception:
            days_remaining = 0
            
    all_plans = list(db.membership_plans.find({"status": "Active"}))
    payments = list(db.payments.find({"member_id": member["member_id"]}).sort("created_at", -1))

    return render_template(
        'member/membership.html',
        member=member,
        plan=plan,
        days_remaining=days_remaining,
        status_label=status_label,
        all_plans=all_plans,
        payments=payments
    )

@member_bp.route('/attendance')
@login_required
@role_required('member')
def attendance():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    # Member can view ONLY their own attendance
    records = list(db.attendance.find({
        "member_id": member["member_id"]
    }).sort("created_at", -1))
    
    total_visits = len(records)
    cur_year_month = get_now().strftime("%Y-%m")
    month_visits = sum(1 for r in records if str(r.get("check_in_date") or r.get("check_in", "")).startswith(cur_year_month))
    
    # Check if currently inside
    active_attendance = db.attendance.find_one({"member_id": member["member_id"], "status": "Inside"})
    currently_inside = bool(active_attendance)

    return render_template(
        'member/attendance.html',
        member=member,
        records=records,
        total_visits=total_visits,
        month_visits=month_visits,
        currently_inside=currently_inside,
        active_attendance=active_attendance
    )

@member_bp.route('/attendance/check-in', methods=['POST'])
@login_required
@role_required('member')
def attendance_checkin():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    member_id = member["member_id"]
    member_name = member.get("full_name") or member.get("name") or "Member"
    
    # 1. Check membership status
    mem_status = str(member.get("status", "Active")).lower()
    if mem_status in ['expired', 'inactive', 'suspended']:
        flash(f"Cannot check in: Your membership is currently {member.get('status')}. Please contact the front desk.", "danger")
        return redirect(request.referrer or url_for('member.attendance'))
        
    # 2. Check if already inside
    already_inside = db.attendance.find_one({"member_id": member_id, "status": "Inside"})
    if already_inside:
        time_str = already_inside.get("time_display") or already_inside.get("check_in_time") or "earlier today"
        flash(f"You are already checked in to the gym (since {time_str}).", "warning")
        return redirect(request.referrer or url_for('member.attendance'))
        
    # 3. Check Gym Capacity
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    current_inside = db.attendance.count_documents({"status": "Inside"})
    if current_inside >= capacity:
        flash(f"Gym is currently at maximum capacity ({capacity}/{capacity}). Please wait a few moments until space frees up.", "danger")
        return redirect(request.referrer or url_for('member.attendance'))
        
    # 4. Insert Attendance Record
    now_dt = get_now()
    time_display = now_dt.strftime("%I:%M %p")
    date_str = now_dt.strftime("%Y-%m-%d")
    datetime_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    att_record = {
        "member_id": member_id,
        "member_name": member_name,
        "name": member_name,
        "person_type": "member",
        "role": "Member",
        "plan_name": member.get("plan_name", "Standard"),
        "check_in": datetime_str,
        "check_in_dt": now_dt,
        "check_in_date": date_str,
        "check_in_time": time_display,
        "time_display": time_display,
        "check_out": None,
        "check_out_dt": None,
        "check_out_time": None,
        "duration_minutes": 0,
        "duration_display": "In Progress",
        "status": "Inside",
        "trainer_id": member.get("trainer_id"),
        "created_at": now_dt
    }
    db.attendance.insert_one(att_record)
    
    # 5. Notify Trainer immediately
    if member.get("trainer_id"):
        db.notifications.insert_one({
            "title": "Client Checked In",
            "message": f"🏃 {member_name} ({member_id}) checked in to the gym at {time_display}.",
            "trainer_id": member["trainer_id"],
            "member_id": member_id,
            "type": "info",
            "link": f"/trainer/members/{member_id}",
            "is_read": False,
            "created_at": now_dt
        })
        
    # Notify Admin
    db.notifications.insert_one({
        "title": "Member Check-In",
        "message": f"{member_name} ({member_id}) checked in via Member Portal at {time_display}.",
        "type": "info",
        "link": "/attendance",
        "is_read": False,
        "created_at": now_dt
    })
    
    flash(f"✓ Checked in successfully at {time_display}! Enjoy your workout.", "success")
    return redirect(request.referrer or url_for('member.dashboard'))

@member_bp.route('/attendance/check-out', methods=['POST'])
@login_required
@role_required('member')
def attendance_checkout():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    member_id = member["member_id"]
    member_name = member.get("full_name") or member.get("name") or "Member"
    
    # Find active attendance record
    active_att = db.attendance.find_one({"member_id": member_id, "status": "Inside"})
    if not active_att:
        flash("No active check-in record found for your account.", "info")
        return redirect(request.referrer or url_for('member.attendance'))
        
    now_dt = get_now()
    cin_dt = active_att.get('check_in_dt')
    tz = get_tz()
    if not cin_dt and active_att.get('check_in'):
        try:
            cin_dt = datetime.strptime(active_att.get('check_in'), "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        except Exception:
            cin_dt = now_dt
    elif cin_dt and cin_dt.tzinfo is None:
        cin_dt = cin_dt.replace(tzinfo=tz)
        
    duration_delta = now_dt - cin_dt
    duration_minutes = max(1, int(duration_delta.total_seconds() // 60))
    hours = duration_minutes // 60
    mins = duration_minutes % 60
    duration_display = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    time_display = now_dt.strftime("%I:%M %p")
    datetime_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    db.attendance.update_one(
        {"_id": active_att["_id"]},
        {"$set": {
            "check_out": datetime_str,
            "check_out_dt": now_dt,
            "check_out_time": time_display,
            "duration_minutes": duration_minutes,
            "duration_display": duration_display,
            "status": "Checked Out",
            "updated_at": now_dt
        }}
    )
    
    # Notify Trainer
    if member.get("trainer_id"):
        db.notifications.insert_one({
            "title": "Client Checked Out",
            "message": f"👋 {member_name} ({member_id}) checked out at {time_display} (Session: {duration_display}).",
            "trainer_id": member["trainer_id"],
            "member_id": member_id,
            "type": "info",
            "link": f"/trainer/members/{member_id}",
            "is_read": False,
            "created_at": now_dt
        })
        
    # Notify Admin
    db.notifications.insert_one({
        "title": "Member Check-Out",
        "message": f"{member_name} ({member_id}) checked out after {duration_display}.",
        "type": "info",
        "link": "/attendance",
        "is_read": False,
        "created_at": now_dt
    })
    
    flash(f"✓ Checked out successfully at {time_display}! Total gym session: {duration_display}.", "success")
    return redirect(request.referrer or url_for('member.dashboard'))

@member_bp.route('/payments')
@login_required
@role_required('member')
def payments():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    # Member can view ONLY their own payments
    payments_list = list(db.payments.find({
        "member_id": member["member_id"]
    }).sort("created_at", -1))
    
    total_paid = sum(float(p.get("amount", 0)) for p in payments_list if p.get("payment_status") == "Paid")

    return render_template(
        'member/payments.html',
        member=member,
        payments=payments_list,
        total_paid=total_paid,
        total_paid_formatted=format_currency(total_paid)
    )

@member_bp.route('/trainer')
@login_required
@role_required('member')
def trainer():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    trainer_doc = None
    if member.get('trainer_id'):
        trainer_doc = db.trainers.find_one({"trainer_id": member['trainer_id']})
        
    # Schedules with trainer
    schedules = []
    if member.get('trainer_id'):
        schedules = list(db.schedules.find({
            "member_id": member["member_id"],
            "trainer_id": member["trainer_id"]
        }).sort("date", -1))

    return render_template(
        'member/trainer.html',
        member=member,
        trainer=trainer_doc,
        schedules=schedules
    )

@member_bp.route('/workouts')
@login_required
@role_required('member')
def workouts():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    # View assigned workout plans
    plans = list(db.workout_plans.find({
        "member_id": member["member_id"]
    }).sort("created_at", -1))

    return render_template('member/workouts.html', member=member, workouts=plans)

@member_bp.route('/workouts/<workout_id>/complete', methods=['POST'])
@login_required
@role_required('member')
def complete_workout(workout_id):
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    member_id = member["member_id"]
    
    # Flexible ID matching: workout_id string, ObjectId, or string _id
    or_conds = [
        {"workout_id": workout_id},
        {"workout_id": str(workout_id)},
        {"_id": workout_id}
    ]
    if ObjectId.is_valid(workout_id):
        or_conds.append({"_id": ObjectId(workout_id)})
        
    workout = db.workout_plans.find_one({
        "member_id": member_id,
        "$or": or_conds
    })
    if not workout:
        # Fallback query without member_id restriction in case assigned by email or trainer
        workout = db.workout_plans.find_one({"$or": or_conds})
        
    if not workout:
        flash("Workout plan not found or not assigned to your account.", "danger")
        return redirect(request.referrer or url_for('member.dashboard'))
        
    now = get_now()
    completed_time_str = now.strftime("%I:%M %p")
    completed_date_str = now.strftime("%Y-%m-%d")
    
    db.workout_plans.update_one(
        {"_id": workout["_id"]},
        {"$set": {
            "status": "completed",
            "completed_at": now,
            "completed_date": completed_date_str,
            "completed_time": completed_time_str
        }}
    )
    
    # Send completion notification to Trainer & Gym Admin
    trainer_id = workout.get("trainer_id") or member.get("trainer_id")
    workout_title = workout.get('title') or workout.get('workout_name') or "Workout Routine"
    member_name = member.get('full_name') or member.get('name') or "Member"
    
    if trainer_id:
        db.notifications.insert_one({
            "title": "Workout Completed",
            "message": f"🎉 {member_name} ({member_id}) completed their workout: '{workout_title}' at {completed_time_str}!",
            "trainer_id": trainer_id,
            "member_id": member_id,
            "type": "success",
            "link": "/trainer/workouts",
            "is_read": False,
            "created_at": now
        })
        
    flash(f"✓ Workout '{workout_title}' marked as COMPLETED! Great job sticking to your fitness routine.", "success")
    return redirect(request.referrer or url_for('member.dashboard'))

@member_bp.route('/notifications')
@login_required
@role_required('member')
def notifications():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    notifications_list = list(db.notifications.find({
        "$or": [
            {"member_id": member["member_id"]},
            {"type": {"$in": ["member", "general", "announcement"]}},
            {"member_id": {"$exists": False}}
        ]
    }).sort("created_at", -1))

    return render_template('member/notifications.html', member=member, notifications=notifications_list)

@member_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
@role_required('member')
def mark_notifications_read():
    db = get_db()
    member = get_current_member(db)
    if member:
        db.notifications.update_many(
            {
                "$or": [
                    {"member_id": member["member_id"]},
                    {"type": {"$in": ["member", "general", "announcement"]}}
                ]
            },
            {"$set": {"is_read": True}}
        )
    flash("All notifications marked as read.", "success")
    return redirect(url_for('member.notifications'))

@member_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('member')
def settings():
    db = get_db()
    member = get_current_member(db)
    if not member:
        flash("Member record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')
            
            user = db.users.find_one({"$or": [{"member_id": member["member_id"]}, {"email": member["email"]}]})
            if not user or not verify_password(user.get('password', ''), current_pwd):
                flash("Current password entered is incorrect.", "danger")
                return redirect(url_for('member.settings'))
                
            if len(new_pwd) < 6:
                flash("New password must be at least 6 characters.", "danger")
                return redirect(url_for('member.settings'))
                
            if new_pwd != confirm_pwd:
                flash("New password and confirm password do not match.", "danger")
                return redirect(url_for('member.settings'))
                
            hashed = hash_password(new_pwd)
            db.users.update_one({"_id": user["_id"]}, {"$set": {"password": hashed, "updated_at": get_now()}})
            db.members.update_one({"member_id": member["member_id"]}, {"$set": {"password": hashed}})
            flash("Your password has been updated securely.", "success")
            return redirect(url_for('member.settings'))
            
    return render_template('member/settings.html', member=member)
