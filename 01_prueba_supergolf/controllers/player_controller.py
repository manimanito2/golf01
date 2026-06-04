# controllers/player_controller.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.player import db, Player
from models.match import MatchPlayer, Match  # Importamos todo lo necesario

# Importaciones nuevas para login y roles
from flask_login import login_required
from controllers.auth_controller import role_required

player_bp = Blueprint('player', __name__, url_prefix='/players')


# LISTAR JUGADORES (acceso: admin, ejecutivo, jugador)
@player_bp.route('/')
@login_required
@role_required('admin', 'executive', 'player')
def list_players():
    jugadores_info = []

    for p in Player.query.order_by(Player.name).all():
        # Buscar la primera partida activa del jugador
        partida_activa = MatchPlayer.query.join(Match)\
            .filter(MatchPlayer.player_id == p.id, Match.estado == 'activa')\
            .first()  # Ajusta 'estado' si tu columna se llama diferente

        jugadores_info.append({
            'id': p.id,
            'name': p.name,
            'handicap': p.handicap,
            'country': p.country,
            'match_id': partida_activa.match_id if partida_activa else None
        })

    return render_template('players/list_players.html', players=jugadores_info, titulo="Jugadores")


# AGREGAR JUGADOR (acceso: admin, ejecutivo)
@player_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'executive')
def add_player():
    if request.method == 'POST':
        name = request.form['name']
        handicap = request.form.get('handicap')
        country = request.form.get('country')
        match_id = request.form.get('match_id')  # Nuevo campo

        player = Player(name=name, handicap=handicap, country=country, match_id=match_id)
        db.session.add(player)
        db.session.commit()
        flash('Jugador agregado correctamente.', 'success')
        return redirect(url_for('player.list_players'))

    matches = Match.query.all()  # Lista de partidas disponibles
    return render_template('players/add_player.html', matches=matches)


# ELIMINAR JUGADOR (acceso: solo admin)
@player_bp.route('/delete/<int:player_id>', methods=['POST'])
@login_required
@role_required('admin')
def delete_player(player_id):
    player = Player.query.get_or_404(player_id)

    # Verificar si el jugador está en algún partido activo
    partidas = MatchPlayer.query.filter_by(player_id=player.id).all()
    if partidas:
        flash(f"No se puede eliminar el jugador {player.name}, está en partidas activas.", 'error')
        return redirect(url_for('player.list_players'))

    try:
        db.session.delete(player)
        db.session.commit()
        flash(f'Jugador {player.name} eliminado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el jugador: {str(e)}', 'error')

    return redirect(url_for('player.list_players'))
