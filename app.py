import requests as rq
import pandas as pd
import streamlit as st
import json


def get_credentials(file_path):
    try:
        with open(file_path,"r") as file:
            credentials = json.load(file)
            return credentials["clientId"],credentials["clientSecret"]
    except FileNotFoundError:
        print("Error: credentials file not found")
    except KeyError:
        print("Error: 'clientId' and 'clientSecret' not found")


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
        print(f"authentication error:{e}",response.status_code)
        return None

def get_live_flights():
    url = "https://opensky-network.org/api/states/all"
    headers = {"Authorization": f"Bearer {TOKEN}"}
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




CLIENT_ID, CLIENT_SECRET = get_credentials("credentials.json")
TOKEN = get_access_token()

CDG_ZONE = {
    'lamin': 48.5,
    'lomin': 2.0,
    'lamax': 49.5,
    'lomax': 3.5
}




