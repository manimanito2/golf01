from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.player import Player, db
from models.match import Match, MatchPlayer, MatchScore
import json
from datetime import datetime
from flask_login import login_required
from controllers.auth_controller import role_required

match_bp = Blueprint('match', __name__, url_prefix='/match')

JUEGOS_EQUIPO = ('Best Ball', 'Scramble', 'Alternate Shot')


# ══════════════════════════════════════════════════
#  CALCULADORES
# ══════════════════════════════════════════════════

def calcular_stroke_play(mps, pares):
    res = [{'jugador': mp.jugador.name, 'total': sum(s.golpes or 0 for s in mp.scores), 'detalle': None} for mp in mps]
    return sorted(res, key=lambda x: x['total'])


def calcular_stableford(mps, pares):
    PUNTOS = {-3: 6, -2: 4, -1: 2, 0: 1, 1: 0, 2: 0}
    res = []
    for mp in mps:
        pts = 0
        det = []
        for s in mp.scores:
            if s.golpes is None:
                p = 0
            else:
                diff = s.golpes - pares[s.hoyo - 1]
                p = PUNTOS.get(diff, 0 if diff > 2 else 6)
            pts += p
            det.append(p)
        res.append({'jugador': mp.jugador.name, 'total': pts, 'detalle': det})
    return sorted(res, key=lambda x: x['total'], reverse=True)


def _match_play_dos(mp1, mp2):
    s1 = {s.hoyo: s.golpes for s in mp1.scores}
    s2 = {s.hoyo: s.golpes for s in mp2.scores}
    w1 = w2 = e = 0
    det1, det2 = [], []
    for h in range(1, 19):
        g1, g2 = s1.get(h), s2.get(h)
        if g1 is None or g2 is None:
            det1.append('—'); det2.append('—')
        elif g1 < g2:
            w1 += 1; det1.append('W'); det2.append('L')
        elif g2 < g1:
            w2 += 1; det1.append('L'); det2.append('W')
        else:
            e += 1; det1.append('H'); det2.append('H')
    return w1, w2, e, det1, det2


def calcular_match_play(mps, pares):
    if len(mps) != 2:
        return calcular_stroke_play(mps, pares)
    w1, w2, e, d1, d2 = _match_play_dos(mps[0], mps[1])
    return [
        {'jugador': mps[0].jugador.name, 'total': f'{w1}W/{w2}L/{e}H', 'detalle': d1},
        {'jugador': mps[1].jugador.name, 'total': f'{w2}W/{w1}L/{e}H', 'detalle': d2},
    ]


def calcular_skins(mps, pares):
    skins = {mp.jugador.name: 0 for mp in mps}
    detalle = []
    for h in range(1, 19):
        golpes = {mp.jugador.name: next((s.golpes for s in mp.scores if s.hoyo == h), None) for mp in mps}
        validos = {n: g for n, g in golpes.items() if g is not None}
        if not validos:
            detalle.append({'hoyo': h, 'ganador': '—'}); continue
        mn = min(validos.values())
        ganadores = [n for n, g in validos.items() if g == mn]
        if len(ganadores) == 1:
            skins[ganadores[0]] += 1
            detalle.append({'hoyo': h, 'ganador': ganadores[0]})
        else:
            detalle.append({'hoyo': h, 'ganador': 'Empate'})
    res = [{'jugador': n, 'total': s, 'detalle': detalle} for n, s in skins.items()]
    return sorted(res, key=lambda x: x['total'], reverse=True)


def calcular_nassau(mps, pares):
    """3 apuestas: Front 9 / Back 9 / Total 18 (Match Play)."""
    if len(mps) != 2:
        return calcular_stroke_play(mps, pares)
    mp1, mp2 = mps
    s1 = {s.hoyo: s.golpes for s in mp1.scores}
    s2 = {s.hoyo: s.golpes for s in mp2.scores}

    def seg(start, end):
        w1 = w2 = 0
        for h in range(start, end + 1):
            g1, g2 = s1.get(h), s2.get(h)
            if g1 is not None and g2 is not None:
                if g1 < g2: w1 += 1
                elif g2 < g1: w2 += 1
        return w1, w2

    f1, f2 = seg(1, 9)
    b1, b2 = seg(10, 18)
    t1, t2 = seg(1, 18)

    def fmt(w, l): return f'{w}' if w > l else (f'A{l-w}' if l > w else 'AS')

    return [
        {'jugador': mp1.jugador.name,
         'total': f'F:{fmt(f1,f2)}  B:{fmt(b1,b2)}  T:{fmt(t1,t2)}',
         'nassau': {'front': (f1, f2), 'back': (b1, b2), 'total': (t1, t2)},
         'detalle': None},
        {'jugador': mp2.jugador.name,
         'total': f'F:{fmt(f2,f1)}  B:{fmt(b2,b1)}  T:{fmt(t2,t1)}',
         'nassau': {'front': (f2, f1), 'back': (b2, b1), 'total': (t2, t1)},
         'detalle': None},
    ]


def _team_groups(mps):
    teams = {}
    for mp in mps:
        t = mp.team or 0
        teams.setdefault(t, []).append(mp)
    return teams


def calcular_best_ball(mps, pares):
    """Cada jugador juega su bola; el equipo usa el mejor score por hoyo."""
    teams = _team_groups(mps)
    if len(teams) < 2:
        return calcular_stroke_play(mps, pares)
    res = []
    for tid, tmps in sorted(teams.items()):
        names = ' & '.join(mp.jugador.name for mp in tmps)
        total = 0
        for h in range(1, 19):
            hs = [s.golpes for mp in tmps for s in mp.scores if s.hoyo == h and s.golpes is not None]
            if hs: total += min(hs)
        res.append({'jugador': f'Eq.{"AB"[tid-1] if tid in (1,2) else tid}: {names}', 'total': total, 'detalle': None})
    return sorted(res, key=lambda x: x['total'])


def calcular_scramble(mps, pares):
    """Todos golpean, se usa el mejor. Score = score ingresado del equipo (1 score por equipo)."""
    teams = _team_groups(mps)
    if len(teams) < 2:
        return calcular_stroke_play(mps, pares)
    res = []
    for tid, tmps in sorted(teams.items()):
        names = ' & '.join(mp.jugador.name for mp in tmps)
        # Usamos el mínimo score por hoyo entre los miembros del equipo
        total = 0
        for h in range(1, 19):
            hs = [s.golpes for mp in tmps for s in mp.scores if s.hoyo == h and s.golpes is not None]
            if hs: total += min(hs)
        res.append({'jugador': f'Eq.{"AB"[tid-1] if tid in (1,2) else tid}: {names}', 'total': total, 'detalle': None})
    return sorted(res, key=lambda x: x['total'])


def calcular_alternate_shot(mps, pares):
    """Equipos alternan golpes. Score ingresado es el resultado final por hoyo del equipo."""
    teams = _team_groups(mps)
    if len(teams) < 2:
        return calcular_stroke_play(mps, pares)
    res = []
    for tid, tmps in sorted(teams.items()):
        names = ' & '.join(mp.jugador.name for mp in tmps)
        # Promediamos los scores del equipo por hoyo (reflejan el juego alternado)
        total = 0
        for h in range(1, 19):
            hs = [s.golpes for mp in tmps for s in mp.scores if s.hoyo == h and s.golpes is not None]
            if hs: total += min(hs)
        res.append({'jugador': f'Eq.{"AB"[tid-1] if tid in (1,2) else tid}: {names}', 'total': total, 'detalle': None})
    return sorted(res, key=lambda x: x['total'])


def calcular_wolf(mps, pares, wolf_data):
    """
    Rotación automática de wolf por hoyo.
    Wolf elige compañero o va solo (Lone Wolf).
    Puntos: wolf+compañero ganan → 1pt c/u | pierden → rivales 2pt c/u
            Lone wolf gana → wolf 2*(n-1)pt | pierde → rivales 2pt c/u
    """
    puntos = {mp.id: 0 for mp in mps}
    n = len(mps)
    id_to_mp = {mp.id: mp for mp in mps}

    for h in range(1, 19):
        wolf_mp = mps[(h - 1) % n]
        hdata = wolf_data.get(str(h), {})
        partner_raw = hdata.get('partner', 'lone')

        scores = {mp.id: next((s.golpes for s in mp.scores if s.hoyo == h), None) for mp in mps}

        if partner_raw and partner_raw != 'lone':
            try:
                partner_id = int(partner_raw)
                partner_mp = id_to_mp.get(partner_id)
            except (ValueError, TypeError):
                partner_mp = None

            if partner_mp and partner_mp != wolf_mp:
                team_wolf = [wolf_mp, partner_mp]
                team_opp  = [mp for mp in mps if mp not in team_wolf]
                tw = min((scores[mp.id] for mp in team_wolf if scores[mp.id] is not None), default=999)
                to = min((scores[mp.id] for mp in team_opp  if scores[mp.id] is not None), default=999)
                if tw < to:
                    for mp in team_wolf: puntos[mp.id] += 1
                elif to < tw:
                    for mp in team_opp:  puntos[mp.id] += 2
                continue

        # Lone wolf
        ws = scores.get(wolf_mp.id)
        if ws is None: continue
        opp_min = min((scores[mp.id] for mp in mps if mp != wolf_mp and scores[mp.id] is not None), default=999)
        if ws < opp_min:
            puntos[wolf_mp.id] += 2 * (n - 1)
        elif opp_min < ws:
            for mp in mps:
                if mp != wolf_mp: puntos[mp.id] += 2

    res = [{'jugador': mp.jugador.name, 'total': puntos[mp.id], 'detalle': None} for mp in mps]
    return sorted(res, key=lambda x: x['total'], reverse=True)


def calcular_bbb(mps, pares, bbb_data):
    """
    3 puntos por hoyo:
      Bingo  = primero en verde
      Bango  = más cercano al hoyo cuando todos están en verde
      Bongo  = primero en embocar
    """
    puntos = {mp.id: 0 for mp in mps}
    for h in range(1, 19):
        hdata = bbb_data.get(str(h), {})
        for key in ('bingo', 'bango', 'bongo'):
            try:
                pid = int(hdata.get(key, 0))
                if pid in puntos:
                    puntos[pid] += 1
            except (ValueError, TypeError):
                pass
    res = [{'jugador': mp.jugador.name, 'total': puntos[mp.id], 'detalle': None} for mp in mps]
    return sorted(res, key=lambda x: x['total'], reverse=True)


def calcular_resultados(match, mps):
    pares = match.get_pares()
    t = match.tipo_juego or 'Stroke Play'
    if t == 'Stroke Play':        return calcular_stroke_play(mps, pares)
    elif t == 'Stableford':       return calcular_stableford(mps, pares)
    elif t == 'Match Play':       return calcular_match_play(mps, pares)
    elif t == 'Skins Game':       return calcular_skins(mps, pares)
    elif t == 'Nassau':           return calcular_nassau(mps, pares)
    elif t == 'Best Ball':        return calcular_best_ball(mps, pares)
    elif t == 'Scramble':         return calcular_scramble(mps, pares)
    elif t == 'Alternate Shot':   return calcular_alternate_shot(mps, pares)
    elif t == 'Wolf':             return calcular_wolf(mps, pares, match.get_wolf_data())
    elif t == 'Bingo-Bango-Bongo':return calcular_bbb(mps, pares, match.get_bbb_data())
    else:                         return calcular_stroke_play(mps, pares)


# ══════════════════════════════════════════════════
#  RUTAS
# ══════════════════════════════════════════════════

@match_bp.route('/')
@login_required
def list_matches():
    matches = Match.query.order_by(Match.fecha.desc()).all()
    return render_template('matches/list_matches.html', matches=matches)


@match_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'executive')
def new_match():
    if request.method == 'POST':
        campo       = request.form.get('campo')
        player_ids  = request.form.getlist('players')
        tipo_juego  = request.form.get('tipo_juego', 'Stroke Play')
        tipo_partida= request.form.get('tipo_partida', 'amistoso')

        pares = []
        for h in range(1, 19):
            try:   pares.append(int(request.form.get(f'par_{h}', 4)))
            except: pares.append(4)

        m = Match(campo=campo, fecha=datetime.now(),
                  tipo_juego=tipo_juego, tipo_partida=tipo_partida,
                  pares=json.dumps(pares))
        db.session.add(m)
        db.session.flush()

        for pid in player_ids:
            try:   team = int(request.form.get(f'team_{pid}', 0))
            except: team = 0
            mp = MatchPlayer(match_id=m.id, player_id=int(pid), team=team or None)
            db.session.add(mp)
            db.session.flush()
            for h in range(1, 19):
                db.session.add(MatchScore(match_player_id=mp.id, hoyo=h, golpes=None))

        db.session.commit()
        flash('Partida creada correctamente', 'success')
        return redirect(url_for('match.list_matches'))

    players = Player.query.order_by(Player.name).all()
    return render_template('matches/new_match.html', players=players,
                           pares_default=[4]*18, juegos_equipo=list(JUEGOS_EQUIPO))


@match_bp.route('/<int:match_id>/scorecard', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'executive', 'player')
def scorecard(match_id):
    match = Match.query.get_or_404(match_id)
    mps   = MatchPlayer.query.filter_by(match_id=match_id).all()

    if request.method == 'POST':
        # Scores
        for mp in mps:
            for h in range(1, 19):
                val = request.form.get(f'score_{mp.id}_{h}')
                ms  = MatchScore.query.filter_by(match_player_id=mp.id, hoyo=h).first()
                if ms:
                    try:   ms.golpes = int(val) if val and val != '' else None
                    except: ms.golpes = None

        for mp in mps:
            mp.score_total = sum(s.golpes or 0 for s in mp.scores)

        # Wolf data
        if match.tipo_juego == 'Wolf':
            wd = match.get_wolf_data()
            for h in range(1, 19):
                partner = request.form.get(f'wolf_{h}_partner', 'lone')
                wd[str(h)] = {'partner': partner}
            match.wolf_data = json.dumps(wd)

        # BBB data
        if match.tipo_juego == 'Bingo-Bango-Bongo':
            bbb = match.get_bbb_data()
            for h in range(1, 19):
                bbb[str(h)] = {
                    'bingo': request.form.get(f'bbb_{h}_bingo', ''),
                    'bango': request.form.get(f'bbb_{h}_bango', ''),
                    'bongo': request.form.get(f'bbb_{h}_bongo', ''),
                }
            match.bbb_data = json.dumps(bbb)

        db.session.commit()
        flash('Scores guardados', 'success')
        return redirect(url_for('match.scorecard', match_id=match_id))

    holes      = list(range(1, 19))
    pares      = match.get_pares()
    wolf_data  = match.get_wolf_data()
    bbb_data   = match.get_bbb_data()
    scores_map = {mp.id: {ms.hoyo: ms for ms in mp.scores} for mp in mps}
    resultados = calcular_resultados(match, mps)

    return render_template('matches/scorecard.html',
        match=match, mps=mps, holes=holes, pares=pares,
        scores_map=scores_map, resultados=resultados,
        wolf_data=wolf_data, bbb_data=bbb_data,
        juegos_equipo=list(JUEGOS_EQUIPO))


@match_bp.route('/<int:match_id>/finalizar', methods=['POST'])
@login_required
@role_required('admin', 'executive')
def finalizar_match(match_id):
    match = Match.query.get_or_404(match_id)
    match.estado = 'finalizada'
    db.session.commit()
    flash('Partida marcada como finalizada', 'success')
    return redirect(url_for('match.scorecard', match_id=match_id))


@match_bp.route('/<int:match_id>/delete', methods=['POST', 'GET'])
@login_required
@role_required('admin', 'executive')
def delete_match(match_id):
    match = Match.query.get_or_404(match_id)
    for mp in match.jugadores:
        for ms in mp.scores: db.session.delete(ms)
        db.session.delete(mp)
    db.session.delete(match)
    db.session.commit()
    flash('Partida eliminada correctamente', 'success')
    return redirect(url_for('match.list_matches'))
