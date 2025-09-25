import os
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import streamlit as st
import redis
from dotenv import load_dotenv
import altair as alt


# -----------------------------
# Config & Redis connection
# -----------------------------

REDIS_HOST = "redis-16763.c304.europe-west1-2.gce.redns.redis-cloud.com"
REDIS_PORT = 16763


@st.cache_resource(show_spinner=False)
def get_redis_connection() -> redis.Redis:
    # Load .env at startup so users don't need to export variables in the shell
    load_dotenv(".env")
    username = os.getenv("REDIS_USERNAME")
    password = os.getenv("REDIS_PASSWORD")
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        username=username,
        password=password,
    )


db = get_redis_connection()


# -----------------------------
# Helpers
# -----------------------------

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def iter_movies_fields(field_names: List[str], batch_size: int = 300) -> Iterable[Tuple[str, Tuple[Any, ...]]]:
    """Yield (movie_key, field_values) for all movies in batches using pipeline."""
    members = list(db.smembers("tmdb:movies"))
    for i in range(0, len(members), batch_size):
        batch = members[i : i + batch_size]
        pipe = db.pipeline(transaction=False)
        for k in batch:
            pipe.hmget(k, *field_names)
        results = pipe.execute()
        for k, vals in zip(batch, results):
            yield k, tuple(vals)


def get_top_popular(limit: int = 20) -> List[Tuple[str, float]]:
    members = db.zrevrange("tmdb:idx:popularity", 0, limit - 1)
    if not members:
        return []
    pipe = db.pipeline(transaction=False)
    for k in members:
        pipe.hmget(k, "title", "popularity")
    data = pipe.execute()
    result: List[Tuple[str, float]] = []
    for title, pop in data:
        result.append(((title or "(untitled)"), safe_float(pop)))
    return result


def get_best_rated(min_votes: int = 1000, limit: int = 10) -> List[Tuple[str, float, int]]:
    """Top by vote_average with a minimum vote_count threshold."""
    results: List[Tuple[str, float, int]] = []
    start = 0
    batch = 200
    while len(results) < limit:
        chunk = db.zrevrange("tmdb:idx:vote_average", start, start + batch - 1)
        if not chunk:
            break
        pipe = db.pipeline(transaction=False)
        for k in chunk:
            pipe.hmget(k, "title", "vote_average", "vote_count")
        rows = pipe.execute()
        for title, vote, vcnt in rows:
            votes = int(safe_float(vcnt, 0))
            if votes >= min_votes:
                results.append(((title or "(untitled)"), safe_float(vote), votes))
                if len(results) >= limit:
                    break
        start += batch
    return results


def get_new_releases(min_year: int, limit: int = 20) -> List[Tuple[str, str]]:
    """Use release_date index encoded as YYYYMMDD to filter recent releases."""
    min_score = int(f"{min_year:04d}0101")
    members = db.zrevrangebyscore("tmdb:idx:release_date", "+inf", min_score, start=0, num=limit)
    pipe = db.pipeline(transaction=False)
    for k in members:
        pipe.hmget(k, "title", "release_date")
    rows = pipe.execute()
    return [((t or "(untitled)"), (d or "")) for t, d in rows]


def get_box_office_top(limit: int = 10) -> List[Tuple[str, float]]:
    members = db.zrevrange("tmdb:idx:revenue", 0, limit - 1)
    pipe = db.pipeline(transaction=False)
    for k in members:
        pipe.hmget(k, "title", "revenue")
    rows = pipe.execute()
    return [((t or "(untitled)"), safe_float(r)) for t, r in rows]


def get_genre_distribution(top_n: int = 12) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for _, (genres_json,) in iter_movies_fields(["genres"], batch_size=300):
        if not genres_json:
            continue
        try:
            arr = json.loads(genres_json)
            for g in arr:
                name = (g.get("name") or "").strip()
                if name:
                    counts[name] = counts.get(name, 0) + 1
        except Exception:
            continue
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return items[:top_n]


def get_runtime_distribution() -> Tuple[np.ndarray, float]:
    runtimes: List[float] = []
    for _, (rt,) in iter_movies_fields(["runtime"], batch_size=300):
        try:
            v = float(rt) if rt is not None and rt != "" else None
        except Exception:
            v = None
        if v and v > 0:
            runtimes.append(v)
    arr = np.array(runtimes) if runtimes else np.array([])
    mean_v = float(np.mean(arr)) if arr.size > 0 else 0.0
    return arr, mean_v


def get_rating_vs_votes_sample(max_points: int = 3000) -> Tuple[List[float], List[float]]:
    xs: List[float] = []
    ys: List[float] = []
    for _, (va, vc) in iter_movies_fields(["vote_average", "vote_count"], batch_size=300):
        vote_avg = safe_float(va)
        vote_cnt = safe_float(vc)
        if vote_avg > 0 and vote_cnt > 0:
            xs.append(vote_cnt)
            ys.append(vote_avg)
        if len(xs) >= max_points:
            break
    return xs, ys


def lookup_by_title(title: str) -> Optional[Dict[str, Any]]:
    key = db.hget("tmdb:idx:title_to_key", (title or "").strip().lower())
    if not key:
        return None
    fields = [
        "title",
        "release_date",
        "runtime",
        "vote_average",
        "vote_count",
        "popularity",
        "revenue",
        "genres",
        "overview",
    ]
    values = db.hmget(key, *fields)
    payload = {f: v for f, v in zip(fields, values)}
    # normalize types
    payload["vote_average"] = safe_float(payload.get("vote_average"))
    payload["vote_count"] = int(safe_float(payload.get("vote_count")))
    payload["popularity"] = safe_float(payload.get("popularity"))
    payload["revenue"] = safe_float(payload.get("revenue"))
    try:
        payload["genres"] = json.loads(payload.get("genres") or "[]")
    except Exception:
        payload["genres"] = []
    return payload


# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="TMDB × Redis", page_icon="🎬", layout="wide")

st.title("TMDB × Redis — WebApp")
with st.sidebar:
    st.header("Connexion Redis")
    if db.ping():
        info = db.info("memory")
        used = info.get("used_memory_human", "?")
        keys = db.dbsize()
        st.success(f"Connecté — Mémoire: {used}, Clés: {keys}")
    else:
        st.error("Échec de connexion Redis")

tab_pop, tab_best, tab_new, tab_box, tab_genres, tab_runtime, tab_scatter, tab_search = st.tabs(
    [
        "Populaires",
        "Meilleurs notés",
        "Nouveautés",
        "Box-office",
        "Genres",
        "Durées",
        "Notes vs Votes",
        "Recherche",
    ]
)

with tab_pop:
    st.subheader("Top populaires")
    limit = st.slider("Nombre de films", 5, 50, 20, 5)
    data = get_top_popular(limit)
    if data:
        rows_chart = [{"Titre": t, "Popularité": p} for t, p in data]
        chart = (
            alt.Chart(alt.Data(values=rows_chart))
            .mark_bar()
            .encode(
                y=alt.Y("Titre:N", sort=None),
                x=alt.X("Popularité:Q"),
                tooltip=["Titre:N", "Popularité:Q"],
            )
            .properties(height=max(250, 20 * len(rows_chart)))
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucune donnée.")

with tab_best:
    st.subheader("Meilleurs notés")
    col1, col2 = st.columns(2)
    with col1:
        min_votes = st.number_input("Seuil minimum de votes", min_value=0, value=1000, step=100)
    with col2:
        limit = st.slider("Top N", 5, 30, 10, 1)
    rows = get_best_rated(min_votes=min_votes, limit=limit)
    if rows:
        rows_rev = list(reversed(rows))
        rows_chart = [{"Titre": t, "Note moyenne": rating, "Votes": vcnt} for t, rating, vcnt in rows_rev]
        chart = (
            alt.Chart(alt.Data(values=rows_chart))
            .mark_bar(color="#4e79a7")
            .encode(
                y=alt.Y("Titre:N", sort=None),
                x=alt.X("Note moyenne:Q", scale=alt.Scale(domain=[0, 10])),
                tooltip=["Titre:N", "Note moyenne:Q", "Votes:Q"],
            )
            .properties(height=max(250, 20 * len(rows_chart)))
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucun résultat pour ce seuil.")

with tab_new:
    st.subheader("Nouveautés")
    year = st.slider("Année minimale", 1980, 2025, 2010, 1)
    rows = get_new_releases(min_year=year, limit=20)
    for title, rdate in rows:
        st.write(f"- {title} ({rdate})")

with tab_box:
    st.subheader("Box-office — Top 10")
    rows = get_box_office_top(limit=10)
    if rows:
        rows_chart = [{"Titre": t, "Recettes": r} for t, r in rows]
        chart = (
            alt.Chart(alt.Data(values=rows_chart))
            .mark_bar(color="#e15759")
            .encode(
                y=alt.Y("Titre:N", sort=None),
                x=alt.X("Recettes:Q"),
                tooltip=["Titre:N", "Recettes:Q"],
            )
            .properties(height=max(250, 20 * len(rows_chart)))
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucune donnée.")

with tab_genres:
    st.subheader("Répartition des genres — Top 12")
    items = get_genre_distribution(top_n=12)
    if items:
        rows_chart = [{"Genre": g, "Nombre de films": c} for g, c in items]
        chart = (
            alt.Chart(alt.Data(values=rows_chart))
            .mark_bar(color="#4e79a7")
            .encode(
                y=alt.Y("Genre:N", sort=None),
                x=alt.X("Nombre de films:Q"),
                tooltip=["Genre:N", "Nombre de films:Q"],
            )
            .properties(height=max(250, 20 * len(rows_chart)))
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucune donnée.")

with tab_runtime:
    st.subheader("Distribution des durées")
    arr, mean_v = get_runtime_distribution()
    if arr.size > 0:
        st.caption(f"Durée moyenne ≈ {mean_v:.0f} min")
        # Histogram bins
        hist, bin_edges = np.histogram(arr, bins=[0, 60, 90, 120, 150, 180, 240, 9999])
        labels = ["≤60", "60–90", "90–120", "120–150", "150–180", "180–240", ">240"]
        rows_chart = [{"Classe": lbl, "Films": int(cnt)} for lbl, cnt in zip(labels, hist.tolist())]
        chart = (
            alt.Chart(alt.Data(values=rows_chart))
            .mark_bar(color="#59a14f")
            .encode(
                x=alt.X("Classe:N", sort=None),
                y=alt.Y("Films:Q"),
                tooltip=["Classe:N", "Films:Q"],
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Aucune donnée.")

with tab_scatter:
    st.subheader("Note moyenne vs nombre de votes")
    xs, ys = get_rating_vs_votes_sample(max_points=5000)
    if xs:
        rows_chart = [{"votes": x, "note": y} for x, y in zip(xs, ys)]
        chart = (
            alt.Chart(alt.Data(values=rows_chart))
            .mark_circle(size=28, opacity=0.35, color="#edc949")
            .encode(
                x=alt.X("votes:Q", scale=alt.Scale(type="log")),
                y=alt.Y("note:Q", scale=alt.Scale(domain=[0, 10])),
                tooltip=["votes:Q", "note:Q"],
            )
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption("Axe x en échelle logarithmique.")
    else:
        st.info("Aucune donnée.")

with tab_search:
    st.subheader("Recherche par mots-clés (titre)")

    def search_by_title_keyword(keyword: str, max_results: int = 10) -> List[str]:
        """Recherche simple de titres contenant le mot-clé (fallback sans RediSearch)."""
        needle = (keyword or "").lower().strip()
        if not needle:
            return []

        results: List[str] = []
        movies = list(db.smembers("tmdb:movies"))
        batch_size = 200

        for i in range(0, len(movies), batch_size):
            batch = movies[i : i + batch_size]
            pipe = db.pipeline(transaction=False)
            for k in batch:
                pipe.hget(k, "title")
            titles = pipe.execute()
            for t in titles:
                if t and needle in t.lower():
                    results.append(t)
                    if len(results) >= max_results:
                        return results
        return results

    col_a, col_b = st.columns([3, 1])
    with col_a:
        q = st.text_input("Mots-clés dans le titre", value="")
    with col_b:
        max_n = st.number_input("Max résultats", min_value=1, max_value=100, value=10, step=1)

    if q:
        titles = search_by_title_keyword(q, max_results=int(max_n))
        if titles:
            st.markdown("**Résultats**:")
            for t in titles:
                st.write(f"- {t}")

            selected = st.selectbox("Voir les détails d'un film", options=["(aucun)"] + titles, index=0)
            if selected and selected != "(aucun)":
                movie = lookup_by_title(selected)
                if movie:
                    st.markdown(f"**{movie['title']}** — {movie.get('release_date') or ''}")
                    st.write(f"Note: {movie['vote_average']} ({movie['vote_count']} votes) · Popularité: {movie['popularity']:.1f}")
                    st.write(f"Recettes: ${int(movie['revenue']):,}")
                    genres = ", ".join([g.get("name", "") for g in (movie.get("genres") or [])])
                    if genres:
                        st.write(f"Genres: {genres}")
                    if movie.get("overview"):
                        st.write(movie["overview"])
        else:
            st.info("Aucun résultat.")


