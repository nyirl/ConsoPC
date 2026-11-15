# ConsoPC

Tableau de bord web en temps réel pour suivre la consommation d'énergie (et les autres capteurs) de votre PC, à partir de [HWiNFO](https://www.hwinfo.com/).

Le script lit la mémoire partagée de HWiNFO et sert une page locale qui se met à jour chaque seconde. Il n'utilise que la bibliothèque standard de Python : aucune dépendance à installer.

## Fonctionnalités

- Tableau dynamique : valeur actuelle, minimum, moyenne et maximum de chaque capteur
- Filtre par type (puissance en W, températures, fréquences, charges) et recherche
- Total des puissances sélectionnées
- Graphique de l'historique récent
- Un clic sur une ligne l'ajoute au graphique et au total, ou l'en retire
- Mode démo avec données factices pour tester sans HWiNFO

## Prérequis

- Windows (la lecture de HWiNFO ne fonctionne que sous Windows)
- Python 3.8 ou plus récent
- HWiNFO64, fenêtre **Capteurs** (Sensors) ouverte

## Installation

Avec Git :

```
git clone https://github.com/VOTRE_COMPTE/ConsoPC.git
cd ConsoPC
```

Ou en téléchargeant uniquement le script (PowerShell) :

```
irm https://raw.githubusercontent.com/VOTRE_COMPTE/ConsoPC/main/hwinfo_live.py -OutFile hwinfo_live.py
```

Pour mettre à jour une installation faite avec Git : `git pull`.

## Configuration de HWiNFO

1. Ouvrez HWiNFO en mode **Capteurs**.
2. Ouvrez les **Paramètres** (touche `Ctrl+S` depuis la fenêtre principale), puis **Réglages principaux** si besoin.
3. Cochez **Shared Memory Support** (« Prise en charge de la mémoire partagée »), puis validez avec **OK**.
4. Relancez la fenêtre Capteurs.

> Dans la version gratuite de HWiNFO, la mémoire partagée est désactivée au bout de 12 heures. Il suffit de la réactiver.

## Utilisation

```
python hwinfo_live.py
```

La page s'ouvre sur <http://localhost:8085>.

| Option | Effet |
|---|---|
| `--port 9000` | Change le port (8085 par défaut) |
| `--demo` | Utilise des données factices (fonctionne sur tout système) |
| `--no-browser` | N'ouvre pas le navigateur automatiquement |

## Sécurité

Le serveur écoute uniquement sur `127.0.0.1` : la page n'est pas accessible depuis le réseau.

## Dépannage

- **« Mémoire partagée introuvable »** : HWiNFO n'est pas lancé, la fenêtre Capteurs n'est pas ouverte, ou Shared Memory Support n'est pas activé.
- **« HWiNFO est fermé »** : HWiNFO a été arrêté ou la mémoire partagée a expiré (limite de 12 h en version gratuite).
- **Aucune ligne de puissance** : dans les paramètres des capteurs de HWiNFO, cochez « Consommations d'énergie » dans « Afficher les valeurs », ou passez le filtre de la page sur « Tous les capteurs ».

## État du projet

La lecture de la mémoire partagée HWiNFO suit la structure documentée par HWiNFO (en-tête, capteurs, mesures). L'interface web a été testée en mode démo ; les retours sur d'autres configurations matérielles sont les bienvenus.

## Licence

MIT. Voir le fichier `LICENSE`.
