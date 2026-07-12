# Debito tecnico e punti da verificare

Il recommender e tutte le dipendenze ML sono stati rimossi. L'applicazione è limitata
al tracking personale Notion con metadati TMDB e completamento OMDb.

## Punti aperti

- Verificare periodicamente eventuali modifiche ai termini e ai requisiti di
  attribuzione TMDB.
- Valutare un avviso più evidente quando esistono record TMDB oltre la soglia di
  refresh configurata.
- Definire una strategia di retention che non dipenda dall'esecuzione manuale
  dell'applicazione.
- Il retry HTTP 429 è limitato a due tentativi e rispetta `Retry-After`; non esiste
  ancora un retry automatico per errori transitori diversi dal rate limiting.
- Le credenziali restano in chiaro nel `config.json`; questo rischio è documentato in
  `PRIVACY.md` e va rivalutato prima di trasformare l'app in un servizio pubblico.
- Verificare il job manuale `build-installer` dopo modifiche a dipendenze o packaging.
