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
from kivy.graphics import Color, Rectangle
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
import os
import itertools

# --- Display fest auf 3840x2160, Vollbild aktivierbar (kommentiere die nächste Zeile, falls du Fenster willst)
Config.set('graphics', 'fullscreen', 'auto')
Window.size = (3840, 2160)

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
        self.update_visual()

    def set_live(self, v: bool):
        self.live = v
        self.disabled = not v
        self.update_visual()

    def set_pressed_state(self):
        # nach Auswahl bleibt die live-Grafik sichtbar
        self.selected = True
        self.live = True
        self.disabled = True
        self.update_visual()

    def reset(self):
        self.selected = False
        self.live = False
        self.disabled = True
        self.update_visual()

    def update_visual(self):
        img = self.asset_pair['live'] if (self.live or self.selected) else self.asset_pair['stop']
        self.background_normal = img
        self.background_down = img
        self.opacity = 1.0 if (self.live or self.selected) else 0.6

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

    def make_ui(self):
        W, H = Window.size

        # Start-Buttons links/rechts (für beide Spieler)
        self.btn_start_p1 = IconButton(ASSETS['play'], size_hint=(None,None), size=(300,300), pos=(60, H/2-150))
        self.btn_start_p1.bind(on_release=lambda *_: self.start_pressed(1))
        self.add_widget(self.btn_start_p1)

        self.btn_start_p2 = IconButton(ASSETS['play'], size_hint=(None,None), size=(300,300), pos=(W-360, H/2-150))
        self.btn_start_p2.bind(on_release=lambda *_: self.start_pressed(2))
        self.add_widget(self.btn_start_p2)

        # Spielerzonen (je 2 Karten, links ausgerichtet)
        # Spieler 1 unten
        self.p1_outer = CardWidget(size_hint=(None,None), size=(320,480), pos=(220, 140))
        self.p1_outer.bind(on_release=lambda *_: self.tap_card(1, 'outer'))
        self.add_widget(self.p1_outer)

        self.p1_inner = CardWidget(size_hint=(None,None), size=(320,480), pos=(560, 140))
        self.p1_inner.bind(on_release=lambda *_: self.tap_card(1, 'inner'))
        self.add_widget(self.p1_inner)

        # Spieler 2 oben (gespiegelt in Position, aber gleiche Grafiken)
        self.p2_outer = CardWidget(size_hint=(None,None), size=(320,480), pos=(Window.size[0]-220-320-340, H-140-480))
        self.p2_outer.bind(on_release=lambda *_: self.tap_card(2, 'outer'))
        self.add_widget(self.p2_outer)

        self.p2_inner = CardWidget(size_hint=(None,None), size=(320,480), pos=(Window.size[0]-220-320, H-140-480))
        self.p2_inner.bind(on_release=lambda *_: self.tap_card(2, 'inner'))
        self.add_widget(self.p2_inner)

        # Button-Cluster für Signale & Entscheidungen pro Spieler
        self.signal_buttons = {1: {}, 2: {}}
        self.decision_buttons = {1: {}, 2: {}}

        # Signale Spieler 1 (unten Mitte)
        sig_positions_p1 = [(W/2-420, 60), (W/2-130, 60), (W/2+160, 60)]
        for level, pos in zip(['low','mid','high'], sig_positions_p1):
            btn = IconButton(ASSETS['signal'][level], size_hint=(None,None), size=(260,260), pos=pos)
            btn.bind(on_release=lambda _, lvl=level: self.pick_signal(1, lvl))
            self.signal_buttons[1][level] = btn
            self.add_widget(btn)

        # Signale Spieler 2 (oben Mitte)
        sig_positions_p2 = [(W/2-420, H-60-260), (W/2-130, H-60-260), (W/2+160, H-60-260)]
        for level, pos in zip(['low','mid','high'], sig_positions_p2):
            btn = IconButton(ASSETS['signal'][level], size_hint=(None,None), size=(260,260), pos=pos)
            btn.bind(on_release=lambda _, lvl=level: self.pick_signal(2, lvl))
            self.signal_buttons[2][level] = btn
            self.add_widget(btn)

        # Entscheidungen Spieler 1 (unten links vom Zentrum)
        dec_positions_p1 = [(W/2-420, 360), (W/2-130, 360)]
        for choice, pos in zip(['bluff','wahr'], dec_positions_p1):
            btn = IconButton(ASSETS['decide'][choice], size_hint=(None,None), size=(260,260), pos=pos)
            btn.bind(on_release=lambda _, ch=choice: self.pick_decision(1, ch))
            self.decision_buttons[1][choice] = btn
            self.add_widget(btn)

        # Entscheidungen Spieler 2 (oben links vom Zentrum)
        dec_positions_p2 = [(W/2+160, H-360-260), (W/2+450, H-360-260)]
        for choice, pos in zip(['bluff','wahr'], dec_positions_p2):
            btn = IconButton(ASSETS['decide'][choice], size_hint=(None,None), size=(260,260), pos=pos)
            btn.bind(on_release=lambda _, ch=choice: self.pick_decision(2, ch))
            self.decision_buttons[2][choice] = btn
            self.add_widget(btn)

        # Showdown-Karten in der Mitte
        self.center_cards = {
            1: [Image(size_hint=(None,None), size=(320,480), pos=(W/2-360, H/2-260), opacity=0),
                Image(size_hint=(None,None), size=(320,480), pos=(W/2+40,  H/2-260), opacity=0)],
            2: [Image(size_hint=(None,None), size=(320,480), pos=(W/2-360, H/2+60), opacity=0),
                Image(size_hint=(None,None), size=(320,480), pos=(W/2+40,  H/2+60), opacity=0)],
        }
        for imgs in self.center_cards.values():
            for img in imgs:
                self.add_widget(img)

        # Showdown-Label (Mitte)
        self.showdown_label = Label(text='', font_size=56, color=(1,1,1,1), size_hint=(None,None), size=(1200,180), pos=(W/2-600, H/2-120))
        self.add_widget(self.showdown_label)

        # Rundenbadge unten Mitte
        self.round_badge = Label(text='', font_size=36, color=(1,1,1,1), size_hint=(None,None), size=(1200,60), pos=(W/2-600, 10))
        self.add_widget(self.round_badge)

        # Statusanzeigen
        self.status_labels = {
            1: Label(text='', font_size=40, color=(1,1,1,1), size_hint=(None,None), size=(900,240), pos=(80, 40)),
            2: Label(text='', font_size=40, color=(1,1,1,1), size_hint=(None,None), size=(900,240), pos=(W-980, H-280)),
        }
        for label in self.status_labels.values():
            self.add_widget(label)

        # interne States
        self.p1_pressed = False
        self.p2_pressed = False
        self.player_signals = {1: None, 2: None}
        self.player_decisions = {1: None, 2: None}
        self.status_lines = {1: [], 2: []}
        self.card_cycle = itertools.cycle(['7.png', '8.png', '9.png', '10.png', '11.png'])

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
            self.showdown_label.text = ''
            for imgs in self.center_cards.values():
                for img in imgs:
                    img.opacity = 0

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
        self.showdown_label.text = ''
        for imgs in self.center_cards.values():
            for img in imgs:
                img.opacity = 0

    def update_showdown(self):
        # Karten in der Mitte anzeigen
        self.center_cards[1][0].source = self.p1_inner.front_image
        self.center_cards[1][1].source = self.p1_outer.front_image
        self.center_cards[2][0].source = self.p2_inner.front_image
        self.center_cards[2][1].source = self.p2_outer.front_image
        for imgs in self.center_cards.values():
            for img in imgs:
                img.opacity = 1
        signaler = self.signaler
        judge = self.judge
        signal_choice = self.player_signals[signaler]
        judge_choice = self.player_decisions[judge]
        summary = [f"Du bist Spieler {signaler} – Signaler", f"Deine Wahl: {self.describe_level(signal_choice) if signal_choice else '-'}", f"Anderer Spieler: {judge_choice.upper() if judge_choice else '-'}"]
        self.showdown_label.text = "\n".join(summary)

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
 