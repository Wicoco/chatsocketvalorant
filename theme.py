"""Couleurs ANSI simples pour le terminal client."""

import time

RESET = "\033[0m"
BOLD = "\033[1m"
GRAY = "\033[90m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
WHITE = "\033[97m"

ROLE_COLORS = {"admin": YELLOW, "moderator": CYAN, "user": WHITE}


def now_str():
    return time.strftime("%H:%M:%S")


def role_color(role):
    return ROLE_COLORS.get(role, WHITE)


def fmt_chat(username, role, text, room):
    return (f"{GRAY}[{now_str()}]{RESET} #{room} "
            f"{role_color(role)}{BOLD}{username}{RESET} > {text}")


def fmt_private_in(username, role, text):
    return (f"{GRAY}[{now_str()}]{RESET} {role_color(role)}(privé) {username}{RESET} "
            f"> {text}")


def fmt_private_out(target, text):
    return f"{GRAY}[{now_str()}]{RESET} (privé) vous -> {target} > {text}"


def fmt_system(text):
    return f"{YELLOW}[INFO]{RESET} {text}"


def fmt_error(text):
    return f"{RED}[ERREUR]{RESET} {text}"


def fmt_success(text):
    return f"{GREEN}[OK]{RESET} {text}"


def fmt_join(username):
    return f"{GREEN}>> {username} a rejoint.{RESET}"


def fmt_leave(username):
    return f"{GRAY}<< {username} est parti.{RESET}"


def prompt(username, role):
    return f"{role_color(role)}{BOLD}{username}{RESET} > "
