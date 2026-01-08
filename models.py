from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

class Musical(db.Model):
    __tablename__ = 'musicals'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text)
    images = db.Column(db.JSON)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships - SIN backref duplicado
    links = db.relationship('MusicalLink', back_populates='musical', lazy=True, cascade='all, delete-orphan')
    changes = db.relationship('MusicalChange', back_populates='musical', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Musical {self.name}>'

class MusicalLink(db.Model):
    __tablename__ = 'musical_links'
    
    id = db.Column(db.Integer, primary_key=True)
    musical_id = db.Column(db.Integer, db.ForeignKey('musicals.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_checked = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship - back_populates en lugar de backref
    musical = db.relationship('Musical', back_populates='links')
    
    def __repr__(self):
        return f'<MusicalLink {self.url}>'

class MusicalChange(db.Model):
    __tablename__ = 'musical_changes'
    
    id = db.Column(db.Integer, primary_key=True)
    musical_id = db.Column(db.Integer, db.ForeignKey('musicals.id'), nullable=False)
    change_type = db.Column(db.String(50))
    url = db.Column(db.String(500))
    status_code = db.Column(db.Integer)
    notified = db.Column(db.Boolean, default=False)
    diff_snippet = db.Column(db.Text)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship - back_populates en lugar de backref
    musical = db.relationship('Musical', back_populates='changes')
    
    def __repr__(self):
        return f'<MusicalChange {self.change_type}>'