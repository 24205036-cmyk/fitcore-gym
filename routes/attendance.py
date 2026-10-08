from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta, time
from bson import ObjectId
from database import get_db
from utils.decorators import login_required
from utils.helpers import (
    get_now, get_tz, format_datetime, format_date,
    get_gym_settings, calculate_occupancy_status
)
from utils.notifier import log_notification

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

def compute_hourly_occupancy(db, target_date_str: str, capacity: int) -> list:
    """
    Computes hourly snapshot of gym occupancy for a given date
    based on actual attendance check-in and check-out timestamps.
    """
    tz = get_tz()
    hours_to_check = [6, 8, 10, 12, 14, 16, 18, 20]
    results = []
    
    # Fetch all records that were active on target_date
    records = list(db.attendance.find({
        "check_in_date": target_date_str
    }))
    
    for h in hours_to_check:
        slot_dt = datetime.strptime(f"{target_date_str} {h:02d}:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        slot_time_str = slot_dt.strftime("%I:%M %p")
        
        # Count members inside at slot_dt
        count = 0
        for r in records:
            cin = r.get("check_in_dt")
            cout = r.get("check_out_dt")
            
            # If stored as string, convert
            if isinstance(cin, str):
                try:
                    cin = datetime.fromisoformat(cin)
                except Exception:
                    cin = None
            if isinstance(cout, str):
                try:
                    cout = datetime.fromisoformat(cout)
                except Exception:
                    cout = None
                    
            if cin:
                if cin.tzinfo is None:
                    cin = cin.replace(tzinfo=tz)
                if cout and cout.tzinfo is None:
                    cout = cout.replace(tzinfo=tz)
                    
                if cin <= slot_dt:
                    if cout is None or cout >= slot_dt:
                        count += 1
                        
        pct = round((count / capacity * 100), 1) if capacity > 0 else 0
        st = calculate_occupancy_status(pct)
        results.append({
            "time": slot_time_str,
            "people_inside": count,
            "capacity": capacity,
            "percentage": pct,
            "status": st["label"],
            "badge_class": st["badge_class"],
            "emoji": st["emoji"]
        })
        
    return results

@attendance_bp.route('')
@login_required
def list_attendance():
    db = get_db()
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    
    filter_period = request.args.get('period', 'today')
    custom_date = request.args.get('date', '').strip()
    status_filter = request.args.get('status', '').strip()
    role_filter = request.args.get('role', 'all').strip().lower()
    search_q = request.args.get('search', '').strip()
    
    today_dt = get_now().date()
    target_date_str = today_dt.strftime("%Y-%m-%d")
    
    query = {}
    
    if filter_period == 'today':
        query['check_in_date'] = target_date_str
    elif filter_period == 'yesterday':
        yest_str = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        query['check_in_date'] = yest_str
        target_date_str = yest_str
    elif filter_period == 'this_week':
        start_week = (today_dt - timedelta(days=today_dt.weekday())).strftime("%Y-%m-%d")
        query['check_in_date'] = {'$gte': start_week, '$lte': target_date_str}
    elif filter_period == 'this_month':
        start_month = today_dt.strftime("%Y-%m-01")
        query['check_in_date'] = {'$gte': start_month, '$lte': target_date_str}
    elif filter_period == 'custom' and custom_date:
        query['check_in_date'] = custom_date
        target_date_str = custom_date
        
    if status_filter:
        query['status'] = status_filter
        
    attendance_records = list(db.attendance.find(query).sort("check_in", -1))
    
    # Normalize records for unified display
    normalized_records = []
    for r in attendance_records:
        is_trn = (r.get('person_type') == 'trainer') or (bool(r.get('trainer_id')) and not bool(r.get('member_id')))
        r['is_trainer'] = is_trn
        r['person_role'] = "Trainer" if is_trn else "Member"
        r['person_name'] = (r.get('trainer_name') if is_trn else r.get('member_name')) or r.get('name') or ('Trainer' if is_trn else 'Member')
        r['person_id'] = r.get('trainer_id') if is_trn else (r.get('member_id') or r.get('trainer_id'))
        r['subtext'] = r.get('specialization', 'Fitness Coach') if is_trn else (r.get('plan_name') or 'Standard Plan')
        cin_dt = r.get('check_in_dt')
        if cin_dt and hasattr(cin_dt, 'isoformat'):
            r['check_in_iso'] = cin_dt.isoformat()
        elif r.get('check_in'):
            r['check_in_iso'] = str(r['check_in']).replace(' ', 'T')
        else:
            r['check_in_iso'] = ''

        if role_filter == 'member' and is_trn:
            continue
        if role_filter == 'trainer' and not is_trn:
            continue
        if search_q:
            q_low = search_q.lower()
            if (q_low not in str(r.get('person_id', '')).lower() and
                q_low not in str(r.get('person_name', '')).lower() and
                q_low not in str(r.get('subtext', '')).lower()):
                continue
        normalized_records.append(r)
    attendance_records = normalized_records

    # Calculate statistics for today specifically
    today_records = list(db.attendance.find({"check_in_date": today_dt.strftime("%Y-%m-%d")}))
    today_checkins = len(today_records)
    all_inside = list(db.attendance.find({"status": "Inside"}))
    currently_inside = len(all_inside)
    trainers_inside = sum(1 for r in all_inside if (r.get('person_type') == 'trainer' or (bool(r.get('trainer_id')) and not bool(r.get('member_id')))))
    members_inside = max(0, currently_inside - trainers_inside)
    today_checkouts = sum(1 for r in today_records if r.get('status') == 'Checked Out')
    
    # Average visit duration today
    durations = [r.get('duration_minutes', 0) for r in today_records if r.get('duration_minutes', 0) > 0]
    avg_minutes = round(sum(durations) / len(durations)) if durations else 0
    avg_duration_display = f"{avg_minutes // 60}h {avg_minutes % 60}m" if avg_minutes > 0 else "-"
    
    # Occupancy History Table (Section 36 - NO CHARTS)
    hourly_history = compute_hourly_occupancy(db, target_date_str, capacity)

    return render_template(
        'attendance/list.html',
        records=attendance_records,
        today_checkins=today_checkins,
        currently_inside=currently_inside,
        members_inside=members_inside,
        trainers_inside=trainers_inside,
        today_checkouts=today_checkouts,
        avg_duration_display=avg_duration_display,
        hourly_history=hourly_history,
        filter_period=filter_period,
        custom_date=custom_date,
        target_date_str=target_date_str,
        status_filter=status_filter,
        role_filter=role_filter,
        search_q=search_q,
        capacity=capacity
    )

@attendance_bp.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    db = get_db()
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        if not identifier:
            flash("Please enter Member ID, Trainer ID, Phone, or Name.", 'danger')
            return render_template('attendance/checkin.html')
            
        # 1. Check if matches Member
        member = db.members.find_one({
            '$or': [
                {'member_id': {'$regex': f"^{identifier}$", '$options': 'i'}},
                {'phone': identifier},
                {'full_name': {'$regex': identifier, '$options': 'i'}}
            ]
        })
        
        # 2. Check if matches Trainer
        trainer = None
        if not member:
            trainer = db.trainers.find_one({
                '$or': [
                    {'trainer_id': {'$regex': f"^{identifier}$", '$options': 'i'}},
                    {'phone': identifier},
                    {'name': {'$regex': identifier, '$options': 'i'}}
                ]
            })
            
        if not member and not trainer:
            flash(f"No active member or trainer found matching '{identifier}'.", 'danger')
            return render_template('attendance/checkin.html', identifier=identifier)
            
        now_dt = get_now()
        time_display = now_dt.strftime("%I:%M %p")
        date_str = now_dt.strftime("%Y-%m-%d")
        datetime_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Handle Trainer Check-In
        if trainer:
            trainer_id = trainer['trainer_id']
            trainer_name = trainer['name']
            
            already_inside = db.attendance.find_one({"trainer_id": trainer_id, "status": "Inside"})
            if already_inside:
                flash(f"Trainer {trainer_name} ({trainer_id}) is already checked in on floor since {already_inside.get('time_display', '')}.", 'warning')
                return redirect(url_for('attendance.list_attendance'))
                
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
                "duration_minutes": 0,
                "duration_display": "In Progress",
                "status": "Inside",
                "created_at": now_dt
            }
            db.attendance.insert_one(att_record)
            
            log_notification(
                title="Trainer Checked In",
                message=f"Coach {trainer_name} ({trainer_id}) checked in on floor.",
                notif_type="info",
                link="/attendance"
            )
            flash(f"Check-in successful! Coach {trainer_name} ({trainer_id}) is now marked on floor.", 'success')
            return redirect(url_for('attendance.list_attendance'))
            
        # Handle Member Check-In
        member_id = member['member_id']
        member_name = member['full_name']
        
        # Check Membership Status
        if member.get('status') == 'Expired':
            flash(f"Cannot check in: Membership for {member_name} ({member_id}) has EXPIRED. Please renew first.", 'danger')
            return render_template('attendance/checkin.html', member=member, needs_renewal=True)
            
        if member.get('status') in ['Suspended', 'Inactive']:
            flash(f"Cannot check in: Member {member_name} ({member_id}) is currently {member.get('status')}.", 'danger')
            return render_template('attendance/checkin.html', member=member)
            
        # Check Duplicate Active Check-In
        already_inside = db.attendance.find_one({"member_id": member_id, "status": "Inside"})
        if already_inside:
            flash(f"Member {member_name} ({member_id}) is already checked in and inside the gym since {already_inside.get('time_display', '')}.", 'warning')
            return redirect(url_for('attendance.list_attendance'))
            
        # Check Gym Capacity Limit
        current_inside = db.attendance.count_documents({"status": "Inside"})
        if current_inside >= capacity:
            flash(f"Gym is currently at full capacity ({capacity}/{capacity}). Check-in denied until someone checks out.", 'danger')
            return render_template('attendance/checkin.html', member=member, full_capacity=True)
            
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
            "duration_minutes": 0,
            "duration_display": "In Progress",
            "status": "Inside",
            "trainer_id": member.get("trainer_id"),
            "created_at": now_dt
        }
        db.attendance.insert_one(att_record)
        
        log_notification(
            title="Member Checked In",
            message=f"{member_name} ({member_id}) checked in.",
            notif_type="info",
            link="/attendance"
        )
        
        flash(f"Check-in successful! {member_name} ({member_id}) is now inside.", 'success')
        return redirect(url_for('attendance.list_attendance'))
        
    return render_template('attendance/checkin.html')

@attendance_bp.route('/checkout/<record_id>', methods=['POST'])
@login_required
def checkout(record_id):
    db = get_db()
    try:
        att = db.attendance.find_one({"_id": ObjectId(record_id)})
    except Exception:
        att = None
        
    if not att:
        flash("Attendance record not found.", 'danger')
        return redirect(url_for('attendance.list_attendance'))
        
    if att.get('status') == 'Checked Out':
        flash("Member is already checked out.", 'info')
        return redirect(url_for('attendance.list_attendance'))
        
    now_dt = get_now()
    cin_dt = att.get('check_in_dt')
    if not cin_dt and att.get('check_in'):
        try:
            cin_dt = datetime.strptime(att.get('check_in'), "%Y-%m-%d %H:%M:%S").replace(tzinfo=get_tz())
        except Exception:
            cin_dt = now_dt
    elif cin_dt and cin_dt.tzinfo is None:
        cin_dt = cin_dt.replace(tzinfo=get_tz())
        
    # Calculate duration
    duration_delta = now_dt - cin_dt
    duration_minutes = max(1, int(duration_delta.total_seconds() // 60))
    hours = duration_minutes // 60
    mins = duration_minutes % 60
    duration_display = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    
    db.attendance.update_one(
        {"_id": att["_id"]},
        {"$set": {
            "check_out": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "check_out_dt": now_dt,
            "duration_minutes": duration_minutes,
            "duration_display": duration_display,
            "status": "Checked Out"
        }}
    )
    
    is_trn = (att.get('person_type') == 'trainer') or (bool(att.get('trainer_id')) and not bool(att.get('member_id')))
    person_name = (att.get('trainer_name') if is_trn else att.get('member_name')) or att.get('name') or ('Trainer' if is_trn else 'Member')
    role_label = "Trainer" if is_trn else "Member"
    
    log_notification(
        title=f"{role_label} Checked Out",
        message=f"{person_name} checked out after {duration_display}.",
        notif_type="info",
        link="/attendance"
    )
    
    flash(f"Check-out successful for {person_name}. Duration: {duration_display}.", 'success')
    return redirect(request.referrer or url_for('attendance.list_attendance'))

# API Endpoints
@attendance_bp.route('/api/check-in', methods=['POST'])
@login_required
def api_check_in():
    data = request.get_json(silent=True) or request.form
    identifier = (data.get('member_id') or data.get('identifier') or data.get('trainer_id') or '').strip()
    
    if not identifier:
        return jsonify({"success": False, "message": "Member ID or Trainer ID is required."}), 400
        
    db = get_db()
    # 1. Check member
    member = db.members.find_one({
        '$or': [
            {'member_id': {'$regex': f"^{identifier}$", '$options': 'i'}},
            {'phone': identifier},
            {'full_name': {'$regex': identifier, '$options': 'i'}}
        ]
    })
    
    # 2. Check trainer
    trainer = None
    if not member:
        trainer = db.trainers.find_one({
            '$or': [
                {'trainer_id': {'$regex': f"^{identifier}$", '$options': 'i'}},
                {'phone': identifier},
                {'name': {'$regex': identifier, '$options': 'i'}}
            ]
        })
        
    if not member and not trainer:
        return jsonify({"success": False, "message": f"'{identifier}' was not found as a member or trainer."}), 404
        
    now_dt = get_now()
    time_display = now_dt.strftime("%I:%M %p")
    date_str = now_dt.strftime("%Y-%m-%d")
    datetime_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Trainer API checkin
    if trainer:
        trainer_id = trainer['trainer_id']
        trainer_name = trainer['name']
        existing = db.attendance.find_one({"trainer_id": trainer_id, "status": "Inside"})
        if existing:
            return jsonify({"success": False, "message": f"Trainer {trainer_name} ({trainer_id}) is already inside."}), 400
            
        att_doc = {
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
            "duration_minutes": 0,
            "duration_display": "In Progress",
            "status": "Inside",
            "created_at": now_dt
        }
        res = db.attendance.insert_one(att_doc)
        log_notification(
            title="Trainer Checked In",
            message=f"Coach {trainer_name} ({trainer_id}) checked in on floor.",
            notif_type="info",
            link="/attendance"
        )
        return jsonify({
            "success": True,
            "message": f"Check-in successful for Coach {trainer_name}!",
            "data": {
                "record_id": str(res.inserted_id),
                "id": trainer_id,
                "name": trainer_name,
                "role": "Trainer",
                "check_in": time_display
            }
        })

    # Member API checkin
    member_id = member['member_id']
    member_name = member['full_name']
        
    if member.get('status') == 'Expired':
        return jsonify({"success": False, "message": f"Membership for {member_name} has expired. Please renew first."}), 400
        
    if member.get('status') in ['Suspended', 'Inactive']:
        return jsonify({"success": False, "message": f"Member status is {member.get('status')}."}), 400
        
    existing = db.attendance.find_one({"member_id": member_id, "status": "Inside"})
    if existing:
        return jsonify({"success": False, "message": f"{member_name} ({member_id}) is already inside the gym."}), 400
        
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    current_inside = db.attendance.count_documents({"status": "Inside"})
    if current_inside >= capacity:
        return jsonify({"success": False, "message": f"Gym is currently at full capacity ({capacity}/{capacity})."}), 400
        
    att_doc = {
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
        "duration_minutes": 0,
        "duration_display": "In Progress",
        "status": "Inside",
        "trainer_id": member.get("trainer_id"),
        "created_at": now_dt
    }
    res = db.attendance.insert_one(att_doc)
    
    log_notification(
        title="Member Checked In",
        message=f"{member_name} ({member_id}) checked in.",
        notif_type="info",
        link="/attendance"
    )
    
    return jsonify({
        "success": True,
        "message": f"Check-in successful for {member_name}!",
        "data": {
            "record_id": str(res.inserted_id),
            "id": member_id,
            "name": member_name,
            "role": "Member",
            "check_in": time_display
        }
    })

@attendance_bp.route('/api/check-out', methods=['POST'])
@login_required
def api_check_out():
    data = request.get_json(silent=True) or request.form
    identifier = (data.get('member_id') or data.get('identifier') or data.get('trainer_id') or '').strip()
    
    if not identifier:
        return jsonify({"success": False, "message": "Identifier is required."}), 400
        
    db = get_db()
    # Check for member check-in first
    att = db.attendance.find_one({
        "member_id": {'$regex': f"^{identifier}$", '$options': 'i'},
        "status": "Inside"
    })
    # Otherwise check for trainer check-in
    if not att:
        att = db.attendance.find_one({
            "trainer_id": {'$regex': f"^{identifier}$", '$options': 'i'},
            "person_type": "trainer",
            "status": "Inside"
        })
    if not att:
        att = db.attendance.find_one({
            "trainer_id": {'$regex': f"^{identifier}$", '$options': 'i'},
            "member_id": {"$in": [None, ""]},
            "status": "Inside"
        })
    if not att:
        return jsonify({"success": False, "message": f"No active check-in found for '{identifier}'."}), 404
        
    now_dt = get_now()
    cin_dt = att.get('check_in_dt') or now_dt
    if hasattr(cin_dt, 'tzinfo') and cin_dt.tzinfo is not None:
        cin_dt = cin_dt.replace(tzinfo=None)
    now_naive = now_dt.replace(tzinfo=None) if hasattr(now_dt, 'tzinfo') and now_dt.tzinfo else now_dt
    if not isinstance(cin_dt, datetime):
        try:
            cin_dt = datetime.strptime(str(att.get('check_in')), "%Y-%m-%d %H:%M:%S")
        except Exception:
            cin_dt = now_naive
            
    duration_delta = now_naive - cin_dt
    duration_minutes = max(1, int(duration_delta.total_seconds() // 60))
    hours = duration_minutes // 60
    mins = duration_minutes % 60
    duration_display = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    time_display = now_dt.strftime("%I:%M %p")
    datetime_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    db.attendance.update_one(
        {"_id": att["_id"]},
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
    
    person_name = att.get('trainer_name') or att.get('member_name') or att.get('name')
    return jsonify({
        "success": True,
        "message": f"Check-out successful for {person_name}.",
        "data": {
            "identifier": identifier,
            "duration": duration_display
        }
    })

@attendance_bp.route('/api/today')
@login_required
def api_today():
    db = get_db()
    today_str = get_now().strftime("%Y-%m-%d")
    records = list(db.attendance.find({"check_in_date": today_str}).sort("check_in", -1))
    
    clean_records = []
    for r in records:
        clean_records.append({
            "member_id": r.get("member_id"),
            "member_name": r.get("member_name"),
            "plan_name": r.get("plan_name"),
            "check_in": r.get("time_display"),
            "check_out": r.get("check_out"),
            "duration": r.get("duration_display", "-"),
            "status": r.get("status")
        })
        
    return jsonify({
        "success": True,
        "count": len(clean_records),
        "data": clean_records
    })
