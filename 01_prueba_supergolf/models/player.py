# models/player.py
from models import db

class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    handicap = db.Column(db.Float, nullable=True)
    country = db.Column(db.String(50), nullable=True)

    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'))
    match = db.relationship('Match', backref='players')  # usar string si hay error

    def __init__(self, name, handicap=None, country=None, match_id=None):
        self.name = name
        self.handicap = handicap
        self.country = country
        self.match_id = match_id

    def __repr__(self):
        return f'<Player {self.name}>'
