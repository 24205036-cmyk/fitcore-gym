import re
from datetime import datetime

def is_valid_email(email: str) -> bool:
    if not email:
        return False
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email.strip()))

def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    # Accepts phone with country codes, spaces, dashes: min 7 digits
    digits = re.sub(r'\D', '', phone)
    return len(digits) >= 8

def validate_member_form(data: dict) -> tuple[bool, str]:
    if not data.get('full_name', '').strip():
        return False, "Full Name is required."
    if not is_valid_phone(data.get('phone', '')):
        return False, "A valid Phone number is required (at least 8 digits)."
    if data.get('email') and not is_valid_email(data.get('email')):
        return False, "Invalid email address format."
    if not data.get('plan_id'):
        return False, "Membership Plan must be selected."
        
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    if start_date and end_date:
        try:
            d_start = datetime.strptime(start_date[:10], "%Y-%m-%d")
            d_end = datetime.strptime(end_date[:10], "%Y-%m-%d")
            if d_end < d_start:
                return False, "Membership end date cannot be earlier than start date."
        except ValueError:
            return False, "Invalid date format. Expected YYYY-MM-DD."
            
    return True, ""

def validate_registration_form(data: dict) -> tuple[bool, str]:
    if not data.get('full_name', '').strip():
        return False, "Full Name is required."
    email = data.get('email', '').strip()
    if not email or not is_valid_email(email):
        return False, "A valid email address is required."
    phone = data.get('phone', '').strip()
    if not phone or not is_valid_phone(phone):
        return False, "A valid phone number is required (at least 8 digits)."
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    if password != confirm_password:
        return False, "Passwords do not match. Please re-enter."
    return True, ""


def validate_trainer_form(data: dict) -> tuple[bool, str]:
    if not data.get('name', '').strip():
        return False, "Trainer Name is required."
    if not is_valid_phone(data.get('phone', '')):
        return False, "Valid Phone number is required."
    if data.get('email') and not is_valid_email(data.get('email')):
        return False, "Invalid email format."
    if not data.get('specialization', '').strip():
        return False, "Specialization is required."
    return True, ""

def validate_plan_form(data: dict) -> tuple[bool, str]:
    if not data.get('name', '').strip():
        return False, "Plan name is required."
    try:
        duration = int(data.get('duration_days', 0))
        if duration <= 0:
            return False, "Duration must be greater than 0 days."
    except (ValueError, TypeError):
        return False, "Valid numeric duration in days is required."
        
    try:
        price = float(data.get('price', 0))
        if price < 0:
            return False, "Price cannot be negative."
    except (ValueError, TypeError):
        return False, "Valid numeric price is required."
        
    return True, ""

def validate_payment_form(data: dict) -> tuple[bool, str]:
    if not data.get('member_id'):
        return False, "Member must be selected."
    try:
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return False, "Payment amount must be greater than zero."
    except (ValueError, TypeError):
        return False, "Valid numeric amount is required."
    if not data.get('payment_method'):
        return False, "Payment method is required."
    return True, ""
