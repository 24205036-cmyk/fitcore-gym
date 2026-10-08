import os
import uuid
from datetime import datetime, date, time, timezone, timedelta
from werkzeug.utils import secure_filename
from config import Config
from database import get_db
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

def get_tz():
    """Returns timezone object for the configured timezone, with safe fallback."""
    if ZoneInfo:
        try:
            return ZoneInfo(Config.TIMEZONE)
        except Exception:
            pass
            
    # Fallback to IST (+05:30) if configured or UTC
    if "Kolkata" in Config.TIMEZONE or "Calcutta" in Config.TIMEZONE:
        return timezone(timedelta(hours=5, minutes=30), name="IST")
    return timezone.utc

def get_now() -> datetime:
    """Returns current localized datetime."""
    return datetime.now(get_tz())

def format_datetime(dt, fmt="%d %b %Y, %I:%M %p") -> str:
    """Formats datetime object to standard string."""
    if not dt:
        return "-"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    if hasattr(dt, 'astimezone'):
        dt = dt.astimezone(get_tz())
    return dt.strftime(fmt)

def format_date(d, fmt="%d %b %Y") -> str:
    """Formats date or datetime to readable date string."""
    if not d:
        return "-"
    if isinstance(d, str):
        try:
            d = datetime.strptime(d[:10], "%Y-%m-%d").date()
        except Exception:
            return d
    if isinstance(d, datetime):
        d = d.astimezone(get_tz()).date()
    return d.strftime(fmt)

def format_currency(val) -> str:
    """Formats amount as Indian Rupee or general currency string (e.g. ₹18,500)."""
    try:
        val_float = float(val)
        # Format with commas: ₹18,500 or ₹1,000
        val_int = int(round(val_float))
        # Indian format style or standard format with thousands separator
        formatted = f"{val_int:,}"
        return f"₹{formatted}"
    except (ValueError, TypeError):
        return f"₹0"

def get_gym_settings() -> dict:
    """Retrieves current settings from MongoDB, falling back to defaults."""
    db = get_db()
    settings = db.settings.find_one({"type": "general"})
    if not settings:
        settings = {
            "type": "general",
            "gym_name": "FITCORE",
            "gym_address": "42 Fitness Boulevard, Tech City, Bangalore",
            "gym_phone": "+91 98765 43210",
            "gym_email": "admin@fitcore.local",
            "gym_capacity": Config.DEFAULT_GYM_CAPACITY,
            "opening_time": "05:00 AM",
            "closing_time": "10:00 PM",
            "currency": "INR",
            "currency_symbol": "₹",
            "timezone": Config.TIMEZONE
        }
    return settings

def is_gym_open(settings: dict = None) -> bool:
    """Determines whether the gym is currently open based on settings."""
    if settings is None:
        settings = get_gym_settings()
        
    now = get_now()
    current_time_minutes = now.hour * 60 + now.minute
    
    def parse_time_to_minutes(time_str):
        time_str = time_str.strip().upper()
        try:
            t = datetime.strptime(time_str, "%I:%M %p")
            return t.hour * 60 + t.minute
        except ValueError:
            try:
                t = datetime.strptime(time_str, "%H:%M")
                return t.hour * 60 + t.minute
            except ValueError:
                return 0
                
    open_min = parse_time_to_minutes(settings.get("opening_time", "05:00 AM"))
    close_min = parse_time_to_minutes(settings.get("closing_time", "10:00 PM"))
    
    if open_min <= close_min:
        return open_min <= current_time_minutes <= close_min
    else:
        # Overnight operating hours
        return current_time_minutes >= open_min or current_time_minutes <= close_min

def calculate_occupancy_status(percentage: float) -> dict:
    """Returns visual status information based on occupancy percentage."""
    if percentage <= 50:
        return {
            "label": "NORMAL",
            "badge_class": "bg-success",
            "progress_class": "bg-success",
            "icon": "bi-check-circle-fill",
            "emoji": "🟢"
        }
    elif percentage <= 80:
        return {
            "label": "MODERATELY BUSY",
            "badge_class": "bg-warning text-dark",
            "progress_class": "bg-warning",
            "icon": "bi-exclamation-circle-fill",
            "emoji": "🟡"
        }
    elif percentage <= 99:
        return {
            "label": "CROWDED",
            "badge_class": "bg-orange",
            "progress_class": "bg-danger",
            "icon": "bi-exclamation-triangle-fill",
            "emoji": "🟠"
        }
    else:
        return {
            "label": "FULL",
            "badge_class": "bg-danger",
            "progress_class": "bg-danger",
            "icon": "bi-x-circle-fill",
            "emoji": "🔴"
        }

def calculate_member_status(end_date_val, manual_status: str = "Active") -> str:
    """Calculates member status based on end_date and manual overrides."""
    if manual_status in ["Suspended", "Inactive"]:
        return manual_status
        
    if not end_date_val:
        return "Active"
        
    now_date = get_now().date()
    target_date = None
    if isinstance(end_date_val, str):
        try:
            target_date = datetime.strptime(end_date_val[:10], "%Y-%m-%d").date()
        except ValueError:
            target_date = now_date
    elif isinstance(end_date_val, datetime):
        target_date = end_date_val.date()
    elif isinstance(end_date_val, date):
        target_date = end_date_val

    if target_date and target_date < now_date:
        return "Expired"
    return "Active"

def allowed_file(filename: str) -> bool:
    """Checks if uploaded file has allowed image extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def save_uploaded_file(file, folder_type: str = 'members') -> str:
    """Saves uploaded file securely and returns relative URL path."""
    if not file or not file.filename:
        return ""
    if not allowed_file(file.filename):
        return ""
        
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{folder_type}_{uuid.uuid4().hex[:10]}.{ext}"
    
    target_dir = Config.MEMBERS_UPLOAD_FOLDER if folder_type == 'members' else Config.TRAINERS_UPLOAD_FOLDER
    os.makedirs(target_dir, exist_ok=True)
    
    save_path = os.path.join(target_dir, unique_name)
    file.save(save_path)
    return f"uploads/{folder_type}/{unique_name}"
