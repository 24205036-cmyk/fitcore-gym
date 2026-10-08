from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from database import get_db
from utils.decorators import login_required
from utils.helpers import get_gym_settings, is_gym_open, get_now
from utils.auth import hash_password, verify_password

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('', methods=['GET', 'POST'])
@login_required
def index():
    db = get_db()
    settings = get_gym_settings()
    admin_id = session.get('admin_id')
    admin = db.admins.find_one({"_id": ObjectId(admin_id)}) if admin_id else None
    
    gym_open = is_gym_open(settings)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_settings':
            gym_name = request.form.get('gym_name', 'FITCORE').strip()
            gym_address = request.form.get('gym_address', '').strip()
            gym_phone = request.form.get('gym_phone', '').strip()
            gym_email = request.form.get('gym_email', '').strip()
            try:
                gym_capacity = int(request.form.get('gym_capacity', 100))
                if gym_capacity <= 0:
                    gym_capacity = 100
            except ValueError:
                gym_capacity = 100
                
            opening_time = request.form.get('opening_time', '05:00 AM').strip()
            closing_time = request.form.get('closing_time', '10:00 PM').strip()
            currency = request.form.get('currency', 'INR').strip()
            timezone_val = request.form.get('timezone', 'Asia/Kolkata').strip()
            
            db.settings.update_one(
                {"type": "general"},
                {"$set": {
                    "gym_name": gym_name,
                    "gym_address": gym_address,
                    "gym_phone": gym_phone,
                    "gym_email": gym_email,
                    "gym_capacity": gym_capacity,
                    "opening_time": opening_time,
                    "closing_time": closing_time,
                    "currency": currency,
                    "currency_symbol": "₹",
                    "timezone": timezone_val,
                    "updated_at": get_now()
                }},
                upsert=True
            )
            flash("Gym settings updated successfully!", "success")
            return redirect(url_for('settings.index'))
            
        elif action == 'update_profile':
            full_name = request.form.get('admin_name', '').strip()
            email = request.form.get('admin_email', '').strip()
            
            if admin and full_name:
                db.admins.update_one(
                    {"_id": admin["_id"]},
                    {"$set": {
                        "full_name": full_name,
                        "email": email,
                        "updated_at": get_now()
                    }}
                )
                session['admin_name'] = full_name
                session['admin_email'] = email
                flash("Admin profile updated successfully.", "success")
            return redirect(url_for('settings.index'))
            
        elif action == 'change_password':
            current_pass = request.form.get('current_password', '')
            new_pass = request.form.get('new_password', '')
            confirm_pass = request.form.get('confirm_password', '')
            
            if not current_pass or not new_pass or not confirm_pass:
                flash("All password fields are required.", "danger")
                return redirect(url_for('settings.index'))
                
            if new_pass != confirm_pass:
                flash("New password and confirmation do not match.", "danger")
                return redirect(url_for('settings.index'))
                
            if len(new_pass) < 6:
                flash("New password must be at least 6 characters long.", "danger")
                return redirect(url_for('settings.index'))
                
            if admin and verify_password(admin.get('password', ''), current_pass):
                hashed = hash_password(new_pass)
                db.admins.update_one({"_id": admin["_id"]}, {"$set": {"password": hashed, "updated_at": get_now()}})
                flash("Password changed successfully! Keep your new credentials safe.", "success")
            else:
                flash("Incorrect current password.", "danger")
                
            return redirect(url_for('settings.index'))

    return render_template(
        'settings/index.html',
        settings=settings,
        admin=admin,
        gym_open=gym_open
    )
