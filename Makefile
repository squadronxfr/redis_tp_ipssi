# Makefile — Commandes principales pour le projet TMDB × Redis
# Utilisation: `make <cible>`
# Exemple: `make install`, `make app`, `make notebook`

SHELL := /bin/bash

# Variables configurables (surchargables en ligne de commande ou via env)
PY ?= python3
VENV ?= .venv
PORT ?= 8501
REDIS_HOST ?= redis-16763.c304.europe-west1-2.gce.redns.redis-cloud.com
REDIS_PORT ?= 16763
DOTENV ?= .env

# Détection du dossier binaire de l'environnement virtuel (Windows vs Unix)
ifeq ($(OS),Windows_NT)
  VENV_BIN := $(VENV)/Scripts
else
  VENV_BIN := $(VENV)/bin
endif

PYTHON := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip
STREAMLIT := $(VENV_BIN)/streamlit
JUPYTER := $(VENV_BIN)/jupyter

.PHONY: help venv install notebook lab app app-port ping freeze clean

help: ## Affiche cette aide
	@echo "Cibles disponibles:" && \
	awk 'BEGIN {FS = ":.*##"}; /^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(VENV):
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip

venv: $(VENV) ## Crée un environnement virtuel .venv et met pip à jour

install: venv ## Installe les dépendances dans .venv
	$(PIP) install -r requirements.txt

notebook: install ## Ouvre le notebook Jupyter (main.ipynb)
	$(JUPYTER) notebook main.ipynb

lab: install ## Ouvre JupyterLab à la racine du projet
	$(JUPYTER) lab

app: install ## Lance l'application Streamlit (port par défaut 8501)
	$(STREAMLIT) run app_streamlit.py --server.port $(PORT)

app-port: ## Lance Streamlit sur un port spécifique: make app-port PORT=8502
	$(MAKE) app PORT=$(PORT)

ping: install ## Vérifie la connexion à Redis (via Python + .env)
	$(PYTHON) -c "import os, redis; from dotenv import load_dotenv; load_dotenv(os.getenv('DOTENV', '.env')); u=os.getenv('REDIS_USERNAME'); p=os.getenv('REDIS_PASSWORD'); host=os.getenv('REDIS_HOST','$(REDIS_HOST)'); port=int(os.getenv('REDIS_PORT','$(REDIS_PORT)')); r=redis.Redis(host=host, port=port, decode_responses=True, username=u, password=p); print('Redis PING: OK' if r.ping() else 'Redis PING: FAIL')"

freeze: install ## Écrit les versions exactes installées dans requirements.txt
	$(PIP) freeze > requirements.txt

clean: ## Nettoie fichiers temporaires (__pycache__, *.pyc)
	$(PYTHON) -c "import os, shutil; from pathlib import Path; [shutil.rmtree(str(d), ignore_errors=True) for d in Path('.').rglob('__pycache__')]; [os.remove(str(f)) for f in Path('.').rglob('*.pyc') if os.path.isfile(f)]; print('Nettoyage terminé')"
