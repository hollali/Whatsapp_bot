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
        self.client.post("/api/v1/auth/register", json={"email": "t@t.com", "password": "pass1234", "name": "T"})
        r = self.client.post("/api/v1/auth/login", json={"email": "t@t.com", "password": "pass1234"})
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

    def _register(self, email):
        response = self.client.post("/api/v1/auth/register", json={
            "email": email, "password": "pass1234", "name": email.split("@")[0]
        })
        return response

    def test_api_key_authentication(self):
        from app.models.apikey import ApiKey
        self._register("key@example.com")
        self.client.post("/api/v1/auth/login", json={"email": "key@example.com", "password": "pass1234"})
        created = self.client.post("/api/v1/auth/api-keys", json={"name": "ci"}).get_json()
        raw = created["key"]
        self.assertTrue(ApiKey.query.filter_by(prefix=created["prefix"]).first().last_used_at is None)
        from flask import request
        from app.extensions import db, login_manager
        with self.app.test_request_context("/api/v1/auth/me", headers={"X-API-Key": raw}):
            user = login_manager._request_callback(request)
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "key@example.com")
        db.session.expire_all()
        self.assertIsNotNone(ApiKey.query.filter_by(prefix=created["prefix"]).first().last_used_at)

    def test_retry_is_scoped_to_owner(self):
        from app.models.schedule import ScheduledJob
        self._register("owner@example.com")
        self.client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "pass1234"})
        job = self.client.post("/api/v1/messages/schedule", json={"phone": "+123", "message": "hi"}).get_json()
        ScheduledJob.query.filter_by(id=job["id"]).update({"status": "failed"})
        from app.extensions import db
        db.session.commit()
        self._register("other@example.com")
        self.client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "pass1234"})
        response = self.client.post("/api/v1/messages/jobs/" + job["id"] + "/retry", json={})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(db.session.get(ScheduledJob, job["id"]).status, "failed")

    def test_campaign_cannot_use_another_users_template(self):
        self._register("alice@example.com")
        self.client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "pass1234"})
        template = self.client.post("/api/v1/templates", json={"name": "Hi", "body": "Hello {{ name }}"}).get_json()
        self._register("bob@example.com")
        self.client.post("/api/v1/auth/login", json={"email": "bob@example.com", "password": "pass1234"})
        response = self.client.post("/api/v1/campaigns", json={"name": "Stolen", "template_id": template["id"]})
        self.assertEqual(response.status_code, 400)

    def test_bad_payloads_return_json_errors(self):
        self._register_login()
        response = self.client.post("/api/v1/messages/send", json={"phone": "nope", "message": "hi"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid phone number")


if __name__ == "__main__":
    unittest.main()
