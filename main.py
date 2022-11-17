from imdb import Cinemagoer, IMDbError, Person
# https://cinemagoer.readthedocs.io/en/latest/
import requests
import os
import json
from datetime import date

#TOKEN = 'secret_3NcUdmAExOUaHmJ5DSiHaNVzXaJcO4EgISVlGkS2s2Z'  # token of the integration

### THE ID OF THE DATABASE TO FILL ###
#DATABASE_ID = '3f1b10c7f541400cb259bf6550a8fd4d'  # be sure there is no query ?v

my_keys:dict = {
                    "TOKEN": "secret_3NcUdmAExOUaHmJ5DSiHaNVzXaJcO4EgISVlGkS2s2Z",
                    "DATABASE_ID": "3f1b10c7f541400cb259bf6550a8fd4d"
                }

def readDatabase(databaseId: str, token: str):
    url = f"https://api.notion.com/v1/databases/{databaseId}"
    headers = {
        "accept": "application/json",
        "Notion-Version": "2022-06-28",
        "authorization": "Bearer " + token
    }
    response = requests.get(url, headers=headers)
    return {'statusCode': response.status_code, 'text': response.text}


def createPayload(databaseId: str, values: dict, seen: bool) -> dict:
    if seen:
        payload = {
            "parent": {
                "database_id": databaseId
            },
            "properties": {
                "Title": {
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Title"]
                            }
                        }
                    ]
                },
                "Tags": {
                    "type": "multi_select",
                    "multi_select": [
                        {
                            "name": values["Tags"]
                        }
                    ]
                },
                "Plot": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Plot"]
                            }
                        }
                    ]
                },
                "Actors": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Actors"]
                            }
                        }
                    ]
                },
                "Directors": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Directors"]
                            }
                        }
                    ]
                },
                "Writers": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Writers"]
                            }
                        }
                    ]
                },
                "Year": {
                    "type": "number",
                    "number": values["Year"]
                },
                "Runtime": {
                    "type": "number",
                    "number": values["Runtime"]
                },
                "Rating - IMDb": {
                    "type": "number",
                    "number": values["Rating - IMDb"]
                },
                "IMDb URL": {
                    "type": "url",
                    "url": values["IMDb URL"]
                },
                "Last Seen": {
                    "date": {
                        "start": values["Last Seen"]  # year-month-day
                    }
                },
                "Cover": {
                    "files": [
                        {
                            "type": "external",
                            "name": "Movie Cover",
                            "external": {
                                "url": values["Cover"]  # the url
                            }
                        }
                    ]
                },
                "Release Date": {
                    "date":
                        {
                            "start": values["Release Date"]
                        }
                },
                "My Score": {
                    "type": "number",
                    # "number_with_commas": values["My Score"]
                    "number": values["My Score"]
                }
            }
        }
    else:
        payload = {
            "parent": {
                "database_id": databaseId
            },
            "properties": {
                "Title": {
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Title"]
                            }
                        }
                    ]
                },
                "Tags": {
                    "type": "multi_select",
                    "multi_select": [
                        {
                            "name": values["Tags"]
                        }
                    ]
                },
                "Plot": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Plot"]
                            }
                        }
                    ]
                },
                "Actors": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Actors"]
                            }
                        }
                    ]
                },
                "Directors": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Directors"]
                            }
                        }
                    ]
                },
                "Writers": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": values["Writers"]
                            }
                        }
                    ]
                },
                "Year": {
                    "type": "number",
                    "number": values["Year"]
                },
                "Runtime": {
                    "type": "number",
                    "number": values["Runtime"]
                },
                "Rating - IMDb": {
                    "type": "number",
                    "number": values["Rating - IMDb"]
                },
                "IMDb URL": {
                    "type": "url",
                    "url": values["IMDb URL"]
                },
                "Cover": {
                    "files": [
                        {
                            "type": "external",
                            "name": "Movie Cover",
                            "external": {
                                "url": values["Cover"]  # the url
                            }
                        }
                    ]
                },
                "Release Date": {
                    "date":
                        {
                            "start": values["Release Date"]
                        }
                }
            }
        }
    return payload


def createPage(token: str, payload: dict):
    # Notion API reference: https://developers.notion.com/reference/post-page
    url = 'https://api.notion.com/v1/pages'
    headers = {
        "accept": "application/json",
        "Notion-Version": "2022-06-28",
        "content-type": "application/json",
        "authorization": "Bearer " + token
    }
    # how to build the parameters value inside the payload: https://developers.notion.com/reference/property-value-object

    # data = json.dumps(payload)
    response = requests.post(url, headers=headers, json=payload)
    return response.status_code, response.text


def names(people: list[Person.Person]) -> str:
    """Returns a comma-separated string of the names in the given list."""
    return ", ".join([person["name"] for person in people if "name" in person])


def isodate(date: str):
    months = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
              "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
    date = date.split(" ")
    date = f"{date[2]}-{months[date[1]]}-{date[0]}"
    return date


def getMovieValues(movie_id: str):
    values: dict = {}
    ia = Cinemagoer()  # creates an instance of cinemagoer class

    # Get Movie and fill values dictionary
    try:
        movie = ia.get_movie(movie_id)
    except IMDbError as e:
        print(e)
        return 1
    #print(movie.get_current_info())
    #print(movie['title'])
    values["Title"] = movie['title']
    try:
        values["Plot"] = movie['plot'][0]
    except:
        values["Plot"] = None
    try:
        values["Year"] = int(movie['year'])
    except:
        values["Year"] = None
    try:
        values["Directors"] = names(movie['directors'])
    except:
        values["Directors"] = None
    try:
        values["Runtime"] = int(movie['runtime'][0])
    except:
        values["Runtime"] = None
    try:
        values["Cover"] = movie['full-size cover url']
    except:
        values["Cover"] = None
    try:
        values["Writers"] = names(movie["writers"])
    except:
        values["Writers"] = None
    values["IMDb URL"] = "https://www.imdb.com/title/tt" + movie["imdbID"]
    try:
        values["Rating - IMDb"]: float = movie["rating"]
    except:
        values["Rating - IMDb"] = None
    try:
        values["Actors"] = names(movie["cast"][0:6])
    except:
        values["Actors"] = None
    try:
        values["Release Date"] = isodate(movie["original air date"])
    except:
        values["Release Date"] = None

    return values

def check_config() -> str:
    documents = os.path.join(os.environ['USERPROFILE'], 'Documents')
    movie_tracker = os.path.join(documents, 'Movie_Tracker')
    if not os.path.exists(movie_tracker):
        os.mkdir(movie_tracker)
    config_json = os.path.join(movie_tracker, 'config.json')
    if not os.path.exists(config_json):
        # the config.json file doesn't exist yet,
        # so this is the first time the movie tracker has been launched
        print("Welcome to the Movie Tracker application! Please, configure your settings.")
        TOKEN = input("Enter your Notion integration token: ")
        DATABASE_ID = input("Enter the Notion table's URL: ")
        config = {"TOKEN": TOKEN, "DATABASE_ID": DATABASE_ID}
        with open(config_json, "w", encoding='utf-8') as f:
            # writing config.json for the first time
            json.dump(config, f, ensure_ascii=False, indent=4)
        print(f"Configuration file correctly written inside directory: {movie_tracker}")
    return config_json

def get_config(path:str) -> tuple:
    with open(path, "r") as f:
        config = json.load(f)
    if "TOKEN" not in config or "DATABASE_ID" not in config:
        TOKEN = input("There is an error in your configuration file, please, enter your Notion integration token: ")
        DATABASE_ID = input("Enter the Notion table's URL: ")
        config = {"TOKEN": TOKEN, "DATABASE_ID": DATABASE_ID}
        with open(path, "w", encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    else: #config file properly formed
        TOKEN = config["TOKEN"]
        DATABASE_ID = config["DATABASE_ID"]
    return TOKEN, DATABASE_ID

def update_config(path) -> tuple:
    # print("Please, enter your Notion integration token: ")
    TOKEN = input("Please, enter your Notion integration token: ")
    # print("Enter the Notion table's URL: ")
    DATABASE_ID = input("Enter the Notion table's URL: ")
    config = {"TOKEN": TOKEN, "DATABASE_ID": DATABASE_ID}
    with open(path, "w", encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    print("Configuration file correctly updated")
    return TOKEN, DATABASE_ID

def print_menu():
    menu_options = {
        1: 'Insert a new movie',
        2: 'Update your configuration file',
        3: 'Quit',
    }
    for key in menu_options.keys():
        print(key, '--', menu_options[key])
    return

def isfloat(num:str) -> bool:
    try:
        float(num)
        return True
    except ValueError:
        return False

def insert_movie(TOKEN, DATABASE_ID) -> (int, str):
    values = {}

    ### USER PROMPT ###

    # GETTING MOVIE ID
    check_movie = False
    while not check_movie:
        movie_id: str = input("Insert movie ID: ")
        if movie_id.isdigit():
            check_movie = True
        else:
            print("Wrong input, insert a valid movie ID.")
    # GETTING TO KNOW IF USER HAS SEEN THE MOVIE
    check_seen = False
    while not check_seen:
        seen_str: str = input("Have you seen the movie? Type 0 for no, 1 for yes: ")
        if seen_str.isdigit() and (seen_str == "0" or seen_str == "1"):
            seen: bool = bool(int(seen_str))
            check_seen = True
        else:
            print("Wrong input, insert a valid value.")
    if not seen:
        tag = "" #instantiation needed before while loop in order to check input
        while(tag != 'y' and tag != 'n'):
            tag = input("Is the movie out yet? y/n: ")
            if tag == 'y':
                values["Tags"] = "Want to see"
            elif tag == 'n':
                values["Tags"] = "Not yet Released"
            else:
                print("Try again. Enter y for yes or n for no.")
    if seen:
        ### GETTING MY SCORE FROM INPUT ###
        check_score = False
        while not check_score:
            my_score = input("What's your score? Choose a number between 0.0 to 10.00, or leave blank: ")
            if my_score == "":
                values["My Score"] = None
                check_score = True
            elif isfloat(my_score) and 0 <= float(my_score) <= 10:
                values["My Score"] = float(my_score)
                check_score = True
            else:
                print("Wrong input, try again. Enter a valid number.")
        ### GETTING LAST SEEN FROM INPUT ###
        check_date = False
        while not check_date:
            last_seen = input("When did you watch it? yyyy-mm-dd: ")
            if last_seen == "":
                values["Last Seen"] = None
                check_date = True
            else:
                try:
                    date.fromisoformat(last_seen)
                    values["Last Seen"] = last_seen
                    check_date = True
                except ValueError:
                    print("Wrong input, try again. Enter a valid date format.")
        values["Tags"] = "Seen"

    print("Sending your request, please wait...")
    ### GETTING VALUES FROM IMDB ###
    values_ = getMovieValues(movie_id) # @TODO: insert check on return value for error
    if values_ == 1:
        return 400, f"{movie_id} movie id"
    values = values | values_

    ### CREATING PAYLOAD AND SENDING IT THROUGH NOTION API'S ###
    payload = createPayload(DATABASE_ID, values, seen)
    # Cleaning operation, because some movies may not have some values
    for key, value in values.items():
        if value == None:
            del payload["properties"][key]
    res = createPage(TOKEN, payload)
    return res[0], values["Title"]

def main():
    #user = os.getlogin()
    #path = r"C:\Users\{}\Documents\Movie_Tracker\config.json".format(user)
    path = check_config()
    TOKEN, DATABASE_ID = get_config(path)

    loop = True
    while(loop):
        print_menu()
        option = int(input('Enter your choice: '))
        if option == 1:
            res_code, title = insert_movie(TOKEN, DATABASE_ID)
            if res_code == 200:
                print(f"{title} has been successfully added to the Movie Tracker!")
            else:
                print(f"Unable to add {title} to the Movie Tracker, please try again.")
        elif option == 2:
            TOKEN, DATABASE_ID = update_config(path)
        elif option == 3:
            exit()
        else:
            print('Invalid option. Please enter a number between 1 and 3.')

    return 0


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
