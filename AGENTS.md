# Movie Tracker — guida di lavoro per agenti

Questo file e la cartella `docs/` sono memoria tecnica per chi lavora sul repository. Prima di modificare il codice, leggere almeno `docs/ARCHITECTURE.md` e `docs/KNOWN_ISSUES.md`.

## Obiettivo del progetto

Movie Tracker è un'applicazione console Python per Windows che usa un database Notion come libreria personale di film. Inserisce e aggiorna metadati ottenuti da TMDB con completamento e rating IMDb da OMDb. Non include raccomandazioni, machine learning o funzionalità AI.

## Comandi utili

```powershell
# Avvio dal checkout
python -m movie_tracker.main

# Controllo sintattico senza contattare servizi esterni
python -m compileall -q movie_tracker

# Installazione dipendenze
python -m pip install -r requirements.txt

# Installazione dipendenze di sviluppo ed esecuzione test
python -m pip install -r requirements-dev.txt
python -m pytest

# Build installer Windows (Python 3.9 + Pynsist + NSIS)
pynsist installer.cfg
```

I test usano pytest e devono rimanere offline. Le funzioni che chiamano Notion, TMDB o OMDb non vanno eseguite durante verifiche automatiche senza mock: possono consumare quota o modificare il database dell'utente.

## Vincoli da preservare

- Non committare token Notion, chiavi OMDb, `config.json`, cache o dataset scaricati.
- La configurazione runtime vive in `%USERPROFILE%\Documents\Movie_Tracker\config.json`, non nel repository.
- La configurazione distingue il container Notion (`DATABASE_ID`) dalla tabella interrogabile (`DATA_SOURCE_ID`); non scambiarli nei payload o negli endpoint.
- I log di aggiornamento vivono in `%USERPROFILE%\Documents\Movie_Tracker\logs`.
- I nomi delle proprietà Notion sono attualmente un contratto applicativo. Prima di rinominarli, aggiornare inserimento, aggiornamento ed exporter insieme.
- Conservare i dati personali (`Tags`, `My Score`, `Last Seen`) durante l'aggiornamento dei metadati.
- Il target dichiarato dell'installer è Python 3.9 a 64 bit.

## Mappa rapida

- `movie_tracker/main.py`: bootstrap, menu e orchestrazione.
- `movie_tracker/config.py`: creazione, lettura e migrazione incrementale della configurazione.
- `movie_tracker/movie_inserter.py`: payload Notion, inserimento e aggiornamento.
- `movie_tracker/notion_api.py`: chiamate HTTP raw all'API Notion.
- `movie_tracker/notion_id.py`: normalizzazione di UUID e URL dei database Notion.
- `movie_tracker/metadata/`: modello neutrale, provider TMDB/OMDb e servizio di composizione del tracker.
- `installer.cfg`: build distributiva principale con Pynsist.
- `tools/gen_pynsist_wheels.py`: supporto alla preparazione delle wheel per il packaging.

## Prassi per le modifiche

1. Verificare prima il contratto dati descritto in `docs/ARCHITECTURE.md`.
2. Tenere separati metadati esterni e campi personali dell'utente.
3. Aggiungere test unitari con mock per ogni correzione alle API.
4. Eseguire almeno `python -m compileall -q movie_tracker`.
5. Se cambiano dipendenze o entry point, allineare `requirements.txt`, `pyproject.toml` e `installer.cfg`.
6. Per modifiche al packaging, verificare anche il job manuale `build-installer` in GitHub Actions.
7. Aggiornare questi documenti quando cambia un flusso, un percorso runtime o il contratto Notion.
