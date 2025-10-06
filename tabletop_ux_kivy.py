# tabletop_ux_kivy.py
# -------------------------------------------------------------
# Fertiges UX-Skript für deine Masterarbeit
# - 43" Tisch-Display, 3840x2160 (4K UHD)
# - Vollbild, Hintergrundfarbe #BFBFBF
# - Ordnerstruktur exakt wie in deinen Screenshots:
#     ./UX/  -> play_*.png, hoch_*.png, mittel_*.png, tief_*.png, bluff_*.png, wahr_*.png
#     ./Karten/ -> back.png, back_stop.png  (Kartenwerte optional)
# - Ablauf exakt nach Beschreibung inkl. Rollenwechsel pro Runde
# - Beide Karten pro Spieler werden im Ablauf aufgedeckt (erst innere, dann äußere)
# - Buttons sind nur „live“, wenn *_live.png verwendet wird; sonst *_stop.png
# - Keine Anpassungen nötig, einfach `python tabletop_ux_kivy.py` starten.
# -------------------------------------------------------------

from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Rotate
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
import os
import itertools

# --- Display fest auf 3840x2160, Vollbild aktivierbar (kommentiere die nächste Zeile, falls du Fenster willst)
Config.set('graphics', 'fullscreen', 'auto')

# --- Konstanten & Assets
ROOT = os.path.dirname(os.path.abspath(__file__))
UX_DIR = os.path.join(ROOT, 'UX')
CARD_DIR = os.path.join(ROOT, 'Karten')

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

# --- Phasen der Runde
PH_WAIT_BOTH_START = 'WAIT_BOTH_START'
PH_P1_INNER = 'P1_INNER'
PH_P2_INNER = 'P2_INNER'
PH_P1_OUTER = 'P1_OUTER'
PH_P2_OUTER = 'P2_OUTER'
PH_SIGNALER = 'SIGNALER'
PH_JUDGE = 'JUDGE'
PH_SHOWDOWN = 'SHOWDOWN'

class CardWidget(Button):
    """Karten-Slot: zeigt back_stop bis aktiv und/oder aufgedeckt."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.live = False
        self.face_up = False
        self.front_image = ASSETS['cards']['back']
        self.border = (0, 0, 0, 0)
        self.background_normal = ASSETS['cards']['back_stop']
        self.background_down = ASSETS['cards']['back_stop']
        self.background_disabled_normal = ASSETS['cards']['back_stop']
        self.background_disabled_down = ASSETS['cards']['back_stop']
        self.disabled_color = (1,1,1,1)
        self.update_visual()

    def set_live(self, v: bool):
        self.live = v
        self.disabled = not v
        self.update_visual()

    def flip(self):
        if not self.live:
            return
        self.face_up = True
        self.set_live(False)

    def reset(self):
        self.live = False
        self.face_up = False
        self.disabled = True
        self.update_visual()

    def set_front(self, img_path: str):
        self.front_image = img_path
        if not os.path.exists(img_path):
            self.front_image = ASSETS['cards']['back']
        self.update_visual()

    def update_visual(self):
        if self.face_up:
            img = self.front_image
        elif self.live:
            img = ASSETS['cards']['back']
        else:
            img = ASSETS['cards']['back_stop']
        self.background_normal = img
        self.background_down = img
        self.background_disabled_normal = img
        self.background_disabled_down = img
        self.opacity = 1.0 if (self.live or self.face_up) else 0.55

class IconButton(Button):
    """Button, der automatisch live/stop-Grafiken nutzt."""
    def __init__(self, asset_pair: dict, label_text: str = '', **kw):
        super().__init__(**kw)
        self.asset_pair = asset_pair
        self.live = False
        self.selected = False
        self.border = (0, 0, 0, 0)
        self.background_normal = asset_pair['stop']
        self.background_down = asset_pair['stop']
        self.background_disabled_normal = asset_pair['stop']
        self.disabled_color = (1,1,1,1)
        self.text = ''  # wir nutzen die Grafik
        self.rotation_angle = 0
        with self.canvas.before:
            self._push_matrix = PushMatrix()
            self._rotation = Rotate(angle=0, origin=self.center)
        with self.canvas.after:
            self._pop_matrix = PopMatrix()
        self.bind(pos=self._update_transform, size=self._update_transform)
        self.update_visual()

    def set_live(self, v: bool):
        self.live = v
        self.disabled = not v
        self.update_visual()

    def set_pressed_state(self):
        # nach Auswahl bleibt die live-Grafik sichtbar, ohne dass der Button live bleibt
        self.selected = True
        self.live = False
        self.disabled = True
        self.update_visual()

    def reset(self):
        self.selected = False
        self.live = False
        self.disabled = True
        self.update_visual()

    def set_rotation(self, angle: float):
        self.rotation_angle = angle
        self._update_transform()

    def _update_transform(self, *args):
        if hasattr(self, '_rotation'):
            self._rotation.origin = self.center
            self._rotation.angle = self.rotation_angle

    def update_visual(self):
        img = self.asset_pair['live'] if (self.live or self.selected) else self.asset_pair['stop']
        self.background_normal = img
        self.background_down = img
        self.opacity = 1.0 if (self.live or self.selected) else 0.6


class RotatedLabel(Label):
    """Label mit Rotationsunterstützung (für gespiegelte Anzeige)."""
    def __init__(self, angle: float = 0, **kwargs):
        self.rotation_angle = angle
        super().__init__(**kwargs)
        with self.canvas.before:
            self._push_matrix = PushMatrix()
            self._rotation = Rotate(angle=self.rotation_angle, origin=self.center)
        with self.canvas.after:
            self._pop_matrix = PopMatrix()
        self.bind(pos=self._update_transform, size=self._update_transform)

    def set_rotation(self, angle: float):
        self.rotation_angle = angle
        self._update_transform()

    def _update_transform(self, *args):
        if hasattr(self, '_rotation'):
            self._rotation.origin = self.center
            self._rotation.angle = self.rotation_angle

class TabletopRoot(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(0.75, 0.75, 0.75, 1)  # #BFBFBF
            self.bg = Rectangle(pos=(0,0), size=Window.size)
        Window.bind(on_resize=self.on_resize)

        self.round = 1
        self.signaler = 1
        self.judge = 2
        self.phase = PH_WAIT_BOTH_START

        # --- UI Elemente platzieren
        self.make_ui()
        self.setup_round()
        self.apply_phase()

    # --- Layout & Elemente
    def on_resize(self, *_):
        self.bg.size = Window.size
        self.update_layout()

    def make_ui(self):
        # Start-Buttons links/rechts (für beide Spieler)
        self.btn_start_p1 = IconButton(
            ASSETS['play'],
            size_hint=(None, None),
        )
        self.btn_start_p1.bind(on_release=lambda *_: self.start_pressed(1))
        self.add_widget(self.btn_start_p1)

        self.btn_start_p2 = IconButton(
            ASSETS['play'],
            size_hint=(None, None),
        )
        self.btn_start_p2.bind(on_release=lambda *_: self.start_pressed(2))
        self.add_widget(self.btn_start_p2)

        # Ergebnis-Labels oben/unten (oben gespiegelt)
        self.info_labels = {
            'bottom': RotatedLabel(
                color=(1, 1, 1, 1),
                size_hint=(None, None),
                halign='center',
                valign='middle'
            ),
            'top': RotatedLabel(
                angle=180,
                color=(1, 1, 1, 1),
                size_hint=(None, None),
                halign='center',
                valign='middle'
            )
        }
        for lbl in self.info_labels.values():
            self.add_widget(lbl)

        # Spielerzonen (je 2 Karten in den Ecken)
        self.p1_outer = CardWidget(size_hint=(None, None))
        self.p1_outer.bind(on_release=lambda *_: self.tap_card(1, 'outer'))
        self.add_widget(self.p1_outer)

        self.p1_inner = CardWidget(size_hint=(None, None))
        self.p1_inner.bind(on_release=lambda *_: self.tap_card(1, 'inner'))
        self.add_widget(self.p1_inner)

        self.p2_outer = CardWidget(size_hint=(None, None))
        self.p2_outer.bind(on_release=lambda *_: self.tap_card(2, 'outer'))
        self.add_widget(self.p2_outer)

        self.p2_inner = CardWidget(size_hint=(None, None))
        self.p2_inner.bind(on_release=lambda *_: self.tap_card(2, 'inner'))
        self.add_widget(self.p2_inner)

        # Button-Cluster für Signale & Entscheidungen pro Spieler
        self.signal_buttons = {1: {}, 2: {}}
        self.decision_buttons = {1: {}, 2: {}}

        for level in ['low', 'mid', 'high']:
            btn = IconButton(ASSETS['signal'][level], size_hint=(None, None))
            btn.bind(on_release=lambda _, lvl=level: self.pick_signal(1, lvl))
            self.signal_buttons[1][level] = btn
            self.add_widget(btn)

        for choice in ['bluff', 'wahr']:
            btn = IconButton(ASSETS['decide'][choice], size_hint=(None, None))
            btn.bind(on_release=lambda _, ch=choice: self.pick_decision(1, ch))
            self.decision_buttons[1][choice] = btn
            self.add_widget(btn)

        for level in ['low', 'mid', 'high']:
            btn = IconButton(ASSETS['signal'][level], size_hint=(None, None))
            btn.bind(on_release=lambda _, lvl=level: self.pick_signal(2, lvl))
            self.signal_buttons[2][level] = btn
            self.add_widget(btn)

        for choice in ['bluff', 'wahr']:
            btn = IconButton(ASSETS['decide'][choice], size_hint=(None, None))
            btn.bind(on_release=lambda _, ch=choice: self.pick_decision(2, ch))
            self.decision_buttons[2][choice] = btn
            self.add_widget(btn)

        # Showdown-Karten in der Mitte (immer sichtbar, zuerst verdeckt)
        self.center_cards = {
            1: [Image(size_hint=(None, None), allow_stretch=True, keep_ratio=True),
                Image(size_hint=(None, None), allow_stretch=True, keep_ratio=True)],
            2: [Image(size_hint=(None, None), allow_stretch=True, keep_ratio=True),
                Image(size_hint=(None, None), allow_stretch=True, keep_ratio=True)],
        }
        for imgs in self.center_cards.values():
            for img in imgs:
                self.add_widget(img)

        # Rundenbadge unten Mitte
        self.round_badge = Label(
            text='',
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            halign='center',
            valign='middle'
        )
        self.add_widget(self.round_badge)

        # interne States
        self.p1_pressed = False
        self.p2_pressed = False
        self.player_signals = {1: None, 2: None}
        self.player_decisions = {1: None, 2: None}
        self.status_lines = {1: [], 2: []}
        self.status_labels = {1: None, 2: None}
        self.last_outcome = {
            'winner': None,
            'truthful': None,
            'actual_level': None,
            'signal_choice': None,
            'judge_choice': None
        }
        self.card_cycle = itertools.cycle(['7.png', '8.png', '9.png', '10.png', '11.png'])

        self.update_layout()

    def update_layout(self):
        W, H = Window.size
        base_w, base_h = 3840.0, 2160.0
        scale = min(W / base_w if base_w else 1, H / base_h if base_h else 1)

        self.bg.pos = (0, 0)
        self.bg.size = (W, H)

        corner_margin = 120 * scale
        card_width, card_height = 420 * scale, 640 * scale
        card_gap = 70 * scale
        start_size = (360 * scale, 360 * scale)

        # Start buttons
        self.btn_start_p1.size = start_size
        start_margin = 60 * scale
        self.btn_start_p1.pos = (start_margin, start_margin)
        self.btn_start_p1.set_rotation(0)

        self.btn_start_p2.size = start_size
        self.btn_start_p2.pos = (W - start_margin - start_size[0], H - start_margin - start_size[1])
        self.btn_start_p2.set_rotation(180)

        # Cards positions
        p1_outer_pos = (corner_margin, corner_margin)
        p1_inner_pos = (corner_margin + card_width + card_gap, corner_margin)
        self.p1_outer.size = (card_width, card_height)
        self.p1_outer.pos = p1_outer_pos
        self.p1_inner.size = (card_width, card_height)
        self.p1_inner.pos = p1_inner_pos

        p2_outer_pos = (W - corner_margin - card_width, H - corner_margin - card_height)
        p2_inner_pos = (p2_outer_pos[0] - card_width - card_gap, p2_outer_pos[1])
        self.p2_outer.size = (card_width, card_height)
        self.p2_outer.pos = p2_outer_pos
        self.p2_inner.size = (card_width, card_height)
        self.p2_inner.pos = p2_inner_pos

        # Button stacks
        btn_width, btn_height = 260 * scale, 260 * scale
        vertical_gap = 40 * scale
        horizontal_gap = 60 * scale
        cluster_shift = 360 * scale

        # Player 1 (bottom right)
        signal_x = W - corner_margin - btn_width - cluster_shift
        base_y = corner_margin
        for idx, level in enumerate(['low', 'mid', 'high']):
            btn = self.signal_buttons[1][level]
            btn.size = (btn_width, btn_height)
            btn.pos = (signal_x, base_y + idx * (btn_height + vertical_gap))
            btn.set_rotation(0)

        decision_x = signal_x - horizontal_gap - btn_width
        for idx, choice in enumerate(['bluff', 'wahr']):
            btn = self.decision_buttons[1][choice]
            btn.size = (btn_width, btn_height)
            btn.pos = (decision_x, base_y + idx * (btn_height + vertical_gap))
            btn.set_rotation(0)

        # Player 2 (top left)
        signal2_x = corner_margin + cluster_shift
        top_y = H - corner_margin
        for idx, level in enumerate(['low', 'mid', 'high']):
            btn = self.signal_buttons[2][level]
            btn.size = (btn_width, btn_height)
            btn.pos = (signal2_x, top_y - btn_height - idx * (btn_height + vertical_gap))
            btn.set_rotation(180)

        decision2_x = signal2_x + btn_width + horizontal_gap
        for idx, choice in enumerate(['bluff', 'wahr']):
            btn = self.decision_buttons[2][choice]
            btn.size = (btn_width, btn_height)
            btn.pos = (decision2_x, top_y - btn_height - idx * (btn_height + vertical_gap))
            btn.set_rotation(180)

        # Center cards
        center_card_width, center_card_height = 380 * scale, 560 * scale
        center_gap_x = 90 * scale
        center_gap_y = 60 * scale
        left_x = W / 2 - center_card_width - center_gap_x / 2
        right_x = W / 2 + center_gap_x / 2
        bottom_y = H / 2 - center_card_height - center_gap_y / 2
        top_y_center = H / 2 + center_gap_y / 2

        for idx, img in enumerate(self.center_cards[1]):
            img.size = (center_card_width, center_card_height)
        self.center_cards[1][0].pos = (right_x, bottom_y)
        self.center_cards[1][1].pos = (left_x, bottom_y)

        for idx, img in enumerate(self.center_cards[2]):
            img.size = (center_card_width, center_card_height)
        self.center_cards[2][0].pos = (left_x, top_y_center)
        self.center_cards[2][1].pos = (right_x, top_y_center)

        # Info labels
        info_width, info_height = 2000 * scale, 160 * scale
        info_margin = 60 * scale

        bottom_label = self.info_labels['bottom']
        bottom_label.size = (info_width, info_height)
        bottom_label.font_size = 56 * scale if scale else 56
        bottom_label.pos = (W / 2 - info_width / 2, bottom_y - info_height - info_margin)
        bottom_label.text_size = (info_width, info_height)
        bottom_label.set_rotation(0)

        top_label = self.info_labels['top']
        top_label.size = (info_width, info_height)
        top_label.font_size = 56 * scale if scale else 56
        top_label.pos = (W / 2 - info_width / 2, top_y_center + center_card_height + info_margin)
        top_label.text_size = (info_width, info_height)
        top_label.set_rotation(180)

        # Round badge
        badge_width, badge_height = 1400 * scale, 70 * scale
        self.round_badge.size = (badge_width, badge_height)
        self.round_badge.font_size = 40 * scale if scale else 40
        self.round_badge.pos = (W / 2 - badge_width / 2, corner_margin / 2)
        self.round_badge.text_size = (badge_width, badge_height)

        # Refresh transforms after layout changes
        for buttons in self.signal_buttons.values():
            for btn in buttons.values():
                btn._update_transform()
        for buttons in self.decision_buttons.values():
            for btn in buttons.values():
                btn._update_transform()
        self.btn_start_p1._update_transform()
        self.btn_start_p2._update_transform()
        for lbl in self.info_labels.values():
            lbl._update_transform()

    # --- Logik
    def apply_phase(self):
        # Alles zunächst deaktivieren
        for c in (self.p1_outer, self.p1_inner, self.p2_outer, self.p2_inner):
            c.set_live(False)
        for buttons in self.signal_buttons.values():
            for b in buttons.values():
                b.set_live(False)
        for buttons in self.decision_buttons.values():
            for b in buttons.values():
                b.set_live(False)

        # Showdown zurücksetzen
        if self.phase != PH_SHOWDOWN:
            self.refresh_center_cards(reveal=False)

        # Startbuttons
        start_active = (self.phase in (PH_WAIT_BOTH_START, PH_SHOWDOWN))
        self.btn_start_p1.set_live(start_active)
        self.btn_start_p2.set_live(start_active)

        # Phasen-spezifisch
        if self.phase == PH_P1_INNER:
            self.p1_inner.set_live(True)
        elif self.phase == PH_P2_INNER:
            self.p2_inner.set_live(True)
        elif self.phase == PH_P1_OUTER:
            self.p1_outer.set_live(True)
        elif self.phase == PH_P2_OUTER:
            self.p2_outer.set_live(True)
        elif self.phase == PH_SIGNALER:
            signaler = self.signaler
            for btn in self.signal_buttons[signaler].values():
                btn.set_live(True)
        elif self.phase == PH_JUDGE:
            judge = self.judge
            for btn in self.decision_buttons[judge].values():
                btn.set_live(True)
        elif self.phase == PH_SHOWDOWN:
            self.btn_start_p1.set_live(True)
            self.btn_start_p2.set_live(True)
            self.update_showdown()

        # Badge unten
        role_txt = f"P1: {'Signal' if self.signaler==1 else 'Judge'} · P2: {'Signal' if self.signaler==2 else 'Judge'}"
        self.round_badge.text = f"Runde {self.round} · {role_txt}"
        self.update_info_labels()

    def start_pressed(self, who:int):
        if self.phase not in (PH_WAIT_BOTH_START, PH_SHOWDOWN):
            return
        if who == 1:
            self.p1_pressed = True
        else:
            self.p2_pressed = True
        self.record_action(who, 'Play gedrückt')
        if self.p1_pressed and self.p2_pressed:
            # in nächste Phase
            self.p1_pressed = False
            self.p2_pressed = False
            if self.phase == PH_SHOWDOWN:
                self.prepare_next_round(start_immediately=True)
            else:
                self.phase = PH_P1_INNER
                self.apply_phase()

    def tap_card(self, who:int, which:str):
        # which in {'inner','outer'}
        if who == 1 and which == 'inner' and self.phase == PH_P1_INNER:
            self.p1_inner.flip()
            self.record_action(1, 'Karte innen aufgedeckt')
            Clock.schedule_once(lambda *_: self.goto(PH_P2_INNER), 0.2)
        elif who == 2 and which == 'inner' and self.phase == PH_P2_INNER:
            self.p2_inner.flip()
            self.record_action(2, 'Karte innen aufgedeckt')
            Clock.schedule_once(lambda *_: self.goto(PH_P1_OUTER), 0.2)
        elif who == 1 and which == 'outer' and self.phase == PH_P1_OUTER:
            self.p1_outer.flip()
            self.record_action(1, 'Karte außen aufgedeckt')
            Clock.schedule_once(lambda *_: self.goto(PH_P2_OUTER), 0.2)
        elif who == 2 and which == 'outer' and self.phase == PH_P2_OUTER:
            self.p2_outer.flip()
            self.record_action(2, 'Karte außen aufgedeckt')
            Clock.schedule_once(lambda *_: self.goto(PH_SIGNALER), 0.2)

    def pick_signal(self, player:int, level:str):
        if self.phase != PH_SIGNALER or player != self.signaler:
            return
        self.player_signals[player] = level
        # fixiere Auswahl optisch (Button bleibt live)
        for lvl, btn in self.signal_buttons[player].items():
            if lvl == level:
                btn.set_pressed_state()
            else:
                btn.set_live(False)
                btn.disabled = True
        self.record_action(player, f'Signal gewählt: {self.describe_level(level)}')
        self.update_info_labels()
        Clock.schedule_once(lambda *_: self.goto(PH_JUDGE), 0.2)

    def pick_decision(self, player:int, decision:str):
        if self.phase != PH_JUDGE or player != self.judge:
            return
        self.player_decisions[player] = decision
        for choice, btn in self.decision_buttons[player].items():
            if choice == decision:
                btn.set_pressed_state()
            else:
                btn.set_live(False)
                btn.disabled = True
        self.record_action(player, f'Entscheidung: {decision.upper()}')
        self.update_info_labels()
        Clock.schedule_once(lambda *_: self.goto(PH_SHOWDOWN), 0.2)

    def goto(self, phase):
        self.phase = phase
        self.apply_phase()

    def prepare_next_round(self, start_immediately: bool = False):
        # Rollen tauschen
        self.signaler, self.judge = self.judge, self.signaler
        self.round += 1
        self.setup_round()
        if start_immediately:
            self.phase = PH_P1_INNER
        else:
            self.phase = PH_WAIT_BOTH_START
        self.apply_phase()

    def setup_round(self):
        # neue Karten ziehen
        next_cards = [next(self.card_cycle) for _ in range(4)]
        paths = [os.path.join(CARD_DIR, name) for name in next_cards]
        self.p1_inner.set_front(paths[0])
        self.p2_inner.set_front(paths[1])
        self.p1_outer.set_front(paths[2])
        self.p2_outer.set_front(paths[3])
        for c in (self.p1_inner, self.p1_outer, self.p2_inner, self.p2_outer):
            c.reset()
        # Reset Buttons
        for buttons in self.signal_buttons.values():
            for btn in buttons.values():
                btn.reset()
        for buttons in self.decision_buttons.values():
            for btn in buttons.values():
                btn.reset()
        # Reset Status
        self.player_signals = {1: None, 2: None}
        self.player_decisions = {1: None, 2: None}
        self.status_lines = {1: [], 2: []}
        self.update_status_label(1)
        self.update_status_label(2)
        # Showdown Elements
        self.last_outcome = {
            'winner': None,
            'truthful': None,
            'actual_level': None,
            'signal_choice': None,
            'judge_choice': None
        }
        self.refresh_center_cards(reveal=False)
        self.update_info_labels()

    def refresh_center_cards(self, reveal: bool):
        if reveal:
            sources = {
                1: [self.p1_inner.front_image, self.p1_outer.front_image],
                2: [self.p2_inner.front_image, self.p2_outer.front_image],
            }
        else:
            back = ASSETS['cards']['back']
            sources = {1: [back, back], 2: [back, back]}

        for player, imgs in self.center_cards.items():
            for idx, img in enumerate(imgs):
                img.source = sources[player][idx]
                img.opacity = 1

    def update_showdown(self):
        # Karten in der Mitte anzeigen
        self.refresh_center_cards(reveal=True)
        self.compute_outcome()
        self.update_info_labels()

    def card_value_from_path(self, path: str):
        if not path:
            return None
        name = os.path.basename(path)
        digits = ''.join(ch for ch in name if ch.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except ValueError:
            return None

    def determine_signal_level(self, player: int):
        if player == 1:
            inner_widget, outer_widget = self.p1_inner, self.p1_outer
        else:
            inner_widget, outer_widget = self.p2_inner, self.p2_outer
        inner_val = self.card_value_from_path(inner_widget.front_image)
        outer_val = self.card_value_from_path(outer_widget.front_image)
        if inner_val is None or outer_val is None:
            return None
        total = inner_val + outer_val
        if total == 19:
            return 'high'
        if total in (16, 17, 18):
            return 'mid'
        if total in (14, 15):
            return 'low'
        return None

    def compute_outcome(self):
        signaler = self.signaler
        judge = self.judge
        signal_choice = self.player_signals.get(signaler)
        judge_choice = self.player_decisions.get(judge)
        actual_level = self.determine_signal_level(signaler)

        truthful = None
        if signal_choice and actual_level:
            truthful = (signal_choice == actual_level)

        winner = None
        if judge_choice and truthful is not None:
            if judge_choice == 'wahr':
                winner = judge if truthful else signaler
            elif judge_choice == 'bluff':
                winner = judge if not truthful else signaler

        self.last_outcome = {
            'winner': winner,
            'truthful': truthful,
            'actual_level': actual_level,
            'signal_choice': signal_choice,
            'judge_choice': judge_choice
        }
        return self.last_outcome

    def describe_player_choice(self, player: int) -> str:
        signal = self.player_signals.get(player)
        decision = self.player_decisions.get(player)
        if signal:
            return self.describe_level(signal)
        if decision:
            mapping = {'wahr': 'WAHR', 'bluff': 'BLUFF'}
            return mapping.get(decision, decision.upper())
        return '-'

    def result_text(self, player: int) -> str:
        winner = self.last_outcome.get('winner') if self.last_outcome else None
        if winner is None:
            return '-'
        if winner == player:
            return 'Gewonnen'
        return 'Verloren'

    def update_info_labels(self):
        self.compute_outcome()
        choice_p1 = self.describe_player_choice(1)
        choice_p2 = self.describe_player_choice(2)
        bottom_lines = [
            'Du bist Spieler 1',
            f'Wahl Spieler 1: {choice_p1}',
            f'Wahl Spieler 2: {choice_p2}',
            f'Ergebnis: {self.result_text(1)}'
        ]
        top_lines = [
            'Du bist Spieler 2',
            f'Wahl Spieler 1: {choice_p1}',
            f'Wahl Spieler 2: {choice_p2}',
            f'Ergebnis: {self.result_text(2)}'
        ]
        self.info_labels['bottom'].text = "\n".join(bottom_lines)
        self.info_labels['top'].text = "\n".join(top_lines)

    def describe_level(self, level:str) -> str:
        mapping = {
            'low': 'Tief',
            'mid': 'Mittel',
            'high': 'Hoch',
            None: '-',
        }
        return mapping.get(level, level)

    def record_action(self, player:int, text:str):
        self.status_lines[player].append(text)
        self.update_status_label(player)

    def update_status_label(self, player:int):
        label = self.status_labels.get(player)
        if not label:
            return
        role = 'Signal' if self.signaler == player else 'Judge'
        header = [f"Du bist Spieler {player}", f"Rolle: {role}"]
        body = self.status_lines[player]
        self.status_labels[player].text = "\n".join(header + body)

class TabletopApp(App):
    def build(self):
        self.title = 'Masterarbeit – Tabletop UX'
        root = TabletopRoot()
        return root

if __name__ == '__main__':
    TabletopApp().run()
 