# 📓 Changelog

All notable changes to this project will be documented in this file.

This project adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
and follows [Semantic Versioning](https://semver.org/).

---

## [1.1.0] - 2025-07-29

> **Note:**  
> This release introduces several changes due to new limitations imposed by IMDb, which restrict access to detailed movie data and high-resolution covers via third-party libraries.  
> As a result, Movie Tracker now relies primarily on the OMDb API for movie information and cover images.

### Changed
- 🔑 OMDb API integration: now uses a personal OMDb API key stored in the configuration file for all movie data retrieval.
- 🖼️ Improved cover quality: attempts to fetch higher resolution posters from OMDb when available.
- 🧩 Fallback logic: missing fields from IMDbPY are now automatically filled using OMDb data.

### Fixed
- 🐞 IMDb URL and cover fields are now always correctly populated and not truncated after updates.

---

## [1.0.0] - 2025-04-12
### Added
- 🎉 First stable release of Movie Tracker!
- 🎬 Ability to add new movies by IMDb ID
- 🔁 Support for updating existing movies without losing user-provided data (e.g. tags and personal ratings)
- 🧠 Integration with Notion API to store movies in your personal database
- 📝 Auto-generated logs saved in `Documents/Movie_Tracker/logs`
- 🛠 Configuration persistence via `config.json`
- 📦 Windows installer generated using Pynsist

---

