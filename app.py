import requests as rq
import pandas as pd
import streamlit as st
import json
import sqlite3 as sql
from time import time

#----------- CONSTANTS --------------
#OpenSky column mapping
COL_ICAO24 = 0
COL_CALLSIGN = 1
COL_LONGITUDE = 5
COL_LATITUDE = 6
COL_ALTITUDE = 7
COL_VELOCITY = 9

#CDG BOUNDING BOX
CDG_ZONE = {
    'lamin': 48.5,
    'lomin': 2.0,
    'lamax': 49.5,
    'lomax': 3.5
}
def init_database():

    con = sql.connect("radar_database.db")
    cursor = con.cursor()

    #create database
    cursor.execute('''CREATE TABLE IF NOT EXISTS watched_flights(
                          icao24 TEXT PRIMARY KEY,
                          callsign TEXT,
                          added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                          note TEXT
                      )
     ''')
    con.commit()
    cursor.close()
    con.close()

def add_watched_flight(icao24,callsign,note=""):
    try:
        con = sql.connect("radar_database.db")
        cursor = con.cursor()

        request = '''INSERT OR REPLACE INTO watched_flights(icao24,callsign,note)
                  VALUES (?,?,?)'''
        cursor.execute(request,(icao24,callsign,note))
        con.commit()
        cursor.close()
        con.close()


    except Exception as e:
        print(f"sql error:{e}")
        return False



def get_watched_flights():
    try:
        con = sql.connect("radar_database.db")
        cursor = con.cursor()
        df = pd.read_sql_query("SELECT * FROM watched_flights ORDER BY added_at DESC",con)
        con.close()
        return df
    except Exception as e:
        print(f"error:{e}")
        return pd.DataFrame()



#Get credentials for Oauth2
def get_credentials(file_path):
    try:
        with open(file_path,"r") as file:
            credentials = json.load(file)
            return credentials["clientId"],credentials["clientSecret"]
    except FileNotFoundError:
        st.error("Credentials file not found")
        st.stop()
    except KeyError:
        print("Error: 'clientId' and 'clientSecret' not found")

#Get the access token for Oauth2
def get_access_token(client_id,client_secret):
    base_url ="https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

    payload = {"grant_type":"client_credentials",
               "client_id":client_id,
               "client_secret":client_secret,
               }
    try:
        response = rq.post(base_url, data=payload)
        if response.status_code == 200:
            access_token = response.json()["access_token"]
            return access_token
        else:
            print("authentication error:",response.status_code)
            return None

    except Exception as e:
        print(f"authentication error:{e}")
        return None

#Get the live flights state vectors in The Paris CDG bounding box
def get_live_flights():
    url = "https://opensky-network.org/api/states/all"

    headers = {"Authorization": f"Bearer {st.session_state['access_token']}"}
    params ={"lamin":CDG_ZONE["lamin"],
             "lomin":CDG_ZONE["lomin"],
             "lamax":CDG_ZONE["lamax"],
             "lomax":CDG_ZONE["lomax"],
             }

    try:
        response = rq.get(url,params =params,headers=headers)
        if response.status_code == 200:
            live_flights = response.json()
            return live_flights
        else:
            print("fetch error:", response.status_code)
            return None

    except Exception as e:
        print(f"fetch error:{e}")
        return None

def clean_data(df):
    # Cleaning
    df = df[[COL_ICAO24,COL_CALLSIGN,COL_LONGITUDE,COL_LATITUDE, COL_ALTITUDE,COL_VELOCITY]]
    df.columns = ["ID","Flight", "longitude", "latitude", "altitude", "velocity"]
    df = df.dropna(subset=["altitude"])

    return df

@st.cache_data(ttl=1500,show_spinner= True)  # 1500 secondes = 25 minutes
def get_cached_token(cid, secret):
    # Cette fonction ne sera réellement exécutée que toutes les 25 min
    return get_access_token(cid, secret)


# --- INITIALISATION AU CHARGEMENT ---
    # On récupère les identifiants
cid, secret = get_credentials("credentials.json")
#On demande le jeton une seule fois
token = get_cached_token(cid, secret)
if token:
    st.session_state['access_token'] = token
else:
    st.error("Impossible de s'authentifier. Vérifie tes credentials.")

#database setup
init_database()

#Streamlit page
st.title("Mini-ATC Paris CDG")

#onglets
tab_radar,tab_bdd = st.tabs(["Radar temps_reel","Vols surveillés"])

with tab_radar:
    #Refresh radar data but doesnt display it
    if st.button("Refresh radar data"):
        live_flights = get_live_flights()
        if live_flights and "states" in live_flights:
            df = pd.DataFrame(live_flights["states"])
            df = clean_data(df)

            #Stores the data in browser memory
            st.session_state["current_flights"] = df
        else:
            st.warning("Aucun vol détecté.")

    #Displays the data which is in the browser memory
    if "current_flights" in st.session_state:

        df_memory = st.session_state["current_flights"]


        st.metric("Vols détectés", len(df_memory), border=True)
        st.map(df_memory)
        st.dataframe(df_memory)

        #Display the interactive tools
        st.subheader("Sélectionner un Vol à surveiller")
        selected_id = st.selectbox("Sélectionnez l'ID du vol", df_memory["ID"].tolist())


        # --- TON PROCHAIN DÉFI SERA ICI ---
        if st.button ("Follow this flight"):
            followed_flight_id = selected_id
            followed_flight_callsign = df_memory[df_memory["ID"] == selected_id]["Flight"].values[0]

            add_watched_flight(followed_flight_id,followed_flight_callsign,note ="Surveillance UI")
            st.success(f"Vous surveillez maintenant le vol {followed_flight_callsign}")






with tab_bdd:
    st.subheader("Historique SQL")
    if st.button("Rafraîchir la base"):
        df_bdd = get_watched_flights()
        if not df_bdd.empty:
            st.dataframe(df_bdd)
        else:
            st.info("Empty database")






