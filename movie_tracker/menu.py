from colorama import Fore, Style, init


def print_menu():
    init(autoreset=True)  # Needed for Windows to reset colors automatically

    print(f"\n{Fore.CYAN}{Style.BRIGHT}🎬  Movie Tracker Menu")
    print(f"{Fore.CYAN}{'─' * 30}")

    menu_items = [
        ("1", "Insert a new movie"),
        ("2", "Update your configuration file"),
        ("3", "Update movie(s) with latest IMDb data"),
        ("4", "Get recommendations"),
        ("5", "Quit"),
    ]

    for key, desc in menu_items:
        print(f"{Fore.YELLOW}{key} {Fore.WHITE}-- {desc}")

    print(f"{Fore.CYAN}{'─' * 30}")
