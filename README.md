# Chat Textuel Sockets — Thème Valorant

Projet basé sur le code vu en cours (thread par client, JSON persistant), étendu pour couvrir
l'intégralité des consignes.

## Fichiers

- `protocol.py` — framing des messages (JSON, un message par ligne) partagé client/serveur.
- `theme.py` — couleurs ANSI et bannière façon Valorant pour le terminal client.
- `server.py` — serveur multi-clients (threading), rooms, rôles, modération.
- `client.py` — client avec thread de réception asynchrone + boucle de saisie.

Aucune dépendance externe : uniquement la bibliothèque standard Python 3.

## Lancer le projet

Dans deux terminaux VSCode séparés (même dossier) :

```bash
python3 server.py
```

```bash
python3 client.py
```

Ouvrez plusieurs terminaux `client.py` pour simuler plusieurs joueurs.

## Commandes disponibles côté client

| Commande | Rôle requis | Effet |
|---|---|---|
| `/nick <pseudo>` | tous | change de pseudo (conservé dans `user_data.json`) |
| `/msg <pseudo> <texte>` | tous | message privé |
| `/time` | tous | heure du serveur |
| `/ping` | tous | latence aller-retour |
| `/clear` | tous | nettoie l'écran (local) |
| `/join <salon>` | tous | rejoint / crée un salon |
| `/leave` | tous | retourne au salon `general` |
| `/rooms` | tous | liste les salons et leur population |
| `/who` | tous | liste les joueurs du salon courant |
| `/kick <pseudo>` | modérateur+ | déconnecte un joueur |
| `/mute <pseudo> [s]` | modérateur+ | coupe le micro (défaut 60s) |
| `/unmute <pseudo>` | modérateur+ | lève le mute |
| `/ban <pseudo>` | admin | bannit définitivement (persisté) |
| `/setmodo`, `/remmodo` | admin | attribue/retire le rôle modérateur |
| `/setadmin`, `/remadmin` | admin | attribue/retire le rôle admin |
| `/quit` | tous | quitte proprement |

Un joueur ne peut jamais cibler un rôle égal ou supérieur au sien.
Le tout premier compte créé sur le serveur devient automatiquement `admin` (bootstrap).

## Correspondance avec les consignes

- **Connexion + échange de message** : boucle `chat` avec broadcast dans la room.
- **Plusieurs clients simultanés** : un thread par connexion côté serveur (`threading.Thread`).
- **Déconnexion propre sans crash** : `try/except/finally` isole chaque client, nettoyage de
  `clients`/`rooms` dans tous les cas (déconnexion volontaire, brutale, kick, ban).
- **Pseudo + stockage JSON** : `user_data.json`, régénéré/mis à jour à chaque changement.
- **Changer de pseudo** : `/nick`.
- **Message privé** : `/msg`.
- **`/time` et `/ping`** : implémentés avec aller-retour serveur réel (mesure de latence
  effective, pas simulée).
- **Timeout d'inactivité** : `conn.settimeout()` + compteur d'inactivité cumulée
  (`MAX_IDLE_TIME`, 180s par défaut) → déconnexion automatique.
- **`/clear`** : géré côté client (`os.system`), pas besoin d'aller-retour réseau.
- **Rôles (user/modérateur/admin)** : persistés par pseudo, avec hiérarchie de permissions.
- **Commandes de rôles** : `kick`, `ban`, `mute`, `unmute`, `setmodo/remmodo`, `setadmin/remadmin`,
  chacune vérifiant le niveau minimum requis et interdisant de cibler un rôle égal/supérieur.
- **Salons (rooms)** : `/join`, `/leave`, `/rooms`, `/who`, avec broadcast d'entrée/sortie.
- **Sécurité** :
  - validation stricte des pseudos (regex, longueur, unicité en ligne),
  - assainissement des messages (caractères non imprimables filtrés, longueur plafonnée),
  - anti-flood (5 messages / 5s → mute automatique 30s),
  - vérification du ban à chaque tentative de connexion,
  - verrous (`threading.Lock`) sur les structures partagées et l'écriture du fichier JSON pour
    éviter les races conditions en environnement multi-thread,
  - les messages malformés/types inconnus sont ignorés silencieusement plutôt que de faire
    planter le serveur.
- **Bonus QoL** : thème Valorant complet (bannière, couleurs par rôle, horodatage des messages,
  affichage `[SYSTEM]`/`[SPIKE ERROR]`/`[DEFUSED]` stylisé), affichage non bloquant côté client
  (thread de réception séparé du prompt de saisie).

## Limites connues / pistes d'amélioration

- Le mute n'est pas persisté après redémarrage du serveur (volontaire, c'est une sanction
  temporaire).
- Pas de mot de passe : l'identité repose sur le pseudo choisi (cohérent avec le niveau du cours).
- Le rafraîchissement du prompt pendant la saisie est une solution simple ; un vrai TUI
  (ex. `curses` ou `rich`) donnerait un rendu plus propre mais dépasse le cadre du cours.
