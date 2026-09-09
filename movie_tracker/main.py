import os
import traceback

try:
    from movie_tracker.config import (
        CONFIG_DIR,
        ensure_config_file,
        load_config,
        load_metadata_refresh_days,
        load_tmdb_token,
        save_data_source_id,
        update_config,
    )
    from movie_tracker.credits import show_credits
    from movie_tracker.http_client import HttpClientError
    from movie_tracker.menu import print_menu
    from movie_tracker.metadata import MetadataError
    from movie_tracker.movie_inserter import (
        insert_movie,
        refresh_stale_movies,
        update_movie,
    )
    from movie_tracker.notion_api import NotionApiError, resolve_data_source_id

    def _load_runtime_config(config_path: str):
        token, database_id, data_source_id, omdb_api_key = load_config(config_path)
        tmdb_api_token = load_tmdb_token(config_path)
        refresh_days = load_metadata_refresh_days(config_path)
        resolved_data_source_id = resolve_data_source_id(
            token, database_id, data_source_id
        )
        if resolved_data_source_id != data_source_id:
            data_source_id = save_data_source_id(config_path, resolved_data_source_id)
        return (
            token,
            database_id,
            data_source_id,
            omdb_api_key,
            tmdb_api_token,
            refresh_days,
        )

    def _print_credits(opener=None) -> bool:
        return show_credits() if opener is None else show_credits(opener=opener)

    def _run_metadata_refresh(
        token,
        data_source_id,
        omdb_api_key,
        tmdb_api_token,
        refresh_days,
        automatic=False,
    ):
        if automatic:
            print("Checking for stale TMDB metadata...")
        try:
            refresh_stale_movies(
                token,
                data_source_id,
                omdb_api_key,
                tmdb_api_token,
                max_age_days=refresh_days,
                confirm=None if automatic else input,
            )
        except (ValueError, MetadataError, NotionApiError, OSError) as exc:
            print(f"Unable to refresh TMDB metadata: {exc}")
            print("You can retry using menu option 4 or restart the application.")

    def main():
        try:
            config_path = ensure_config_file()
            (
                token,
                database_id,
                data_source_id,
                omdb_api_key,
                tmdb_api_token,
                refresh_days,
            ) = _load_runtime_config(config_path)

            _run_metadata_refresh(
                token,
                data_source_id,
                omdb_api_key,
                tmdb_api_token,
                refresh_days,
                automatic=True,
            )

            while True:
                print_menu()
                choice = input("Enter your choice: ")
                if choice == "1":
                    try:
                        status, title = insert_movie(
                            token, data_source_id, omdb_api_key, tmdb_api_token
                        )
                        print(
                            f"{title} successfully added!"
                            if status == 200
                            else f"Failed to add {title}."
                        )
                    except (ValueError, MetadataError, NotionApiError) as exc:
                        print(f"Unable to add movie: {exc}")
                elif choice == "2":
                    with open(config_path, "r", encoding="utf-8") as config_file:
                        previous_config = config_file.read()
                    try:
                        update_config(config_path)
                        (
                            token,
                            database_id,
                            data_source_id,
                            omdb_api_key,
                            tmdb_api_token,
                            refresh_days,
                        ) = _load_runtime_config(config_path)
                        print("Configuration updated.")
                    except (ValueError, NotionApiError) as exc:
                        with open(config_path, "w", encoding="utf-8") as config_file:
                            config_file.write(previous_config)
                        print(f"Unable to update configuration: {exc}")
                elif choice == "3":
                    try:
                        update_movie(
                            token, data_source_id, omdb_api_key, tmdb_api_token
                        )
                    except (ValueError, MetadataError, NotionApiError) as exc:
                        print(f"Unable to update movies: {exc}")
                elif choice == "4":
                    _run_metadata_refresh(
                        token,
                        data_source_id,
                        omdb_api_key,
                        tmdb_api_token,
                        refresh_days,
                    )
                elif choice == "5":
                    _print_credits()
                elif choice == "6":
                    break
                else:
                    print("Invalid option. Choose 1 to 6.")
        except (ValueError, MetadataError, NotionApiError, HttpClientError) as exc:
            print(f"Configuration or service error: {exc}")
            input("Press Enter to exit...")
        except Exception:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            log_path = os.path.join(CONFIG_DIR, "error_log.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            print("An error occurred. Details written to error_log.txt")
            input("Press Enter to exit...")

    if __name__ == "__main__":
        main()

except Exception:
    fallback_dir = os.path.expanduser("~")
    fallback_log = os.path.join(fallback_dir, "movie_tracker_fatal_error.txt")
    with open(fallback_log, "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    input(
        "A fatal error occurred. Log written to your home directory. Press Enter to close..."
    )
