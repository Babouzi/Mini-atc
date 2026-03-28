#!/bin/bash
# Script d'entrée pour créer le fichier secrets.toml à partir des variables d'env

# Créer le dossier .streamlit s'il n'existe pas
mkdir -p /app/.streamlit

# Créer le fichier secrets.toml avec les variables d'env
cat > /app/.streamlit/secrets.toml << EOF
clientId = "${STREAMLIT_CLIENTID}"
clientSecret = "${STREAMLIT_CLIENTSECRET}"
EOF

# Lancer Streamlit
exec streamlit run app.py
