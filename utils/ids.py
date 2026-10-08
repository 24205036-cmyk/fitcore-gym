import re
from database import get_db

def generate_next_id(prefix: str, collection_name: str, field_name: str, padding: int = 3) -> str:
    """
    Generates the next sequential readable ID (e.g., GYM001, TRN001, PAY001).
    Scans existing records to find the maximum integer suffix and increments it.
    """
    db = get_db()
    collection = db[collection_name]
    
    # Find all documents with that prefix
    pattern = f"^{prefix}\\d+"
    cursor = collection.find({field_name: {"$regex": pattern}}, {field_name: 1})
    
    max_num = 0
    for doc in cursor:
        val = doc.get(field_name, '')
        match = re.search(r'\d+', val)
        if match:
            try:
                num = int(match.group())
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
                
    next_num = max_num + 1
    return f"{prefix}{str(next_num).zfill(padding)}"

def get_next_member_id() -> str:
    return generate_next_id("GYM", "members", "member_id", padding=3)

def get_next_trainer_id() -> str:
    return generate_next_id("TRN", "trainers", "trainer_id", padding=3)

def get_next_plan_id() -> str:
    return generate_next_id("PLAN", "membership_plans", "plan_id", padding=3)

def get_next_payment_id() -> str:
    return generate_next_id("PAY", "payments", "payment_id", padding=3)
