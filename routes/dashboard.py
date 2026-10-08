from flask import Blueprint, render_template, jsonify, request
from database import get_db
from utils.decorators import login_required
from utils.helpers import (
    get_now, get_gym_settings, is_gym_open, 
    calculate_occupancy_status, format_currency
)
from utils.notifier import sync_membership_expiry_notifications
from datetime import datetime, date

dashboard_bp = Blueprint('dashboard', __name__)

def get_dashboard_data():
    db = get_db()
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    
    # Run expiry sync check in background
    sync_membership_expiry_notifications()
    
    # Member counts
    total_members = db.members.count_documents({})
    active_members = db.members.count_documents({"status": "Active"})
    expired_members = db.members.count_documents({"status": "Expired"})
    suspended_members = db.members.count_documents({"status": "Suspended"})
    
    # Trainers count
    total_trainers = db.trainers.count_documents({"status": "Active"})
    
    # Occupancy
    current_inside = db.attendance.count_documents({"status": "Inside"})
    occupancy_pct = round((current_inside / capacity * 100), 1) if capacity > 0 else 0
    available_spaces = max(0, capacity - current_inside)
    occ_status = calculate_occupancy_status(occupancy_pct)
    
    # Today's Revenue
    today_str = get_now().strftime("%Y-%m-%d")
    today_payments = list(db.payments.find({
        "payment_date": {"$regex": f"^{today_str}"},
        "payment_status": "Paid"
    }))
    today_revenue = sum(float(p.get("amount", 0)) for p in today_payments)
    
    # Recent Activities (combine recent attendance, payments, and members)
    recent_activities = []
    
    # Recent checkins/outs
    recent_att = list(db.attendance.find().sort("created_at", -1).limit(6))
    for a in recent_att:
        action_text = "checked in" if a.get("status") == "Inside" else "checked out"
        icon_type = "bi-box-arrow-in-right text-success" if a.get("status") == "Inside" else "bi-box-arrow-left text-secondary"
        recent_activities.append({
            "text": f"{a.get('member_name', 'Member')} {action_text}",
            "detail": f"ID: {a.get('member_id')} • {a.get('time_display', '')}",
            "icon": icon_type,
            "timestamp": a.get("created_at") or get_now()
        })
        
    # Recent payments
    recent_pays = list(db.payments.find({"payment_status": "Paid"}).sort("created_at", -1).limit(4))
    for p in recent_pays:
        recent_activities.append({
            "text": f"Payment received from {p.get('member_name', 'Member')}",
            "detail": f"{format_currency(p.get('amount', 0))} via {p.get('payment_method', 'Cash')}",
            "icon": "bi-currency-rupee text-primary",
            "timestamp": p.get("created_at") or get_now()
        })
        
    # Sort combined activities by timestamp descending
    recent_activities.sort(key=lambda x: str(x.get("timestamp")), reverse=True)
    recent_activities = recent_activities[:7]
    
    # Recent notifications
    notifications = list(db.notifications.find().sort("created_at", -1).limit(5))
    
    # Currently inside members list for live preview widget
    inside_members = list(db.attendance.find({"status": "Inside"}).sort("check_in", -1).limit(10))
    
    gym_open = is_gym_open(settings)

    return {
        "settings": settings,
        "gym_open": gym_open,
        "total_members": total_members,
        "active_members": active_members,
        "expired_members": expired_members,
        "suspended_members": suspended_members,
        "total_trainers": total_trainers,
        "today_revenue": today_revenue,
        "today_revenue_formatted": format_currency(today_revenue),
        "current_inside": current_inside,
        "capacity": capacity,
        "available_spaces": available_spaces,
        "occupancy_pct": occupancy_pct,
        "occupancy_status": occ_status,
        "recent_activities": recent_activities,
        "notifications": notifications,
        "inside_members": inside_members
    }

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    data = get_dashboard_data()
    return render_template('dashboard.html', **data)

@dashboard_bp.route('/api/occupancy')
@login_required
def api_occupancy():
    db = get_db()
    settings = get_gym_settings()
    capacity = int(settings.get('gym_capacity', 100))
    current_inside = db.attendance.count_documents({"status": "Inside"})
    occupancy_pct = round((current_inside / capacity * 100), 1) if capacity > 0 else 0
    available_spaces = max(0, capacity - current_inside)
    occ_status = calculate_occupancy_status(occupancy_pct)
    gym_open = is_gym_open(settings)
    
    return jsonify({
        "success": True,
        "current": current_inside,
        "capacity": capacity,
        "available": available_spaces,
        "percentage": occupancy_pct,
        "status": occ_status["label"],
        "badge_class": occ_status["badge_class"],
        "progress_class": occ_status["progress_class"],
        "icon": occ_status["icon"],
        "emoji": occ_status["emoji"],
        "gym_open": gym_open
    })

@dashboard_bp.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    data = get_dashboard_data()
    return jsonify({
        "success": True,
        "total_members": data["total_members"],
        "active_members": data["active_members"],
        "expired_members": data["expired_members"],
        "total_trainers": data["total_trainers"],
        "today_revenue": data["today_revenue_formatted"],
        "current_inside": data["current_inside"],
        "capacity": data["capacity"],
        "available_spaces": data["available_spaces"],
        "occupancy_pct": data["occupancy_pct"],
        "occupancy_status": data["occupancy_status"]["label"],
        "gym_open": data["gym_open"]
    })

@dashboard_bp.route('/api/revenue')
@login_required
def api_revenue():
    data = get_dashboard_data()
    db = get_db()
    all_paid = list(db.payments.find({"payment_status": "Paid"}))
    total_rev = sum(float(p.get("amount", 0)) for p in all_paid)
    
    return jsonify({
        "success": True,
        "today_revenue": data["today_revenue"],
        "today_revenue_formatted": data["today_revenue_formatted"],
        "total_revenue": total_rev,
        "total_revenue_formatted": format_currency(total_rev)
    })

@dashboard_bp.route('/api/members/search')
@login_required
def api_members_search_alias():
    from routes.members import api_search_members
    return api_search_members()

@dashboard_bp.route('/api/attendance/check-in', methods=['POST'])
@login_required
def api_checkin_alias():
    from routes.attendance import api_check_in
    return api_check_in()

@dashboard_bp.route('/api/attendance/check-out', methods=['POST'])
@login_required
def api_checkout_alias():
    from routes.attendance import api_check_out
    return api_check_out()

@dashboard_bp.route('/api/attendance/today')
@login_required
def api_attendance_today_alias():
    from routes.attendance import api_today
    return api_today()
