from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class Musical(db.Model):
    __tablename__ = 'musicals'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text)
    images = db.Column(db.JSON)  # ← NUEVO: Lista de URLs de imágenes
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship
    links = db.relationship('MusicalLink', backref='musical', lazy=True, cascade='all, delete-orphan')
    changes = db.relationship('MusicalChange', backref='musical', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Musical {self.name}>'

class MusicalLink(db.Model):
    __tablename__ = 'musical_links'
    id = db.Column(db.Integer, primary_key=True)
    musical_id = db.Column(db.Integer, db.ForeignKey('musicals.id'), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    notes = db.Column(db.String(500), default='')
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_checked = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default='active')
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
    change_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, default='')
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    changed_by = db.Column(db.String(100), default='system')
    extra_data = db.Column(db.Text, default='{}')  # ← CAMBIADO de 'metadata' a 'extra_data'
    musical = db.relationship('Musical', back_populates='changes')

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'change_type': self.change_type,
            'description': self.description,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
            'changed_by': self.changed_by,
            'extra_data': json.loads(self.extra_data) if self.extra_data else {}
        }