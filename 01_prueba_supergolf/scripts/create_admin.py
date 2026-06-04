import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db
from models.user import User

USERNAME = 'admin'
PASSWORD = '0000'

with app.app_context():
    if User.query.filter_by(username=USERNAME).first():
        print('Usuario admin ya existe')
    else:
        u = User(username=USERNAME, role='admin')
        u.set_password(PASSWORD)
        db.session.add(u)
        db.session.commit()
        print('Admin creado:', USERNAME)
