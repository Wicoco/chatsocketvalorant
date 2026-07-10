import socket
import threading
import os
import json
import time

from protocol import send_json, SocketReader

SERVER = socket.gethostbyname(socket.gethostname())
PORT = 5000
ADDR = (SERVER, PORT)

USER_DB_FILE = "user_data.json"

IDLE_CHECK_INTERVAL = 30      # granularité du recv timeout (s)
MAX_IDLE_TIME = 180           # déconnexion auto après ce temps d'inactivité (s)
DEFAULT_MUTE_DURATION = 60
MAX_MESSAGE_LEN = 500
DEFAULT_ROOM = "general"

ROLE_LEVELS = {"user": 0, "moderator": 1, "admin": 2}

# ---- état partagé ----
clients_lock = threading.Lock()
json_lock = threading.Lock()

# conn -> {"username","role","room","addr","muted_until","last_active"}
clients = {}
# room_name -> set(conn)
rooms = {DEFAULT_ROOM: set()}


# ---------------------------------------------------------------------------
# Persistance des comptes (rôles, bans)
# ---------------------------------------------------------------------------

def load_users():
    with json_lock:
        if not os.path.exists(USER_DB_FILE):
            return {}
        try:
            with open(USER_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}


def save_users(users):
    with json_lock:
        with open(USER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)


def get_or_create_user(username):
    users = load_users()
    if username not in users:
        is_first_user = len(users) == 0
        users[username] = {
            "role": "admin" if is_first_user else "user",
            "banned": False,
        }
        save_users(users)
    return users[username]


def set_user_role(username, role):
    users = load_users()
    if username in users:
        users[username]["role"] = role
        save_users(users)


def set_user_banned(username, banned=True):
    users = load_users()
    if username in users:
        users[username]["banned"] = banned
        save_users(users)


# ---------------------------------------------------------------------------
# Helpers réseau
# ---------------------------------------------------------------------------

def safe_send(conn, payload):
    try:
        send_json(conn, payload)
    except OSError:
        pass


def system(conn, text):
    safe_send(conn, {"type": "system", "text": text})


def error(conn, text):
    safe_send(conn, {"type": "error", "text": text})


def broadcast(room, payload, exclude=None):
    with clients_lock:
        targets = list(rooms.get(room, set()))
    for c in targets:
        if c is exclude:
            continue
        safe_send(c, payload)


def find_conn_by_username(username):
    with clients_lock:
        for c, info in clients.items():
            if info["username"].lower() == username.lower():
                return c, info
    return None, None


def sanitize_text(text, max_len=MAX_MESSAGE_LEN):
    text = "".join(ch for ch in text if ch.isprintable() or ch == " ")
    return text.strip()[:max_len]


def is_valid_username(name):
    if not (3 <= len(name) <= 16):
        return False
    return all(ch.isalnum() or ch in "_-" for ch in name)


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def has_role(info, min_role):
    return ROLE_LEVELS[info["role"]] >= ROLE_LEVELS[min_role]


def resolve_target(conn, info, username):
    target_conn, target_info = find_conn_by_username(username)
    if target_conn is None:
        error(conn, f"Utilisateur '{username}' introuvable ou hors ligne.")
        return None, None
    if target_conn is not conn and ROLE_LEVELS[target_info["role"]] >= ROLE_LEVELS[info["role"]]:
        error(conn, "Vous ne pouvez pas cibler un rôle égal ou supérieur au vôtre.")
        return None, None
    return target_conn, target_info


def cmd_nickname(conn, info, args):
    if not args:
        error(conn, "Usage: /nickname <nouveau_pseudo>")
        return
    new_name = args[0]
    if not is_valid_username(new_name):
        error(conn, "Pseudo invalide (3-16 caractères, lettres/chiffres/_/-).")
        return
    existing_conn, _ = find_conn_by_username(new_name)
    if existing_conn is not None:
        error(conn, "Ce pseudo est déjà utilisé.")
        return

    users = load_users()
    old_name = info["username"]
    if old_name in users:
        users[new_name] = users.pop(old_name)
        save_users(users)
    else:
        get_or_create_user(new_name)

    with clients_lock:
        info["username"] = new_name
    system(conn, f"Pseudo changé : {old_name} -> {new_name}")
    broadcast(info["room"], {"type": "system", "text": f"{old_name} est maintenant {new_name}"}, exclude=conn)


def cmd_message(conn, info, args):
    if len(args) < 2:
        error(conn, "Usage: /message <pseudo> <message>")
        return
    target_name, text = args[0], " ".join(args[1:])
    text = sanitize_text(text)
    if not text:
        return
    target_conn, target_info = find_conn_by_username(target_name)
    if target_conn is None:
        error(conn, f"Utilisateur '{target_name}' introuvable ou hors ligne.")
        return
    safe_send(target_conn, {
        "type": "private", "from": info["username"], "role": info["role"], "text": text,
    })
    safe_send(conn, {"type": "private_ack", "to": target_info["username"], "text": text})


def cmd_time(conn, info, args):
    safe_send(conn, {"type": "time", "server_time": time.strftime("%Y-%m-%d %H:%M:%S")})


def cmd_rooms(conn, info, args):
    with clients_lock:
        snapshot = {name: len(members) for name, members in rooms.items()}
    safe_send(conn, {"type": "rooms", "rooms": snapshot})


def cmd_who(conn, info, args):
    room = info["room"]
    with clients_lock:
        users_list = [{"username": i["username"], "role": i["role"]}
                      for c, i in clients.items() if i["room"] == room]
    safe_send(conn, {"type": "who", "room": room, "users": users_list})


def cmd_join(conn, info, args):
    if not args:
        error(conn, "Usage: /join <salon>")
        return
    room_name = sanitize_text(args[0], 24)
    if not room_name:
        error(conn, "Nom de salon invalide.")
        return
    old_room = info["room"]
    with clients_lock:
        rooms[old_room].discard(conn)
        rooms.setdefault(room_name, set()).add(conn)
        info["room"] = room_name
    broadcast(old_room, {"type": "system", "text": f"{info['username']} a quitté le salon."})
    broadcast(room_name, {"type": "system", "text": f"{info['username']} a rejoint le salon."}, exclude=conn)
    safe_send(conn, {"type": "room_changed", "room": room_name})
    system(conn, f"Vous avez rejoint le salon '{room_name}'.")


def cmd_leave(conn, info, args):
    if info["room"] == DEFAULT_ROOM:
        error(conn, "Vous êtes déjà dans le salon principal.")
        return
    cmd_join(conn, info, [DEFAULT_ROOM])


def cmd_kick(conn, info, args):
    if not has_role(info, "moderator"):
        error(conn, "Permission refusée.")
        return
    if not args:
        error(conn, "Usage: /kick <pseudo>")
        return
    target_conn, target_info = resolve_target(conn, info, args[0])
    if target_conn is None:
        return
    safe_send(target_conn, {"type": "kicked", "reason": f"Expulsé par {info['username']}"})
    system(conn, f"{target_info['username']} a été expulsé.")
    try:
        target_conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    target_conn.close()


def cmd_ban(conn, info, args):
    if not has_role(info, "admin"):
        error(conn, "Permission refusée.")
        return
    if not args:
        error(conn, "Usage: /ban <pseudo>")
        return
    target_conn, target_info = resolve_target(conn, info, args[0])
    if target_conn is None:
        return
    set_user_banned(target_info["username"], True)
    safe_send(target_conn, {"type": "banned", "reason": f"Banni par {info['username']}"})
    system(conn, f"{target_info['username']} a été banni.")
    try:
        target_conn.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    target_conn.close()


def cmd_mute(conn, info, args):
    if not has_role(info, "moderator"):
        error(conn, "Permission refusée.")
        return
    if not args:
        error(conn, "Usage: /mute <pseudo> [secondes]")
        return
    duration = DEFAULT_MUTE_DURATION
    if len(args) > 1 and args[1].isdigit():
        duration = int(args[1])
    target_conn, target_info = resolve_target(conn, info, args[0])
    if target_conn is None:
        return
    with clients_lock:
        target_info["muted_until"] = time.time() + duration
    system(conn, f"{target_info['username']} rendu muet pendant {duration}s.")
    system(target_conn, f"Vous êtes muet pendant {duration}s.")


def cmd_unmute(conn, info, args):
    if not has_role(info, "moderator"):
        error(conn, "Permission refusée.")
        return
    if not args:
        error(conn, "Usage: /unmute <pseudo>")
        return
    target_conn, target_info = resolve_target(conn, info, args[0])
    if target_conn is None:
        return
    with clients_lock:
        target_info["muted_until"] = None
    system(conn, f"{target_info['username']} peut de nouveau parler.")
    system(target_conn, "Vous pouvez de nouveau parler.")


def cmd_setrole(conn, info, args, role, label):
    if not has_role(info, "admin"):
        error(conn, "Permission refusée.")
        return
    if not args:
        error(conn, f"Usage: /{label} <pseudo>")
        return
    target_conn, target_info = resolve_target(conn, info, args[0])
    if target_conn is None:
        return
    with clients_lock:
        target_info["role"] = role
    set_user_role(target_info["username"], role)
    system(conn, f"{target_info['username']} est maintenant {role}.")
    system(target_conn, f"Vous êtes maintenant {role}.")
    safe_send(target_conn, {"type": "role_changed", "role": role})


COMMANDS = {
    "nickname": cmd_nickname,
    "message": cmd_message,
    "time": cmd_time,
    "rooms": cmd_rooms,
    "who": cmd_who,
    "join": cmd_join,
    "leave": cmd_leave,
    "kick": cmd_kick,
    "ban": cmd_ban,
    "mute": cmd_mute,
    "unmute": cmd_unmute,
    "set_moderator": lambda c, i, a: cmd_setrole(c, i, a, "moderator", "set_moderator"),
    "set_administrator": lambda c, i, a: cmd_setrole(c, i, a, "admin", "set_administrator"),
    "remove_moderator": lambda c, i, a: cmd_setrole(c, i, a, "user", "remove_moderator"),
    "remove_administrator": lambda c, i, a: cmd_setrole(c, i, a, "user", "remove_administrator"),
}


# ---------------------------------------------------------------------------
# Boucle client
# ---------------------------------------------------------------------------

def register_client(conn, addr):
    reader = SocketReader(conn)
    msg = reader.read_message()
    if not msg or msg.get("type") != "register":
        return None, None, None

    username = sanitize_text(msg.get("username", ""), 16)
    if not is_valid_username(username):
        safe_send(conn, {"type": "error", "text": "Pseudo invalide (3-16 caractères, lettres/chiffres/_/-)."})
        return None, None, None

    existing_conn, _ = find_conn_by_username(username)
    if existing_conn is not None:
        safe_send(conn, {"type": "error", "text": "Ce pseudo est déjà connecté."})
        return None, None, None

    users = load_users()
    if username in users and users[username].get("banned"):
        safe_send(conn, {"type": "banned", "reason": "Vous êtes banni de ce serveur."})
        return None, None, None

    user_record = get_or_create_user(username)
    return reader, username, user_record["role"]


def handle_client(conn, addr):
    print(f"[SERVER] Nouvelle connexion : {addr}")
    conn.settimeout(IDLE_CHECK_INTERVAL)

    reader, username, role = register_client(conn, addr)
    if username is None:
        conn.close()
        return

    info = {
        "username": username, "role": role, "room": DEFAULT_ROOM, "addr": addr,
        "muted_until": None, "last_active": time.time(),
    }
    with clients_lock:
        clients[conn] = info
        rooms[DEFAULT_ROOM].add(conn)

    safe_send(conn, {"type": "registered", "username": username, "role": role, "room": DEFAULT_ROOM})
    broadcast(DEFAULT_ROOM, {"type": "join", "username": username}, exclude=conn)
    print(f"[SERVER] {username} ({role}) connecté depuis {addr}")

    idle_elapsed = 0
    try:
        while True:
            try:
                msg = reader.read_message()
            except socket.timeout:
                idle_elapsed += IDLE_CHECK_INTERVAL
                if idle_elapsed >= MAX_IDLE_TIME:
                    system(conn, "Déconnexion pour inactivité.")
                    break
                continue

            if msg is None:
                break
            idle_elapsed = 0
            info["last_active"] = time.time()

            if not msg:
                continue

            mtype = msg.get("type")

            if mtype == "quit":
                break

            elif mtype == "ping":
                safe_send(conn, {"type": "pong", "ts": msg.get("ts")})

            elif mtype == "command":
                cmd = msg.get("cmd", "")
                args = msg.get("args", [])
                handler = COMMANDS.get(cmd)
                if handler:
                    handler(conn, info, args)
                else:
                    error(conn, f"Commande inconnue : /{cmd}")

            elif mtype == "chat":
                if info["muted_until"] and time.time() < info["muted_until"]:
                    remaining = int(info["muted_until"] - time.time())
                    error(conn, f"Vous êtes muted encore {remaining}s.")
                    continue

                text = sanitize_text(msg.get("text", ""))
                if not text:
                    continue
                broadcast(info["room"], {
                    "type": "chat", "room": info["room"], "username": info["username"],
                    "role": info["role"], "text": text,
                })
            # types inconnus : ignorés silencieusement (durcissement sécurité)

    except (ConnectionResetError, BrokenPipeError):
        print(f"[SERVER] Connexion perdue brutalement : {addr}")
    finally:
        with clients_lock:
            clients.pop(conn, None)
            rooms.get(info["room"], set()).discard(conn)
        broadcast(info["room"], {"type": "leave", "username": info["username"]})
        conn.close()
        print(f"[SERVER] {info['username']} déconnecté ({addr})")


def start():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(ADDR)
    server.listen()
    print(f"[SERVER] Serveur lancé sur {ADDR}")
    print("[SERVER] En attente de connexions...")
    try:
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
            print(f"[SERVER] Connexions actives : {threading.active_count() - 1}")
    except KeyboardInterrupt:
        print("\n[SERVER] Arrêt du serveur.")
    finally:
        server.close()


if __name__ == "__main__":
    start()
