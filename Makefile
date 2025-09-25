# Makefile — Commandes principales pour le projet TMDB × Redis
# Utilisation: `make <cible>`
# Exemple: `make install`, `make app`, `make notebook`

SHELL := /bin/bash
PY ?= python3
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
STREAMLIT := $(VENV)/bin/streamlit
JUPYTER := $(VENV)/bin/jupyter
PORT ?= 8501

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
	$(PYTHON) -c "from dotenv import load_dotenv;import os,redis;load_dotenv('.env');u=os.getenv('REDIS_USERNAME');p=os.getenv('REDIS_PASSWORD');r=redis.Redis(host='redis-16763.c304.europe-west1-2.gce.redns.redis-cloud.com',port=16763,decode_responses=True,username=u,password=p);print('Redis PING: OK' if r.ping() else 'Redis PING: FAIL')"

freeze: install ## Écrit les versions exactes installées dans requirements.txt
	$(PIP) freeze > requirements.txt

clean: ## Nettoie fichiers temporaires (__pycache__, *.pyc)
	rm -rf **/__pycache__
	find . -type f -name "*.py[co]" -delete
