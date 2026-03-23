# Mini-ATC: Radar de trafic aérien Paris CDG
# Affiche les vols en temps réel au-dessus de CDG via l'API OpenSky Network
# Permet de surveiller des vols spécifiques en base de données

import requests as rq
import pandas as pd
import streamlit as st
import sqlite3 as sql
import plotly.express as px
from datetime import datetime, timedelta

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

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
TOKEN_REFRESH_MARGIN = 30  # Renouvellement 30s avant expiration


# ============================================
# TOKEN MANAGER
# ============================================

class TokenManager:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.expires_at = None

    def get_token(self):
        """Retourne un token valide, le renouvelle automatiquement si nécessaire."""
        if self.token and self.expires_at and datetime.now() < self.expires_at:
            return self.token
        return self._refresh()

    def _refresh(self):
        """Récupère un nouveau token auprès du serveur d'authentification OpenSky."""
        r = rq.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        r.raise_for_status()

        data = r.json()
        self.token = data["access_token"]
        expires_in = data.get("expires_in", 1800)
        self.expires_at = datetime.now() + timedelta(seconds=expires_in - TOKEN_REFRESH_MARGIN)
        return self.token

    def headers(self):
        """Retourne les headers HTTP avec un Bearer token valide."""
        return {"Authorization": f"Bearer {self.get_token()}"}


# ============================================
# CREDENTIALS
# ============================================

def get_credentials():
    """
    Lit les credentials OpenSky depuis st.secrets.
    Fonctionne identiquement en local (.streamlit/secrets.toml)
    et sur Streamlit Community Cloud (dashboard Secrets).
    """
    try:
        return st.secrets["clientId"], st.secrets["clientSecret"]
    except KeyError:
        st.error("Secrets manquants. Configurez .streamlit/secrets.toml en local ou le dashboard sur Streamlit Cloud.")
        st.stop()


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

        cursor.execute('SELECT icao24 FROM watched_flights WHERE icao24 = ?', (icao24,))
        exists = cursor.fetchone() is not None

        if exists:
            cursor.execute('''UPDATE watched_flights SET callsign = ?, note = ? WHERE icao24 = ?''',
                         (callsign, note, icao24))
        else:
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
# API OPENSKY FUNCTIONS
# ============================================

def get_live_flights():
    """Récupère les vols en direct au-dessus de CDG via l'API OpenSky"""
    url = "https://opensky-network.org/api/states/all"
    params = {
        "lamin": CDG_ZONE["lamin"],
        "lomin": CDG_ZONE["lomin"],
        "lamax": CDG_ZONE["lamax"],
        "lomax": CDG_ZONE["lomax"],
    }

    try:
        tm = st.session_state["token_manager"]
        response = rq.get(url, params=params, headers=tm.headers())

        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur API: {response.status_code}")
            return None

    except Exception as e:
        st.error(f"Erreur réseau: {e}")
        return None

def clean_data(df):
    """Nettoie les données récupérées de l'API OpenSky"""
    df = df[[COL_ICAO24, COL_CALLSIGN, COL_LONGITUDE, COL_LATITUDE, COL_ALTITUDE, COL_VELOCITY]]
    df.columns = ["ID", "Flight", "longitude", "latitude", "altitude", "velocity"]
    df["Flight"] = df["Flight"].str.strip()
    df = df.dropna(subset=["altitude"])
    return df


# ============================================
# INITIALISATION
# ============================================

if "token_manager" not in st.session_state:
    cid, secret = get_credentials()
    st.session_state["token_manager"] = TokenManager(cid, secret)

if "db_initialized" not in st.session_state:
    init_database()
    st.session_state["db_initialized"] = True


# ============================================
# INTERFACE STREAMLIT
# ============================================

tab_radar, tab_bdd = st.tabs(["Radar temps réel", "Vols surveillés"])


# ============================================
# ONGLET 1: RADAR EN TEMPS RÉEL
# ============================================

with tab_radar:
    if st.button("🔄 Actualiser le radar"):
        live_flights = get_live_flights()
        if live_flights and "states" in live_flights:
            df = pd.DataFrame(live_flights["states"])
            df = clean_data(df)
            st.session_state["current_flights"] = df
        else:
            st.warning("Aucun vol détecté.")

    if "current_flights" in st.session_state:
        df_memory = st.session_state["current_flights"].copy()

        total_flights = len(df_memory)
        max_altitude = int(df_memory["altitude"].max())
        max_speed = int(df_memory["velocity"].max() * 3.6)

        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric(label="Vols détectés", value=total_flights)
        kpi2.metric(label="Altitude max (m)", value=max_altitude)
        kpi3.metric(label="Vitesse max (km/h)", value=max_speed)
        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            watched_flights_df = get_watched_flights()
            watched_flights_ids = watched_flights_df["icao24"].tolist() if not watched_flights_df.empty else []

            df_memory["status"] = "standard"
            df_memory.loc[df_memory["ID"].isin(watched_flights_ids), "status"] = "followed"

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

        st.subheader("Détail des vols détectés")
        st.dataframe(df_memory[["ID", "Flight", "longitude", "latitude", "altitude", "velocity"]], use_container_width=True)

        st.divider()

        st.subheader("Ajouter un vol à la surveillance")
        selected_id = st.selectbox("Sélectionnez un vol", df_memory["ID"].tolist())

        if st.button("Ajouter ce vol"):
            flight_row = df_memory[df_memory["ID"] == selected_id].iloc[0]
            if add_watched_flight(flight_row["ID"], flight_row["Flight"]):
                st.success(f"{flight_row['Flight']} ajouté à la surveillance")
                st.rerun()
            else:
                st.error("Erreur lors de l'ajout du vol")


# ============================================
# ONGLET 2: VOLS SOUS SURVEILLANCE
# ============================================

with tab_bdd:
    st.subheader("Suivi des vols surveillés")

    df_bdd = get_watched_flights()

    if df_bdd.empty:
        st.info("Aucun vol sous surveillance actuellement")
    else:
        watched_ids = df_bdd["icao24"].tolist()

        if st.button("🔄 Actualiser les données radar"):
            live_flights = get_live_flights()
            if live_flights and "states" in live_flights:
                df = pd.DataFrame(live_flights["states"])
                df = clean_data(df)
                st.session_state["current_flights_tab2"] = df
            else:
                st.warning("Impossible de récupérer les données radar")

        df_memory = None

        if "current_flights_tab2" in st.session_state:
            df_memory = st.session_state["current_flights_tab2"].copy()
        elif "current_flights" in st.session_state:
            df_memory = st.session_state["current_flights"].copy()

        if df_memory is not None:
            df_live_watched = df_memory[df_memory["ID"].isin(watched_ids)]

            if not df_live_watched.empty:
                st.success(f"{len(df_live_watched)} vol(s) surveillé(s) détecté(s) actuellement")

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

                st.dataframe(df_live_watched[["Flight", "altitude", "velocity", "longitude", "latitude"]], use_container_width=True)
            else:
                st.warning("Aucun vol surveillé détecté actuellement")
        else:
            st.info("Cliquez sur 'Actualiser les données radar' pour charger les vols")

        st.divider()

        st.subheader("Tous vos vols sous surveillance")
        st.dataframe(df_bdd, use_container_width=True)
