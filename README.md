# Chat Textuel Sockets

Projet basé sur le code vu en cours (thread par client, JSON persistant), étendu pour couvrir
l'intégralité des consignes.

## Fichiers

- `protocol.py` — framing des messages (JSON, un message par ligne) partagé client/serveur.
- `theme.py` — couleurs ANSI pour le terminal client.
- `server.py` — serveur multi-clients (threading), rooms, rôles, modération.
- `client.py` — client avec thread de réception asynchrone + boucle de saisie.

Aucune dépendance externe : uniquement la bibliothèque standard Python 3.

## Tutoriel : lancer et utiliser le projet

### 1. Prérequis

Python 3 (aucune dépendance externe, uniquement la bibliothèque standard). Tous les fichiers
(`server.py`, `client.py`, `protocol.py`, `theme.py`) doivent rester dans le même dossier.

### 2. Démarrer le serveur

Ouvrez un terminal dans le dossier du projet :

```bash
python3 server.py
```

Le serveur affiche l'adresse et le port sur lesquels il écoute, puis attend des connexions :

```
[SERVER] Serveur lancé sur ('192.168.x.x', 5000)
[SERVER] En attente de connexions...
```

Laissez ce terminal ouvert : c'est le processus serveur, il doit rester actif tant que le chat
doit fonctionner. Un fichier `user_data.json` sera créé automatiquement à côté pour stocker les
pseudos, rôles et bans.

### 3. Connecter un ou plusieurs clients

Dans un **nouveau** terminal (le serveur doit déjà tourner) :

```bash
python3 client.py
```

Le client demande un pseudo (3-16 caractères, lettres/chiffres/`_`/`-`) :

```
Choisissez votre pseudo : alice
[OK] Connecté en tant que alice (admin)
```

Le tout premier compte créé sur le serveur devient automatiquement `admin`. Les suivants sont
`user` par défaut.

Répétez l'opération (`python3 client.py` dans un nouveau terminal) pour simuler plusieurs joueurs
connectés en même temps, par exemple `bobby` dans un second terminal.

### 4. Discuter

Tapez simplement du texte puis Entrée : le message est diffusé à tous les clients présents dans
le même salon.

```
alice > salut tout le monde
[12:03:41] #general alice > salut tout le monde
```

### 5. Utiliser les commandes

Toutes les commandes commencent par `/`. Tapez `/help` à tout moment pour voir la liste complète
dans le client. Quelques exemples pour démarrer :

```
/nick nouveau_pseudo        change votre pseudo
/msg bobby coucou            envoie un message privé à bobby
/time                        affiche l'heure du serveur
/ping                        mesure la latence
/join taverne                rejoint (ou crée) le salon "taverne"
/leave                       revient au salon "general"
/rooms                       liste les salons existants
/who                         liste les membres du salon courant
```

### 6. Modération (rôles moderateur/admin)

Si votre compte a le rôle `moderator` ou `admin` (voir le tableau des commandes ci-dessous),
vous pouvez gérer les autres utilisateurs :

```
/kick bobby        déconnecte bobby
/mute bobby 120     mute bobby pendant 120s
/ban bobby          bannit bobby définitivement (persisté dans user_data.json)
/setmodo bobby       promeut bobby modérateur
```

### 7. Quitter

`/quit` (ou `Ctrl+C`) ferme proprement la connexion du client. Le serveur détecte aussi les
déconnexions brutales et les timeouts d'inactivité (180s par défaut) sans planter.

Pour arrêter le serveur : `Ctrl+C` dans son terminal.

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
  - validation des pseudos (longueur, caractères autorisés, unicité en ligne),
  - assainissement des messages (caractères non imprimables filtrés, longueur plafonnée),
  - vérification du ban à chaque tentative de connexion,
  - verrous (`threading.Lock`) sur les structures partagées et l'écriture du fichier JSON pour
    éviter les races conditions en environnement multi-thread,
  - les messages malformés/types inconnus sont ignorés silencieusement plutôt que de faire
    planter le serveur.
- **Bonus QoL** : couleurs par rôle, horodatage des messages, affichage `[INFO]`/`[ERREUR]`/`[OK]`,
  affichage non bloquant côté client (thread de réception séparé du prompt de saisie).
