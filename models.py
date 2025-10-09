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
    links = db.relationship('MusicalLink', back_populates='musical', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'links': [link.to_dict() for link in self.links],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class MusicalLink(db.Model):
    __tablename__ = 'musical_links'
    id = db.Column(db.Integer, primary_key=True)
    musical_id = db.Column(db.Integer, db.ForeignKey('musicals.id'), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    notes = db.Column(db.String(500), default='')
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    musical = db.relationship('Musical', back_populates='links')

    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'notes': self.notes,
            'added_at': self.added_at.isoformat() if self.added_at else None
        }