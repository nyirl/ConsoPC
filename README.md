# ConsoPC

Tableau de bord web en temps réel pour suivre la consommation d'énergie (et les autres capteurs) de votre PC, à partir de [HWiNFO](https://www.hwinfo.com/).

Une page locale se met à jour chaque seconde avec les valeurs de HWiNFO. Il existe deux versions du programme :

| Version | Fichier | Ce qu'il faut | Source des données |
|---|---|---|---|
| **PowerShell** (recommandée) | `hwinfo_live.ps1` | Rien à installer (PowerShell est inclus dans Windows) | Registre Windows, alimenté par HWiNFO |
| Python | `hwinfo_live.py` | Python 3.8 ou plus récent | Mémoire partagée de HWiNFO |

## Fonctionnalités

- Tableau dynamique : valeur actuelle, minimum, moyenne et maximum de chaque capteur
- Filtre par type (puissance en W, températures, fréquences, charges) et recherche
- Total des puissances sélectionnées
- Graphique de l'historique récent
- Un clic sur une ligne l'ajoute au graphique et au total, ou l'en retire
- Mode démo avec données factices pour tester sans HWiNFO

## Version PowerShell

### 1. Récupérer le script

Dans PowerShell (remplacez `VOTRE_COMPTE` par votre identifiant GitHub) :

```
irm https://raw.githubusercontent.com/VOTRE_COMPTE/ConsoPC/main/hwinfo_live.ps1 -OutFile hwinfo_live.ps1
```

Ou avec Git : `git clone https://github.com/VOTRE_COMPTE/ConsoPC.git`, puis `git pull` pour mettre à jour.

### 2. Configurer HWiNFO

1. Ouvrez HWiNFO en mode **Capteurs** et laissez cette fenêtre ouverte.
2. Ouvrez les **Paramètres** de la fenêtre Capteurs, onglet **HWiNFO Gadget**.
3. Cochez **Activer la création de rapports vers Gadget** (« Enable reporting to Gadget »).
4. Dans la liste, cliquez sur un capteur à suivre, par exemple **CPU PPT**, puis cochez **Valeur du rapport dans Gadget**. HWiNFO lui attribue un index. Répétez l'opération pour chaque capteur voulu.
5. Cliquez sur **OK**.

Seuls les capteurs cochés apparaissent dans le tableau.

### 3. Lancer

```
powershell -ExecutionPolicy Bypass -File .\hwinfo_live.ps1
```

La page s'ouvre sur <http://localhost:8085>. L'option `-ExecutionPolicy Bypass` évite que Windows bloque le script, sans modifier vos réglages.

| Option | Effet |
|---|---|
| `-Port 9000` | Change le port (8085 par défaut) |
| `-Demo` | Utilise des données factices (test sans HWiNFO) |
| `-NoBrowser` | N'ouvre pas le navigateur automatiquement |

`Ctrl+C` arrête le programme.

## Version Python

Prérequis : Windows, Python 3.8 ou plus récent (installateur sur [python.org](https://www.python.org/downloads/), en cochant « Add python.exe to PATH »).

Dans HWiNFO, activez **Shared Memory Support** dans les **Réglages principaux** (dans la version gratuite, la mémoire partagée est coupée au bout de 12 heures et doit être réactivée), puis :

```
python hwinfo_live.py
```

Options : `--port 9000`, `--demo`, `--no-browser`.

## Sécurité

Le serveur écoute uniquement sur `localhost` : la page n'est pas accessible depuis le réseau.

## Dépannage

- **« Aucune valeur de HWiNFO dans le registre »** (PowerShell) : l'option de rapport vers le Gadget n'est pas activée, ou aucun capteur n'est coché. La fenêtre Capteurs doit rester ouverte.
- **Vérifier le registre** : `Get-ItemProperty 'HKCU:\SOFTWARE\HWiNFO64\VSB'` doit afficher des lignes `Label…`, `Value…`, `ValueRaw…`.
- **Tableau vide** : passez le menu « Afficher » de la page sur « Tous les capteurs ». Les lignes dont l'unité n'est pas reconnue ne sont pas dans le filtre « Puissance ».
- **« Mémoire partagée introuvable »** (Python) : HWiNFO n'est pas lancé, la fenêtre Capteurs n'est pas ouverte, ou Shared Memory Support n'est pas activé.
- **Le navigateur bloque le téléchargement d'un `.ps1`** : téléchargez-le en `.txt` puis renommez-le, ou utilisez la commande `irm` ci-dessus.

## État du projet

La version PowerShell est testée avec HWiNFO 8 sur un Ryzen 7 5700X. La version Python suit la structure de mémoire partagée documentée par HWiNFO mais n'a été testée qu'en mode démo. Les retours sur d'autres configurations sont les bienvenus.

## Licence

MIT. Voir le fichier `LICENSE`.
