"""Palette et textes du thème Valorant pour l'interface graphique Tkinter."""

import time

# Couleurs
BG = "#0F1923"
BG_PANEL = "#161F2B"
BG_INPUT = "#1F2933"
RED = "#FF4655"
RED_DARK = "#BD3944"
WHITE = "#ECE8E1"
GRAY = "#7A8896"
CYAN = "#4DD8E6"
GOLD = "#C89B3C"
GREEN = "#3ADE7D"
PURPLE = "#BD88F5"

FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_HEADER = ("Segoe UI", 12, "bold")
FONT_TEXT = ("Consolas", 10)
FONT_BOLD = ("Consolas", 10, "bold")

TITLE = "VALORANT - TACTICAL CHAT PROTOCOL"

ROLE_COLORS = {"admin": GOLD, "moderator": CYAN, "user": WHITE}
ROLE_LABELS = {"admin": "ADMINISTRATEUR", "moderator": "MODÉRATEUR", "user": "AGENT"}


def role_color(role):
    return ROLE_COLORS.get(role, WHITE)


def role_label(role):
    return ROLE_LABELS.get(role, "AGENT")


def now_str():
    return time.strftime("%H:%M:%S")
