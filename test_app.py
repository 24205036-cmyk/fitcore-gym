import unittest
import json
from app import create_app
from database import get_db

class FitcoreTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.db = get_db()
        
    def login(self, username="admin", password="admin123"):
        return self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def test_01_login_success_and_logout(self):
        print("\n[TEST] 01: Testing Authentication (Login & Logout)...")
        # Invalid login
        res_invalid = self.login("admin", "wrongpassword")
        self.assertIn(b"Invalid", res_invalid.data)
        
        # Valid login
        res_valid = self.login("admin", "admin123")
        self.assertIn(b"FITCORE", res_valid.data)
        
        # Logout
        res_logout = self.client.get('/logout', follow_redirects=True)
        self.assertIn(b"You have been logged out securely", res_logout.data)
        print("  [OK] Login and Logout passed.")

    def test_02_protected_routes(self):
        print("\n[TEST] 02: Testing Protected Routes...")
        # Accessing dashboard without login redirects to /login
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 302)
        self.assertTrue('/login' in res.headers['Location'])
        print("  [OK] Protected route redirect passed.")

    def test_03_dashboard_and_occupancy_api(self):
        print("\n[TEST] 03: Testing Dashboard and Live Occupancy API...")
        self.login()
        res_dash = self.client.get('/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Floor Occupancy", res_dash.data)
        
        # API test
        res_api = self.client.get('/api/occupancy')
        self.assertEqual(res_api.status_code, 200)
        data = json.loads(res_api.data)
        self.assertTrue(data['success'])
        self.assertIn('current', data)
        self.assertIn('capacity', data)
        self.assertIn('percentage', data)
        self.assertIn('status', data)
        print(f"  [OK] Live Occupancy API returned: {data['current']}/{data['capacity']} ({data['percentage']}%) - {data['status']}.")

    def test_04_member_crud(self):
        print("\n[TEST] 04: Testing Member CRUD & Renewal...")
        self.login()
        
        # Add new member
        res_add = self.client.post('/members/add', data={
            'full_name': 'Test Athlete',
            'phone': '+91 99999 88888',
            'email': 'athlete.test@fitcore.local',
            'age': '26',
            'gender': 'Male',
            'plan_id': 'PLAN001',
            'start_date': '2026-10-01',
            'end_date': '2026-10-31',
            'record_payment': 'yes',
            'payment_method': 'UPI',
            'payment_status': 'Paid'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b"Test Athlete", res_add.data)
        
        # Verify member in db
        member = self.db.members.find_one({"phone": "+91 99999 88888"})
        self.assertIsNotNone(member)
        member_id = member['member_id']
        
        # View profile
        res_view = self.client.get(f'/members/{member_id}')
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b"Test Athlete", res_view.data)
        
        # Edit member
        res_edit = self.client.post(f'/members/{member_id}/edit', data={
            'full_name': 'Test Athlete Pro',
            'phone': '+91 99999 88888',
            'email': 'athlete.test@fitcore.local',
            'age': '27',
            'gender': 'Male',
            'status': 'Active'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b"Test Athlete Pro", res_edit.data)
        
        # Renew member
        res_renew = self.client.post(f'/members/{member_id}/renew', data={
            'plan_id': 'PLAN002',
            'payment_method': 'Cash',
            'payment_status': 'Paid'
        }, follow_redirects=True)
        self.assertEqual(res_renew.status_code, 200)
        self.assertIn(b"renewed successfully", res_renew.data)
        print("  [OK] Member registration, profile view, edit, and renewal passed.")

    def test_05_attendance_checkin_checkout_and_duplicate_protection(self):
        print("\n[TEST] 05: Testing Attendance Check-in, Duplicate Protection & Check-out...")
        self.login()
        
        member = self.db.members.find_one({"status": "Active"})
        member_id = member['member_id']
        
        # Ensure member is checked out first
        self.db.attendance.delete_many({"member_id": member_id})
        
        # Check-in member
        res_cin = self.client.post('/attendance/api/check-in', json={'member_id': member_id})
        data_cin = json.loads(res_cin.data)
        self.assertTrue(data_cin['success'])
        
        # Duplicate check-in attempt (Must fail!)
        res_dup = self.client.post('/attendance/api/check-in', json={'member_id': member_id})
        data_dup = json.loads(res_dup.data)
        self.assertFalse(data_dup['success'])
        self.assertIn("already inside", data_dup['message'])
        
        # Check-out member
        res_cout = self.client.post('/attendance/api/check-out', json={'member_id': member_id})
        data_cout = json.loads(res_cout.data)
        self.assertTrue(data_cout['success'])
        print("  [OK] Check-in, duplicate prevention, and check-out logic passed.")

    def test_06_reports_and_csv_exports(self):
        print("\n[TEST] 06: Testing Reports & CSV Exports...")
        self.login()
        
        # View report pages
        for path in ['/reports', '/reports/members', '/reports/attendance', '/reports/revenue', '/reports/occupancy']:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200)
            
        # Export CSVs
        for csv_path in ['/reports/export/members', '/reports/export/attendance', '/reports/export/payments', '/reports/export/occupancy']:
            res_csv = self.client.get(csv_path)
            self.assertEqual(res_csv.status_code, 200)
            self.assertEqual(res_csv.content_type, 'text/csv; charset=utf-8')
            self.assertTrue(len(res_csv.data) > 0)
        print("  [OK] All reports loaded and all 4 CSV exports succeeded.")

    def test_07_no_charts_verification(self):
        print("\n[TEST] 07: Verifying ZERO Charts in codebase...")
        self.login()
        
        # Check all rendered pages to confirm no chart library is referenced
        pages = ['/dashboard', '/reports', '/reports/members', '/reports/revenue', '/reports/occupancy', '/attendance']
        for p in pages:
            res = self.client.get(p)
            content = res.data.decode('utf-8', errors='ignore')
            self.assertNotIn("chart.js", content.lower())
            self.assertNotIn("chartist", content.lower())
            self.assertNotIn("<canvas", content.lower())
        print("  [OK] Verification confirmed: ZERO charts found.")

if __name__ == '__main__':
    unittest.main()
