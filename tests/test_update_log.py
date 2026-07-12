from movie_tracker.movie_inserter import _append_update_log


def test_update_log_appends_runs_instead_of_overwriting(tmp_path):
    _append_update_log(str(tmp_path), ["first run", "Updated 1"])
    _append_update_log(str(tmp_path), ["second run", "Updated 2"])

    assert (tmp_path / "update_log.txt").read_text(encoding="utf-8") == (
        "first run\nUpdated 1\n\nsecond run\nUpdated 2\n"
    )
