from service.input_service import do_tap, do_input_text, do_scroll_down
from dotenv import load_dotenv
import os

# -    load the .env file   -
load_dotenv()

# -     DEFINE THE MOCK DATA    -
MOCK_FIRST_NAME = os.getenv("MOCK_FIRST_NAME")
MOCK_LAST_NAME = os.getenv("MOCK_LAST_NAME")
MOCK_EMAIL = os.getenv("MOCK_EMAIL")
MOCK_PHONE = os.getenv("MOCK_PHONE")

""""

   Application: Scooters
   This file maps the relevant flows of the application

"""

def create_account():
   # -- First Screen --
    # tap create account button
    do_tap(390, 953)
    # click first name
    do_tap(121, 474)
    # input data
    do_input_text(MOCK_FIRST_NAME)
    # tap last name
    do_tap(100, 651)
    # input data
    do_input_text(MOCK_LAST_NAME)
    # tap email
    do_tap(100, 840)
    # input data
    do_input_text(MOCK_EMAIL)
    # tap confirm email
    do_tap(100, 1040)
    # input data
    do_input_text(MOCK_EMAIL)
    # scroll down the screen
    do_scroll_down()
    # tap phone
    do_tap(209, 457)
    # input data
    do_input_text(MOCK_PHONE)
    # tap birth data
    do_tap(209, 657)
    # select random date
    do_tap(387, 732)
    # tap ok
    do_tap(657, 1130)
    # tap gender
    do_tap(209, 857)
    # tap prefer not to say
    do_tap(197, 702)
    # scroll down the screen
    do_scroll_down()
    # tap continue
    do_tap(371, 1016)

    
    
    
    