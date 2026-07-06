"""End-to-end tests covering the main system workflows (Chapter 3, section 3.4.1)."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Point the app at a throwaway database BEFORE importing it — Flask-SQLAlchemy
# binds its engine to the URI configured at import time.
_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="atm-test-"), "test.db")
os.environ["DATABASE_URL"] = "sqlite:///" + _TEST_DB

import app as app_module
from app import CardRequest, Notification, User, db


@pytest.fixture()
def client():
    app_module.app.config.update(TESTING=True)
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        app_module.create_default_admin()
    with app_module.app.test_client() as client:
        yield client


CUSTOMER = {
    "full_name": "Test Customer",
    "email": "test@example.com",
    "phone": "08011112222",
    "account_number": "1234567890",
    "address": "1 Test Street, Lagos",
    "password": "secret123",
    "confirm_password": "secret123",
}


def register_and_login(client):
    client.post("/register", data=CUSTOMER)
    client.post("/login", data={"email": CUSTOMER["email"],
                                "password": CUSTOMER["password"]})


def login_admin(client):
    client.post("/login", data={"email": "admin@bank.com", "password": "admin123"})


def submit_request(client):
    client.post("/requests/new", data={
        "request_type": "New Card",
        "card_scheme": "Verve",
        "delivery_method": "Home Delivery",
        "delivery_address": "1 Test Street, Lagos",
    })
    with app_module.app.app_context():
        return CardRequest.query.first()


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"CardExpress" in response.data


def test_registration_validates_account_number(client):
    bad = dict(CUSTOMER, account_number="123")
    response = client.post("/register", data=bad)
    assert response.status_code == 400
    assert b"10 digits" in response.data


def test_registration_and_login(client):
    register_and_login(client)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"My card requests" in response.data


def test_customer_can_submit_and_track_request(client):
    register_and_login(client)
    card_request = submit_request(client)
    assert card_request is not None
    assert card_request.status == "Pending"

    # Authenticated detail view
    response = client.get(f"/requests/{card_request.id}")
    assert card_request.reference.encode() in response.data

    # Public tracking by reference
    response = client.post("/track", data={"reference": card_request.reference})
    assert b"Pending" in response.data


def test_admin_full_lifecycle(client):
    register_and_login(client)
    card_request = submit_request(client)
    client.get("/logout")

    login_admin(client)
    url = f"/admin/requests/{card_request.id}"

    client.post(url, data={"action": "approve", "note": "Verified OK"})
    client.post(url, data={"action": "advance"})  # -> In Production

    # Dispatch requires a delivery agent
    response = client.post(url, data={"action": "advance"})
    assert response.status_code == 400

    client.post(url, data={"action": "advance", "delivery_agent": "Swift Couriers"})
    client.post(url, data={"action": "advance"})  # -> Delivered

    with app_module.app.app_context():
        updated = db.session.get(CardRequest, card_request.id)
        assert updated.status == "Delivered"
        assert updated.delivery_agent == "Swift Couriers"
        # Customer received notifications at every stage
        customer = User.query.filter_by(email=CUSTOMER["email"]).first()
        messages = [n.message for n in Notification.query.filter_by(
            user_id=customer.id, channel="in-app")]
        for status in ["Pending", "Approved", "In Production",
                       "Dispatched", "Delivered"]:
            assert any(status in m for m in messages)


def test_admin_can_reject_with_reason(client):
    register_and_login(client)
    card_request = submit_request(client)
    client.get("/logout")

    login_admin(client)
    client.post(f"/admin/requests/{card_request.id}",
                data={"action": "reject", "note": "Invalid document"})
    with app_module.app.app_context():
        updated = db.session.get(CardRequest, card_request.id)
        assert updated.status == "Rejected"
        assert updated.admin_note == "Invalid document"


def test_customer_cannot_access_admin_pages(client):
    register_and_login(client)
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 302  # redirected away


def test_customer_cannot_view_other_customers_request(client):
    register_and_login(client)
    card_request = submit_request(client)
    client.get("/logout")

    other = dict(CUSTOMER, email="other@example.com", account_number="1111111111")
    client.post("/register", data=other)
    client.post("/login", data={"email": other["email"],
                                "password": other["password"]})
    response = client.get(f"/requests/{card_request.id}")
    assert response.status_code == 403
