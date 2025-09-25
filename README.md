# TMDB × Redis — Projet NoSQL (Médias & Divertissement)

Ce dépôt implémente une base NoSQL **Redis** pour un catalogue de films **TMDB** avec :
- Import CSV → **HASH** par film `tmdb:movie:{id}` + **SET** `tmdb:movies`
- Index applicatifs via **Sorted Sets** (popularité, notes, votes, recettes, date) et **Hash** (titre→clé)
- Requêtes métier utiles (populaires, meilleurs notés, nouveautés, box-office, par genre, recherche, détail)
- Notebook démontrant la démarche, le nettoyage et les requêtes
- WebApp Streamlit et scripts d’admin

---

## 1) Contexte & objectifs

- **Secteur** : Médias & divertissement (cinéma) — dataset Kaggle *TMDB 5000 Movies*.
- **Objectifs pédagogiques** : concevoir une DB NoSQL, **CRUD Python**, requêtes d’agrégation/viz, et mise en prod d’une WebApp.
- **Choix techniques** : Redis, stockage **HASH**, index **Sorted Sets**, recherche titre→clé en **HASH**.
- **Questions métier** : top genres, meilleurs notés (avec seuil de votes), tendances récentes, box office, navigation par genre.

---

## 2) Arborescence

```
.
├─ notebooks/
│  └─ tmdb_redis.ipynb                # Démarche, nettoyage, requêtes
├─ datasets/
│  └─ tmdb_5000_movies.csv            # Dataset Kaggle
├─ requirements.txt                   # Dépendances
├─ README.md                          # Ce fichier
└─ .env                               # Credentials Redis
```

---

## 3) Pré-requis & installation

- **Python** ≥ 3.10
- **Redis**

Installation des dépendances :
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Makefile — commandes principales

Le projet fournit un Makefile pour simplifier les tâches courantes. Assurez-vous d’être à la racine du dépôt.

- Prérequis: make (GNU Make), Python installé sur la machine.
- Le Makefile crée et utilise un environnement virtuel local .venv.

Commandes principales:
- make help — affiche la liste des commandes avec leur description
- make venv — crée l’environnement virtuel (.venv) et met pip à jour
- make install — installe les dépendances dans .venv (requirements.txt)
- make notebook — ouvre le notebook Jupyter main.ipynb
- make lab — ouvre JupyterLab à la racine du projet
- make app — lance l’application Streamlit sur le port par défaut 8501
- make app-port PORT=8502 — lance Streamlit sur un port spécifique
- make ping — teste la connexion Redis (nécessite .env)
- make freeze — fige les versions installées dans requirements.txt
- make clean — supprime les caches Python (__pycache__, *.pyc)

Exemples d’utilisation:
- Initialisation du projet:
  make install
- Lancer le notebook:
  make notebook
- Lancer JupyterLab:
  make lab
- Lancer la WebApp Streamlit (port par défaut):
  make app
- Lancer la WebApp Streamlit sur un autre port (ex: 8502):
  make app-port PORT=8502
- Vérifier la connexion Redis via .env:
  make ping

Astuce: sous Windows PowerShell, exécutez les commandes dans le terminal intégré de l’éditeur (ou WSL) si GNU Make n’est pas disponible nativement.

## 4) Configuration (.env)

Créer un fichier `.env` à la racine :
```env
REDIS_USERNAME=...
REDIS_PASSWORD=...
```

---

## 5) Lancer le notebook / script principal

1. **Connexion & diagnostic**
2. **Import CSV → Redis (HASH + SET)**
3. **Construction des index applicatifs**
4. **Vérification des index**
5. **Requêtes métier (populaires, meilleurs notés, nouveautés, box-office, par genre, recherche, détail)**
6. **CRUD**

---

## 6) Extraits de code clés

### Recherche sur le titre
```python
def search_by_title_keyword(keyword, max_results=10):
    """Recherche films par mot-clé dans le titre uniquement (fallback sans RediSearch)"""
    needle = (keyword or "").lower().strip()
    if not needle:
        return []

    results = []
    movies = list(db.smembers("tmdb:movies"))
    batch_size = 200

    for i in range(0, len(movies), batch_size):
        batch = movies[i:i+batch_size]
        pipe = db.pipeline(transaction=False)

        for k in batch:
            pipe.hget(k, "title")

        titles = pipe.execute()

        for title in titles:
            if title and needle in title.lower():
                results.append(title)
                if len(results) >= max_results:
                    return results

    return results
```

### Exemple : films les plus populaires
```python
members = db.zrevrange("tmdb:idx:popularity", 0, 19)
for rank, k in enumerate(members, start=1):
    title, pop = db.hmget(k, "title", "popularity")
    print(f"{rank:2d}. {title} (popularité={pop})")
```

---

## 7) Lancer la WebApp

`app_streamlit.py` (Windows PowerShell) :
```powershell
cd C:\Users\Kilian\Documents\tech\cours\redis_tp_ipssi
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Lancement (le fichier .env est chargé automatiquement par l'app)
.\.venv\Scripts\python.exe -m streamlit run app_streamlit.py
# Si besoin, changer de port
.\.venv\Scripts\python.exe -m streamlit run app_streamlit.py --server.port 8502
```

Fonctionnalités principales de la WebApp:
- Populaires (bar chart)
- Meilleurs notés (seuil de votes configurable)
- Nouveautés (filtre par année)
- Box-office — Top 10
- Répartition des genres (Top 12)
- Distribution des durées (histogramme agrégé)
- Notes vs Votes (scatter, axe X logarithmique)
- Recherche par mots-clés (liste de titres) + détail du film

---

## 8) Scripts d’administration

- Export NDJSON  
- Restore NDJSON  
- Bench (pipeline vs non, ZRANGE vs SCAN)  
- Sauvegardes RDB/AOF

---

## 9) Trello & Slides

- **Trello** : organisation Backlog / À faire / En cours / Terminé  
- **Support de présentation** : slides + vidéo démo

---

## 10) Dépannage

- **OutOfMemoryError (maxmemory)** : rogner `overview`, pipelines par petits lots (50–200).  
- **CSV introuvable** : vérifier `datasets/tmdb_5000_movies.csv`.  
- **Connexion Redis** : vérifier `.env`.

---

## 11) Auteurs

- Projet — Master Big Data & IA  
- Équipe : *TEROSIER Eddy*,*TIGNOKPA Carolle*, *TOMEN NANA Samuel*, *TROUET Killian*  