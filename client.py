import socket
import threading
import os
import time
import sys

from protocol import send_json, SocketReader
import theme
from theme import C

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER, PORT)

print_lock = threading.Lock()
state = {"username": None, "role": "user", "room": "general", "running": True}


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def reprint_line(text):
    """Affiche une ligne au dessus du prompt sans casser la saisie en cours."""
    with print_lock:
        sys.stdout.write("\r" + " " * 100 + "\r")
        print(text)
        sys.stdout.write(theme.prompt(state["username"], state["role"]))
        sys.stdout.flush()


def receiver_loop(sock):
    reader = SocketReader(sock)
    while state["running"]:
        try:
            msg = reader.read_message()
        except OSError:
            break
        if msg is None:
            reprint_line(theme.fmt_error("Connexion perdue avec le serveur."))
            state["running"] = False
            break
        if not msg:
            continue

        mtype = msg.get("type")

        if mtype == "chat":
            reprint_line(theme.fmt_chat(msg["username"], msg["role"], msg["text"], msg["room"]))

        elif mtype == "private":
            reprint_line(theme.fmt_private_in(msg["from"], msg["role"], msg["text"]))

        elif mtype == "private_ack":
            reprint_line(theme.fmt_private_out(msg["to"], msg["text"]))

        elif mtype == "system":
            reprint_line(theme.fmt_system(msg["text"]))

        elif mtype == "error":
            reprint_line(theme.fmt_error(msg["text"]))

        elif mtype == "join":
            reprint_line(theme.fmt_join(msg["username"]))

        elif mtype == "leave":
            reprint_line(theme.fmt_leave(msg["username"]))

        elif mtype == "pong":
            rtt_ms = int((time.time() - msg["ts"]) * 1000)
            reprint_line(theme.fmt_success(f"PING : {rtt_ms} ms"))

        elif mtype == "time":
            reprint_line(theme.fmt_system(f"Heure serveur : {msg['server_time']}"))

        elif mtype == "rooms":
            rooms_str = ", ".join(f"{name} ({count})" for name, count in msg["rooms"].items())
            reprint_line(theme.fmt_system(f"Salons : {rooms_str}"))

        elif mtype == "who":
            users_str = ", ".join(f"{u['username']}[{u['role']}]" for u in msg["users"])
            reprint_line(theme.fmt_system(f"Dans #{msg['room']} : {users_str}"))

        elif mtype == "registered":
            state["username"] = msg["username"]
            state["role"] = msg["role"]
            state["room"] = msg["room"]
            reprint_line(theme.fmt_success(f"Connecté en tant que {msg['username']} ({msg['role']})"))

        elif mtype == "kicked":
            reprint_line(theme.fmt_error(f"ELIMINATED : {msg['reason']}"))
            state["running"] = False

        elif mtype == "banned":
            reprint_line(theme.fmt_error(f"BANNI : {msg['reason']}"))
            state["running"] = False


HELP_TEXT = f"""{C.GOLD}{C.BOLD}=== COMMANDES DISPONIBLES ==={C.RESET}
{C.WHITE}/nick <pseudo>{C.RESET}            changer de pseudo
{C.WHITE}/msg <pseudo> <texte>{C.RESET}     message privé
{C.WHITE}/time{C.RESET}                     heure du serveur
{C.WHITE}/ping{C.RESET}                     latence
{C.WHITE}/clear{C.RESET}                    nettoyer l'écran
{C.WHITE}/join <salon>{C.RESET}             rejoindre / créer un salon
{C.WHITE}/leave{C.RESET}                    revenir au salon principal
{C.WHITE}/rooms{C.RESET}                    lister les salons
{C.WHITE}/who{C.RESET}                      lister les joueurs du salon
{C.CYAN}/kick /mute /unmute <pseudo>{C.RESET}   (modérateur+)
{C.GOLD}/ban /setmodo /setadmin /remmodo /remadmin <pseudo>{C.RESET}  (admin)
{C.WHITE}/quit{C.RESET}                     quitter la partie
"""


def send_command(sock, cmd, args):
    send_json(sock, {"type": "command", "cmd": cmd, "args": args})


def main():
    clear_screen()
    print(theme.BANNER)

    username = ""
    while not username:
        username = input(f"{C.WHITE}> Choisissez votre agent (pseudo) : {C.RESET}").strip()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(ADDR)
    except OSError:
        print(theme.fmt_error("Impossible de rejoindre le serveur."))
        return

    send_json(sock, {"type": "register", "username": username})

    t = threading.Thread(target=receiver_loop, args=(sock,), daemon=True)
    t.start()
    time.sleep(0.3)

    try:
        while state["running"]:
            try:
                text = input(theme.prompt(state["username"] or username, state["role"]))
            except (EOFError, KeyboardInterrupt):
                break

            if not text:
                continue

            if text == "/quit":
                send_json(sock, {"type": "quit"})
                break

            elif text == "/clear":
                clear_screen()
                print(theme.BANNER)
                continue

            elif text == "/help":
                print(HELP_TEXT)
                continue

            elif text == "/ping":
                send_json(sock, {"type": "ping", "ts": time.time()})
                continue

            elif text.startswith("/"):
                parts = text[1:].split(" ")
                cmd, args = parts[0], parts[1:]
                send_command(sock, cmd, args)
                continue

            send_json(sock, {"type": "chat", "text": text})

    finally:
        state["running"] = False
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        print(f"\n{C.RED}{C.BOLD}>> GG WP. Fin de la partie.{C.RESET}")


if __name__ == "__main__":
    main()
