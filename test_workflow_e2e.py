import requests
import time
from database.db import get_db

BASE_URL = "http://127.0.0.1:5000"

def run_test():
    db = get_db()
    ts = int(time.time())
    test_email = f"workflow_member_{ts}@fitcoretest.com"
    test_name = f"Test Workflow User {ts}"
    test_password = "password123"
    
    print("=" * 65)
    print("FITCORE END-TO-END WORKFLOW TEST: MEMBER -> ADMIN -> TRAINER -> MEMBER")
    print("=" * 65)
    
    # STEP 1: New member opens Register
    print("\n[STEP 1] New member opens Register page (/register)...")
    s_member = requests.Session()
    r = s_member.get(f"{BASE_URL}/register")
    assert r.status_code == 200, f"Register page failed: {r.status_code}"
    print("  [PASS] Register page loaded successfully.")

    # STEP 2: Member submits registration
    print("\n[STEP 2] Member submits registration...")
    reg_data = {
        "full_name": test_name,
        "email": test_email,
        "phone": "+91 98888 77777",
        "gender": "Male",
        "date_of_birth": "1998-05-15",
        "plan_id": "PLAN001",
        "fitness_goal": "Weight Loss",
        "address": "123 Fitness St, Block B",
        "password": test_password,
        "confirm_password": test_password
    }
    r = s_member.post(f"{BASE_URL}/register", data=reg_data, allow_redirects=True)
    assert r.status_code == 200, f"Registration post failed: {r.status_code}"
    
    # Verify status in database = Pending
    member_doc = db.members.find_one({"email": test_email})
    assert member_doc is not None, "Member doc not found in db.members"
    user_doc = db.users.find_one({"email": test_email})
    assert user_doc is not None, "User doc not found in db.users"
    
    member_id = member_doc["member_id"]
    print(f"  [PASS] Member created: {test_name} ({member_id})")
    print(f"  [PASS] Member DB status: {member_doc.get('status')} (Expected: Pending)")
    print(f"  [PASS] User DB status: {user_doc.get('status')} (Expected: pending)")
    assert member_doc.get("status") in ["Pending", "pending"]
    assert user_doc.get("status") == "pending"

    # Verify protected access is blocked while pending
    r_attempt = s_member.post(f"{BASE_URL}/login", data={"username": test_email, "password": test_password}, allow_redirects=True)
    assert "Waiting for Admin approval" in r_attempt.text, "Pending message not displayed on login attempt"
    print("  [PASS] Protected access correctly blocked while status is PENDING.")

    # STEP 3: Admin logs in
    print("\n[STEP 3] Admin logs in...")
    s_admin = requests.Session()
    r = s_admin.post(f"{BASE_URL}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
    assert r.status_code == 200, f"Admin login failed: {r.status_code}"
    print("  [PASS] Admin logged in successfully.")

    # STEP 4: Admin sees Pending Member Request
    print("\n[STEP 4] Admin opens requests page (/members/requests)...")
    r = s_admin.get(f"{BASE_URL}/members/requests")
    assert r.status_code == 200, f"Requests page failed: {r.status_code}"
    assert member_id in r.text or test_name in r.text, "Pending member not visible on requests page"
    print(f"  [PASS] Admin sees Pending Member Request for {test_name} ({member_id}).")

    # STEP 5 & 6 & 7: Admin clicks ACCEPT and selects an existing trainer
    print("\n[STEP 5, 6, 7] Admin selects active trainer and accepts member request...")
    active_trainer = db.trainers.find_one({"status": {"$in": ["Active", "active"]}})
    assert active_trainer is not None, "No active trainer in database"
    trainer_id = active_trainer["trainer_id"]
    trainer_name = active_trainer.get("name")
    print(f"  Assigning to Trainer: {trainer_name} ({trainer_id})")

    r = s_admin.post(f"{BASE_URL}/members/requests/{member_id}/accept", data={"trainer_id": trainer_id}, allow_redirects=True)
    assert r.status_code == 200, f"Accept request failed: {r.status_code}"

    # Verify DB updates
    member_doc = db.members.find_one({"member_id": member_id})
    user_doc = db.users.find_one({"member_id": member_id})
    assert member_doc.get("status") == "Active", f"Member status not Active: {member_doc.get('status')}"
    assert user_doc.get("status") == "active", f"User status not active: {user_doc.get('status')}"
    assert member_doc.get("trainer_id") == trainer_id, f"Trainer ID mismatch: {member_doc.get('trainer_id')}"
    print(f"  [PASS] Member status updated to ACTIVE.")
    print(f"  [PASS] Member assigned to Trainer: {member_doc.get('trainer_name')} ({trainer_id}).")

    # Verify Trainer Notification
    trn_notif = db.notifications.find_one({"trainer_id": trainer_id, "title": "New member assigned to you."})
    assert trn_notif is not None, "Trainer new member notification not found"
    print(f"  [PASS] Trainer received notification: '{trn_notif['title']}' - {trn_notif['message']}")

    # Verify Member Notifications
    mbr_notif_appr = db.notifications.find_one({"member_id": member_id, "title": "Your registration has been approved."})
    assert mbr_notif_appr is not None, "Member approval notification not found"
    mbr_notif_trn = db.notifications.find_one({"member_id": member_id, "title": "Your trainer has been assigned."})
    assert mbr_notif_trn is not None, "Member trainer notification not found"
    print(f"  [PASS] Member received approval notification: '{mbr_notif_appr['title']}'")
    print(f"  [PASS] Member received trainer assigned notification: '{mbr_notif_trn['title']}' ({mbr_notif_trn['message']})")

    # STEP 8: Trainer logs in
    print("\n[STEP 8] Trainer logs in...")
    trainer_user = db.users.find_one({"trainer_id": trainer_id})
    trainer_login_ident = active_trainer.get("email") or trainer_id
    
    s_trainer = requests.Session()
    # Trainer credentials
    r = s_trainer.post(f"{BASE_URL}/login", data={"username": trainer_login_ident, "password": "trainer123"}, allow_redirects=True)
    if r.status_code != 200 or "trainer" not in r.url:
        # Fallback to test trainer
        r = s_trainer.post(f"{BASE_URL}/login", data={"username": "trainer@fitcore.com", "password": "trainer123"}, allow_redirects=True)
    assert "/trainer" in r.url, f"Trainer login did not land on trainer portal: {r.url}"
    print("  [PASS] Trainer logged in successfully.")

    # Check My Members
    r = s_trainer.get(f"{BASE_URL}/trainer/members")
    assert r.status_code == 200
    assert member_id in r.text or test_name in r.text, "New member does not appear under My Members"
    print(f"  [PASS] New member {test_name} appears under My Members.")

    # STEP 9: Trainer opens member details
    print("\n[STEP 9] Trainer opens member detail (/trainer/members/<id>)...")
    r = s_trainer.get(f"{BASE_URL}/trainer/members/{member_id}")
    assert r.status_code == 200
    assert test_name in r.text
    print(f"  [PASS] Member detail loaded with age, gender, goal: {member_doc.get('fitness_goal')}")

    # STEP 10 & 11: Trainer creates today's workout and assigns it
    print("\n[STEP 10, 11] Trainer creates and assigns today's workout...")
    workout_title = "Chest & Triceps"
    workout_data = {
        "action": "create",
        "member_id": member_id,
        "workout_date": "2026-10-08",
        "title": workout_title,
        "goal": "Hypertrophy & Strength",
        "exercise_name[]": ["Push Ups", "Bench Press", "Triceps Pushdown"],
        "exercise_sets[]": ["3", "3", "3"],
        "exercise_reps[]": ["12", "10", "12"],
        "exercise_duration[]": ["", "", ""],
        "exercise_notes[]": ["Warmup", "Heavy", "Control"],
        "trainer_notes": "Focus on proper form."
    }
    r = s_trainer.post(f"{BASE_URL}/trainer/workouts", data=workout_data, allow_redirects=True)
    assert r.status_code == 200

    # Verify workout created in db
    workout_doc = db.workout_plans.find_one({"member_id": member_id, "title": workout_title})
    assert workout_doc is not None, "Workout not found in db.workout_plans"
    workout_id = workout_doc["workout_id"]
    assert workout_doc.get("status") == "assigned"
    print(f"  [PASS] Workout created: '{workout_title}' ({workout_id}) with status='assigned'")

    # Verify Member received notification
    mbr_wkt_notif = db.notifications.find_one({"member_id": member_id, "title": "New Workout Assigned"})
    assert mbr_wkt_notif is not None, "Member new workout notification not found"
    print(f"  [PASS] Member received notification: '{mbr_wkt_notif['title']}' - {mbr_wkt_notif['message']}")

    # STEP 12: Member logs in and sees Today's Workout
    print("\n[STEP 12] Member logs in...")
    s_member_active = requests.Session()
    r = s_member_active.post(f"{BASE_URL}/login", data={"username": test_email, "password": test_password}, allow_redirects=True)
    assert "/member/dashboard" in r.url, f"Active member did not land on dashboard: {r.url}"
    
    import html
    page_text = html.unescape(r.text)
    assert "TODAY'S WORKOUT" in page_text
    assert workout_title in page_text
    assert trainer_name in page_text
    assert "Push Ups" in page_text
    print(f"  [PASS] Today's Workout '{workout_title}' is visible on Member Dashboard.")
    print(f"  [PASS] Assigned Trainer Name ({trainer_name}) is visible.")

    # STEP 13: Member completes workout
    print("\n[STEP 13] Member clicks MARK WORKOUT COMPLETED...")
    r = s_member_active.post(f"{BASE_URL}/member/workouts/{workout_id}/complete", allow_redirects=True)
    assert r.status_code == 200
    
    # Check updated status
    workout_check = db.workout_plans.find_one({"workout_id": workout_id})
    assert workout_check.get("status") == "completed", f"Status not completed: {workout_check.get('status')}"
    assert workout_check.get("completed_at") is not None
    print(f"  [PASS] Workout status updated to COMPLETED in database.")
    
    # Check dashboard now shows Workout Completed
    r = s_member_active.get(f"{BASE_URL}/member/dashboard")
    assert "Workout Completed" in r.text
    print("  [PASS] Member dashboard displays 'Workout Completed'.")

    # STEP 14: Trainer logs in and sees completion
    print("\n[STEP 14] Trainer verifies workout completion...")
    r = s_trainer.get(f"{BASE_URL}/trainer/workouts")
    assert r.status_code == 200
    assert workout_id in r.text or workout_title in r.text
    assert "Completed" in r.text
    print(f"  [PASS] Trainer sees workout completion status: COMPLETED.")

    print("\n" + "=" * 65)
    print("ALL 14 STEPS OF THE COMPLETE WORKFLOW PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    run_test()
