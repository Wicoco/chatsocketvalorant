"""Thème visuel façon Valorant pour le terminal client (ANSI escape codes)."""

import time


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[38;5;203m"       # rouge Valorant
    DARKRED = "\033[38;5;124m"
    WHITE = "\033[97m"
    GRAY = "\033[38;5;245m"
    CYAN = "\033[38;5;80m"       # modérateur
    GOLD = "\033[38;5;220m"      # admin
    GREEN = "\033[38;5;83m"      # succès / connecté
    PURPLE = "\033[38;5;141m"    # message privé


BANNER = f"""{C.RED}{C.BOLD}
██╗   ██╗ █████╗ ██╗      ██████╗ ██████╗  █████╗ ███╗   ██╗████████╗
██║   ██║██╔══██╗██║     ██╔═══██╗██╔══██╗██╔══██╗████╗  ██║╚══██╔══╝
██║   ██║███████║██║     ██║   ██║██████╔╝███████║██╔██╗ ██║   ██║
╚██╗ ██╔╝██╔══██║██║     ██║   ██║██╔══██╗██╔══██║██║╚██╗██║   ██║
 ╚████╔╝ ██║  ██║███████╗╚██████╔╝██║  ██║██║  ██║██║ ╚████║   ██║
  ╚═══╝  ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝
{C.RESET}{C.WHITE}{C.BOLD}          T A C T I C A L   C H A T   P R O T O C O L{C.RESET}
{C.GRAY}------------------------------------------------------------------{C.RESET}
"""

ROLE_COLORS = {"admin": C.GOLD, "moderator": C.CYAN, "user": C.WHITE}
ROLE_TAGS = {"admin": "ADMIN", "moderator": "MODO", "user": "AGENT"}


def now_str():
    return time.strftime("%H:%M:%S")


def role_color(role):
    return ROLE_COLORS.get(role, C.WHITE)


def role_tag(role):
    return ROLE_TAGS.get(role, "AGENT")


def fmt_chat(username, role, text, room, ts=None):
    ts = ts or now_str()
    rc = role_color(role)
    return (f"{C.GRAY}[{ts}]{C.RESET} {C.DIM}#{room}{C.RESET} "
            f"{rc}{C.BOLD}[{role_tag(role)}] {username}{C.RESET} {C.WHITE}> {text}{C.RESET}")


def fmt_private_in(username, role, text, ts=None):
    ts = ts or now_str()
    rc = role_color(role)
    return (f"{C.GRAY}[{ts}]{C.RESET} {C.PURPLE}{C.BOLD}[MSG PRIVÉ]{C.RESET} "
            f"{rc}{username}{C.RESET} {C.PURPLE}chuchote>{C.RESET} {C.WHITE}{text}{C.RESET}")


def fmt_private_out(target, text, ts=None):
    ts = ts or now_str()
    return (f"{C.GRAY}[{ts}]{C.RESET} {C.PURPLE}{C.BOLD}[MSG PRIVÉ]{C.RESET} "
            f"{C.PURPLE}vous -> {target}{C.RESET} {C.WHITE}{text}{C.RESET}")


def fmt_system(text):
    return f"{C.GOLD}{C.BOLD}[SYSTEM]{C.RESET} {C.WHITE}{text}{C.RESET}"


def fmt_error(text):
    return f"{C.RED}{C.BOLD}[SPIKE ERROR]{C.RESET} {C.RED}{text}{C.RESET}"


def fmt_success(text):
    return f"{C.GREEN}{C.BOLD}[DEFUSED]{C.RESET} {C.GREEN}{text}{C.RESET}"


def fmt_join(username):
    return f"{C.GREEN}>> {username} a rejoint la partie.{C.RESET}"


def fmt_leave(username):
    return f"{C.DARKRED}<< {username} a quitté la partie.{C.RESET}"


def prompt(username, role):
    rc = role_color(role)
    return f"{rc}{C.BOLD}[{role_tag(role)}] {username}{C.RESET} {C.WHITE}> {C.RESET}"
