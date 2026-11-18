import unittest
import os

os.environ["APP_ENV"] = "testing"

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.contact import Contact


class BaseModelTest(unittest.TestCase):
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

    def test_user_create(self):
        u = User(email="a@b.com", name="A")
        u.set_password("secret")
        db.session.add(u)
        db.session.commit()
        self.assertTrue(u.check_password("secret"))
        self.assertFalse(u.check_password("wrong"))

    def test_contact_unique(self):
        u = User(email="a@b.com", name="A")
        u.set_password("secret")
        db.session.add(u)
        db.session.commit()
        c1 = Contact(user_id=u.id, phone="+123", name="X")
        db.session.add(c1)
        db.session.commit()
        c2 = Contact(user_id=u.id, phone="+123", name="Y")
        db.session.add(c2)
        with self.assertRaises(Exception):
            db.session.commit()
        db.session.rollback()


if __name__ == "__main__":
    unittest.main()
