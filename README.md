# 🎬 Movie Tracker Notion

**Movie Tracker Notion** is a Python-based console application that lets you track and manage movies in a beautiful [Notion](https://www.notion.so/) database — with metadata automatically fetched from IMDb!

📥 You can download the latest Windows installer from the [Releases Page](https://github.com/YOUR_USERNAME/movie_tracker_notion/releases).

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