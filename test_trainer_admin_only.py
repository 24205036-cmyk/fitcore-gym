import requests
from database.db import get_db

BASE_URL = "http://127.0.0.1:5000"

def test_admin_trainer_change():
    db = get_db()
    print("=" * 60)
    print("TEST: TRAINER CHANGE IS STRICTLY RESTRICTED TO ADMINS")
    print("=" * 60)

    # 1. Fetch an existing member and at least 2 active trainers
    member = db.members.find_one({"status": "Active"})
    assert member is not None, "Need at least one active member in database"
    member_id = member["member_id"]
    print(f"Target Member: {member.get('full_name')} ({member_id})")

    trainers = list(db.trainers.find({"status": {"$in": ["Active", "active"]}}).limit(2))
    assert len(trainers) >= 1, "Need at least one active trainer"
    trainer_1 = trainers[0]
    trainer_2 = trainers[1] if len(trainers) > 1 else trainers[0]

    # 2. Test Unauthenticated POST -> must be blocked / redirected to login
    print("\n[TEST 1] Unauthenticated request to /members/<id>/change-trainer...")
    s_anon = requests.Session()
    r = s_anon.post(f"{BASE_URL}/members/{member_id}/change-trainer", data={"trainer_id": trainer_1["trainer_id"]}, allow_redirects=False)
    assert r.status_code in [302, 401, 403], f"Expected redirect/forbidden, got {r.status_code}"
    print("  [PASS] Unauthenticated request blocked.")

    # 3. Test Member login trying to POST to /members/<id>/change-trainer -> must be blocked
    print("\n[TEST 2] Member attempting to change trainer...")
    member_user = db.users.find_one({"role": "member", "status": "active"})
    if member_user:
        s_member = requests.Session()
        # Login as member
        r_log = s_member.post(f"{BASE_URL}/login", data={"username": member_user.get("email") or member_user.get("member_id"), "password": "member123"}, allow_redirects=True)
        assert r_log.status_code == 200, "Member login failed"
        # Try to post to change-trainer
        r = s_member.post(f"{BASE_URL}/members/{member_id}/change-trainer", data={"trainer_id": trainer_1["trainer_id"]}, allow_redirects=True)
        # Check that it redirected away and showed Access Denied or blocked
        assert "Access Denied" in r.text or r.status_code in [403, 302] or "/member/dashboard" in r.url, f"Member was not blocked! Status: {r.status_code}, URL: {r.url}"
        print("  [PASS] Member cannot change trainer (Access Denied / Blocked).")

    # 4. Test Trainer login trying to POST to /members/<id>/change-trainer -> must be blocked
    print("\n[TEST 3] Trainer attempting to change trainer...")
    trainer_user = db.users.find_one({"role": "trainer", "status": "active"})
    if trainer_user:
        s_trainer = requests.Session()
        r_log = s_trainer.post(f"{BASE_URL}/login", data={"username": trainer_user.get("email") or trainer_user.get("trainer_id"), "password": "trainer123"}, allow_redirects=True)
        assert r_log.status_code == 200, "Trainer login failed"
        r = s_trainer.post(f"{BASE_URL}/members/{member_id}/change-trainer", data={"trainer_id": trainer_1["trainer_id"]}, allow_redirects=True)
        assert "Access Denied" in r.text or r.status_code in [403, 302] or "/trainer/dashboard" in r.url, f"Trainer was not blocked! Status: {r.status_code}, URL: {r.url}"
        print("  [PASS] Trainer cannot change trainer (Access Denied / Blocked).")

    # 5. Test Admin login and successfully changing trainer
    print("\n[TEST 4] Admin successfully changing trainer...")
    s_admin = requests.Session()
    r = s_admin.post(f"{BASE_URL}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
    assert r.status_code == 200, "Admin login failed"

    # Assign to trainer_1
    r = s_admin.post(f"{BASE_URL}/members/{member_id}/change-trainer", data={"trainer_id": trainer_1["trainer_id"]}, allow_redirects=True)
    assert r.status_code == 200, f"Admin change-trainer request failed: {r.status_code}"
    
    # Verify in DB
    updated_m = db.members.find_one({"member_id": member_id})
    assert updated_m.get("trainer_id") == trainer_1["trainer_id"], "db.members not updated"
    assert updated_m.get("trainer_name") == trainer_1.get("name"), "db.members trainer_name not updated"
    
    updated_u = db.users.find_one({"member_id": member_id})
    if updated_u:
        assert updated_u.get("trainer_id") == trainer_1["trainer_id"], "db.users not updated"

    print(f"  [PASS] Admin successfully assigned trainer: {trainer_1.get('name')}")

    # Verify notifications were sent
    m_notif = db.notifications.find_one({"member_id": member_id, "title": "Your trainer has been assigned."})
    assert m_notif is not None, "Member did not receive notification"
    t_notif = db.notifications.find_one({"trainer_id": trainer_1["trainer_id"], "title": "New member assigned to you."})
    assert t_notif is not None, "Trainer did not receive notification"
    print("  [PASS] Notifications generated for Member and Trainer.")

    # 6. Test Admin reassigning to trainer_2 or unassigning
    print("\n[TEST 5] Admin reassigning trainer...")
    r = s_admin.post(f"{BASE_URL}/members/{member_id}/change-trainer", data={"trainer_id": trainer_2["trainer_id"]}, allow_redirects=True)
    assert r.status_code == 200
    updated_m = db.members.find_one({"member_id": member_id})
    assert updated_m.get("trainer_id") == trainer_2["trainer_id"]
    print(f"  [PASS] Successfully reassigned to: {trainer_2.get('name')}")

    # 7. Check UI renders modal for Admin
    print("\n[TEST 6] Checking Members Directory and Member Profile HTML for Change Trainer modal...")
    r_dir = s_admin.get(f"{BASE_URL}/members")
    assert "Change Trainer" in r_dir.text, "Change Trainer not in members directory"
    assert f"changeTrainerModal{member_id}" in r_dir.text, "Modal not found in directory"

    r_prof = s_admin.get(f"{BASE_URL}/members/{member_id}")
    assert "Change Trainer" in r_prof.text, "Change Trainer not in profile"
    assert "changeTrainerModal" in r_prof.text, "Modal not found in profile"
    print("  [PASS] Change Trainer buttons and modals render properly on both directory & profile.")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ONLY ADMINS CAN CHANGE TRAINERS.")
    print("=" * 60)

if __name__ == "__main__":
    test_admin_trainer_change()
