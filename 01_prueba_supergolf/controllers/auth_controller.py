from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db
from models.user import User
from functools import wraps

# --- Blueprint de autenticación ---
auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth', url_prefix='')

# --- Configuración del login manager ---
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

# --- Cargador de usuario para Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- Decorador personalizado para roles ---
def role_required(*roles):
    """Permite acceso solo si current_user.role está dentro de roles."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Debe iniciar sesión para acceder a esta página.', 'warning')
                return login_manager.unauthorized()
            if current_user.role not in roles:
                flash('No tienes permisos para acceder a esta página.', 'danger')
                return redirect(url_for('main.home'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# --- Ruta de Login ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Ingreso exitoso.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.home'))

        flash('Usuario o contraseña inválidos.', 'danger')

    return render_template('auth/login.html')


# --- Ruta de Logout ---
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('main.home'))


# --- Ruta de Registro (solo admin) ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Solo el administrador puede registrar usuarios
    if current_user.is_authenticated and current_user.role != 'admin':
        flash('Solo administradores pueden crear usuarios.', 'warning')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        if not username or not password or role not in ('admin', 'executive', 'player'):
            flash('Datos inválidos.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'danger')
            return render_template('auth/register.html')

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Usuario creado correctamente.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')
