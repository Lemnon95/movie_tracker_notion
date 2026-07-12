from colorama import Fore, Style, init


def print_menu():
    init(autoreset=True)

    print(f"\n{Fore.CYAN}{Style.BRIGHT}Movie Tracker Menu")
    print(f"{Fore.CYAN}{'─' * 30}")

    menu_items = [
        ("1", "Insert a new movie"),
        ("2", "Update your configuration file"),
        ("3", "Update movie(s) with latest metadata"),
        ("4", "Refresh stale TMDB metadata"),
        ("5", "About / Credits"),
        ("6", "Quit"),
    ]

    for key, description in menu_items:
        print(f"{Fore.YELLOW}{key} {Fore.WHITE}-- {description}")

    print(f"{Fore.CYAN}{'─' * 30}")
