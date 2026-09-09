# Debito tecnico e punti da verificare

Il recommender e tutte le dipendenze ML sono stati rimossi. L'applicazione è limitata
al tracking personale Notion con metadati TMDB e completamento OMDb.

## Installazioni legacy con la stessa versione dichiarata

Una vecchia installazione Windows e le prime build del checkout TMDB dichiaravano
entrambe `1.2.0`. Per distinguerle, verificare il percorso del collegamento e i moduli
installati: `imdb_utils.py` con Cinemagoer identifica il codice legacy; la cartella
`metadata/` identifica il nuovo flusso. Il numero mostrato dall'installer da solo
non basta. La build corrente usa `1.3.0` in package e installer e mostra il numero
anche nel menu.

Nella diagnosi del 9 settembre 2026, un IMDb ID numerico incollato con uno spazio
finale causava la risposta OMDb `Incorrect IMDb ID.`. Il codice legacy proseguiva
comunque e creava una scheda priva di titolo e metadati. Il codice corrente
normalizza già ID e URL; un test offline verifica anche il parametro inviato a OMDb.
Il controllo sul titolo è ora presente anche nel checkout, dopo la composizione
dei provider e prima delle scritture Notion, con test per inserimento, aggiornamento
e refresh.

La riparazione locale dell'installazione legacy normalizza gli ID, usa HTTPS per
OMDb e interrompe inserimenti/aggiornamenti quando manca il titolo. I file originali
e i test offline della riparazione sono conservati nella cartella runtime
`Documents/Movie_Tracker/repairs/<timestamp>-imdb-id/`. Questa riparazione non è una
migrazione a TMDB: per quest'ultima servono il token TMDB e le proprietà Notion
`Metadata Source` (select) e `Metadata Synced At` (date). Le schede incomplete già
create richiedono una verifica separata, soprattutto se duplicate.

## Punti aperti

- Verificare periodicamente eventuali modifiche ai termini e ai requisiti di
  attribuzione TMDB.
- Il retry HTTP 429 è limitato a due tentativi e rispetta `Retry-After`; non esiste
  ancora un retry automatico per errori transitori diversi dal rate limiting.
- Le credenziali restano in chiaro nel `config.json`; questo rischio è documentato in
  `PRIVACY.md` e va rivalutato prima di trasformare l'app in un servizio pubblico.
- Verificare il job manuale `build-installer` dopo modifiche a dipendenze o packaging.
