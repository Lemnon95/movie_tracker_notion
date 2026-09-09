from configparser import ConfigParser
from pathlib import Path

from movie_tracker import __version__

try:
    import tomllib
except ImportError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]


def _read_requirements_pins():
    pins = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==", 1)
            pins[name] = version
    return pins


def _read_installer_pins():
    config = ConfigParser()
    config.read(ROOT / "installer.cfg", encoding="utf-8")
    pins = {}
    for line in config["Include"]["pypi_wheels"].splitlines():
        line = line.strip()
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==", 1)
            pins[name] = version
    return pins


def test_runtime_dependency_pins_match_installer():
    requirements = _read_requirements_pins()
    installer = _read_installer_pins()

    assert {name: installer[name] for name in requirements} == requirements


def test_pynsist_is_the_only_installer_definition():
    config = ConfigParser()
    config.read(ROOT / "installer.cfg", encoding="utf-8")

    assert config["Application"]["entry_point"].strip() == "movie_tracker.main:main"
    assert not (ROOT / "main.spec").exists()


def test_project_metadata_dependencies_match_requirements():
    with (ROOT / "pyproject.toml").open("rb") as f:
        project = tomllib.load(f)["project"]
    metadata_pins = dict(item.split("==", 1) for item in project["dependencies"])

    assert metadata_pins == _read_requirements_pins()
    installer = ConfigParser()
    installer.read(ROOT / "installer.cfg", encoding="utf-8")
    assert project["version"] == installer["Application"]["version"] == __version__
    assert (
        installer["Build"]["installer_name"]
        == f"movietracker_{__version__}_installer.exe"
    )


def test_installer_contains_requests_transitive_dependency_and_credits_assets():
    installer_text = (ROOT / "installer.cfg").read_text(encoding="utf-8")
    installer_pins = _read_installer_pins()

    assert installer_pins["charset-normalizer"] == "2.0.12"
    assert installer_pins["urllib3"] == "1.26.20"
    assert "chardet" not in installer_pins
    assert "movie_tracker/assets > $INSTDIR\\pkgs\\movie_tracker" in installer_text
    assert "LICENSE.md > $INSTDIR" in installer_text
    assert "PRIVACY.md > $INSTDIR" in installer_text
    assert "THIRD_PARTY_NOTICES.md > $INSTDIR" in installer_text
