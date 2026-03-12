# Mini-ATC: Radar de trafic aérien Paris CDG
# Affiche les vols en temps réel au-dessus de CDG via l'API OpenSky Network
# Permet de surveiller des vols spécifiques en base de données

import requests as rq
import pandas as pd
import streamlit as st
import json
import sqlite3 as sql
import plotly.express as px

# Configuration Streamlit
st.set_page_config(page_title="Mini-ATC Paris CDG", layout="wide")

# Les colonnes retournées par l'API OpenSky (state vectors)
# Voir: https://opensky-network.org/api/states/all
COL_ICAO24 = 0      # Identifiant unique de l'aéronef
COL_CALLSIGN = 1    # Numéro du vol (ex: "AFR123")
COL_LONGITUDE = 5   # Longitude en degrés
COL_LATITUDE = 6    # Latitude en degrés
COL_ALTITUDE = 7    # Altitude en mètres
COL_VELOCITY = 9    # Vitesse en m/s

# Zone géographique d'intérêt: Paris CDG
CDG_ZONE = {
    'lamin': 48.5,   # Latitude sud
    'lomin': 2.0,    # Longitude ouest
    'lamax': 49.5,   # Latitude nord
    'lomax': 3.5     # Longitude est
}

# ============================================
# DATABASE FUNCTIONS
# ============================================

def init_database():
    """Crée la base de données et la table watched_flights"""
    con = sql.connect("radar_database.db")
    cursor = con.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS watched_flights(
                          icao24 TEXT PRIMARY KEY,
                          callsign TEXT,
                          added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                          note TEXT
                      )''')
    con.commit()
    cursor.close()
    con.close()

def add_watched_flight(icao24, callsign, note=""):
    """Ajoute un vol à la liste de surveillance"""
    try:
        con = sql.connect("radar_database.db")
        cursor = con.cursor()

        # Vérifier si le vol existe déjà
        cursor.execute('SELECT icao24 FROM watched_flights WHERE icao24 = ?', (icao24,))
        exists = cursor.fetchone() is not None

        if exists:
            # Mise à jour: on change le callsign/note mais on garde added_at
            cursor.execute('''UPDATE watched_flights SET callsign = ?, note = ? WHERE icao24 = ?''',
                         (callsign, note, icao24))
        else:
            # Insertion: nouveau vol à surveiller
            cursor.execute('''INSERT INTO watched_flights(icao24, callsign, note) VALUES (?, ?, ?)''',
                         (icao24, callsign, note))
        
        con.commit()
        cursor.close()
        con.close()
        return True

    except Exception as e:
        print(f"Erreur base de données: {e}")
        return False

def get_watched_flights():
    """Récupère tous les vols sous surveillance depuis la BDD"""
    try:
        con = sql.connect("radar_database.db")
        df = pd.read_sql_query("SELECT * FROM watched_flights ORDER BY added_at DESC", con)
        con.close()
        return df
    except Exception as e:
        print(f"Erreur lecture BDD: {e}")
        return pd.DataFrame()


# ============================================
# AUTHENTICATION FUNCTIONS (OAuth2)
# ============================================

@st.cache_data(show_spinner=False)
def get_credentials(file_path):
    """Lit les credentials OpenSky depuis credentials.json"""
    try:
        with open(file_path, "r") as file:
            credentials = json.load(file)
            return credentials["clientId"], credentials["clientSecret"]
    except FileNotFoundError:
        st.error("Fichier credentials.json non trouvé")
        st.stop()
    except KeyError:
        st.error("Clés 'clientId' ou 'clientSecret' manquantes")
        st.stop()

def get_access_token(client_id, client_secret):
    """Récupère un token d'accès OAuth2 auprès d'OpenSky"""
    base_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        response = rq.post(base_url, data=payload)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"Erreur auth: {response.status_code}")
            return None

    except Exception as e:
        print(f"Erreur réseau: {e}")
        return None

@st.cache_data(ttl=1500, show_spinner=True)  # Cache 25 minutes
def get_cached_token(cid, secret):
    """Récupère le token avec cache (pour ne pas le demander à chaque fois)"""
    return get_access_token(cid, secret)

def get_fresh_token():
    """Initialise le token au démarrage de l'app"""
    cid, secret = get_credentials("credentials.json")
    token = get_cached_token(cid, secret)
    if token:
        st.session_state['access_token'] = token
        return True
    else:
        st.error("Impossible d'obtenir un token. Vérifiez vos credentials.")
        return False

def retry_with_fresh_token():
    """Récupère un nouveau token si l'ancien a expiré (erreur 401)"""
    st.cache_data.clear()
    cid, secret = get_credentials("credentials.json")
    token = get_cached_token(cid, secret)
    if token:
        st.session_state['access_token'] = token
        return True
    return False


# ============================================
# API OPENSKY FUNCTIONS
# ============================================

def get_live_flights():
    """Récupère les vols en direct au-dessus de CDG via l'API OpenSky"""
    url = "https://opensky-network.org/api/states/all"

    headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
    params = {
        "lamin": CDG_ZONE["lamin"],
        "lomin": CDG_ZONE["lomin"],
        "lamax": CDG_ZONE["lamax"],
        "lomax": CDG_ZONE["lomax"],
    }

    try:
        response = rq.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Token expiré, on essaie d'en récupérer un nouveau
            print("Token expiré, tentative de renouvellement...")
            if retry_with_fresh_token():
                headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
                response = rq.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    return response.json()
            st.warning("Impossible de se reconnecter à l'API")
            return None
        else:
            st.error(f"Erreur API: {response.status_code}")
            return None

    except Exception as e:
        st.error(f"Erreur réseau: {e}")
        return None

def clean_data(df):
    """Nettoie les données récupérées de l'API OpenSky"""
    # On garde seulement les colonnes utiles
    df = df[[COL_ICAO24, COL_CALLSIGN, COL_LONGITUDE, COL_LATITUDE, COL_ALTITUDE, COL_VELOCITY]]
    df.columns = ["ID", "Flight", "longitude", "latitude", "altitude", "velocity"]
    
    # Supprimer les espaces inutiles des callsigns
    # (OpenSky retourne "AFR123   " au lieu de "AFR123")
    df["Flight"] = df["Flight"].str.strip()
    
    # Supprimer les vols sans altitude valide
    df = df.dropna(subset=["altitude"])

    return df


# ============================================
# INITIALISATION
# ============================================

# Récupérer le token au démarrage (une seule fois par session)
if "access_token" not in st.session_state:
    if not get_fresh_token():
        st.stop()

# Initialiser la base de données au démarrage
if "db_initialized" not in st.session_state:
    init_database()
    st.session_state["db_initialized"] = True


# ============================================
# INTERFACE STREAMLIT
# ============================================

# Créer les 2 onglets principaux
tab_radar, tab_bdd = st.tabs(["Radar temps réel", "Vols surveillés"])


# ============================================
# ONGLET 1: RADAR EN TEMPS RÉEL
# ============================================

with tab_radar:
    # Bouton pour charger les données radar
    if st.button("🔄 Actualiser le radar"):
        live_flights = get_live_flights()
        if live_flights and "states" in live_flights:
            df = pd.DataFrame(live_flights["states"])
            df = clean_data(df)
            st.session_state["current_flights"] = df
        else:
            st.warning("Aucun vol détecté.")

    # Afficher les données si elles sont disponibles
    if "current_flights" in st.session_state:
        df_memory = st.session_state["current_flights"].copy()

        # Calculer quelques stats
        total_flights = len(df_memory)
        max_altitude = int(df_memory["altitude"].max())
        max_speed = int(df_memory["velocity"].max() * 3.6)  # m/s en km/h

        # Afficher les KPI en haut
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric(label="Vols détectés", value=total_flights)
        kpi2.metric(label="Altitude max (m)", value=max_altitude)
        kpi3.metric(label="Vitesse max (km/h)", value=max_speed)
        st.divider()

        # Deux colonnes: carte et graphique
        col1, col2 = st.columns(2)
        
        with col1:
            # Récupérer les vols sous surveillance pour les colorier différemment
            watched_flights_df = get_watched_flights()
            if not watched_flights_df.empty:
                watched_flights_ids = watched_flights_df["icao24"].tolist()
            else:
                watched_flights_ids = []

            # Ajouter une colonne "status" pour différencier les vols
            df_memory["status"] = "standard"
            mask = df_memory["ID"].isin(watched_flights_ids)
            df_memory.loc[mask, "status"] = "followed"

            # Créer la carte avec Plotly
            fig_map = px.scatter_mapbox(
                df_memory,
                lat="latitude",
                lon="longitude",
                hover_name="Flight",
                hover_data={"latitude": False, "longitude": False, "altitude": True, "velocity": True},
                color="status",
                color_discrete_map={"standard": "blue", "followed": "red"},
                zoom=6,
                size_max=15,
                title="Position des vols au-dessus de CDG"
            )
            fig_map.update_layout(mapbox_style="open-street-map")
            st.plotly_chart(fig_map, use_container_width=True)
        
        with col2:
            # Graphique: altitude vs vitesse
            st.subheader("Altitude et vitesse des vols")
            fig = px.bar(
                df_memory,
                x="Flight",
                y="altitude",
                color="velocity",
                labels={"altitude": "Altitude (m)", "Flight": "Indicatif", "velocity": "Vitesse (m/s)"}
            )
            st.plotly_chart(fig, use_container_width=True)
        
        st.divider()

        # Table de toutes les données
        st.subheader("Détail des vols détectés")
        st.dataframe(df_memory[["ID", "Flight", "longitude", "latitude", "altitude", "velocity"]], use_container_width=True)

        st.divider()

        # Section pour ajouter un vol à la surveillance
        st.subheader("Ajouter un vol à la surveillance")
        selected_id = st.selectbox("Sélectionnez un vol", df_memory["ID"].tolist())

        if st.button("Ajouter ce vol"):
            flight_row = df_memory[df_memory["ID"] == selected_id].iloc[0]
            followed_flight_id = flight_row["ID"]
            followed_flight_callsign = flight_row["Flight"]

            if add_watched_flight(followed_flight_id, followed_flight_callsign):
                st.success(f"{followed_flight_callsign} ajouté à la surveillance")
                st.rerun()
            else:
                st.error("Erreur lors de l'ajout du vol")


# ============================================
# ONGLET 2: VOLS SOUS SURVEILLANCE
# ============================================

with tab_bdd:
    st.subheader("Suivi des vols surveillés")

    # Récupérer tous les vols sous surveillance
    df_bdd = get_watched_flights()

    if df_bdd.empty:
        st.info("Aucun vol sous surveillance actuellement")
    else:
        watched_ids = df_bdd["icao24"].tolist()

        # Bouton pour actualiser les données
        if st.button("🔄 Actualiser les données radar"):
            live_flights = get_live_flights()
            if live_flights and "states" in live_flights:
                df = pd.DataFrame(live_flights["states"])
                df = clean_data(df)
                st.session_state["current_flights_tab2"] = df
            else:
                st.warning("Impossible de récupérer les données radar")

        # Déterminer quelle source de données utiliser
        df_memory = None
        
        if "current_flights_tab2" in st.session_state:
            df_memory = st.session_state["current_flights_tab2"].copy()
        elif "current_flights" in st.session_state:
            df_memory = st.session_state["current_flights"].copy()
        
        if df_memory is not None:
            # Filtrer pour ne garder que les vols surveillés
            mask_watched = df_memory["ID"].isin(watched_ids)
            df_live_watched = df_memory[mask_watched]

            if not df_live_watched.empty:
                st.success(f"{len(df_live_watched)} vol(s) surveillé(s) détecté(s) actuellement")

                # Carte des vols surveillés
                fig_watched = px.scatter_mapbox(
                    df_live_watched,
                    lat="latitude",
                    lon="longitude",
                    hover_name="Flight",
                    color="velocity",
                    zoom=5,
                    size_max=15,
                    hover_data={"latitude": False, "longitude": False, "altitude": True, "velocity": True}
                )
                fig_watched.update_layout(mapbox_style="open-street-map")
                st.plotly_chart(fig_watched, use_container_width=True)

                # Table avec les données
                st.dataframe(df_live_watched[["Flight", "altitude", "velocity", "longitude", "latitude"]], use_container_width=True)
            else:
                st.warning("Aucun vol surveillé détecté actuellement")
        else:
            st.info("Cliquez sur 'Actualiser les données radar' pour charger les vols")

        st.divider()

        # Liste des vols en surveillance
        st.subheader("Tous vos vols sous surveillance")
        st.dataframe(df_bdd, use_container_width=True)






