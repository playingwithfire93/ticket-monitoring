from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class Musical(db.Model):
    __tablename__ = 'musicals'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    image_url = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    links = db.relationship('MusicalLink', back_populates='musical', cascade='all, delete-orphan')
    changes = db.relationship('MusicalChange', back_populates='musical', cascade='all, delete-orphan', order_by='MusicalChange.changed_at.desc()')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'links': [link.to_dict() for link in self.links],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'recent_changes': [change.to_dict() for change in self.changes[:5]]  # últimos 5 cambios
        }

class MusicalLink(db.Model):
    __tablename__ = 'musical_links'
    id = db.Column(db.Integer, primary_key=True)
    musical_id = db.Column(db.Integer, db.ForeignKey('musicals.id'), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    notes = db.Column(db.String(500), default='')
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_checked = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='active')  # active, error, removed
    musical = db.relationship('Musical', back_populates='links')

    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'notes': self.notes,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'status': self.status
        }

class MusicalChange(db.Model):
    __tablename__ = 'musical_changes'
    id = db.Column(db.Integer, primary_key=True)
    musical_id = db.Column(db.Integer, db.ForeignKey('musicals.id'), nullable=False)
    change_type = db.Column(db.String(50), nullable=False)  # created, link_added, link_removed, updated, approved
    description = db.Column(db.Text, default='')
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    changed_by = db.Column(db.String(100), default='system')  # system, admin, user
    metadata = db.Column(db.Text, default='{}')  # JSON string para datos extra
    musical = db.relationship('Musical', back_populates='changes')

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'change_type': self.change_type,
            'description': self.description,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
            'changed_by': self.changed_by,
            'metadata': json.loads(self.metadata) if self.metadata else {}
        }