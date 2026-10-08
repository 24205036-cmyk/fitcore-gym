import re
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database import get_db
from utils.decorators import login_required, role_required
from utils.auth import verify_password, hash_password
from utils.ids import get_next_workout_id, get_next_schedule_id
from utils.helpers import (
    get_now, get_gym_settings, is_gym_open, 
    calculate_occupancy_status, format_currency
)

trainer_bp = Blueprint('trainer', __name__, url_prefix='/trainer')

def get_current_trainer(db):
    """
    Retrieves the current authenticated trainer document.
    """
    user_id = session.get('user_id')
    trainer_id = session.get('trainer_id')
    email = session.get('email')
    
    query = {}
    if trainer_id:
        query["trainer_id"] = trainer_id
    elif user_id:
        query["$or"] = [{"user_id": user_id}, {"trainer_id": user_id}]
    elif email:
        query["email"] = {"$regex": f"^{re.escape(email)}$", "$options": "i"}
        
    trainer = db.trainers.find_one(query)
    if trainer and not session.get('trainer_id'):
        session['trainer_id'] = trainer.get('trainer_id')
    return trainer

@trainer_bp.route('/dashboard')
@login_required
@role_required('trainer')
def dashboard():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found. Please contact the administrator.", "danger")
        return redirect(url_for('auth.logout'))
        
    trainer_id = trainer["trainer_id"]
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    gym_open = is_gym_open(settings)
    
    # 1. Assigned Members
    assigned_members = list(db.members.find({"trainer_id": trainer_id}))
    assigned_count = len(assigned_members)
    assigned_member_ids = [m["member_id"] for m in assigned_members]
    
    # 2. Present Members inside gym today from assigned list
    present_assigned_count = 0
    if assigned_member_ids:
        present_assigned_count = db.attendance.count_documents({
            "member_id": {"$in": assigned_member_ids},
            "status": "Inside"
        })
        
    # 3. Overall Gym Occupancy (real-time from actual attendance)
    current_inside = db.attendance.count_documents({"status": "Inside"})
    occupancy_pct = round((current_inside / capacity * 100), 1) if capacity > 0 else 0
    available_spaces = max(0, capacity - current_inside)
    occ_status = calculate_occupancy_status(occupancy_pct)
    
    # 4. Today's Schedules & Sessions
    today_str = get_now().strftime("%Y-%m-%d")
    today_sessions = list(db.schedules.find({
        "trainer_id": trainer_id,
        "date": today_str
    }).sort("time", 1))
    
    today_session_count = len(today_sessions)
    pending_session_count = sum(1 for s in today_sessions if s.get("status") == "Scheduled")
    
    # 5. Recent Attendance of assigned members
    recent_attendance = []
    if assigned_member_ids:
        recent_attendance = list(db.attendance.find({
            "member_id": {"$in": assigned_member_ids}
        }).sort("created_at", -1).limit(5))
        
    # 6. Notifications for trainer
    notifications = list(db.notifications.find({
        "$or": [
            {"trainer_id": trainer_id},
            {"type": {"$in": ["trainer", "general", "announcement"]}},
            {"trainer_id": {"$exists": False}}
        ]
    }).sort("created_at", -1).limit(4))

    # 7. Assigned client workout plans (active & completed)
    assigned_workouts = []
    completed_workouts_count = 0
    if assigned_member_ids:
        assigned_workouts = list(db.workout_plans.find({
            "$or": [
                {"trainer_id": trainer_id},
                {"member_id": {"$in": assigned_member_ids}}
            ]
        }).sort([("completed_at", -1), ("created_at", -1)]).limit(6))
        
        completed_workouts_count = db.workout_plans.count_documents({
            "$or": [
                {"trainer_id": trainer_id},
                {"member_id": {"$in": assigned_member_ids}}
            ],
            "status": "completed"
        })

    # Enrich assigned_members with live attendance status
    for m in assigned_members:
        att = db.attendance.find_one({"member_id": m["member_id"], "status": "Inside"})
        m["is_inside"] = bool(att)
        m["check_in_time"] = att.get("time_display") or att.get("check_in_time") if att else None

    # Check trainer's own shift attendance
    active_trainer_att = db.attendance.find_one({"trainer_id": trainer_id, "status": "Inside"})
    is_checked_in = bool(active_trainer_att)

    return render_template(
        'trainer/dashboard.html',
        trainer=trainer,
        assigned_count=assigned_count,
        present_assigned_count=present_assigned_count,
        today_session_count=today_session_count,
        pending_session_count=pending_session_count,
        current_inside=current_inside,
        capacity=capacity,
        available_spaces=available_spaces,
        occupancy_pct=occupancy_pct,
        occupancy_status=occ_status,
        gym_settings=settings,
        gym_open=gym_open,
        today_sessions=today_sessions,
        recent_attendance=recent_attendance,
        notifications=notifications,
        assigned_members=assigned_members[:6],
        assigned_workouts=assigned_workouts,
        completed_workouts_count=completed_workouts_count,
        active_trainer_att=active_trainer_att,
        is_checked_in=is_checked_in
    )

@trainer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@role_required('trainer')
def profile():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        specialization = request.form.get('specialization', '').strip()
        experience = request.form.get('experience', '').strip()
        gender = request.form.get('gender', trainer.get('gender', 'Male'))
        bio = request.form.get('bio', '').strip()
        
        update_data = {
            "phone": phone,
            "specialization": specialization,
            "experience": experience,
            "gender": gender,
            "bio": bio,
            "updated_at": get_now()
        }
        
        db.trainers.update_one({"trainer_id": trainer["trainer_id"]}, {"$set": update_data})
        db.users.update_one({"trainer_id": trainer["trainer_id"]}, {"$set": {"phone": phone}})
        
        flash("Trainer profile updated successfully.", "success")
        return redirect(url_for('trainer.profile'))
        
    return render_template('trainer/profile.html', trainer=trainer)

@trainer_bp.route('/members')
@login_required
@role_required('trainer')
def members():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    search_q = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    
    query = {"trainer_id": trainer["trainer_id"]}
    if status_filter:
        query["status"] = status_filter
    if search_q:
        query["$or"] = [
            {"member_id": {"$regex": search_q, "$options": "i"}},
            {"full_name": {"$regex": search_q, "$options": "i"}},
            {"phone": {"$regex": search_q, "$options": "i"}}
        ]
        
    members_list = list(db.members.find(query).sort("member_id", 1))
    
    # Enrich with attendance visit count and inside status
    for m in members_list:
        m["visit_count"] = db.attendance.count_documents({"member_id": m["member_id"]})
        m["is_inside"] = bool(db.attendance.find_one({"member_id": m["member_id"], "status": "Inside"}))

    return render_template(
        'trainer/members.html',
        trainer=trainer,
        members=members_list,
        total_count=len(members_list),
        search_q=search_q,
        status_filter=status_filter
    )

@trainer_bp.route('/members/<member_id>')
@login_required
@role_required('trainer')
def member_detail(member_id):
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    # Security: Trainer can view ONLY members assigned to that trainer
    member = db.members.find_one({"member_id": member_id, "trainer_id": trainer["trainer_id"]})
    if not member:
        flash("Access Denied: You can only view members assigned to your training roster.", "danger")
        return redirect(url_for('trainer.members'))
        
    # Attendance history of member
    attendance_history = list(db.attendance.find({"member_id": member_id}).sort("created_at", -1).limit(10))
    total_visits = db.attendance.count_documents({"member_id": member_id})
    
    # Workout plans for this member
    workout_plans = list(db.workout_plans.find({"member_id": member_id}).sort("created_at", -1))
    
    # Upcoming sessions
    sessions = list(db.schedules.find({
        "member_id": member_id,
        "trainer_id": trainer["trainer_id"]
    }).sort("date", -1).limit(5))

    return render_template(
        'trainer/member_detail.html',
        trainer=trainer,
        member=member,
        attendance_history=attendance_history,
        total_visits=total_visits,
        workout_plans=workout_plans,
        sessions=sessions
    )

@trainer_bp.route('/attendance')
@login_required
@role_required('trainer')
def attendance():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    trainer_id = trainer["trainer_id"]
    assigned_members = list(db.members.find({"trainer_id": trainer_id}))
    assigned_member_ids = [m["member_id"] for m in assigned_members]
    
    # Active shift attendance for trainer
    active_trainer_att = db.attendance.find_one({"trainer_id": trainer_id, "status": "Inside"})
    
    # Personal shift logs for trainer
    trainer_records = list(db.attendance.find({
        "trainer_id": trainer_id,
        "person_type": "trainer"
    }).sort("check_in", -1).limit(30))
    
    date_filter = request.args.get('date', '').strip()
    search_q = request.args.get('search', '').strip()
    
    records = []
    if assigned_member_ids:
        and_conditions = [
            {"member_id": {"$in": assigned_member_ids}}
        ]
        if date_filter:
            and_conditions.append({"check_in_date": date_filter})
        if search_q:
            and_conditions.append({
                "$or": [
                    {"member_id": {"$regex": search_q, "$options": "i"}},
                    {"member_name": {"$regex": search_q, "$options": "i"}}
                ]
            })
            
        records = list(db.attendance.find({"$and": and_conditions}).sort("created_at", -1).limit(50))

    return render_template(
        'trainer/attendance.html',
        trainer=trainer,
        records=records,
        trainer_records=trainer_records,
        active_trainer_att=active_trainer_att,
        is_checked_in=bool(active_trainer_att),
        date_filter=date_filter,
        search_q=search_q,
        assigned_count=len(assigned_members)
    )

@trainer_bp.route('/workouts', methods=['GET', 'POST'])
@login_required
@role_required('trainer')
def workouts():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    trainer_id = trainer["trainer_id"]
    assigned_members = list(db.members.find({"trainer_id": trainer_id}))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            member_id = request.form.get('member_id', '').strip()
            # Ensure selected member is assigned to this trainer
            member = db.members.find_one({"member_id": member_id, "trainer_id": trainer_id})
            if not member:
                flash("Invalid member selected. You can only assign plans to your own members.", "danger")
                return redirect(url_for('trainer.workouts'))
                
            workout_id = get_next_workout_id()
            now = get_now()
            workout_date = request.form.get('workout_date', '').strip() or now.strftime("%Y-%m-%d")
            title = request.form.get('title', '').strip() or request.form.get('workout_name', '').strip() or "Daily Workout"
            goal = request.form.get('goal', '').strip() or member.get('fitness_goal', 'General Fitness')
            trainer_notes = request.form.get('trainer_notes', '').strip() or request.form.get('notes', '').strip()
            
            # Parse exercise items
            names = request.form.getlist('exercise_name[]')
            sets_list = request.form.getlist('exercise_sets[]')
            reps_list = request.form.getlist('exercise_reps[]')
            duration_list = request.form.getlist('exercise_duration[]')
            notes_list = request.form.getlist('exercise_notes[]')
            
            exercises_list = []
            if names:
                for idx, n in enumerate(names):
                    if n and n.strip():
                        exercises_list.append({
                            "name": n.strip(),
                            "sets": sets_list[idx].strip() if idx < len(sets_list) and sets_list[idx].strip() else "3",
                            "reps": reps_list[idx].strip() if idx < len(reps_list) and reps_list[idx].strip() else "12",
                            "duration": duration_list[idx].strip() if idx < len(duration_list) else "",
                            "notes": notes_list[idx].strip() if idx < len(notes_list) else ""
                        })
            else:
                single_ex = request.form.get('exercise', '').strip()
                if single_ex:
                    exercises_list.append({
                        "name": single_ex,
                        "sets": str(request.form.get('sets', '3')),
                        "reps": str(request.form.get('repetitions', '12')),
                        "duration": request.form.get('duration', '45 mins'),
                        "notes": ""
                    })
                    
            if not exercises_list:
                exercises_list.append({
                    "name": "General Conditioning Routine",
                    "sets": "3",
                    "reps": "12",
                    "duration": "45 mins",
                    "notes": ""
                })

            new_workout = {
                "workout_id": workout_id,
                "trainer_id": trainer_id,
                "trainer_name": trainer.get("name", "Trainer"),
                "member_id": member_id,
                "member_name": member.get("full_name", "Member"),
                "workout_date": workout_date,
                "title": title,
                "workout_name": title,
                "goal": goal,
                "exercises": exercises_list,
                "exercise": ", ".join([e["name"] for e in exercises_list]),
                "sets": exercises_list[0]["sets"],
                "repetitions": exercises_list[0]["reps"],
                "duration": exercises_list[0].get("duration") or request.form.get('duration', '45 mins'),
                "trainer_notes": trainer_notes,
                "notes": trainer_notes,
                "status": "assigned",
                "created_at": now
            }
            db.workout_plans.insert_one(new_workout)
            
            # Send notification to assigned member
            db.notifications.insert_one({
                "title": "New Workout Assigned",
                "message": f"Trainer {trainer.get('name')} assigned '{title}' for {workout_date}.",
                "member_id": member_id,
                "type": "info",
                "link": "/member/dashboard",
                "is_read": False,
                "created_at": now
            })
            
            flash(f"Workout '{title}' assigned successfully to {member.get('full_name')} for {workout_date}!", "success")
            return redirect(url_for('trainer.workouts'))
            
        elif action == 'delete':
            workout_id = request.form.get('workout_id', '').strip()
            db.workout_plans.delete_one({"workout_id": workout_id, "trainer_id": trainer_id})
            flash("Workout plan deleted.", "info")
            return redirect(url_for('trainer.workouts'))
            
    assigned_member_ids = [m["member_id"] for m in assigned_members]
    plans = list(db.workout_plans.find({
        "$or": [
            {"trainer_id": trainer_id},
            {"member_id": {"$in": assigned_member_ids}}
        ]
    }).sort([("completed_at", -1), ("created_at", -1)]))

    return render_template(
        'trainer/workouts.html',
        trainer=trainer,
        assigned_members=assigned_members,
        workouts=plans
    )

@trainer_bp.route('/schedule', methods=['GET', 'POST'])
@login_required
@role_required('trainer')
def schedule():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    trainer_id = trainer["trainer_id"]
    assigned_members = list(db.members.find({"trainer_id": trainer_id}))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            member_id = request.form.get('member_id', '').strip()
            member = db.members.find_one({"member_id": member_id, "trainer_id": trainer_id})
            if not member:
                flash("Selected member is not assigned to you.", "danger")
                return redirect(url_for('trainer.schedule'))
                
            sch_id = get_next_schedule_id()
            new_session = {
                "schedule_id": sch_id,
                "trainer_id": trainer_id,
                "trainer_name": trainer.get("name"),
                "member_id": member_id,
                "member_name": member.get("full_name"),
                "date": request.form.get('date', '').strip(),
                "time": request.form.get('time', '').strip(),
                "session_type": request.form.get('session_type', 'Personal Training').strip(),
                "status": "Scheduled",
                "notes": request.form.get('notes', '').strip(),
                "created_at": get_now()
            }
            db.schedules.insert_one(new_session)
            flash(f"Session scheduled with {member.get('full_name')} for {new_session['date']} at {new_session['time']}.", "success")
            return redirect(url_for('trainer.schedule'))
            
        elif action == 'update_status':
            schedule_id = request.form.get('schedule_id', '').strip()
            new_status = request.form.get('status', 'Scheduled').strip()
            if new_status in ['Scheduled', 'Completed', 'Cancelled']:
                db.schedules.update_one(
                    {"schedule_id": schedule_id, "trainer_id": trainer_id},
                    {"$set": {"status": new_status, "updated_at": get_now()}}
                )
                flash(f"Session status updated to {new_status}.", "success")
            return redirect(url_for('trainer.schedule'))

    schedules_list = list(db.schedules.find({"trainer_id": trainer_id}).sort("date", -1))

    return render_template(
        'trainer/schedule.html',
        trainer=trainer,
        assigned_members=assigned_members,
        schedules=schedules_list
    )

@trainer_bp.route('/attendance/check-in', methods=['POST'])
@login_required
@role_required('trainer')
def attendance_checkin():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    trainer_id = trainer["trainer_id"]
    trainer_name = trainer.get("name", "Trainer")
    
    # Check if already inside
    already_inside = db.attendance.find_one({"trainer_id": trainer_id, "status": "Inside"})
    if already_inside:
        time_str = already_inside.get("time_display") or "earlier today"
        flash(f"You are already checked in on floor (since {time_str}).", "warning")
        return redirect(request.referrer or url_for('trainer.dashboard'))
        
    now_dt = get_now()
    time_display = now_dt.strftime("%I:%M %p")
    date_str = now_dt.strftime("%Y-%m-%d")
    datetime_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    att_record = {
        "trainer_id": trainer_id,
        "trainer_name": trainer_name,
        "name": trainer_name,
        "person_type": "trainer",
        "role": "Trainer",
        "specialization": trainer.get("specialization", "Fitness Coach"),
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
        "created_at": now_dt
    }
    db.attendance.insert_one(att_record)
    
    # Notify Admin
    db.notifications.insert_one({
        "title": "Trainer Shift Check-In",
        "message": f"Trainer {trainer_name} ({trainer_id}) checked in on duty at {time_display}.",
        "type": "info",
        "link": "/attendance",
        "is_read": False,
        "created_at": now_dt
    })
    
    flash(f"Shift Check-In successful at {time_display}! You are now on duty.", "success")
    return redirect(request.referrer or url_for('trainer.dashboard'))

@trainer_bp.route('/attendance/check-out', methods=['POST'])
@login_required
@role_required('trainer')
def attendance_checkout():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    trainer_id = trainer["trainer_id"]
    trainer_name = trainer.get("name", "Trainer")
    
    active_att = db.attendance.find_one({"trainer_id": trainer_id, "status": "Inside"})
    if not active_att:
        flash("No active shift check-in found for your account.", "info")
        return redirect(request.referrer or url_for('trainer.dashboard'))
        
    now_dt = get_now()
    cin_dt = active_att.get('check_in_dt')
    if not cin_dt and active_att.get('check_in'):
        try:
            cin_dt = datetime.strptime(active_att.get('check_in'), "%Y-%m-%d %H:%M:%S")
        except Exception:
            cin_dt = now_dt
    elif cin_dt and cin_dt.tzinfo is not None:
        # Strip or handle tz if needed
        cin_dt = cin_dt.replace(tzinfo=None)
        
    now_naive = now_dt.replace(tzinfo=None) if now_dt.tzinfo else now_dt
    cin_naive = cin_dt.replace(tzinfo=None) if cin_dt and getattr(cin_dt, 'tzinfo', None) else (cin_dt or now_naive)
    
    duration_delta = now_naive - cin_naive
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
    
    # Notify Admin
    db.notifications.insert_one({
        "title": "Trainer Shift Check-Out",
        "message": f"Trainer {trainer_name} ({trainer_id}) ended shift at {time_display} (Duration: {duration_display}).",
        "type": "info",
        "link": "/attendance",
        "is_read": False,
        "created_at": now_dt
    })
    
    flash(f"Shift Check-Out successful at {time_display}! Total shift duration: {duration_display}.", "success")
    return redirect(request.referrer or url_for('trainer.dashboard'))

@trainer_bp.route('/notifications')
@login_required
@role_required('trainer')
def notifications():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    notifications_list = list(db.notifications.find({
        "$or": [
            {"trainer_id": trainer["trainer_id"]},
            {"type": {"$in": ["trainer", "general", "announcement"]}},
            {"trainer_id": {"$exists": False}}
        ]
    }).sort("created_at", -1))

    return render_template('trainer/notifications.html', trainer=trainer, notifications=notifications_list)

@trainer_bp.route('/notifications/mark-read', methods=['POST'])
@login_required
@role_required('trainer')
def mark_notifications_read():
    db = get_db()
    trainer = get_current_trainer(db)
    if trainer:
        db.notifications.update_many(
            {
                "$or": [
                    {"trainer_id": trainer["trainer_id"]},
                    {"type": {"$in": ["trainer", "general", "announcement"]}}
                ]
            },
            {"$set": {"is_read": True}}
        )
    flash("All notifications marked as read.", "success")
    return redirect(url_for('trainer.notifications'))

@trainer_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('trainer')
def settings():
    db = get_db()
    trainer = get_current_trainer(db)
    if not trainer:
        flash("Trainer record not found.", "danger")
        return redirect(url_for('auth.logout'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')
            
            user = db.users.find_one({"$or": [{"trainer_id": trainer["trainer_id"]}, {"email": trainer["email"]}]})
            if not user or not verify_password(user.get('password', ''), current_pwd):
                flash("Current password entered is incorrect.", "danger")
                return redirect(url_for('trainer.settings'))
                
            if len(new_pwd) < 6:
                flash("New password must be at least 6 characters.", "danger")
                return redirect(url_for('trainer.settings'))
                
            if new_pwd != confirm_pwd:
                flash("New password and confirm password do not match.", "danger")
                return redirect(url_for('trainer.settings'))
                
            hashed = hash_password(new_pwd)
            db.users.update_one({"_id": user["_id"]}, {"$set": {"password": hashed, "updated_at": get_now()}})
            db.trainers.update_one({"trainer_id": trainer["trainer_id"]}, {"$set": {"password": hashed}})
            flash("Your password has been updated securely.", "success")
            return redirect(url_for('trainer.settings'))
            
    return render_template('trainer/settings.html', trainer=trainer)
