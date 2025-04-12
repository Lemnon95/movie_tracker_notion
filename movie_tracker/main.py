from config import ensure_config_file, load_config, update_config
from movie_inserter import insert_movie
from menu import print_menu

def main():
    config_path = ensure_config_file()
    token, database_id = load_config(config_path)

    while True:
        print_menu()
        choice = input("Enter your choice: ")
        if choice == "1":
            status, title = insert_movie(token, database_id)
            print(f"{title} successfully added!" if status == 200 else f"Failed to add {title}.")
        elif choice == "2":
            token, database_id = update_config(config_path)
        elif choice == "3":
            break
        else:
            print("Invalid option. Choose 1, 2 or 3.")

if __name__ == "__main__":
    main()
