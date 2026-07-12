# Privacy and credentials

Movie Tracker is a local console application. The project author does not operate a
backend for the application, does not include telemetry, and does not collect or
receive users' movie libraries, API keys, or Notion integration tokens.

## External services

The application contacts Notion, TMDB, and OMDb directly from the user's computer.
Those services receive the requests and associated technical information according
to their own privacy policies and terms. Movie Tracker does not proxy those requests.

## Local storage

The following values are stored unencrypted in
`%USERPROFILE%\Documents\Movie_Tracker\config.json`:

- the user's Notion internal integration token;
- the Notion database and data source identifiers;
- the user's OMDb API key;
- the user's TMDB API Read Access Token;
- the metadata refresh interval.

Anyone who can read that Windows account's files may be able to use those
credentials. Use a dedicated Notion integration with access only to the Movie
Tracker database, do not share `config.json`, and never commit it to source control.

## Notion authentication

Movie Tracker does not require OAuth because each user creates and controls their
own Notion internal integration. Its token is entered directly into the local
application and is never sent to the project author. This authentication model is
intended for personal, local use and is not a hosted or public Notion integration.

## Revocation and deletion

To stop using Movie Tracker:

1. Revoke or delete the Notion integration in Notion.
2. Revoke the TMDB token and OMDb key in the respective provider accounts.
3. Delete `%USERPROFILE%\Documents\Movie_Tracker\config.json` and the optional log
   files in the same directory.
4. Delete TMDB- and OMDb-derived metadata from the Notion database, or delete the
   dedicated database entirely. Personal fields such as tags and scores should be
   exported first if they need to be retained.

The current application does not perform this final remote-data deletion
automatically.
