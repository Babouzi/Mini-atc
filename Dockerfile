# Dockerfile - Définit comment construire l'image Docker pour Mini-ATC

# On utilise Python 3.11 slim (version légère, ~150MB au lieu de 1GB)
FROM python:3.11-slim

# Tous les fichiers seront copiés dans /app
WORKDIR /app

# Copier les fichiers du projet dans le conteneur
# On copie requirements.txt d'abord (pour profiter du cache Docker)
COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du projet
COPY app.py .
COPY entrypoint.sh .

# Exposer le port (Streamlit utilise le port 8501 par défaut)
EXPOSE 8501

# Ces variables d'environnement disent à Streamlit de:
# - Ne pas afficher le menu de config
# - Écouter sur 0.0.0.0 (accessible de l'extérieur)
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Rendre le script exécutable
RUN chmod +x /app/entrypoint.sh

# Commande de démarrage
# Le script crée le fichier secrets.toml à partir des variables d'env
# Puis lance Streamlit
ENTRYPOINT ["/app/entrypoint.sh"]
