# 🎬 Movie Tracker Notion

**Movie Tracker Notion** is a Python-based console application that lets you track and manage movies in a beautiful [Notion](https://www.notion.so/) database — with metadata automatically fetched from IMDb!

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

These values will be saved in a config file located at:

`Documents/Movie_Tracker/config.json`

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