from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_privacy_notice_documents_local_plaintext_credentials_and_no_telemetry():
    privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")

    assert "does not include telemetry" in privacy
    assert "stored unencrypted" in privacy
    assert "config.json" in privacy
    assert "does not require OAuth" in privacy
    assert "Revoke or delete the Notion integration" in privacy


def test_third_party_notice_separates_code_license_from_api_permissions():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    normalized = " ".join(notices.split())

    assert "software license does not grant rights to third-party APIs" in notices
    assert "not endorsed, certified, or otherwise approved by TMDB" in normalized
    assert "personal, non-commercial use" in notices
    assert "https://www.omdbapi.com/legal.htm" in notices
    assert "Developer-Terms" in notices


def test_local_credits_disclose_provider_flow_and_plaintext_storage():
    credits = (ROOT / "movie_tracker/assets/credits.html").read_text(encoding="utf-8")

    assert "personal, non-commercial use" in credits
    assert "no telemetry or author-operated backend" in credits
    assert "stored unencrypted" in credits
    assert "https://www.omdbapi.com/legal.htm" in credits
