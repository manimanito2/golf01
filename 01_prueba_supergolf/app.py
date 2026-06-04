import os
from flask import Flask
from models import db
from controllers.player_controller import player_bp
from controllers.main_controller import main_bp
from controllers.match_controller import match_bp
from controllers.auth_controller import auth_bp, login_manager

app = Flask(__name__, template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'instance', 'golf.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = '0000'

db.init_app(app)
login_manager.init_app(app)

app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(match_bp)
app.register_blueprint(player_bp)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)