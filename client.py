"""Client graphique (Tkinter) du chat, thème Valorant, connecté au serveur via sockets TCP."""

import socket
import threading
import queue
import time
import tkinter as tk
from tkinter import simpledialog, messagebox

from protocol import send_json, SocketReader
import theme

PORT = 5000
DEFAULT_HOST = socket.gethostbyname(socket.gethostname())

HELP_TEXT = """Commandes disponibles :

/nickname <nouveau_pseudo>     changer de pseudo
/message <pseudo> <texte>      message privé
/time                          heure du serveur
/ping                          latence
/clear                         nettoyer l'écran (local)
/join <salon>                  rejoindre / créer un salon
/leave                         revenir au salon principal
/rooms                         lister les salons
/who                           lister les membres du salon

Modération (modérateur+) :
/kick <pseudo>
/mute <pseudo> [secondes]
/unmute <pseudo>

Administration (admin) :
/ban <pseudo>
/set_moderator <pseudo>
/remove_moderator <pseudo>
/set_administrator <pseudo>
/remove_administrator <pseudo>

/quit                          quitter le chat
/help                           afficher cette aide
"""

# Source unique pour l'auto-complétion : (nom, usage, description, rôle minimum requis)
COMMANDS_INFO = [
    ("nickname", "<nouveau_pseudo>", "changer de pseudo", "user"),
    ("message", "<pseudo> <texte>", "message privé", "user"),
    ("time", "", "heure du serveur", "user"),
    ("ping", "", "latence", "user"),
    ("clear", "", "nettoyer l'écran (local)", "user"),
    ("join", "<salon>", "rejoindre / créer un salon", "user"),
    ("leave", "", "revenir au salon principal", "user"),
    ("rooms", "", "lister les salons", "user"),
    ("who", "", "lister les membres du salon", "user"),
    ("kick", "<pseudo>", "expulser un membre", "moderator"),
    ("mute", "<pseudo> [secondes]", "rendre muet", "moderator"),
    ("unmute", "<pseudo>", "réautoriser la parole", "moderator"),
    ("ban", "<pseudo>", "bannir un membre", "admin"),
    ("set_moderator", "<pseudo>", "nommer modérateur", "admin"),
    ("remove_moderator", "<pseudo>", "retirer modérateur", "admin"),
    ("set_administrator", "<pseudo>", "nommer administrateur", "admin"),
    ("remove_administrator", "<pseudo>", "retirer administrateur", "admin"),
    ("quit", "", "quitter le chat", "user"),
    ("help", "", "afficher cette aide", "user"),
]
ROLE_LEVEL = {"user": 0, "moderator": 1, "admin": 2}


class ChatClient:
    """Fenêtre unique qui bascule entre écran de connexion et écran de chat."""

    def __init__(self):
        self.sock = None
        self.reader = None
        self.incoming = queue.Queue()
        self.username = ""
        self.role = "user"
        self.room = "general"
        self.connected = False
        self.members = {}  # pseudo -> rôle, tenu à jour via /who, join, leave
        self.rooms = {}    # nom du salon -> nombre de membres, tenu à jour via /rooms
        self.suggest_popup = None   # fenêtre d'auto-complétion des commandes (None si masquée)
        self.suggest_listbox = None
        self.suggestions = []       # commandes actuellement proposées dans self.suggest_listbox

        self.root = tk.Tk()
        self.root.title(theme.TITLE)
        self.root.configure(bg=theme.BG)
        self.build_login_screen()
        self.root.mainloop()

    # Écran de connexion
    def build_login_screen(self):
        self.root.geometry("420x340")
        frame = tk.Frame(self.root, bg=theme.BG)
        frame.pack(expand=True, fill="both")
        self.login_frame = frame

        tk.Label(frame, text="VALORANT", font=theme.FONT_TITLE, fg=theme.RED, bg=theme.BG).pack(pady=(40, 0))
        tk.Label(frame, text="TACTICAL CHAT PROTOCOL", font=theme.FONT_HEADER,
                 fg=theme.WHITE, bg=theme.BG).pack(pady=(0, 30))

        tk.Label(frame, text="Adresse du serveur", fg=theme.GRAY, bg=theme.BG).pack()
        self.host_entry = tk.Entry(frame, justify="center")
        self.host_entry.insert(0, DEFAULT_HOST)
        self.host_entry.pack(pady=(0, 10))

        tk.Label(frame, text="Choisissez votre agent (pseudo)", fg=theme.GRAY, bg=theme.BG).pack()
        self.name_entry = tk.Entry(frame, justify="center")
        self.name_entry.pack(pady=(0, 10))
        self.name_entry.bind("<Return>", lambda e: self.connect())
        self.name_entry.focus()

        self.login_error = tk.Label(frame, text="", fg=theme.RED, bg=theme.BG)
        self.login_error.pack()

        tk.Button(frame, text="REJOINDRE LA PARTIE", command=self.connect, bg=theme.RED, fg=theme.WHITE,
                  font=theme.FONT_BOLD, relief="flat").pack(pady=20, ipadx=10, ipady=5)

    def connect(self):
        host = self.host_entry.get().strip() or DEFAULT_HOST
        username = self.name_entry.get().strip()
        if not username:
            self.login_error.config(text="Entrez un pseudo.")
            return

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((host, PORT))
        except OSError:
            self.login_error.config(text="Impossible de rejoindre le serveur.")
            return

        self.reader = SocketReader(self.sock)
        send_json(self.sock, {"type": "register", "username": username})
        self.connected = True

        threading.Thread(target=self.receive_loop, daemon=True).start()
        self.login_frame.destroy()
        self.build_chat_screen()
        self.root.after(50, self.process_queue)

    # Réception réseau (tourne dans un thread séparé, ne touche jamais Tkinter)
    def receive_loop(self):
        while True:
            try:
                msg = self.reader.read_message()
            except OSError:
                msg = None
            if msg is None:
                self.incoming.put({"type": "_disconnected"})
                return
            if msg:
                self.incoming.put(msg)

    def process_queue(self):
        try:
            while True:
                self.handle_message(self.incoming.get_nowait())
        except queue.Empty:
            pass
        if self.connected and self.root.winfo_exists():
            self.root.after(50, self.process_queue)

    # Écran de chat
    def build_chat_screen(self):
        self.root.geometry("900x580")
        self.root.minsize(700, 450)

        header = tk.Frame(self.root, bg=theme.BG_PANEL)
        header.pack(fill="x")
        tk.Label(header, text=theme.TITLE, font=theme.FONT_HEADER, fg=theme.RED,
                 bg=theme.BG_PANEL).pack(side="left", padx=10, pady=8)
        self.status_label = tk.Label(header, text="Connexion...", font=theme.FONT_BOLD,
                                      fg=theme.GRAY, bg=theme.BG_PANEL)
        self.status_label.pack(side="right", padx=10)

        # PanedWindow : la zone de chat et la barre latérale se redimensionnent
        # fluidement avec la fenêtre (et la séparation reste ajustable à la souris).
        body = tk.PanedWindow(self.root, orient="horizontal", bg=theme.BG,
                               sashwidth=6, sashrelief="flat", bd=0)
        body.pack(fill="both", expand=True)

        chat_frame = tk.Frame(body, bg=theme.BG)
        self.chat_text = tk.Text(chat_frame, bg=theme.BG, fg=theme.WHITE, font=theme.FONT_TEXT,
                                  state="disabled", wrap="word", relief="flat")
        self.chat_text.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=10)
        self._configure_tags()
        body.add(chat_frame, minsize=300, stretch="always")

        sidebar_frame = tk.Frame(body, bg=theme.BG)
        self.sidebar = tk.Frame(sidebar_frame, bg=theme.BG_PANEL)
        self.sidebar.pack(fill="both", expand=True, padx=(5, 10), pady=10)
        self.build_sidebar()
        body.add(sidebar_frame, width=230, minsize=200, stretch="never")

        entry_frame = tk.Frame(self.root, bg=theme.BG)
        entry_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.entry = tk.Entry(entry_frame, bg=theme.BG_INPUT, fg=theme.WHITE, insertbackground=theme.WHITE,
                               font=theme.FONT_TEXT, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", self.on_entry_return)
        self.entry.bind("<KeyRelease>", self.on_entry_key)
        self.entry.bind("<Down>", self.on_entry_down)
        self.entry.bind("<Up>", self.on_entry_up)
        self.entry.bind("<Tab>", self.on_entry_tab)
        self.entry.bind("<Escape>", self.on_entry_escape)
        self.entry.focus()
        tk.Button(entry_frame, text="ENVOYER", command=self.send_entry, bg=theme.RED, fg=theme.WHITE,
                  font=theme.FONT_BOLD, relief="flat").pack(side="left", padx=(6, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.append_system("Bienvenue. Tapez /help pour la liste des commandes.")

    def _configure_tags(self):
        t = self.chat_text
        t.tag_config("meta", foreground=theme.GRAY)
        t.tag_config("system", foreground=theme.GOLD, font=theme.FONT_BOLD)
        t.tag_config("error", foreground=theme.RED, font=theme.FONT_BOLD)
        t.tag_config("success", foreground=theme.GREEN, font=theme.FONT_BOLD)
        t.tag_config("private", foreground=theme.PURPLE, font=theme.FONT_BOLD)
        t.tag_config("join", foreground=theme.GREEN)
        t.tag_config("leave", foreground=theme.RED_DARK)
        for role, color in theme.ROLE_COLORS.items():
            t.tag_config(f"role_{role}", foreground=color, font=theme.FONT_BOLD)

    def build_sidebar(self):
        def section(title, color=theme.GRAY):
            tk.Label(self.sidebar, text=title, font=theme.FONT_BOLD, fg=color,
                     bg=theme.BG_PANEL).pack(anchor="w", padx=10, pady=(12, 2))

        def button(parent, label, command, color=theme.WHITE):
            tk.Button(parent, text=label, command=command, bg=theme.BG_INPUT, fg=color,
                      font=theme.FONT_TEXT, relief="flat", anchor="w").pack(fill="x", padx=10, pady=1)

        section("SALON")
        self.room_label = tk.Label(self.sidebar, text=self.room, fg=theme.WHITE, bg=theme.BG_PANEL)
        self.room_label.pack(anchor="w", padx=10)
        button(self.sidebar, "Rejoindre un salon", self.action_join_room)
        button(self.sidebar, "Revenir au salon principal", self.action_leave_room)
        button(self.sidebar, "Lister les salons", self.action_list_rooms)
        button(self.sidebar, "Lister les membres", self.action_list_members)

        section("AGENT")
        button(self.sidebar, "Changer de pseudo", self.action_change_nick)
        button(self.sidebar, "Message privé", self.action_private_message)
        button(self.sidebar, "Heure serveur", self.action_time)
        button(self.sidebar, "Ping", self.action_ping)
        button(self.sidebar, "Effacer l'écran", self.action_clear)
        button(self.sidebar, "Aide", self.action_help)

        # Panneaux affichés/masqués selon le rôle une fois connecté (voir refresh_role_panels)
        self.mod_frame = tk.Frame(self.sidebar, bg=theme.BG_PANEL)
        self.admin_frame = tk.Frame(self.sidebar, bg=theme.BG_PANEL)

        tk.Button(self.sidebar, text="QUITTER", command=self.quit_app, bg=theme.RED_DARK, fg=theme.WHITE,
                  font=theme.FONT_BOLD, relief="flat").pack(side="bottom", fill="x", padx=10, pady=10)

    def refresh_role_panels(self):
        for frame in (self.mod_frame, self.admin_frame):
            for widget in list(frame.children.values()):
                widget.destroy()
            frame.pack_forget()

        def button(parent, label, command):
            tk.Button(parent, text=label, command=command, bg=theme.BG_INPUT, fg=theme.CYAN,
                      font=theme.FONT_TEXT, relief="flat", anchor="w").pack(fill="x", padx=10, pady=1)

        if self.role in ("moderator", "admin"):
            tk.Label(self.mod_frame, text="MODÉRATION", font=theme.FONT_BOLD, fg=theme.CYAN,
                     bg=theme.BG_PANEL).pack(anchor="w", padx=10, pady=(12, 2))
            button(self.mod_frame, "Expulser", self.action_kick)
            button(self.mod_frame, "Rendre muet", self.action_mute)
            button(self.mod_frame, "Réautoriser la parole", self.action_unmute)
            self.mod_frame.pack(fill="x")

        if self.role == "admin":
            tk.Label(self.admin_frame, text="ADMINISTRATION", font=theme.FONT_BOLD, fg=theme.GOLD,
                     bg=theme.BG_PANEL).pack(anchor="w", padx=10, pady=(12, 2))
            button(self.admin_frame, "Bannir", self.action_ban)
            button(self.admin_frame, "Nommer modérateur", lambda: self.action_setrole("set_moderator"))
            button(self.admin_frame, "Retirer modérateur", lambda: self.action_setrole("remove_moderator"))
            button(self.admin_frame, "Nommer administrateur", lambda: self.action_setrole("set_administrator"))
            button(self.admin_frame, "Retirer administrateur", lambda: self.action_setrole("remove_administrator"))
            self.admin_frame.pack(fill="x")

    def update_status(self):
        self.status_label.config(text=f"{self.username}  [{theme.role_label(self.role)}]",
                                  fg=theme.role_color(self.role))
        self.room_label.config(text=self.room)
        self.refresh_role_panels()

    # Affichage des messages dans le journal de chat
    def append_line(self, text, tag=None):
        self.chat_text.configure(state="normal")
        self.chat_text.insert("end", text + "\n", tag or ())
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    def append_chat(self, username, role, text, room):
        self.chat_text.configure(state="normal")
        self.chat_text.insert("end", f"[{theme.now_str()}] ", "meta")
        self.chat_text.insert("end", f"#{room} ", "meta")
        self.chat_text.insert("end", f"[{theme.role_label(role)}] {username} ", f"role_{role}")
        self.chat_text.insert("end", f"> {text}\n")
        self.chat_text.configure(state="disabled")
        self.chat_text.see("end")

    def append_private(self, label, text):
        self.append_line(f"[{theme.now_str()}] [MESSAGE PRIVÉ] {label} : {text}", "private")

    def append_system(self, text):
        self.append_line(f"[SYSTÈME] {text}", "system")

    def append_error(self, text):
        self.append_line(f"[ERREUR] {text}", "error")

    def append_success(self, text):
        self.append_line(f"[OK] {text}", "success")

    # Traitement des messages reçus du serveur
    def handle_message(self, msg):
        mtype = msg.get("type")

        if mtype == "_disconnected":
            self.append_error("Connexion perdue avec le serveur.")
            self.connected = False
            self.entry.config(state="disabled")

        elif mtype == "chat":
            self.append_chat(msg["username"], msg["role"], msg["text"], msg["room"])

        elif mtype == "private":
            self.append_private(f"{msg['from']} chuchote", msg["text"])

        elif mtype == "private_ack":
            self.append_private(f"vous -> {msg['to']}", msg["text"])

        elif mtype == "system":
            self.append_system(msg["text"])

        elif mtype == "error":
            self.append_error(msg["text"])

        elif mtype == "join":
            self.append_line(f">> {msg['username']} a rejoint la partie.", "join")
            self.members[msg["username"]] = msg.get("role", "user")

        elif mtype == "leave":
            self.append_line(f"<< {msg['username']} a quitté la partie.", "leave")
            self.members.pop(msg["username"], None)

        elif mtype == "pong":
            rtt_ms = int((time.time() - msg["ts"]) * 1000)
            self.append_success(f"Ping : {rtt_ms} ms")

        elif mtype == "time":
            self.append_system(f"Heure serveur : {msg['server_time']}")

        elif mtype == "rooms":
            rooms_str = ", ".join(f"{name} ({count})" for name, count in msg["rooms"].items())
            self.append_system(f"Salons : {rooms_str}")
            self.rooms = dict(msg["rooms"])

        elif mtype == "who":
            users_str = ", ".join(f"{u['username']} [{theme.role_label(u['role'])}]" for u in msg["users"])
            self.append_system(f"Membres de #{msg['room']} : {users_str}")
            self.members = {u["username"]: u["role"] for u in msg["users"]}

        elif mtype == "room_changed":
            self.room = msg["room"]
            self.room_label.config(text=self.room)
            self.send_command("who", [])
            self.send_command("rooms", [])

        elif mtype == "role_changed":
            self.role = msg["role"]
            self.update_status()

        elif mtype == "registered":
            self.username = msg["username"]
            self.role = msg["role"]
            self.room = msg["room"]
            self.update_status()
            self.append_success(f"Connecté en tant que {msg['username']} ({theme.role_label(msg['role'])})")
            self.send_command("who", [])
            self.send_command("rooms", [])

        elif mtype == "kicked":
            self.append_error(f"Expulsé : {msg['reason']}")
            self.connected = False
            self.entry.config(state="disabled")

        elif mtype == "banned":
            self.append_error(f"Banni : {msg['reason']}")
            self.connected = False
            self.entry.config(state="disabled")

    # Auto-complétion des commandes (déclenchée en tapant "/")
    def visible_commands(self):
        level = ROLE_LEVEL.get(self.role, 0)
        return [c for c in COMMANDS_INFO if ROLE_LEVEL.get(c[3], 0) <= level]

    def suggestions_visible(self):
        return self.suggest_popup is not None and self.suggest_popup.winfo_exists()

    def on_entry_key(self, event):
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape"):
            return
        text = self.entry.get()
        if not text.startswith("/") or " " in text:
            self.hide_suggestions()
            return
        prefix = text[1:].lower()
        matches = [c for c in self.visible_commands() if c[0].startswith(prefix)]
        if matches:
            self.show_suggestions(matches)
        else:
            self.hide_suggestions()

    def show_suggestions(self, matches):
        self.suggestions = matches
        if not self.suggestions_visible():
            self.suggest_popup = tk.Toplevel(self.root)
            self.suggest_popup.overrideredirect(True)
            self.suggest_popup.configure(bg=theme.RED)
            self.suggest_listbox = tk.Listbox(self.suggest_popup, bg=theme.BG_INPUT, fg=theme.WHITE,
                                               selectbackground=theme.RED, activestyle="none",
                                               exportselection=False, relief="flat", bd=0,
                                               highlightthickness=0, font=theme.FONT_TEXT)
            self.suggest_listbox.pack(padx=1, pady=1, fill="both", expand=True)
            self.suggest_listbox.bind("<Button-1>", self.on_suggest_click)

        self.suggest_listbox.delete(0, "end")
        for cmd, usage, desc, _role in matches:
            label = f"/{cmd} {usage}".rstrip() + f"  —  {desc}"
            self.suggest_listbox.insert("end", label)
        self.suggest_listbox.config(height=min(6, len(matches)))
        self.suggest_listbox.selection_clear(0, "end")
        self.suggest_listbox.selection_set(0)
        self.suggest_listbox.activate(0)

        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        width = self.entry.winfo_width()
        self.suggest_popup.update_idletasks()
        height = self.suggest_listbox.winfo_reqheight() + 2
        self.suggest_popup.geometry(f"{width}x{height}+{x}+{y}")
        self.suggest_popup.lift()

    def hide_suggestions(self):
        if self.suggestions_visible():
            self.suggest_popup.destroy()
        self.suggest_popup = None
        self.suggest_listbox = None
        self.suggestions = []

    def move_suggestion_selection(self, delta):
        size = self.suggest_listbox.size()
        if size == 0:
            return
        current = self.suggest_listbox.curselection()
        idx = (current[0] + delta) % size if current else 0
        self.suggest_listbox.selection_clear(0, "end")
        self.suggest_listbox.selection_set(idx)
        self.suggest_listbox.activate(idx)
        self.suggest_listbox.see(idx)

    def accept_suggestion(self):
        if not self.suggestions_visible():
            return False
        selection = self.suggest_listbox.curselection()
        idx = selection[0] if selection else 0
        if idx >= len(self.suggestions):
            return False
        cmd = self.suggestions[idx][0]
        self.entry.delete(0, "end")
        self.entry.insert(0, f"/{cmd} ")
        self.entry.icursor("end")
        self.hide_suggestions()
        return True

    def on_entry_down(self, event):
        if not self.suggestions_visible():
            return None
        self.move_suggestion_selection(1)
        return "break"

    def on_entry_up(self, event):
        if not self.suggestions_visible():
            return None
        self.move_suggestion_selection(-1)
        return "break"

    def on_entry_tab(self, event):
        if self.accept_suggestion():
            return "break"
        return None

    def on_entry_escape(self, event):
        if self.suggestions_visible():
            self.hide_suggestions()
            return "break"
        return None

    def on_entry_return(self, event=None):
        if self.accept_suggestion():
            return "break"
        self.send_entry()
        return "break"

    def on_suggest_click(self, event):
        idx = self.suggest_listbox.nearest(event.y)
        self.suggest_listbox.selection_clear(0, "end")
        self.suggest_listbox.selection_set(idx)
        self.accept_suggestion()
        self.entry.focus()

    # Envoi vers le serveur
    def send_command(self, cmd, args):
        send_json(self.sock, {"type": "command", "cmd": cmd, "args": args})

    def send_entry(self):
        text = self.entry.get().strip()
        self.entry.delete(0, "end")
        self.hide_suggestions()
        if not text:
            return

        # Commandes gérées localement (pas envoyées au serveur)
        if text == "/quit":
            self.quit_app()
            return
        if text == "/clear":
            self.action_clear()
            return
        if text == "/help":
            self.action_help()
            return
        if text == "/ping":
            self.action_ping()
            return

        if text.startswith("/"):
            parts = text[1:].split(" ")
            cmd, args = parts[0], parts[1:]
            self.send_command(cmd, args)
            return

        send_json(self.sock, {"type": "chat", "text": text})

    # Sélection d'un pseudo parmi les membres présents (plutôt qu'une saisie libre)
    def pick_username(self, title, prompt, exclude_self=True):
        candidates = sorted(name for name in self.members if not (exclude_self and name == self.username))
        if not candidates:
            messagebox.showinfo(title, "Aucun membre disponible pour le moment.", parent=self.root)
            return None

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=theme.BG)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text=prompt, fg=theme.WHITE, bg=theme.BG).pack(padx=10, pady=(10, 5))

        listbox = tk.Listbox(dialog, bg=theme.BG_INPUT, fg=theme.WHITE, selectbackground=theme.RED,
                              activestyle="none", exportselection=False,
                              height=min(8, len(candidates)), width=30)
        for name in candidates:
            listbox.insert("end", f"{name} [{theme.role_label(self.members.get(name, 'user'))}]")
        listbox.pack(padx=10, pady=5, fill="both", expand=True)
        listbox.selection_set(0)
        listbox.focus()

        result = {"value": None}

        def confirm(event=None):
            selection = listbox.curselection()
            if selection:
                result["value"] = candidates[selection[0]]
            dialog.destroy()

        def cancel(event=None):
            dialog.destroy()

        listbox.bind("<Double-Button-1>", confirm)
        dialog.bind("<Return>", confirm)
        dialog.bind("<Escape>", cancel)
        dialog.protocol("WM_DELETE_WINDOW", cancel)

        btn_frame = tk.Frame(dialog, bg=theme.BG)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btn_frame, text="OK", command=confirm, bg=theme.RED, fg=theme.WHITE,
                  font=theme.FONT_BOLD, relief="flat").pack(side="right", padx=(6, 0))
        tk.Button(btn_frame, text="Annuler", command=cancel, bg=theme.BG_INPUT, fg=theme.WHITE,
                  font=theme.FONT_TEXT, relief="flat").pack(side="right")

        dialog.wait_window()
        return result["value"]

    # Sélection d'un salon parmi ceux existants, avec possibilité d'en créer un nouveau
    def pick_room(self, title, prompt):
        candidates = sorted(name for name in self.rooms if name != self.room)

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=theme.BG)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text=prompt, fg=theme.WHITE, bg=theme.BG).pack(padx=10, pady=(10, 5))

        listbox = tk.Listbox(dialog, bg=theme.BG_INPUT, fg=theme.WHITE, selectbackground=theme.RED,
                              activestyle="none", exportselection=False,
                              height=min(8, len(candidates)) if candidates else 1, width=30)
        for name in candidates:
            listbox.insert("end", f"{name} ({self.rooms[name]})")
        if not candidates:
            listbox.insert("end", "Aucun autre salon pour le moment")
            listbox.config(state="disabled")
        listbox.pack(padx=10, pady=5, fill="both", expand=True)
        if candidates:
            listbox.selection_set(0)

        tk.Label(dialog, text="Ou créer / rejoindre un nouveau salon :", fg=theme.GRAY, bg=theme.BG).pack(
            anchor="w", padx=10, pady=(5, 0))
        entry = tk.Entry(dialog, bg=theme.BG_INPUT, fg=theme.WHITE, insertbackground=theme.WHITE, width=30)
        entry.pack(padx=10, pady=(0, 5))

        def fill_entry(event=None):
            selection = listbox.curselection()
            if selection and candidates:
                entry.delete(0, "end")
                entry.insert(0, candidates[selection[0]])

        listbox.bind("<<ListboxSelect>>", fill_entry)
        entry.focus()

        result = {"value": None}

        def confirm(event=None):
            new_name = entry.get().strip()
            if new_name:
                result["value"] = new_name
            else:
                selection = listbox.curselection()
                if selection and candidates:
                    result["value"] = candidates[selection[0]]
            dialog.destroy()

        def cancel(event=None):
            dialog.destroy()

        listbox.bind("<Double-Button-1>", confirm)
        dialog.bind("<Return>", confirm)
        dialog.bind("<Escape>", cancel)
        dialog.protocol("WM_DELETE_WINDOW", cancel)

        btn_frame = tk.Frame(dialog, bg=theme.BG)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btn_frame, text="OK", command=confirm, bg=theme.RED, fg=theme.WHITE,
                  font=theme.FONT_BOLD, relief="flat").pack(side="right", padx=(6, 0))
        tk.Button(btn_frame, text="Annuler", command=cancel, bg=theme.BG_INPUT, fg=theme.WHITE,
                  font=theme.FONT_TEXT, relief="flat").pack(side="right")

        dialog.wait_window()
        return result["value"]

    # Actions de la barre latérale (ouvrent une boîte de dialogue puis envoient la commande)
    def action_join_room(self):
        self.send_command("rooms", [])
        name = self.pick_room("Rejoindre un salon", "Salons disponibles :")
        if name:
            self.send_command("join", [name])

    def action_leave_room(self):
        self.send_command("leave", [])

    def action_list_rooms(self):
        self.send_command("rooms", [])

    def action_list_members(self):
        self.send_command("who", [])

    def action_change_nick(self):
        name = simpledialog.askstring("Changer de pseudo", "Nouveau pseudo :", parent=self.root)
        if name and name.strip():
            self.send_command("nickname", [name.strip()])

    def action_private_message(self):
        target = self.pick_username("Message privé", "Destinataire :")
        if not target:
            return
        text = simpledialog.askstring("Message privé", f"Message pour {target} :", parent=self.root)
        if text and text.strip():
            self.send_command("message", [target, text.strip()])

    def action_time(self):
        self.send_command("time", [])

    def action_ping(self):
        send_json(self.sock, {"type": "ping", "ts": time.time()})

    def action_clear(self):
        self.chat_text.configure(state="normal")
        self.chat_text.delete("1.0", "end")
        self.chat_text.configure(state="disabled")

    def action_help(self):
        messagebox.showinfo("Commandes disponibles", HELP_TEXT, parent=self.root)

    def action_kick(self):
        target = self.pick_username("Expulser", "Membre à expulser :")
        if target:
            self.send_command("kick", [target])

    def action_ban(self):
        target = self.pick_username("Bannir", "Membre à bannir :")
        if target:
            self.send_command("ban", [target])

    def action_mute(self):
        target = self.pick_username("Rendre muet", "Membre à museler :")
        if not target:
            return
        duration = simpledialog.askstring("Rendre muet", "Durée en secondes (défaut 60) :", parent=self.root)
        args = [target] + ([duration.strip()] if duration and duration.strip() else [])
        self.send_command("mute", args)

    def action_unmute(self):
        target = self.pick_username("Réautoriser la parole", "Membre à démuter :")
        if target:
            self.send_command("unmute", [target])

    def action_setrole(self, cmd):
        target = self.pick_username(cmd.replace("_", " ").capitalize(), "Membre concerné :")
        if target:
            self.send_command(cmd, [target])

    def quit_app(self):
        self.connected = False
        if self.sock:
            try:
                send_json(self.sock, {"type": "quit"})
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
        self.root.destroy()


if __name__ == "__main__":
    ChatClient()