# Architettura e flussi

## Vista generale

Movie Tracker è un'applicazione console sincrona per gestire una libreria personale
in Notion. Non contiene recommender, ranking, machine learning, AI, download di dataset
o cache di dati per raccomandazioni.

```text
movie_tracker.main
  ├─ config ──> Documents/Movie_Tracker/config.json
  ├─ metadata
  │    ├─ TmdbProvider ──> metadati primari
  │    ├─ OmdbProvider ──> rating IMDb, completamento e fallback
  │    └─ TrackerMetadataService ──> composizione dei provider
  ├─ movie_inserter ──> payload, inserimento, aggiornamento e refresh
  └─ notion_api ──> Notion REST API
```

Tutte le integrazioni HTTP riusano `movie_tracker.http_client`, che applica timeout,
rispetta `Retry-After` sulle risposte HTTP 429 con al massimo due retry e traduce
problemi di rete, status HTTP e JSON invalido in errori applicativi.

## Configurazione

Il file runtime contiene:

```json
{
  "TOKEN": "...",
  "DATABASE_ID": "...",
  "DATA_SOURCE_ID": "...",
  "OMDB_API_KEY": "...",
  "TMDB_API_TOKEN": "...",
  "METADATA_REFRESH_DAYS": 150
}
```

`load_config()` normalizza gli ID Notion, aggiunge in modo incrementale token TMDB e
soglia refresh mancanti e rimuove l'obsoleta chiave `ML_SETTINGS` dalle configurazioni
create dalle versioni che includevano il recommender.

## Contratto Notion

| Proprietà | Tipo | Origine |
| --- | --- | --- |
| `Title` | title | TMDB/OMDb |
| `Tags` | multi_select | utente |
| `Plot` | rich_text | TMDB/OMDb |
| `Actors` | rich_text | TMDB/OMDb |
| `Directors` | rich_text | TMDB/OMDb |
| `Writers` | rich_text | TMDB/OMDb |
| `Year` | number | TMDB/OMDb |
| `Runtime` | number | TMDB/OMDb |
| `Rating - IMDb` | number | esclusivamente OMDb |
| `IMDb URL` | url | identità IMDb richiesta |
| `Cover` | files | TMDB, completamento OMDb |
| `Release Date` | date | TMDB/OMDb |
| `Last Seen` | date | utente |
| `My Score` | number | utente |
| `Metadata Source` | select | `TMDB` o `OMDb` |
| `Metadata Synced At` | date | sincronizzazione riuscita |

Gli aggiornamenti preservano sempre `Tags`, `My Score` e `Last Seen`.

## Acquisizione metadati

1. L'utente inserisce un IMDb ID.
2. TMDB risolve l'external ID e restituisce dettagli e credits.
3. OMDb viene sempre interrogato per il rating IMDb e completa i campi mancanti.
4. Se TMDB fallisce, OMDb diventa fallback completo.
5. Se OMDb fallisce ma TMDB riesce, i dati TMDB vengono mantenuti senza rating IMDb.
6. Se entrambi falliscono, viene sollevato un errore composto senza credenziali.
7. Prima di qualsiasi scrittura Notion, il risultato composto deve avere un titolo
   valido. Un titolo assente, vuoto o `N/A` interrompe inserimento, aggiornamento o
   refresh senza scrivere proprietà o timestamp di sincronizzazione.

La configurazione immagini TMDB viene letta da `/configuration`; la dimensione poster
è scelta solo tra quelle annunciate. Il miglioramento della cover tramite richieste
HEAD resta confinato al provider OMDb.

## Refresh e persistenza TMDB

Dopo la configurazione, prima del menu, l'app seleziona i record con
`Metadata Source = TMDB` più vecchi della soglia configurata, 150 giorni per default,
e li aggiorna automaticamente senza richiedere conferma. Il comando esplicito dal
menu conserva la richiesta di conferma. Entrambi i flussi mostrano il conteggio e
il riepilogo, continuano dopo errori isolati e aggiornano il timestamp soltanto con
il PATCH riuscito. Se non ci sono record da aggiornare, non contattano TMDB o OMDb.

Gli errori dei singoli film vengono scritti nel log di aggiornamento. Un errore
generale del refresh viene mostrato senza impedire l'accesso al menu. I record non
aggiornati conservano il timestamp precedente e rimangono candidati al successivo
avvio o a un nuovo tentativo manuale. Non esiste un servizio in background.

Nel [chiarimento dello staff TMDB](https://www.themoviedb.org/talk/6a54940acc8e2346a5b52b0b#6a5fadcbbf69fe558ed64652)
riportato dall'autore del progetto il 9 settembre 2026, Travis Bell conferma che,
per l'app locale e il database Notion personale descritti nella richiesta, è
accettabile aggiornare o rimuovere i metadati scaduti al successivo avvio. Riconosce
i limiti di controllo della cache in Notion e non considera necessario un servizio
sempre attivo per consentire questa persistenza. La fonte di questa annotazione è
la trascrizione fornita dall'autore; il thread non è stato verificabile direttamente
durante la revisione.

Il controllo all'avvio allinea il flusso al comportamento descritto nel chiarimento.
La soglia di 150 giorni è un margine applicativo; la risposta non approva la conservazione
indefinita senza refresh. Gli interventi sui metadati devono continuare a preservare
`Tags`, `My Score` e `Last Seen`.

## Attribuzione e distribuzione

This application uses TMDB and the TMDB APIs but is not endorsed, certified, or
otherwise approved by TMDB.

Il comando `About / Credits` stampa la dicitura nel terminale e apre una pagina HTML
locale inclusa nell'applicazione. La pagina mostra un logo TMDB approvato e non
modificato, meno prominente dell'identità Movie Tracker, e collega direttamente a
`https://www.themoviedb.org`. Gli asset vivono in `movie_tracker/assets/` e sono
inclusi esplicitamente nel package Python e nell'installer Pynsist.

L'app è progettata per uso non commerciale. Non contiene funzionalità di
raccomandazione, ML o AI. Prima di distribuire nuove versioni occorre comunque
ricontrollare i termini TMDB, mantenere l'attribuzione richiesta e rispettare i limiti
di persistenza dei contenuti.

`PRIVACY.md` documenta l'assenza di telemetria e backend dell'autore, il flusso
diretto verso i provider e la memorizzazione locale non cifrata delle credenziali.
`THIRD_PARTY_NOTICES.md` separa la licenza GPL del codice dai permessi necessari per
usare API, contenuti, marchi e loghi dei provider. L'autenticazione Notion usa una
integrazione interna creata e controllata dal singolo utente; l'autore non riceve il
token.

## Percorsi runtime

| Risorsa | Posizione/servizio |
| --- | --- |
| Configurazione | `%USERPROFILE%\Documents\Movie_Tracker\config.json` |
| Log aggiornamento | `...\logs\update_log.txt` |
| Log errore | `...\error_log.txt` |
| API Notion | `https://api.notion.com/v1` |
| API TMDB | `https://api.themoviedb.org/3` |
| API OMDb | `https://www.omdbapi.com/` |
