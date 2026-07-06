"""
Protocole applicatif au dessus de TCP.
On échange des messages JSON, un par ligne (delimiter '\n'),
pour ne pas dépendre de la taille des paquets recv(1024).
"""

import json

ENCODING = "utf-8"


def send_json(sock, data: dict):
    payload = json.dumps(data, ensure_ascii=False) + "\n"
    sock.sendall(payload.encode(ENCODING))


class SocketReader:
    """Bufferise les octets reçus et retourne un message JSON complet à la fois."""

    def __init__(self, sock, bufsize=4096):
        self.sock = sock
        self.bufsize = bufsize
        self.buffer = ""

    def read_message(self):
        """Retourne un dict, {} si ligne vide/corrompue, ou None si la socket est fermée."""
        while "\n" not in self.buffer:
            chunk = self.sock.recv(self.bufsize)
            if not chunk:
                return None
            self.buffer += chunk.decode(ENCODING, errors="ignore")

        line, self.buffer = self.buffer.split("\n", 1)
        line = line.strip()
        if not line:
            return {}
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {}
