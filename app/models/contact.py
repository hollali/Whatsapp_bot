import uuid

from app.extensions import db
from app.utils import utcnow


class ContactGroup(db.Model):
    __tablename__ = "contact_groups"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    contacts = db.relationship("Contact", backref="group", lazy="dynamic")


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    group_id = db.Column(db.String(36), db.ForeignKey("contact_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    name = db.Column(db.String(120))
    phone = db.Column(db.String(32), nullable=False, index=True)
    email = db.Column(db.String(255))
    tags = db.Column(db.String(255))
    opted_out = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "phone", name="uq_user_phone"),)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "tags": self.tags,
            "group_id": self.group_id,
            "opted_out": self.opted_out,
        }
