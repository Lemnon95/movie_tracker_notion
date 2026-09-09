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

📥 You can download the latest Windows installer from the [Releases Page](https://github.com/Lemnon95/movie_tracker_notion/releases).

> 🧠 Inspired by the idea of maintaining a centralized movie list that stays updated without manual input.

---

## ✨ Features

- 🎥 Add movies by IMDb ID
- 🔁 Update existing movies while keeping your personal score and tags
- 🧠 Sync with a Notion database
- 🏷 Automatically fills: title, plot, cast, directors, runtime, cover, rating
- 💾 Keeps a log of updates in your Documents folder
- 📦 Windows installer available

---

## 📐 Notion Template

To get started, duplicate the template to your Notion workspace:

👉 [📋 Movie Tracker Template](https://simone-mille.notion.site/Movie-Tracker-Template-881d7724f3244634834dc3c0f97f4213)

---

## 🔧 Configuration

The first time you run Movie Tracker, it will ask you to enter:

1. **Your Notion integration token**
2. **The Notion database URL (template-based)**
3. **The Notion data source ID** (optional when the database has only one)
4. **Your OMDb API key** (required for fetching movie data and covers)
5. **Your TMDB API Read Access Token** (required for primary movie metadata)

The app detects and stores the database's data source automatically when there is only one. If the database contains multiple data sources, copy the intended ID from Notion's **Manage data sources** menu and enter it during configuration.

These values will be saved in a config file located at:

`Documents/Movie_Tracker/config.json`

The file is not encrypted. Use a dedicated Notion integration with access only to
the Movie Tracker database, keep the file private, and revoke the provider keys if it
is exposed. Each user creates their own local Notion integration; this personal-use
workflow does not require OAuth because the token is never received by the project
author.

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

### 📁 How to get the Notion database ID

1. Open your duplicated Movie Tracker template in Notion
2. Click “Share” → Invite your integration to the page
3. Copy the database link (it should end with a long string of letters/numbers)
4. Remove any parameters like `?v=` from the URL

> Example:  
> `https://www.notion.so/username/3f1b10c7f541400cb259bf6550a8fd4d`

From that link, the **database ID** is the long string at the end:

`3f1b10c7f541400cb259bf6550a8fd4d`

Once set up, you won’t need to enter this information again.  
You can always edit or reset the configuration via the app’s menu.

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
