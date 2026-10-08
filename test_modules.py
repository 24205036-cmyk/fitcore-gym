import requests
import re
import sys
import time

BASE_URL = "http://127.0.0.1:5000"

def test_rbac_and_modules():
    print("=" * 60)
    print("FITCORE E2E RBAC & MODULES VERIFICATION")
    print("=" * 60)
    
    # 1. Test Admin Login & Redirection
    print("\n[TEST 1] Admin Login (admin / admin123)...")
    admin_session = requests.Session()
    r = admin_session.post(f"{BASE_URL}/login", data={"username": "admin", "password": "admin123"}, allow_redirects=True)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "/dashboard" in r.url or "SMART GYM OS" in r.text
    assert "FITCORE" in r.text
    print("  [PASS] Admin logged in and redirected to Admin Dashboard successfully.")

    # 2. Test Trainer Login & Redirection
    print("\n[TEST 2] Trainer Login (trainer@fitcore.com / trainer123)...")
    trainer_session = requests.Session()
    r = trainer_session.post(f"{BASE_URL}/login", data={"username": "trainer@fitcore.com", "password": "trainer123"}, allow_redirects=True)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "/trainer/dashboard" in r.url
    assert "TRAINER PORTAL" in r.text or "Trainer Dashboard" in r.text
    assert "Assigned Members" in r.text
    print("  [PASS] Trainer logged in and redirected to Trainer Dashboard successfully.")

    # 3. Test Member Login & Redirection
    print("\n[TEST 3] Member Login (member@fitcore.com / member123)...")
    member_session = requests.Session()
    r = member_session.post(f"{BASE_URL}/login", data={"username": "member@fitcore.com", "password": "member123"}, allow_redirects=True)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "/member/dashboard" in r.url
    assert "MEMBER PORTAL" in r.text or "Member Dashboard" in r.text
    assert "Membership Plan" in r.text
    print("  [PASS] Member logged in and redirected to Member Dashboard successfully.")

    # 4. Test URL Security: Member attempting Admin route
    print("\n[TEST 4] URL Security: Member attempting /dashboard...")
    r = member_session.get(f"{BASE_URL}/dashboard", allow_redirects=True)
    assert "/member/dashboard" in r.url
    print(f"  [PASS] Member blocked from Admin dashboard, redirected to {r.url}")

    print("\n[TEST 5] URL Security: Member attempting /trainers...")
    r = member_session.get(f"{BASE_URL}/trainers", allow_redirects=True)
    assert "/member/dashboard" in r.url
    print(f"  [PASS] Member blocked from Admin trainers route, redirected to {r.url}")

    print("\n[TEST 6] URL Security: Member attempting /trainer/dashboard...")
    r = member_session.get(f"{BASE_URL}/trainer/dashboard", allow_redirects=True)
    assert "/member/dashboard" in r.url
    print(f"  [PASS] Member blocked from Trainer dashboard, redirected to {r.url}")

    # 5. Test URL Security: Trainer attempting Admin route and Member route
    print("\n[TEST 7] URL Security: Trainer attempting /members...")
    r = trainer_session.get(f"{BASE_URL}/members", allow_redirects=True)
    assert "/trainer/dashboard" in r.url
    print(f"  [PASS] Trainer blocked from Admin members route, redirected to {r.url}")

    print("\n[TEST 8] URL Security: Trainer attempting /member/dashboard...")
    r = trainer_session.get(f"{BASE_URL}/member/dashboard", allow_redirects=True)
    assert "/trainer/dashboard" in r.url
    print(f"  [PASS] Trainer blocked from Member dashboard, redirected to {r.url}")

    # 6. Test Member Module Routes
    print("\n[TEST 9] Member Sub-Pages:")
    member_routes = [
        "/member/profile",
        "/member/membership",
        "/member/attendance",
        "/member/payments",
        "/member/trainer",
        "/member/workouts",
        "/member/notifications",
        "/member/settings"
    ]
    for route in member_routes:
        r = member_session.get(f"{BASE_URL}{route}")
        assert r.status_code == 200, f"Route {route} failed with status {r.status_code}"
        print(f"  [PASS] {route} loaded with HTTP 200 OK")

    # 7. Test Trainer Module Routes
    print("\n[TEST 10] Trainer Sub-Pages:")
    trainer_routes = [
        "/trainer/profile",
        "/trainer/members",
        "/trainer/attendance",
        "/trainer/workouts",
        "/trainer/schedule",
        "/trainer/notifications",
        "/trainer/settings"
    ]
    for route in trainer_routes:
        r = trainer_session.get(f"{BASE_URL}{route}")
        assert r.status_code == 200, f"Route {route} failed with status {r.status_code}"
        print(f"  [PASS] {route} loaded with HTTP 200 OK")

    # 8. Test Member Registration Flow
    print("\n[TEST 11] Member Online Registration Flow (/register)...")
    test_reg_email = f"newmember_{int(time.time())}@fitcoretest.com"
    reg_data = {
        "full_name": "Test Athlete",
        "email": test_reg_email,
        "phone": "9876543219",
        "password": "password123",
        "confirm_password": "password123",
        "gender": "Female",
        "date_of_birth": "1998-05-15",
        "address": "77 Fitness Avenue",
        "plan_id": "PLAN001"
    }
    anon_session = requests.Session()
    r = anon_session.post(f"{BASE_URL}/register", data=reg_data, allow_redirects=True)
    assert r.status_code == 200
    assert "/login" in r.url
    print(f"  [PASS] Member {test_reg_email} registered successfully.")

    # Verify pending status check before approval
    r = anon_session.post(f"{BASE_URL}/login", data={"username": test_reg_email, "password": "password123"}, allow_redirects=True)
    assert "Waiting for Admin approval" in r.text
    print("  [PASS] Member account initially holds PENDING status and login is properly gated.")

    # Admin approves and assigns coach
    from database.db import get_db
    db = get_db()
    m_doc = db.members.find_one({"email": test_reg_email})
    assert m_doc is not None
    trainer = db.trainers.find_one()
    admin_session.post(f"{BASE_URL}/members/requests/{m_doc['member_id']}/accept", data={"trainer_id": trainer["trainer_id"]}, allow_redirects=True)

    # Now verify login with the approved account
    r = anon_session.post(f"{BASE_URL}/login", data={"username": test_reg_email, "password": "password123"}, allow_redirects=True)
    assert r.status_code == 200
    assert "/member/dashboard" in r.url
    assert "Test Athlete" in r.text
    print("  [PASS] Approved member logged in and landed on Member Dashboard.")

    # 9. Test Invalid Login
    print("\n[TEST 12] Wrong Credentials Validation...")
    bad_session = requests.Session()
    r = bad_session.post(f"{BASE_URL}/login", data={"username": "admin", "password": "wrongpassword"}, allow_redirects=True)
    assert "/login" in r.url
    assert "Invalid email/username or password" in r.text
    print("  [PASS] Wrong password rejected properly.")

    # 10. Test Logout
    print("\n[TEST 13] Logout...")
    r = anon_session.get(f"{BASE_URL}/logout", allow_redirects=True)
    assert "/login" in r.url
    # Attempt to access /member/dashboard after logout
    r2 = anon_session.get(f"{BASE_URL}/member/dashboard", allow_redirects=False)
    assert r2.status_code == 302
    assert "/login" in r2.headers.get("Location", "")
    print("  [PASS] Logout terminated session and blocked subsequent dashboard access.")

    print("\n" + "=" * 60)
    print("ALL 13 ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    test_rbac_and_modules()
