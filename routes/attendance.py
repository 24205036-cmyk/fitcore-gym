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
        
    if search_q:
        query['$or'] = [
            {'member_id': {'$regex': search_q, '$options': 'i'}},
            {'member_name': {'$regex': search_q, '$options': 'i'}}
        ]

    attendance_records = list(db.attendance.find(query).sort("check_in", -1))
    
    # Calculate statistics for today specifically
    today_records = list(db.attendance.find({"check_in_date": today_dt.strftime("%Y-%m-%d")}))
    today_checkins = len(today_records)
    currently_inside = db.attendance.count_documents({"status": "Inside"})
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
        today_checkouts=today_checkouts,
        avg_duration_display=avg_duration_display,
        hourly_history=hourly_history,
        filter_period=filter_period,
        custom_date=custom_date,
        target_date_str=target_date_str,
        status_filter=status_filter,
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
            flash("Please enter Member ID, Phone, or Name.", 'danger')
            return render_template('attendance/checkin.html')
            
        # 1. Find Member
        member = db.members.find_one({
            '$or': [
                {'member_id': {'$regex': f"^{identifier}$", '$options': 'i'}},
                {'phone': identifier},
                {'full_name': {'$regex': identifier, '$options': 'i'}}
            ]
        })
        
        if not member:
            flash(f"No member found matching '{identifier}'.", 'danger')
            return render_template('attendance/checkin.html', identifier=identifier)
            
        member_id = member['member_id']
        member_name = member['full_name']
        
        # 2. Check Membership Status
        if member.get('status') == 'Expired':
            flash(f"Cannot check in: Membership for {member_name} ({member_id}) has EXPIRED. Please renew first.", 'danger')
            return render_template('attendance/checkin.html', member=member, needs_renewal=True)
            
        if member.get('status') in ['Suspended', 'Inactive']:
            flash(f"Cannot check in: Member {member_name} ({member_id}) is currently {member.get('status')}.", 'danger')
            return render_template('attendance/checkin.html', member=member)
            
        # 3. Check Duplicate Active Check-In
        already_inside = db.attendance.find_one({"member_id": member_id, "status": "Inside"})
        if already_inside:
            flash(f"Member {member_name} ({member_id}) is already checked in and inside the gym since {already_inside.get('time_display', '')}.", 'warning')
            return redirect(url_for('attendance.list_attendance'))
            
        # 4. Check Gym Capacity Limit
        current_inside = db.attendance.count_documents({"status": "Inside"})
        if current_inside >= capacity:
            flash(f"Gym is currently at full capacity ({capacity}/{capacity}). Check-in denied until someone checks out.", 'danger')
            return render_template('attendance/checkin.html', member=member, full_capacity=True)
            
        # 5. Record Attendance
        now_dt = get_now()
        att_record = {
            "member_id": member_id,
            "member_name": member_name,
            "plan_name": member.get("plan_name", "Standard"),
            "check_in": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "check_in_dt": now_dt,
            "check_in_date": now_dt.strftime("%Y-%m-%d"),
            "time_display": now_dt.strftime("%I:%M %p"),
            "check_out": None,
            "check_out_dt": None,
            "duration_minutes": 0,
            "duration_display": "-",
            "status": "Inside",
            "created_at": now_dt
        }
        db.attendance.insert_one(att_record)
        
        # 6. Notification
        log_notification(
            title="Member Checked In",
            message=f"{member_name} ({member_id}) checked in.",
            notif_type="info",
            link="/attendance"
        )
        
        # Check capacity threshold warning
        new_inside = current_inside + 1
        pct = (new_inside / capacity) * 100
        if pct >= 90:
            log_notification(
                title="High Gym Occupancy",
                message=f"Gym capacity has reached {int(pct)}% ({new_inside}/{capacity} members inside).",
                notif_type="warning",
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
    
    log_notification(
        title="Member Checked Out",
        message=f"{att.get('member_name')} checked out after {duration_display}.",
        notif_type="info",
        link="/attendance"
    )
    
    flash(f"Check-out successful for {att.get('member_name')}. Duration: {duration_display}.", 'success')
    return redirect(request.referrer or url_for('attendance.list_attendance'))

# API Endpoints
@attendance_bp.route('/api/check-in', methods=['POST'])
@login_required
def api_check_in():
    data = request.get_json(silent=True) or request.form
    member_id = data.get('member_id', '').strip()
    
    if not member_id:
        return jsonify({"success": False, "message": "Member ID is required."}), 400
        
    db = get_db()
    member = db.members.find_one({
        '$or': [
            {'member_id': {'$regex': f"^{member_id}$", '$options': 'i'}},
            {'phone': member_id},
            {'full_name': {'$regex': member_id, '$options': 'i'}}
        ]
    })
    if not member:
        return jsonify({"success": False, "message": f"Member '{member_id}' not found."}), 404
        
    member_id = member['member_id']
    member_name = member['full_name']
        
    if member.get('status') == 'Expired':
        return jsonify({"success": False, "message": f"Membership for {member_name} has expired. Please renew first."}), 400
        
    if member.get('status') in ['Suspended', 'Inactive']:
        return jsonify({"success": False, "message": f"Member status is {member.get('status')}."}), 400
        
    # Check duplicate
    existing = db.attendance.find_one({"member_id": member_id, "status": "Inside"})
    if existing:
        return jsonify({"success": False, "message": f"{member_name} ({member_id}) is already inside the gym."}), 400
        
    # Capacity check
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    current_inside = db.attendance.count_documents({"status": "Inside"})
    if current_inside >= capacity:
        return jsonify({"success": False, "message": f"Gym is currently at full capacity ({capacity}/{capacity})."}), 400
        
    now_dt = get_now()
    att_doc = {
        "member_id": member_id,
        "member_name": member.get("full_name"),
        "plan_name": member.get("plan_name", "Standard"),
        "check_in": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "check_in_dt": now_dt,
        "check_in_date": now_dt.strftime("%Y-%m-%d"),
        "time_display": now_dt.strftime("%I:%M %p"),
        "check_out": None,
        "check_out_dt": None,
        "duration_minutes": 0,
        "duration_display": "-",
        "status": "Inside",
        "created_at": now_dt
    }
    res = db.attendance.insert_one(att_doc)
    
    log_notification(
        title="Member Checked In",
        message=f"{member.get('full_name')} ({member_id}) checked in.",
        notif_type="info",
        link="/attendance"
    )
    
    return jsonify({
        "success": True,
        "message": f"Check-in successful for {member.get('full_name')}!",
        "data": {
            "record_id": str(res.inserted_id),
            "member_id": member_id,
            "member_name": member.get("full_name"),
            "check_in": att_doc["time_display"]
        }
    })

@attendance_bp.route('/api/check-out', methods=['POST'])
@login_required
def api_check_out():
    data = request.get_json(silent=True) or request.form
    member_id = data.get('member_id', '').strip()
    
    if not member_id:
        return jsonify({"success": False, "message": "Member ID is required."}), 400
        
    db = get_db()
    att = db.attendance.find_one({"member_id": member_id, "status": "Inside"})
    if not att:
        return jsonify({"success": False, "message": f"No active check-in found for {member_id}."}), 404
        
    now_dt = get_now()
    cin_dt = att.get('check_in_dt') or now_dt
    if cin_dt.tzinfo is None:
        cin_dt = cin_dt.replace(tzinfo=get_tz())
        
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
    
    return jsonify({
        "success": True,
        "message": f"Check-out successful for {att.get('member_name')}.",
        "data": {
            "member_id": member_id,
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
