import json
import hashlib
from pathlib import Path

from movie_tracker import config, main, menu


ROOT = Path(__file__).resolve().parents[1]


def test_recommender_source_tree_and_providers_are_absent():
    recommender_dir = ROOT / "movie_tracker" / "recommender"
    if recommender_dir.exists():
        assert not list(recommender_dir.rglob("*.py"))
    assert not (ROOT / "movie_tracker" / "metadata" / "cinemagoer_provider.py").exists()
    assert not (ROOT / "movie_tracker" / "metadata" / "recommender_service.py").exists()


def test_runtime_dependencies_have_no_ml_or_cinemagoer_packages():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    forbidden = (
        "cinemagoer",
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "sklearn",
    )
    assert all(package not in requirements for package in forbidden)


def test_main_has_no_recommender_imports_or_menu_flow():
    source = (ROOT / "movie_tracker" / "main.py").read_text(encoding="utf-8").lower()
    assert "movie_tracker.recommender" not in source
    assert "cinemagoer" not in source
    assert "get recommendations" not in source


def test_menu_exposes_tracking_only(capsys):
    menu.print_menu()
    output = capsys.readouterr().out.lower()
    assert "recommend" not in output
    assert "insert a new movie" in output
    assert "refresh stale tmdb metadata" in output


def test_credits_explicitly_state_absence_of_ml_ai_and_recommendations(capsys):
    opened = []

    def opener(url, new):
        opened.append((url, new))
        return True

    assert main._print_credits(opener=opener)
    output = capsys.readouterr().out.lower()
    assert "does not contain recommendation" in output
    assert "ml" in output and "ai" in output
    assert "not endorsed, certified, or otherwise approved by tmdb" in output
    assert "https://www.themoviedb.org" in output
    assert opened and opened[0][0].startswith("file:") and opened[0][1] == 2


def test_readme_contains_approved_tmdb_logo_and_notice():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'src="movie_tracker/assets/tmdb_logo.svg"' in readme
    normalized = " ".join(readme.split())
    assert "not endorsed, certified, or otherwise approved by TMDB" in normalized


def test_local_credits_page_contains_logo_notice_and_tmdb_link():
    page = ROOT / "movie_tracker" / "assets" / "credits.html"
    html = " ".join(page.read_text(encoding="utf-8").split())
    assert 'src="tmdb_logo.svg"' in html
    assert 'href="https://www.themoviedb.org"' in html
    assert "not endorsed, certified, or otherwise approved by TMDB" in html


def test_approved_tmdb_logo_is_bundled_unmodified():
    logo = ROOT / "movie_tracker" / "assets" / "tmdb_logo.svg"
    normalized = logo.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    digest = hashlib.sha256(normalized).hexdigest()
    assert digest == "1f9d6d66a2d6ac70b95eb7a2fb83c4e7284eaa881bad21ecda5b7d988cc07bf1"


def test_legacy_ml_settings_are_removed_during_config_migration(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "TOKEN": "notion",
                "DATABASE_ID": "248104cd-477e-80fd-b757-e945d38000bd",
                "DATA_SOURCE_ID": "",
                "OMDB_API_KEY": "omdb",
                "TMDB_API_TOKEN": "tmdb",
                "METADATA_REFRESH_DAYS": 150,
                "ML_SETTINGS": {"top_k": 20},
            }
        ),
        encoding="utf-8",
    )

    loaded = config.load_config(str(path))

    assert loaded == ("notion", "248104cd-477e-80fd-b757-e945d38000bd", "", "omdb")
    assert "ML_SETTINGS" not in json.loads(path.read_text(encoding="utf-8"))
