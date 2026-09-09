# 🎬 Movie Tracker Notion

**Movie Tracker Notion** is a Python console application that manages a personal
Notion movie library. Tracker metadata comes primarily from TMDB, while OMDb supplies
the IMDb rating and completes missing fields. The application does not contain movie
recommendations, machine learning, AI functionality, or IMDb dataset downloads.

The Notion schema also requires `Metadata Source` (select) and `Metadata Synced At`
(date). Runtime configuration requires a TMDB API read access token. At startup,
the app automatically refreshes TMDB-backed records older than the configured age
threshold, 150 days by default. A manual refresh command is also available. There
is no background service: unsuccessful refreshes are reported and remain eligible
for retry on the next launch. Personal tags, scores, and viewing dates are preserved.

<a href="https://www.themoviedb.org">
  <img src="movie_tracker/assets/tmdb_logo.svg" alt="TMDB" width="80">
</a>

This application uses TMDB and the TMDB APIs but is not endorsed, certified, or
otherwise approved by TMDB. Its bundled API integration is intended for personal,
non-commercial use. Commercial operators must obtain their own permissions from the
service providers. This requirement applies to use of their services and does not
alter the GPL license covering Movie Tracker's source code.

Movie Tracker has no telemetry or author-operated backend. Credentials are stored
unencrypted in the local `config.json` and API requests go directly to Notion, TMDB,
and OMDb. Read [Privacy and credentials](PRIVACY.md) and
[Third-party notices](THIRD_PARTY_NOTICES.md) before use or distribution.

📥 **[Download Movie Tracker 1.3.0 for Windows (64-bit)](https://github.com/Lemnon95/movie_tracker_notion/releases/download/1.3.0/movietracker_1.3.0_installer.exe)**

The installer includes Python; a separate Python installation is not required.
See the [1.3.0 release notes and checksum](https://github.com/Lemnon95/movie_tracker_notion/releases/tag/1.3.0)
or browse [all releases](https://github.com/Lemnon95/movie_tracker_notion/releases).

---

## ✨ Features

- 🎥 Add movies by numeric IMDb ID, `tt` ID, or IMDb title URL
- 🔁 Update existing movies while keeping your personal score and tags
- 🧠 Sync with a Notion database
- 🏷 Automatically fills: title, plot, cast, directors, runtime, cover, rating
- 💾 Keeps a log of updates in your Documents folder
- 🔄 Refreshes stale TMDB metadata at startup and records the last successful sync
- ✅ Rejects missing or invalid movie titles before writing to Notion
- 📦 Windows installer available

---

## 📐 Notion Template

To get started, duplicate the template to your Notion workspace:

👉 [📋 Movie Tracker Template](https://simone-mille.notion.site/Movie-Tracker-Template-881d7724f3244634834dc3c0f97f4213)

After duplicating the template, check that the database includes these properties.
If either is missing, add it using the exact name and type:

| Property | Notion type | Options |
| --- | --- | --- |
| `Metadata Source` | Select | `TMDB`, `OMDb` |
| `Metadata Synced At` | Date | — |

Movie Tracker fills these fields when a movie is inserted or updated. The app does
not create database properties automatically.

---

## 🔧 Configuration

The first time you run Movie Tracker, it will ask you to enter:

1. **Your Notion integration token**
2. **The Notion database URL (template-based)**
3. **The Notion data source ID** (optional when the database has only one)
4. **Your OMDb API key** (required for IMDb ratings, missing fields, and fallback)
5. **Your TMDB API Read Access Token** (required for primary movie metadata)

The app detects and stores the database's data source automatically when there is only one. If the database contains multiple data sources, copy the intended ID from Notion's **Manage data sources** menu and enter it during configuration.

When upgrading an existing configuration that lacks a TMDB token, the app prompts
only for the missing **API Read Access Token** and preserves the other settings.
Once saved, the token is reused on subsequent launches. Each user supplies their
own credentials; the installer does not include any API tokens or keys.

These values will be saved in a config file located at:

`%USERPROFILE%\Documents\Movie_Tracker\config.json`

The file is not encrypted. Use a dedicated Notion integration with access only to
the Movie Tracker database, keep the file private, and revoke the provider keys if it
is exposed. Each user creates their own local Notion integration; this personal-use
workflow does not require OAuth because the token is never received by the project
author.

### 🎬 How to get your TMDB token

1. Sign in to your [TMDB account](https://www.themoviedb.org/).
2. Open the **API** section of your account settings and register your application.
   See TMDB's [getting started guide](https://developer.themoviedb.org/docs/getting-started).
3. Copy the **API Read Access Token** from the API settings page and paste it into
   Movie Tracker when prompted. The separate API key is not the value this prompt expects.

The application uses the token for Bearer authentication, as described in
[TMDB's authentication documentation](https://developer.themoviedb.org/docs/authentication-application).

### 🗝️ How to get your OMDb API key

1. Go to [OMDb API](https://www.omdbapi.com/apikey.aspx)
2. Request a free API key by entering your email and following the instructions
3. Once you receive your key, enter it when prompted by Movie Tracker

> **Note:**  
> Each user must use their own OMDb API key. Do not share your key publicly.

---

### 🧩 How to get your Notion token

1. Go to [Notion Developers](https://www.notion.so/my-integrations)
2. Create a new internal integration (give it a name like `Movie Tracker`)
3. Copy the **"Internal Integration Token"**

> Example token format: `secret_abc123def456...`

---

### 📁 How to connect your Notion database

1. Open your duplicated Movie Tracker database in Notion and grant your integration
   access to it.
2. Copy the database's full URL and paste it into Movie Tracker's setup prompt.
   The app extracts and normalizes the database ID automatically, including URLs
   with query parameters.
3. Leave the data source ID blank for automatic detection when the database has
   a single data source.

Once set up, you won’t need to enter this information again.  
You can always edit or reset the configuration via the app’s menu.

---

## ⬆️ Upgrading from an older version

1. Close Movie Tracker and keep a backup of `Documents/Movie_Tracker/config.json`.
2. For legacy installations, uninstall the old application to remove unused
   dependencies, then run the 1.3.0 installer.
3. Add the two metadata properties listed above to your existing Notion database
   if they are missing.
4. Launch Movie Tracker and enter your TMDB API Read Access Token if requested.
   The menu displays **Movie Tracker 1.3.0** so you can confirm which version is running.
5. Use **Update movie(s) with latest metadata** to update records created by older
   versions and populate their metadata source and synchronization date.

The automatic startup refresh selects records already marked as `TMDB` whose last
successful synchronization is at least 150 days old by default. Existing records
with empty metadata fields are not selected until they have been updated with this
version. The interval is configurable through `METADATA_REFRESH_DAYS` in the local
configuration file. Personal tags, scores, and viewing dates are preserved.

---

## 🛠 For Developers: Build the Installer (Windows)

Want to generate your own installer? Here's how.

### Prerequisites

- ✅ Python 3.9 (from [python.org](https://www.python.org/downloads/))
- ✅ [NSIS (Nullsoft Scriptable Install System)](https://nsis.sourceforge.io/Download)
- ✅ Pynsist (`pip install pynsist`)

### Build

From the root directory, run:

```bash
pynsist installer.cfg
```
The installer will be generated in the `build/nsis` directory.

### Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

GitHub Actions runs the suite on Windows with Python 3.9. A manual `workflow_dispatch` also builds the complete Pynsist/NSIS installer and publishes it as an artifact.
