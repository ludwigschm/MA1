import os
import csv
from pathlib import Path
from datetime import datetime
import streamlit as st

# -------------------------------------------------------------
# Streamlit-Port (MVP) deiner Kivy-Tabletop-UX
# - Verwendet die Ordnerstruktur und Dateinamen wie im Kivy-Skript
# - Läuft ohne Kivy, komplett im Browser (Streamlit)
# - Ziel: gleiche Phasen/Buttons/Logik in einfacher Web-UI
# - Hinweise:
#     * Bilder: leere Platzhalter, wenn Dateien fehlen
#     * CSV-Planung (Paare*.csv): optional, wenn vorhanden
#     * Logging: einfache CSV-Logs unter ./logs/
# -------------------------------------------------------------

# --- Konstanten & Assets (analog zu deinem Kivy-Code)
ROOT = os.path.dirname(os.path.abspath(__file__))
UX_DIR = os.path.join(ROOT, 'UX')
CARD_DIR = os.path.join(ROOT, 'Karten')
LOG_DIR = os.path.join(ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

ASSETS = {
    'play': {
        'live':  os.path.join(UX_DIR, 'play_live.png'),
        'stop':  os.path.join(UX_DIR, 'play_stop.png'),
    },
    'signal': {
        'low':   {'live': os.path.join(UX_DIR, 'tief_live.png'),   'stop': os.path.join(UX_DIR, 'tief_stop.png')},
        'mid':   {'live': os.path.join(UX_DIR, 'mittel_live.png'), 'stop': os.path.join(UX_DIR, 'mittel_stop.png')},
        'high':  {'live': os.path.join(UX_DIR, 'hoch_live.png'),   'stop': os.path.join(UX_DIR, 'hoch_stop.png')},
    },
    'decide': {
        'bluff': {'live': os.path.join(UX_DIR, 'bluff_live.png'),  'stop': os.path.join(UX_DIR, 'bluff_stop.png')},
        'wahr':  {'live': os.path.join(UX_DIR, 'wahr_live.png'),   'stop': os.path.join(UX_DIR, 'wahr_stop.png')},
    },
    'cards': {
        'back':      os.path.join(CARD_DIR, 'back.png'),
        'back_stop': os.path.join(CARD_DIR, 'back_stop.png'),
    }
}

# --- Phasen (analog)
PH_WAIT_BOTH_START = 'WAIT_BOTH_START'
PH_P1_INNER = 'P1_INNER'
PH_P2_INNER = 'P2_INNER'
PH_P1_OUTER = 'P1_OUTER'
PH_P2_OUTER = 'P2_OUTER'
PH_SIGNALER = 'SIGNALER'
PH_JUDGE = 'JUDGE'
PH_SHOWDOWN = 'SHOWDOWN'

st.set_page_config(page_title='Tabletop UX – Streamlit', layout='wide')

# ------------------------- Helpers --------------------------

def file_or_none(path):
    return path if os.path.exists(path) else None


def value_to_card_path(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return file_or_none(ASSETS['cards']['back'])
    filename = f'{number}.png'
    path = os.path.join(CARD_DIR, filename)
    return file_or_none(path) or file_or_none(ASSETS['cards']['back'])


def parse_csv_rounds(path: Path):
    rounds = []
    if not path.exists():
        return rounds
    try:
        with open(path, newline='', encoding='utf-8') as fp:
            rows = list(csv.reader(fp))
    except Exception:
        return rounds

    def parse_cards(row, start, end):
        vals = []
        for idx in range(start, min(end, len(row))):
            cell = (row[idx] or '').strip()
            if not cell:
                continue
            try:
                vals.append(int(float(cell)))
            except ValueError:
                continue
            if len(vals) == 2:
                break
        if len(vals) < 2:
            return None
        return tuple(vals[:2])

    start_idx = 0
    if rows:
        try:
            _ = parse_cards(rows[0], 2, 4)
            _ = parse_cards(rows[0], 7, 9)
        except Exception:
            start_idx = 1

    for row in rows[start_idx:]:
        if not row or all((cell or '').strip() == '' for cell in row):
            continue
        vp1 = parse_cards(row, 2, 4)
        vp2 = parse_cards(row, 7, 9)
        if not vp1 or not vp2:
            continue
        rounds.append({'vp1': vp1, 'vp2': vp2})
    return rounds


def load_blocks():
    order = [
        (1, 'Paare1.csv', False),
        (2, 'Paare3.csv', True),
        (3, 'Paare2.csv', False),
        (4, 'Paare4.csv', True),
    ]
    blocks = []
    for idx, filename, payout in order:
        path = Path(ROOT) / filename
        rounds = parse_csv_rounds(path)
        blocks.append({
            'index': idx,
            'csv': filename,
            'path': path,
            'rounds': rounds,
            'payout': payout,
        })
    return blocks


def ensure_state():
    if 'initialized' in st.session_state:
        return

    st.session_state.initialized = True
    st.session_state.blocks = load_blocks()
    st.session_state.current_block_idx = 0
    st.session_state.current_round_idx = 0
    st.session_state.in_block_pause = False
    st.session_state.session_finished = False

    st.session_state.signaler = 1
    st.session_state.judge = 2

    st.session_state.phase = PH_WAIT_BOTH_START
    st.session_state.player_signals = {1: None, 2: None}
    st.session_state.player_decisions = {1: None, 2: None}

    st.session_state.score_state_block = None
    st.session_state.score_state = None  # {1: 16, 2: 16} in Stake-Blöcken

    st.session_state.session_id = None
    st.session_state.round_in_block = 1

    setup_round()


def compute_global_round():
    blocks = st.session_state.blocks
    total = 0
    for i, b in enumerate(blocks):
        if i < st.session_state.current_block_idx:
            total += len(b['rounds'])
    if st.session_state.current_block_idx >= len(blocks):
        return max(1, total)
    return total + st.session_state.current_round_idx + 1


def current_plan():
    blocks = st.session_state.blocks
    if not blocks or st.session_state.session_finished or st.session_state.in_block_pause:
        return None
    i = st.session_state.current_block_idx
    if i >= len(blocks):
        return None
    rounds = blocks[i]['rounds']
    if not rounds:
        return None
    j = st.session_state.current_round_idx
    if j >= len(rounds):
        return None
    return {'block': blocks[i], 'round': rounds[j]}


def setup_round():
    st.session_state.player_signals = {1: None, 2: None}
    st.session_state.player_decisions = {1: None, 2: None}

    info = current_plan()
    st.session_state.round = compute_global_round()
    if info:
        block = info['block']
        st.session_state.round_in_block = st.session_state.current_round_idx + 1
        payout = block['payout']
        st.session_state.current_round_has_stake = payout
        if payout and st.session_state.score_state_block != block['index']:
            st.session_state.score_state = {1: 16, 2: 16}
            st.session_state.score_state_block = block['index']
        if not payout:
            st.session_state.score_state = None
            st.session_state.score_state_block = None
    else:
        st.session_state.current_round_has_stake = False


def advance_round_pointer():
    if st.session_state.session_finished:
        return
    blocks = st.session_state.blocks
    i = st.session_state.current_block_idx
    if i >= len(blocks):
        st.session_state.session_finished = True
        return
    st.session_state.current_round_idx += 1
    if st.session_state.current_round_idx >= len(blocks[i]['rounds']):
        # Block fertig
        st.session_state.current_block_idx += 1
        st.session_state.current_round_idx = 0
        if st.session_state.current_block_idx >= len(blocks):
            st.session_state.session_finished = True
            st.session_state.in_block_pause = False
        else:
            st.session_state.in_block_pause = True


def swap_roles():
    st.session_state.signaler, st.session_state.judge = st.session_state.judge, st.session_state.signaler


def signal_level_from_value(value):
    try:
        v = int(value)
    except Exception:
        return None
    if v <= 0 or v in (20, 21, 22):
        return None
    if v == 19:
        return 'high'
    if v in (16, 17, 18):
        return 'mid'
    if v in (14, 15):
        return 'low'
    if v >= 16:
        return 'mid'
    return 'low'


def get_current_values():
    info = current_plan()
    if not info:
        return None
    vp1 = info['round']['vp1']
    vp2 = info['round']['vp2']
    def val(cards):
        total = sum(cards)
        return 0 if total in (20, 21, 22) else total
    return {
        1: {
            'cards': vp1,
            'value': val(vp1),
            'total': sum(vp1)
        },
        2: {
            'cards': vp2,
            'value': val(vp2),
            'total': sum(vp2)
        }
    }


def compute_outcome():
    state = get_current_values()
    if not state:
        return None
    signaler = st.session_state.signaler
    judge = st.session_state.judge

    signal_choice = st.session_state.player_signals.get(signaler)
    judge_choice = st.session_state.player_decisions.get(judge)

    actual_total = state[signaler]['total']
    actual_value = state[signaler]['value']
    actual_level = signal_level_from_value(actual_value)

    truthful = None
    if signal_choice:
        if actual_level:
            truthful = (signal_choice == actual_level)
        elif actual_total in (20, 21, 22):
            truthful = False

    winner = None
    draw = False
    if judge_choice and truthful is not None:
        if judge_choice == 'wahr':
            winner = judge if truthful else signaler
        else:  # 'bluff'
            winner = judge if not truthful else signaler
        # Sonderfall Gleichstand bei wahr/wahr
        judge_total = state[judge]['total']
        if (winner in (signaler, judge)
            and truthful is True
            and judge_choice == 'wahr'
            and actual_total == judge_total):
            winner = None
            draw = True

    res = {
        'winner': winner,
        'truthful': truthful,
        'actual_level': actual_level,
        'actual_value': actual_value,
        'actual_total': actual_total,
        'judge_total': state[judge]['total'],
        'signal_choice': signal_choice,
        'judge_choice': judge_choice,
        'payout': st.session_state.current_round_has_stake,
        'draw': draw,
    }

    # Punkte anwenden (falls Stake) – einmalig pro Runde
    if st.session_state.current_round_has_stake and st.session_state.score_state and 'score_applied' not in st.session_state:
        if winner in (1, 2):
            # winner ist Spieler (1/2); Punkte zählen relativ zu VP1/VP2 = fix 1/2
            # Signaler/Judge sind nur Rollen, nicht VP-IDs
            # Hier setzen wir VP1 -> unten (Spieler 1), VP2 -> oben (Spieler 2), wie im Kivy-Code
            winner_vp = 1 if winner == 1 else 2
            loser_vp = 2 if winner_vp == 1 else 1
            st.session_state.score_state[winner_vp] += 1
            st.session_state.score_state[loser_vp] -= 1
        st.session_state.score_applied = True
    return res


def reset_score_applied():
    if 'score_applied' in st.session_state:
        del st.session_state['score_applied']


def write_round_log(action, payload=None, actor_player=None):
    payload = payload or {}
    sid = st.session_state.session_id or ''
    info = current_plan()
    block = info['block']['index'] if info else ''
    round_in_block = st.session_state.round_in_block if info else ''
    vp1_cards = info['round']['vp1'] if info else ('', '')
    vp2_cards = info['round']['vp2'] if info else ('', '')
    winner_label = ''
    score1 = st.session_state.score_state.get(1, '') if st.session_state.score_state else ''
    score2 = st.session_state.score_state.get(2, '') if st.session_state.score_state else ''
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]

    # CSV schreiben
    path = Path(LOG_DIR) / f'round_log_{sid or "session"}.csv'
    new_file = not path.exists()
    with open(path, 'a', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp)
        if new_file:
            w.writerow(['Session','Block','Runde','K1 VP1','K2 VP1','K1 VP2','K2 VP2','Aktion','Zeit','Gewinner','Punkte VP1','Punkte VP2'])
        if action == 'showdown':
            outcome = compute_outcome() or {}
            winner = outcome.get('winner')
            winner_label = f'VP{winner}' if winner in (1,2) else ''
        w.writerow([
            sid, block, round_in_block,
            vp1_cards[0] if vp1_cards else '', vp1_cards[1] if vp1_cards else '',
            vp2_cards[0] if vp2_cards else '', vp2_cards[1] if vp2_cards else '',
            action, ts, winner_label, score1, score2
        ])


# -------------------------- UI ------------------------------
ensure_state()

# Kopfzeile / Session
col_left, col_mid, col_right = st.columns([1,2,1])
with col_left:
    st.title('Tabletop UX – Web')
with col_right:
    st.text_input('Session-ID (optional):', key='session_id', value=st.session_state.session_id or '')

info = current_plan()
round_str = f"Runde {st.session_state.round_in_block if info else 0}/16"
block_str = f"Block {info['block']['index']} ({'Stake' if info and info['block']['payout'] else 'ohne Stake'})" if info else '—'
status_cols = st.columns(3)
status_cols[0].markdown(f"**{block_str}**")
status_cols[1].markdown(f"**{round_str}**")
status_cols[2].markdown(f"**Signaler:** Spieler {st.session_state.signaler}  |  **Judge:** Spieler {st.session_state.judge}")

# Layout: 2 Reihen Karten + mittige Anzeigen (MVP: simple Grids)
upper = st.columns(5)
lower = st.columns(5)

# Kartenanzeige (verdeckt/aufgedeckt im Streamlit-MVP: wir zeigen Werte erst im Showdown)
state_vals = get_current_values()

# Obere Reihe – Spieler 2
upper[0].markdown('#### Spieler 2 – äußere Karte')
upper[0].image(value_to_card_path(state_vals[2]['cards'][1]) if state_vals else file_or_none(ASSETS['cards']['back']), use_column_width=True)
upper[1].markdown('#### Spieler 2 – innere Karte')
upper[1].image(value_to_card_path(state_vals[2]['cards'][0]) if state_vals else file_or_none(ASSETS['cards']['back']), use_column_width=True)

# Mittig: Anzeigen
center_area = upper[2]

# Untere Reihe – Spieler 1
lower[0].markdown('#### Spieler 1 – innere Karte')
lower[0].image(value_to_card_path(state_vals[1]['cards'][0]) if state_vals else file_or_none(ASSETS['cards']['back']), use_column_width=True)
lower[1].markdown('#### Spieler 1 – äußere Karte')
lower[1].image(value_to_card_path(state_vals[1]['cards'][1]) if state_vals else file_or_none(ASSETS['cards']['back']), use_column_width=True)

# --- Interaktion entsprechend Phase ---
phase = st.session_state.phase

# Start / Next
with center_area:
    st.subheader('Steuerung')
    both_ready = st.checkbox('Beide Spieler bereit (Start/Nächste Runde)', key='both_ready', value=False)
    if both_ready:
        st.session_state['both_ready'] = False
        if st.session_state.phase in (PH_WAIT_BOTH_START, PH_SHOWDOWN):
            if st.session_state.phase == PH_SHOWDOWN:
                # nächste Runde vorbereiten
                reset_score_applied()
                swap_roles()
                advance_round_pointer()
                setup_round()
            # Erste Phase abhängig vom Signaler
            first = st.session_state.signaler
            st.session_state.phase = PH_P1_INNER if first == 1 else PH_P2_INNER
            write_round_log('start_or_next')

# Karten-Aufdecken (MVP: Buttons, die die Phase weiterschalten – Bilder bleiben gleich)
card_cols = st.columns(2)
with card_cols[0]:
    if phase in (PH_P1_INNER, PH_P1_OUTER) and st.button('Spieler 1: Nächste Karte aufdecken'):
        if phase == PH_P1_INNER:
            st.session_state.phase = PH_P2_INNER
        elif phase == PH_P1_OUTER:
            st.session_state.phase = PH_P2_OUTER
        write_round_log('reveal_card_p1')
with card_cols[1]:
    if phase in (PH_P2_INNER, PH_P2_OUTER) and st.button('Spieler 2: Nächste Karte aufdecken'):
        if phase == PH_P2_INNER:
            st.session_state.phase = PH_P1_OUTER
        elif phase == PH_P2_OUTER:
            st.session_state.phase = PH_SIGNALER
        write_round_log('reveal_card_p2')

# Signaler – Signalwahl
if phase == PH_SIGNALER:
    signaler = st.session_state.signaler
    st.markdown(f"### Signaler (Spieler {signaler}): Signal wählen")
    sig_cols = st.columns(3)
    if sig_cols[0].button('Tief'):
        st.session_state.player_signals[signaler] = 'low'
        st.session_state.phase = PH_JUDGE
        write_round_log('signal_choice', {'level': 'low'})
    if sig_cols[1].button('Mittel'):
        st.session_state.player_signals[signaler] = 'mid'
        st.session_state.phase = PH_JUDGE
        write_round_log('signal_choice', {'level': 'mid'})
    if sig_cols[2].button('Hoch'):
        st.session_state.player_signals[signaler] = 'high'
        st.session_state.phase = PH_JUDGE
        write_round_log('signal_choice', {'level': 'high'})

# Judge – Urteil
if phase == PH_JUDGE:
    judge = st.session_state.judge
    st.markdown(f"### Judge (Spieler {judge}): Urteil wählen")
    j_cols = st.columns(2)
    if j_cols[0].button('Wahrheit'):
        st.session_state.player_decisions[judge] = 'wahr'
        st.session_state.phase = PH_SHOWDOWN
        write_round_log('call_choice', {'decision': 'wahr'})
    if j_cols[1].button('Bluff'):
        st.session_state.player_decisions[judge] = 'bluff'
        st.session_state.phase = PH_SHOWDOWN
        write_round_log('call_choice', {'decision': 'bluff'})

# Showdown – Ergebnis anzeigen
if st.session_state.phase == PH_SHOWDOWN:
    outcome = compute_outcome() or {}
    st.markdown('---')
    st.subheader('Showdown')
    c1, c2, c3 = st.columns(3)
    c1.metric('Signal', {'low': 'Tief','mid': 'Mittel','high': 'Hoch'}.get(outcome.get('signal_choice'), '-'))
    c2.metric('Urteil', {'wahr': 'Wahrheit', 'bluff': 'Bluff'}.get(outcome.get('judge_choice'), '-'))
    c3.metric('Wahrheitsgehalt', 'korrekt' if outcome.get('truthful') else ('inkorrekt' if outcome.get('truthful') is False else '-'))

    w = outcome.get('winner')
    if w in (1,2):
        st.success(f"Gewinner: Spieler {w}")
    elif outcome.get('draw'):
        st.info('Unentschieden')
    else:
        st.warning('Kein Ergebnis')

    if st.session_state.score_state:
        s1 = st.session_state.score_state.get(1, '-')
        s2 = st.session_state.score_state.get(2, '-')
        st.markdown(f"**Punkte – VP1: {s1} | VP2: {s2}**")

    write_round_log('showdown')

# Fallback-Hinweise / Assets
with st.expander('Assets/Dateien prüfen'):
    missing = []
    for group, val in ASSETS.items():
        if isinstance(val, dict):
            for k, p in (val.items() if group != 'signal' and group != 'decide' else []):
                if isinstance(p, str) and not os.path.exists(p):
                    missing.append(p)
        if group == 'signal':
            for level in val.values():
                for mode_path in level.values():
                    if not os.path.exists(mode_path):
                        missing.append(mode_path)
        if group == 'decide':
            for choice in val.values():
                for mode_path in choice.values():
                    if not os.path.exists(mode_path):
                        missing.append(mode_path)
    st.write('Fehlende Dateien:', missing or 'Keine – sieht gut aus!')

st.caption('MVP-Port • Hinweis: Bilder bleiben in diesem MVP während der Phasen verdeckt und werden erst in Showdown ausgewertet. Für echtes Karten-Flip-UI wäre ein Frontend-Framework erforderlich.')
