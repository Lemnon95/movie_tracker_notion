import traceback
import os

try:
    from movie_tracker.config import (
        CONFIG_DIR,
        ensure_config_file,
        load_config,
        update_config,
    )
    from movie_tracker.movie_inserter import insert_movie, update_movie
    from movie_tracker.menu import print_menu

    def main():
        try:
            config_path = ensure_config_file()
            token, database_id, omdb_api_key = load_config(config_path)

            while True:
                print_menu()
                choice = input("Enter your choice: ")
                if choice == "1":
                    status, title = insert_movie(token, database_id, omdb_api_key)
                    print(
                        f"{title} successfully added!"
                        if status == 200
                        else f"Failed to add {title}."
                    )
                elif choice == "2":
                    token, database_id = update_config(config_path)
                elif choice == "3":
                    update_movie(token, database_id, omdb_api_key)
                elif choice == "4":
                    break
                else:
                    print("Invalid option. Choose 1 to 4.")
        except Exception:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            log_path = os.path.join(CONFIG_DIR, "error_log.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            print("❌ An error occurred. Details written to error_log.txt")
            input("Press Enter to exit...")

    if __name__ == "__main__":
        main()

except Exception as e:
    fallback_dir = os.path.expanduser("~")
    fallback_log = os.path.join(fallback_dir, "movie_tracker_fatal_error.txt")
    with open(fallback_log, "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    input(
        "A fatal error occurred. Log written to your home directory. Press Enter to close..."
    )
