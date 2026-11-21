import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.database.database import SessionLocal
from app.models.user import User
from app.core.security import create_access_token

def run():
    db = SessionLocal()
    admin = db.query(User).filter(User.role == 'ADMIN').first()
    token = create_access_token({'sub': str(admin.id), 'role': admin.role})

    client = TestClient(app)
    client.cookies.set('complaint_session', token)

    resp = client.get('/admin/complaints/36')
    assert resp.status_code == 200, f'Status: {resp.status_code}'

    # Verify Department dropdown contains all departments from registration
    assert 'name="department" id="adminDepartmentSelect"' in resp.text
    assert 'IT Department' in resp.text
    assert 'Department of Information Sciences' in resp.text
    assert 'Accounts Department' in resp.text
    assert 'Library Department' in resp.text
    assert 'Administration Office' in resp.text

    # Verify Handler dropdown has correct ID
    assert 'name="handler_id" id="adminHandlerSelect"' in resp.text

    # Verify embedded JSON
    assert 'id="deptHandlersData"' in resp.text

    # Test API for each department
    test_depts = [
        'IT Department',
        'Department of Information Sciences',
        'Accounts Department',
        'Administration Office',
        'Department of Education',
        'Department of Mathematics',
        'Library Department',
        'Administration / Maintenance',
        'Directorate of Student Affairs',
    ]
    for dept in test_depts:
        r = client.get('/admin/api/handlers', params={'department': dept})
        assert r.status_code == 200
        handlers = r.json().get('handlers', [])
        names = [f"{h['name']} ({h['role']})" for h in handlers]
        print(f"API check -> {dept}: {names}")
        assert len(handlers) > 0, f"No handlers for {dept}"

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run()
