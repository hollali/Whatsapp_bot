import unittest
import os
import json

os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _register_login(self):
        self.client.post("/api/v1/auth/register", json={"email": "t@t.com", "password": "pass", "name": "T"})
        r = self.client.post("/api/v1/auth/login", json={"email": "t@t.com", "password": "pass"})
        return r

    def test_register_login_me(self):
        self._register_login()
        r = self.client.get("/api/v1/auth/me")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["email"], "t@t.com")

    def test_contact_crud(self):
        self._register_login()
        r = self.client.post("/api/v1/contacts", json={"phone": "+123", "name": "X"})
        self.assertEqual(r.status_code, 201)
        cid = r.get_json()["id"]
        r = self.client.get(f"/api/v1/contacts/{cid}")
        self.assertEqual(r.status_code, 200)
        r = self.client.delete(f"/api/v1/contacts/{cid}")
        self.assertEqual(r.status_code, 200)

    def test_schedule_message(self):
        self._register_login()
        r = self.client.post("/api/v1/messages/schedule", json={"phone": "+123", "message": "hi"})
        self.assertEqual(r.status_code, 202)
        r = self.client.get("/api/v1/messages/jobs")
        self.assertEqual(len(r.get_json()), 1)

    def test_analytics_summary(self):
        self._register_login()
        r = self.client.get("/api/v1/analytics/summary")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
