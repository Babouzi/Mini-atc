# Mini-ATC - Radar de Trafic Aérien

Mini-ATC est un projet de surveillance du trafic aérien en temps réel au-dessus de Paris CDG.
C'est un mini-projet créé pour **apprendre** et pratiquer avec les APIs, pandas et SQLite.

## Ce que j'ai appris

Ce projet m'a permis de pratiquer et améliorer mes connaissances sur:

- **APIs REST** - Intégration avec OpenSky Network (authentification OAuth2, gestion des erreurs)
- **Pandas** - Manipulation et nettoyage de données
- **SQLite** - Création de base de données et requêtes SQL
- **Streamlit** - Création d'interface web interactive
- **Plotly** - Visualisations avec des cartes et graphiques
- **Git & GitHub** - Gestion de version

**Note:** J'ai utilisé des IA génératives (ChatGPT, Claude) pour m'aiguiller sur l'architecture, formater le code et ajouter des commentaires. Je n'ai pas laissé l'IA coder à ma place.

## Description du projet 

Mini-ATC affiche les **vols en temps réel** au-dessus de la région de Paris CDG.
L'app récupère les données via l'API OpenSky Network et les affiche sur une **carte interactive**.

On peut aussi **créer une liste de vols à surveiller**  ils seront stockés en base de données.

### Fonctionnalités

- Carte interactive des vols détectés
- Graphiques (altitude/vitesse)
- Liste de surveillance personnelle
- Mise à jour en temps réel
- Persistance en SQLite

## Technologies utilisées

- **Python 3.8+**
- **Streamlit** - Framework web
- **Plotly** - Visualisations
- **Pandas** - Data manipulation
- **SQLite3** - Base de données
- **Requests** - Requêtes HTTP

## Installation

### 1. Cloner le projet

```bash
git clone https://github.com/babouzi/mini-atc.git
cd mini-atc
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Créer un fichier `credentials.json`

Il faut d'abord créer un compte OpenSky (gratuit):
1. Allez sur https://opensky-network.org
2. Créez un compte
3. Allez sur https://opensky-network.org/my-opensky/account
3. Créez un nouveau client API
4. Copier votre **Client ID** et **Client Secret**

Créez ensuite un fichier `credentials.json` à la racine du projet:

```json
{
    "clientId": "votre_client_id",
    "clientSecret": "votre_client_secret"
}
```

⚠️**IMPORTANT:** Ce fichier est en `.gitignore`, ne l'ajoutez jamais sur GitHub!

### 4. Lancer l'application

```bash
streamlit run app.py
```

L'app s'ouvre automatiquement sur http://localhost:8501

## Comment l'utiliser?

### Onglet "Radar en temps réel"

1. Cliquez sur le bouton **"Actualiser le radar"**
2. Attendez quelques secondes
3. Vous voyez tous les vols détectés sur la carte
4. Explorez les graphiques et la table de données
5. Sélectionnez un vol et cliquez **"Ajouter ce vol"** pour le surveiller

### Onglet "Vols surveillés"

1. Voyez les vols que vous avez ajoutés à votre liste
2. Cliquez **"Actualiser les données radar"** pour mettre à jour leurs positions
3. Consultez l'historique de tous vos vols surveillés

## 🔧 Structure du code

```
app.py
├── DATABASE FUNCTIONS       # Gestion SQLite
├── AUTHENTICATION FUNCTIONS # OAuth2 OpenSky
├── API OPENSKY FUNCTIONS    # Récupération des vols
├── INITIALISATION           # Setup au démarrage
└── INTERFACE STREAMLIT      # Les 2 onglets
```

Chaque section est commentée pour faciliter la compréhension.

## Données

Les données viennent de l'**API OpenSky Network**:
- Requête: Zone CDG (48.5°N-49.5°N, 2.0°E-3.5°E)
- Latence: ~10-15 secondes (délai réel contre détection)

## Améliorations futures

- **Jeu: Tour de contrôle** - Une interface où on gère les pistes de décollage/atterrissage, on donne les autorisations aux vols (avec des niveaux de difficulté)
- Historique des positions (tracer les vols)
- Notifications quand un vol entre/sort la zone CDG
- Export des données (CSV)
- Dashboard avec statistiques

## Notes

- Les données OpenSky Network peuvent être limitées selon votre localisation
- L'API gratuite a une limite de débit (rate limiting)
- En cas de déploiement sur le Cloud (ex: Streamlit Community Cloud), la base de données SQLite locale sera réinitialisée à chaque redémarrage du conteneur. Pour une vraie mise en production, il faudrait utiliser une base de données externe comme PostgreSQL."
## Ressources utiles

- [Documentation OpenSky Network](https://openskynetwork.github.io/opensky-api/)
- [Documentation Streamlit](https://docs.streamlit.io)
- [Documentation Pandas](https://pandas.pydata.org/docs)
- [Documentation SQLite3 Python](https://docs.python.org/3/library/sqlite3.html)

---

**Créé pour apprendre et démontrer des compétences en développement Python** 
