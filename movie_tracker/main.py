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
    from movie_tracker.recommender.notion_exporter import (
        export_movies_df,
    )
    from movie_tracker.recommender.content_based import recommend

    def main():
        try:
            config_path = ensure_config_file()
            token, database_id, omdb_api_key, ml_settings = load_config(config_path)

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
                    token, database_id, omdb_api_key = update_config(config_path)
                elif choice == "3":
                    update_movie(token, database_id, omdb_api_key)
                elif choice == "4":
                    mode = input(
                        "Recommendations mode: 1) In-Library  2) Discovery (IMDb+OMDb)  [1/2]: "
                    ).strip()
                    discovery = mode == "2"
                    try:
                        df = export_movies_df(token, database_id)
                        if df.empty:
                            print("No movies found in your Notion database.")
                        else:
                            top_k = ml_settings.get("top_k", 20)
                            min_score = ml_settings.get("min_score", 7.5)
                            recs = recommend(
                                df,
                                top_k,
                                min_score,
                                include_plot=False,
                                discovery=discovery,
                                omdb_api_key=omdb_api_key if discovery else "",
                                ml_settings=ml_settings,
                            )
                            if recs.empty:
                                print(
                                    "No recommendations yet. Add some scores (>= 7.5) to your movies."
                                )
                            else:
                                print("\n🎯 Recommendations:")
                                for i, row in enumerate(
                                    recs.itertuples(index=False), start=1
                                ):
                                    title = getattr(row, "title")
                                    sim = getattr(row, "similarity")
                                    actors = getattr(row, "actors")
                                    print(f"{i:>2}. {title}  (sim {sim:.3f})")
                                    if actors:
                                        print(f"    with: {actors[:120]}")
                    except Exception as e:
                        print(f"Failed to generate recommendations: {e}")
                elif choice == "5":
                    break
                else:
                    print("Invalid option. Choose 1 to 5.")
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
