from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()


class University(db.Model):
    __tablename__ = 'universities'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    departments = db.relationship('Department', backref='university', lazy=True, cascade='all, delete-orphan')
    professors = db.relationship('Professor', backref='university', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'note': self.note,
        }


class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    university_id = db.Column(db.Integer, db.ForeignKey('universities.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500))

    professors = db.relationship('Professor', backref='department', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'university_id': self.university_id,
            'name': self.name,
            'url': self.url,
        }


class Professor(db.Model):
    __tablename__ = 'professors'
    id = db.Column(db.Integer, primary_key=True)
    university_id = db.Column(db.Integer, db.ForeignKey('universities.id'), nullable=False)
    dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(100))
    email = db.Column(db.String(200))
    phone = db.Column(db.String(100))
    photo_url = db.Column(db.String(500))
    specialty = db.Column(db.String(500))
    source_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sales_info = db.relationship('SalesInfo', backref='professor', lazy=True, uselist=False, cascade='all, delete-orphan')
    custom_field_values = db.relationship('CustomFieldValue', backref='professor', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'university_id': self.university_id,
            'dept_id': self.dept_id,
            'name': self.name,
            'title': self.title,
            'email': self.email,
            'phone': self.phone,
            'photo_url': self.photo_url,
            'specialty': self.specialty,
            'source_url': self.source_url,
        }


SALES_STATUSES = ['未接触', 'アプローチ中', '検討中', '商談中', '成約', '見送り']


class SalesInfo(db.Model):
    __tablename__ = 'sales_info'
    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('professors.id'), nullable=False, unique=True)
    status = db.Column(db.String(50), default='未接触')
    last_contact = db.Column(db.Date, nullable=True)
    next_contact = db.Column(db.Date, nullable=True)
    memo = db.Column(db.Text)
    _tags = db.Column('tags', db.Text, default='[]')

    @property
    def tags(self):
        try:
            return json.loads(self._tags or '[]')
        except Exception:
            return []

    @tags.setter
    def tags(self, value):
        self._tags = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'professor_id': self.professor_id,
            'status': self.status,
            'last_contact': self.last_contact.isoformat() if self.last_contact else None,
            'next_contact': self.next_contact.isoformat() if self.next_contact else None,
            'memo': self.memo,
            'tags': self.tags,
        }


class CustomField(db.Model):
    __tablename__ = 'custom_fields'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    field_type = db.Column(db.String(20), nullable=False, default='text')  # text/date/select/number
    _options = db.Column('options', db.Text, default='[]')
    order = db.Column(db.Integer, default=0)

    values = db.relationship('CustomFieldValue', backref='custom_field', lazy=True, cascade='all, delete-orphan')

    @property
    def options(self):
        try:
            return json.loads(self._options or '[]')
        except Exception:
            return []

    @options.setter
    def options(self, value):
        self._options = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'field_type': self.field_type,
            'options': self.options,
            'order': self.order,
        }


class CustomFieldValue(db.Model):
    __tablename__ = 'custom_field_values'
    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('professors.id'), nullable=False)
    custom_field_id = db.Column(db.Integer, db.ForeignKey('custom_fields.id'), nullable=False)
    value = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'professor_id': self.professor_id,
            'custom_field_id': self.custom_field_id,
            'value': self.value,
        }
