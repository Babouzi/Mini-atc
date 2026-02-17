import requests as rq
import pandas as pd
import streamlit as st
import json

#CDG BOUNDING BOX
CDG_ZONE = {
    'lamin': 48.5,
    'lomin': 2.0,
    'lamax': 49.5,
    'lomax': 3.5
}

#Get credentials for Oauth2
def get_credentials(file_path):
    try:
        with open(file_path,"r") as file:
            credentials = json.load(file)
            return credentials["clientId"],credentials["clientSecret"]
    except FileNotFoundError:
        print("Error: credentials file not found")
    except KeyError:
        print("Error: 'clientId' and 'clientSecret' not found")

#Get the access token for Oauth2
def get_access_token():
    base_url ="https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

    payload = {"grant_type":"client_credentials",
               "client_id":CLIENT_ID,
               "client_secret":CLIENT_SECRET,
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
    if "access_token" not in st.session_state:
        st.session_state["access_token"] = get_access_token()

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
    df = df[[1, 5, 6, 7, 9]]
    df.columns = ["Flight", "longitude", "latitude", "altitude", "velocity"]
    df = df.dropna(subset=["altitude"])

    return df

CLIENT_ID,CLIENT_SECRET = get_credentials("credentials.json")

#Streamlit page
st.title("Mini-ATC Paris CDG")
if st.button("Get flights"):
    live_flights = get_live_flights()
    if live_flights and "states" in live_flights:
        df = pd.DataFrame(live_flights["states"])
        df = clean_data(df)
        st.write(f"Vols détectés {len(df)}")
        st.dataframe(df)
        st.map(df)

    else:
        st.warning("No flights detected")





