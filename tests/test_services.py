import unittest
import os

os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.services.template_engine import TemplateEngine
from app.services.queue import QueueService


class TemplateEngineTest(unittest.TestCase):
    def test_render(self):
        out = TemplateEngine.render("Hi {{ name }}", {"name": "Bob"})
        self.assertEqual(out, "Hi Bob")

    def test_extract(self):
        vars_ = TemplateEngine.extract_variables("Hi {{ name }} your code {{ code }}")
        self.assertEqual(vars_, ["code", "name"])

    def test_render_error(self):
        with self.assertRaises(ValueError):
            TemplateEngine.render("{{ x | nope }}", {})


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        from app.models.user import User
        u = User(email="q@q.com", name="Q")
        u.set_password("x")
        db.session.add(u)
        db.session.commit()
        self.user_id = u.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_enqueue_and_due(self):
        q = QueueService()
        j = q.enqueue(self.user_id, "+1", "hi")
        self.assertEqual(j.status, "pending")
        due = q.due_jobs()
        self.assertEqual(len(due), 1)

    def test_cancel(self):
        q = QueueService()
        j = q.enqueue(self.user_id, "+1", "hi")
        self.assertTrue(q.cancel(j.id, user_id=self.user_id))
        j2 = q.cancel(j.id, user_id=self.user_id)
        self.assertFalse(j2)


if __name__ == "__main__":
    unittest.main()
