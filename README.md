# Chat Textuel Sockets — Interface Valorant

Chat en réseau (sockets TCP) en Python, avec un client graphique Tkinter à l'habillage
inspiré de Valorant.

## Fichiers

- `server.py` — serveur multi-clients (threading), salons, rôles, modération.
- `client.py` — client graphique Tkinter (thème Valorant).
- `protocol.py` — framing des messages JSON partagé client/serveur.
- `theme.py` — palette de couleurs et polices du thème Valorant.

Aucune dépendance externe : bibliothèque standard Python 3 uniquement (Tkinter est inclus
avec Python sur Windows/macOS ; sous Linux, installer le paquet `python3-tk` si besoin).

## Lancer le projet

> Sous Windows : `python`. Sous macOS/Linux : `python3`.

1. Démarrer le serveur (un terminal, à laisser ouvert) :
   ```bash
   python server.py
   ```
2. Lancer un client (une fenêtre par joueur) :
   ```bash
   python client.py
   ```
   Sur l'écran de connexion, vérifiez l'adresse du serveur (pré-remplie automatiquement)
   puis choisissez un pseudo (3-16 caractères, lettres/chiffres/`_`/`-`). Le premier compte
   créé sur le serveur devient automatiquement `admin`, les suivants sont `user`.
3. Discuter : tapez du texte puis Entrée (ou "ENVOYER") pour l'envoyer au salon courant.
   La barre latérale donne accès aux mêmes actions sous forme de boutons. Tapez `/help`
   pour la liste des commandes.
4. Quitter : bouton "QUITTER" ou commande `/quit`.

## Commandes

Les commandes restent en anglais (comme le code), mais sans abréviation, pour rester
explicites et faciles à mémoriser.

| Commande | Rôle requis | Effet |
|---|---|---|
| `/nickname <pseudo>` | tous | change de pseudo |
| `/message <pseudo> <texte>` | tous | message privé |
| `/time` | tous | heure du serveur |
| `/ping` | tous | latence aller-retour |
| `/clear` | tous | nettoie l'écran (local) |
| `/join <salon>` | tous | rejoint / crée un salon |
| `/leave` | tous | retourne au salon `general` |
| `/rooms` | tous | liste les salons et leur population |
| `/who` | tous | liste les membres du salon courant |
| `/kick <pseudo>` | modérateur+ | déconnecte un joueur |
| `/mute <pseudo> [s]` | modérateur+ | coupe le micro (défaut 60s) |
| `/unmute <pseudo>` | modérateur+ | lève le mute |
| `/ban <pseudo>` | admin | bannit définitivement (persisté) |
| `/set_moderator`, `/remove_moderator` | admin | attribue/retire le rôle modérateur |
| `/set_administrator`, `/remove_administrator` | admin | attribue/retire le rôle admin |
| `/quit` | tous | quitte proprement |
| `/help` | tous | affiche l'aide |

Toutes ces commandes sont aussi accessibles depuis les boutons de la barre latérale
(les commandes de modération/administration n'apparaissent que si le rôle du joueur le
permet). Un joueur ne peut jamais cibler un rôle égal ou supérieur au sien. Pseudos, rôles
et bans sont stockés dans `user_data.json`.

## Interface graphique

- Écran de connexion : choix de l'adresse du serveur et du pseudo ("agent").
- Fenêtre de chat : journal de messages coloré par rôle (`AGENT` blanc, `MODÉRATEUR`
  cyan, `ADMINISTRATEUR` or), champ de saisie, et barre latérale d'actions (salons,
  pseudo, message privé, heure, ping, modération/administration).
- Les couleurs et polices viennent de `theme.py` ; pour changer l'habillage, il suffit d'y
  modifier les constantes de couleur.
