from flask import Blueprint, render_template, request, Response
import csv
import io
from datetime import datetime, timedelta
from database import get_db
from utils.decorators import login_required
from utils.helpers import (
    get_now, get_tz, format_currency, format_datetime, format_date,
    get_gym_settings, calculate_occupancy_status
)
from routes.attendance import compute_hourly_occupancy

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('')
@login_required
def index():
    db = get_db()
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    
    # Overview metrics
    total_members = db.members.count_documents({})
    active_members = db.members.count_documents({"status": "Active"})
    expired_members = db.members.count_documents({"status": "Expired"})
    
    total_trainers = db.trainers.count_documents({})
    
    today_str = get_now().strftime("%Y-%m-%d")
    today_visits = db.attendance.count_documents({"check_in_date": today_str})
    current_inside = db.attendance.count_documents({"status": "Inside"})
    
    paid_payments = list(db.payments.find({"payment_status": "Paid"}))
    total_rev = sum(float(p.get("amount", 0)) for p in paid_payments)
    
    occ_pct = round((current_inside / capacity * 100), 1) if capacity > 0 else 0
    occ_status = calculate_occupancy_status(occ_pct)
    
    return render_template(
        'reports/dashboard.html',
        total_members=total_members,
        active_members=active_members,
        expired_members=expired_members,
        total_trainers=total_trainers,
        today_visits=today_visits,
        current_inside=current_inside,
        capacity=capacity,
        total_revenue_formatted=format_currency(total_rev),
        occ_pct=occ_pct,
        occ_status=occ_status
    )

@reports_bp.route('/members')
@login_required
def members_report():
    db = get_db()
    status_filter = request.args.get('status', '').strip()
    plan_filter = request.args.get('plan', '').strip()
    
    query = {}
    if status_filter:
        query['status'] = status_filter
    if plan_filter:
        query['plan_id'] = plan_filter
        
    members = list(db.members.find(query).sort("member_id", 1))
    
    total_members = db.members.count_documents({})
    active_members = db.members.count_documents({"status": "Active"})
    expired_members = db.members.count_documents({"status": "Expired"})
    suspended_members = db.members.count_documents({"status": "Suspended"})
    inactive_members = db.members.count_documents({"status": "Inactive"})
    
    plans = list(db.membership_plans.find({"status": "Active"}))
    
    return render_template(
        'reports/members.html',
        members=members,
        total_members=total_members,
        active_members=active_members,
        expired_members=expired_members,
        suspended_members=suspended_members,
        inactive_members=inactive_members,
        plans=plans,
        status_filter=status_filter,
        plan_filter=plan_filter
    )

@reports_bp.route('/attendance')
@login_required
def attendance_report():
    db = get_db()
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    
    period = request.args.get('period', 'today')
    custom_date = request.args.get('date', '').strip()
    
    today_dt = get_now().date()
    today_str = today_dt.strftime("%Y-%m-%d")
    
    query = {}
    if period == 'today':
        query['check_in_date'] = today_str
    elif period == 'yesterday':
        query['check_in_date'] = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    elif period == 'this_week':
        start_w = (today_dt - timedelta(days=today_dt.weekday())).strftime("%Y-%m-%d")
        query['check_in_date'] = {'$gte': start_w, '$lte': today_str}
    elif period == 'this_month':
        start_m = today_dt.strftime("%Y-%m-01")
        query['check_in_date'] = {'$gte': start_m, '$lte': today_str}
    elif period == 'this_year':
        start_y = today_dt.strftime("%Y-01-01")
        query['check_in_date'] = {'$gte': start_y, '$lte': today_str}
    elif period == 'custom' and custom_date:
        query['check_in_date'] = custom_date
        
    records = list(db.attendance.find(query).sort("check_in", -1))
    
    total_visits = db.attendance.count_documents({})
    today_visits = db.attendance.count_documents({"check_in_date": today_str})
    current_inside = db.attendance.count_documents({"status": "Inside"})
    
    durations = [r.get('duration_minutes', 0) for r in records if r.get('duration_minutes', 0) > 0]
    avg_minutes = round(sum(durations) / len(durations)) if durations else 0
    avg_display = f"{avg_minutes // 60}h {avg_minutes % 60}m" if avg_minutes > 0 else "-"
    
    return render_template(
        'reports/attendance.html',
        records=records,
        total_visits=total_visits,
        today_visits=today_visits,
        current_inside=current_inside,
        avg_display=avg_display,
        period=period,
        custom_date=custom_date
    )

@reports_bp.route('/revenue')
@login_required
def revenue_report():
    db = get_db()
    period = request.args.get('period', 'all')
    method_filter = request.args.get('method', '').strip()
    status_filter = request.args.get('status', '').strip()
    
    query = {}
    if method_filter:
        query['payment_method'] = method_filter
    if status_filter:
        query['payment_status'] = status_filter
        
    now = get_now()
    today_str = now.strftime("%Y-%m-%d")
    if period == 'today':
        query['payment_date'] = {'$regex': f"^{today_str}"}
    elif period == 'this_week':
        w_start = (now.date() - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        query['payment_date'] = {'$gte': w_start}
    elif period == 'this_month':
        query['payment_date'] = {'$regex': f"^{now.strftime('%Y-%m')}"}
    elif period == 'this_year':
        query['payment_date'] = {'$regex': f"^{now.strftime('%Y')}"}
        
    payments = list(db.payments.find(query).sort("payment_date", -1))
    
    # Revenue totals
    paid = list(db.payments.find({"payment_status": "Paid"}))
    today_rev = sum(float(p.get("amount", 0)) for p in paid if p.get("payment_date", "").startswith(today_str))
    week_start = (now.date() - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    week_rev = sum(float(p.get("amount", 0)) for p in paid if p.get("payment_date", "")[:10] >= week_start)
    month_rev = sum(float(p.get("amount", 0)) for p in paid if p.get("payment_date", "").startswith(now.strftime("%Y-%m")))
    year_rev = sum(float(p.get("amount", 0)) for p in paid if p.get("payment_date", "").startswith(now.strftime("%Y")))
    total_rev = sum(float(p.get("amount", 0)) for p in paid)
    
    return render_template(
        'reports/revenue.html',
        payments=payments,
        today_rev=format_currency(today_rev),
        week_rev=format_currency(week_rev),
        month_rev=format_currency(month_rev),
        year_rev=format_currency(year_rev),
        total_rev=format_currency(total_rev),
        period=period,
        method_filter=method_filter,
        status_filter=status_filter
    )

@reports_bp.route('/occupancy')
@login_required
def occupancy_report():
    db = get_db()
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    
    date_str = request.args.get('date', '').strip() or get_now().strftime("%Y-%m-%d")
    
    current_inside = db.attendance.count_documents({"status": "Inside"})
    available_spaces = max(0, capacity - current_inside)
    occ_pct = round((current_inside / capacity * 100), 1) if capacity > 0 else 0
    occ_status = calculate_occupancy_status(occ_pct)
    
    # Hourly history table computed dynamically from records (Section 36 & 46)
    hourly_history = compute_hourly_occupancy(db, date_str, capacity)
    
    return render_template(
        'reports/occupancy.html',
        current_inside=current_inside,
        capacity=capacity,
        available_spaces=available_spaces,
        occ_pct=occ_pct,
        occ_status=occ_status,
        date_str=date_str,
        hourly_history=hourly_history
    )

# CSV Exports
@reports_bp.route('/export/members')
@login_required
def export_members_csv():
    db = get_db()
    members = list(db.members.find().sort("member_id", 1))
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Member ID", "Full Name", "Phone", "Email", "Gender", "Age", "Membership Plan", "Start Date", "End Date", "Status", "Trainer"])
    
    for m in members:
        cw.writerow([
            m.get("member_id", ""),
            m.get("full_name", ""),
            m.get("phone", ""),
            m.get("email", ""),
            m.get("gender", ""),
            m.get("age", ""),
            m.get("plan_name", ""),
            m.get("start_date", ""),
            m.get("end_date", ""),
            m.get("status", ""),
            m.get("trainer_name", "")
        ])
        
    filename = f"fitcore_members_{get_now().strftime('%Y-%m-%d')}.csv"
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@reports_bp.route('/export/attendance')
@login_required
def export_attendance_csv():
    db = get_db()
    records = list(db.attendance.find().sort("check_in", -1))
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Member ID", "Member Name", "Check In", "Check Out", "Duration", "Status"])
    
    for r in records:
        cw.writerow([
            r.get("member_id", ""),
            r.get("member_name", ""),
            r.get("check_in", ""),
            r.get("check_out", "") or "Inside",
            r.get("duration_display", "-"),
            r.get("status", "")
        ])
        
    filename = f"fitcore_attendance_{get_now().strftime('%Y-%m-%d')}.csv"
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@reports_bp.route('/export/payments')
@login_required
def export_payments_csv():
    db = get_db()
    payments = list(db.payments.find().sort("payment_date", -1))
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Payment ID", "Member ID", "Member Name", "Plan Name", "Amount (INR)", "Payment Date", "Method", "Transaction ID", "Status"])
    
    for p in payments:
        cw.writerow([
            p.get("payment_id", ""),
            p.get("member_id", ""),
            p.get("member_name", ""),
            p.get("plan_name", ""),
            p.get("amount", 0),
            p.get("payment_date", ""),
            p.get("payment_method", ""),
            p.get("transaction_id", ""),
            p.get("payment_status", "")
        ])
        
    filename = f"fitcore_payments_{get_now().strftime('%Y-%m-%d')}.csv"
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@reports_bp.route('/export/occupancy')
@login_required
def export_occupancy_csv():
    db = get_db()
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    target_date = request.args.get('date', get_now().strftime('%Y-%m-%d'))
    
    history = compute_hourly_occupancy(db, target_date, capacity)
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Time", "Date", "People Inside", "Capacity", "Occupancy %", "Status"])
    
    for h in history:
        cw.writerow([
            h.get("time", ""),
            target_date,
            h.get("people_inside", 0),
            h.get("capacity", capacity),
            f"{h.get('percentage', 0)}%",
            h.get("status", "")
        ])
        
    filename = f"fitcore_occupancy_{target_date}.csv"
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
