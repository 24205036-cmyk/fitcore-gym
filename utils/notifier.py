from datetime import datetime, timedelta
from database import get_db
from utils.helpers import get_now, get_tz

def log_notification(title: str, message: str, notif_type: str = "info", link: str = ""):
    """
    Logs an event notification to the notifications collection.
    notif_type: info, success, warning, danger
    """
    db = get_db()
    notif = {
        "title": title,
        "message": message,
        "type": notif_type,
        "link": link,
        "is_read": False,
        "created_at": get_now()
    }
    db.notifications.insert_one(notif)

def sync_membership_expiry_notifications():
    """
    Scans members and creates expiry warning notifications
    if not already generated today.
    """
    db = get_db()
    today_date = get_now().date()
    today_str = today_date.strftime("%Y-%m-%d")
    
    # Check members expiring in next 3 days
    three_days_later = (today_date + timedelta(days=3)).strftime("%Y-%m-%d")
    
    expiring_soon = list(db.members.find({
        "status": "Active",
        "end_date": {"$gte": today_str, "$lte": three_days_later}
    }))
    
    if expiring_soon:
        # Check if already notified today
        existing = db.notifications.find_one({
            "title": "Memberships Expiring Soon",
            "date_key": today_str
        })
        if not existing:
            count = len(expiring_soon)
            names = ", ".join([m.get("full_name", "") for m in expiring_soon[:3]])
            extra = f" and {count - 3} more" if count > 3 else ""
            db.notifications.insert_one({
                "title": "Memberships Expiring Soon",
                "message": f"{count} membership(s) expiring within 3 days ({names}{extra}).",
                "type": "warning",
                "link": "/members?status=Active",
                "is_read": False,
                "date_key": today_str,
                "created_at": get_now()
            })
            
    # Check members that expired today
    expired_today = list(db.members.find({
        "end_date": today_str
    }))
    if expired_today:
        existing_exp = db.notifications.find_one({
            "title": "Memberships Expired Today",
            "date_key": today_str
        })
        if not existing_exp:
            count = len(expired_today)
            db.notifications.insert_one({
                "title": "Memberships Expired Today",
                "message": f"{count} membership(s) reached expiry today.",
                "type": "danger",
                "link": "/members?status=Expired",
                "is_read": False,
                "date_key": today_str,
                "created_at": get_now()
            })
