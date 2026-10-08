from flask import Blueprint, render_template, request, redirect, url_for, flash
from bson import ObjectId
from database import get_db
from utils.decorators import login_required
from utils.notifier import sync_membership_expiry_notifications

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('')
@login_required
def list_notifications():
    db = get_db()
    sync_membership_expiry_notifications()
    
    type_filter = request.args.get('type', '').strip()
    query = {}
    if type_filter:
        query['type'] = type_filter
        
    notifications = list(db.notifications.find(query).sort("created_at", -1).limit(50))
    unread_count = db.notifications.count_documents({"is_read": False})
    
    return render_template(
        'notifications/list.html',
        notifications=notifications,
        unread_count=unread_count,
        type_filter=type_filter
    )

@notifications_bp.route('/mark-read/<notif_id>', methods=['POST'])
@login_required
def mark_read(notif_id):
    db = get_db()
    try:
        db.notifications.update_one({"_id": ObjectId(notif_id)}, {"$set": {"is_read": True}})
    except Exception:
        pass
    return redirect(request.referrer or url_for('notifications.list_notifications'))

@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    db = get_db()
    db.notifications.update_many({"is_read": False}, {"$set": {"is_read": True}})
    flash("All notifications marked as read.", "success")
    return redirect(url_for('notifications.list_notifications'))

@notifications_bp.route('/clear', methods=['POST'])
@login_required
def clear_all():
    db = get_db()
    db.notifications.delete_many({})
    flash("Notification history cleared.", "info")
    return redirect(url_for('notifications.list_notifications'))
