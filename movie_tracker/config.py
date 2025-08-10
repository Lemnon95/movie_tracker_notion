import os
import json
from typing import Tuple, Dict, Any

CONFIG_DIR = os.path.join(os.environ["USERPROFILE"], "Documents", "Movie_Tracker")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_ML_SETTINGS = {
    "features": {
        # Se True, includiamo anche la trama (da OMDb) nelle feature testuali finali (TF‑IDF)
        # Aumenta la “tematicità” ma può introdurre rumore se le trame sono generiche.
        "use_plot": True,
        # Quante parole massimo estrarre dalla trama (per limitare rumore e tempi)
        # Aumenta se vuoi più semantica di plot; diminuisci se noti drift/rumore.
        "plot_max_words": 25,
        # Pesi relativi dei token nelle feature (sia per ranking finale sia per discovery TF‑IDF)
        # Valori più alti => maggiore importanza di quel segnale.
        "weights": {
            # Aumenta se vuoi che l’autorevolezza/“firma” del regista guidi le raccomandazioni
            "director": 3,
            # Attori in comune: alza se ti interessa seguire cast ricorrenti
            "actor": 2,
            # Scrittura/sceneggiatura: utile se ti fidi del “tono” narrativo dello scrittore
            "writer": 2,
            # Generi: alza se vuoi raccomandazioni più “tematiche”
            "genre": 1,
            # Trama: alza se vuoi più semantica del plot (consigliato insieme a use_plot=True)
            "plot": 1,
            # Campi avanzati (se presenti nell’indice o dopo enrichment)
            "keywords": 1,  # parole-chiave narrative (se le indicizzi)
            "language": 1,  # lingua originale
            "country": 1,  # paese di produzione
            "decade": 1,  # es. "1990s" per affinità di periodo
        },
    },
    "tfidf": {
        # N‑gram usati dal TF‑IDF sui testi: (1,2) = unigrams + bigrams
        # Aumentare a (1,3) può catturare più contesto ma aumenta dimensione e tempi.
        "ngram_range": [1, 2],
        # Ignora termini troppo rari (comparsi in meno di min_df documenti).
        # Alzalo se vuoi ridurre rumore, abbassalo se il dataset è piccolo.
        "min_df": 2,
        # Ignora termini troppo comuni (presenti in >85% dei documenti).
        # Abbassalo se vedi che termini troppo diffusi “appiattiscono” le differenze.
        "max_df": 0.85,
        # Stopwords per i testi di trama (gli “entity token” tipo actor:XXXX non sono toccati)
        "stop_words": "english",
    },
    "blend": {
        # Pesi per il punteggio finale: combinazione di similarità TF‑IDF, qualità IMDb e “recency”
        # w_sim domina la coerenza con i tuoi anchor; abbassalo se vuoi dare più spazio a qualità/novità
        "w_sim": 0.70,
        # Quanto contano i rating IMDb (normalizzati circa su [0..1] da 5 a 10)
        "w_rating": 0.20,
        # Quanto conta la “recency” (film recenti spinti di più)
        "w_recency": 0.10,
        # Costante di decadimento (anni) per la recency: più alto = effetto più dolce/lento
        "recency_tau_years": 8,
    },
    # Penalizzazione per evitare troppe raccomandazioni dello stesso regista
    "diversity": {
        # Quanti titoli max per lo stesso regista prima di applicare una penalità
        "max_per_director": 2,
        # Intensità della penalità (0.15 = -15% di punteggio per gli extra)
        "penalty": 0.15,
    },
    "discovery": {
        # Filtro iniziale sull’indice IMDb: numero minimo di voti
        # Abbassa per esplorare titoli più di nicchia; alza per restare su film più “solidi”.
        "min_votes": 5000,
        # Finestra temporale dei film considerati in discovery
        "year_from": 1970,
        "year_to": 2100,
        # Quanti candidati grezzi (pre‑enrichment) tenere dalla discovery
        # Aumenta per avere più ampiezza, ma il TF‑IDF sarà più lento.
        "candidate_top_k": 200,
        # Quantile di eleggibilità sullo score di discovery (TF‑IDF preliminare)
        # 0.60 = tieni il top 40% (più selettivo). Abbassa (es. 0.50/0.40) per includere più titoli nell’enrichment.
        "eligibility_quantile": 0.60,
        # Filtro qualità prima dell’enrichment OMDb
        # Abbassa questi valori per aumentare il numero di titoli arricchiti; alzali per pulizia.
        "quality_min_rating": 6.5,
        "quality_min_votes": 2000,
        # Budget dinamico per quante chiamate OMDb fare:
        # max( top_k * per_top_k , anchors * per_anchor , min )
        # Aumenta per_top_k/per_anchor/min per spingere l’arricchimento (più lento).
        "enrich_budget": {"per_top_k": 7, "per_anchor": 5, "min": 30},
        # Campi da usare nella fase di discovery (matching + TF‑IDF preliminare)
        # Aggiungi/togli per sperimentare; ricorda che alcuni campi (language/country/keywords)
        # sono “placeholder” finché non li indicizzi/vai ad arricchirli da altre fonti.
        "include_fields": [
            "actors",
            "directors",
            "writers",
            "genres",
            "plot",  # in discovery viene ignorato dai dump IMDb standard; usato nel ranking finale dopo OMDb
            "keywords",  # richiede indicizzazione dedicata se vuoi usarli davvero in discovery
            "language",  # idem
            "country",  # idem
            "decade",  # derivato da year: utile se ti piace una certa “epoca”
        ],
    },
}


def ensure_config_file() -> str:
    if not os.path.exists(CONFIG_DIR):
        os.mkdir(CONFIG_DIR)
    if not os.path.exists(CONFIG_FILE):
        print(
            "Welcome to the Movie Tracker application! Please, configure your settings."
        )
        token = input("Enter your Notion integration token: ")
        db_id = input("Enter the Notion table's URL: ")
        omdb_api_key = input("Enter your OMDb API key: ")
        save_config(token, db_id, omdb_api_key)
    return CONFIG_FILE


def load_config(path: str) -> Tuple[str, str, str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if (
        ("TOKEN" not in config)
        or ("DATABASE_ID" not in config)
        or ("OMDB_API_KEY" not in config)
    ):
        token, db_id, omdb_api_key = update_config(path)
        with open(path, "r", encoding="utf-8") as f2:
            cfg2 = json.load(f2)
        ml_settings = cfg2.get("ML_SETTINGS", DEFAULT_ML_SETTINGS)
        return token, db_id, omdb_api_key, ml_settings

    if "ML_SETTINGS" not in config:
        config["ML_SETTINGS"] = DEFAULT_ML_SETTINGS
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

    ml_settings = config.get("ML_SETTINGS", DEFAULT_ML_SETTINGS)
    return config["TOKEN"], config["DATABASE_ID"], config["OMDB_API_KEY"], ml_settings


def save_config(token: str, db_id: str, omdb_api_key: str):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "TOKEN": token,
                "DATABASE_ID": db_id,
                "OMDB_API_KEY": omdb_api_key,
                "ML_SETTINGS": DEFAULT_ML_SETTINGS,
            },
            f,
            ensure_ascii=False,
            indent=4,
        )
    print("Configuration saved.")


def update_config(path: str) -> Tuple[str, str, str]:
    token = input("Please, enter your Notion integration token: ")
    db_id = input("Enter the Notion table's URL: ")
    omdb_api_key = input("Enter your OMDb API key: ")
    save_config(token, db_id, omdb_api_key)
    return token, db_id, omdb_api_key
