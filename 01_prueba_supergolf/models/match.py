from datetime import datetime
import json
from models import db
from models.player import Player


class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), default='activa')
    campo = db.Column(db.String(100), nullable=True)
    tipo_juego = db.Column(db.String(50), nullable=True, default='Stroke Play')
    tipo_partida = db.Column(db.String(20), nullable=True, default='amistoso')

    ratings  = db.Column(db.Text, nullable=True)
    slopes   = db.Column(db.Text, nullable=True)
    pares    = db.Column(db.Text, nullable=True)   # JSON [4,3,5,...]
    wolf_data = db.Column(db.Text, nullable=True)  # JSON {hoyo: {partner: id|'lone'}}
    bbb_data  = db.Column(db.Text, nullable=True)  # JSON {hoyo: {bingo:id, bango:id, bongo:id}}

    jugadores = db.relationship('MatchPlayer', backref='match', cascade='all, delete-orphan')

    def get_pares(self):
        return json.loads(self.pares) if self.pares else [4]*18

    def get_wolf_data(self):
        return json.loads(self.wolf_data) if self.wolf_data else {}

    def get_bbb_data(self):
        return json.loads(self.bbb_data) if self.bbb_data else {}


class MatchPlayer(db.Model):
    __tablename__ = 'match_players'
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    handicap_ajustado = db.Column(db.Float, nullable=True)
    score_total = db.Column(db.Integer, default=0)
    team = db.Column(db.Integer, nullable=True)   # 1 = Equipo A, 2 = Equipo B

    jugador = db.relationship('Player', backref='match_entries')
    scores  = db.relationship('MatchScore', backref='match_player',
                              cascade='all, delete-orphan', order_by='MatchScore.hoyo')


class MatchScore(db.Model):
    __tablename__ = 'match_scores'
    id = db.Column(db.Integer, primary_key=True)
    match_player_id = db.Column(db.Integer, db.ForeignKey('match_players.id'), nullable=False)
    hoyo   = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Float,   nullable=True)
    slope  = db.Column(db.Float,   nullable=True)
    golpes = db.Column(db.Integer, nullable=True)
