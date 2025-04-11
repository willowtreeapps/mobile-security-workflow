from service.input_service import do_tap, do_input_text
from dotenv import load_dotenv
import os

# -    load the .env file   -
load_dotenv()

# -     DEFINE THE MOCK DATA    -
MOCK_USR = os.getenv("MOCK_USER_NAME")
MOCK_PASWD = os.getenv("MOCK_PASSWORD")

""""

   Application: Androgoat
   This file maps the relevant flows of the application

"""

# ------ first shared preferences login activity ------
def login_shared_pref_1():
    #select data storage
    do_tap(395, 809)
    #select fisrt option
    do_tap(382, 509)
    # type user
    do_input_text(MOCK_USR)
    # tap pass
    do_tap(372, 601)
    # type pass
    do_input_text(MOCK_PASWD)
    # tap save
    do_tap(391, 703)

# ------ sqlite login ------
def login_sqlite():
    #select data storage
    do_tap(395, 809)
    #select sqlite
    do_tap(377, 715)
    # type user
    do_input_text(MOCK_USR)
    # tap pass
    do_tap(372, 601)
    # type pass
    do_input_text(MOCK_PASWD)
    # tap save
    do_tap(391, 703)

# ------ sdcard login ------
def login_sd_card():
    #select data storage
    do_tap(395, 809)
    #select sdcard
    do_tap(382, 950)
    # type user
    do_input_text(MOCK_USR)
    # tap pass
    do_tap(372, 601)
    # type pass
    do_input_text(MOCK_PASWD)
    # tap save
    do_tap(391, 703)

    # ------ insecure logging ------
def login_insecure_logging():

    #select data storage
    do_tap(369, 1022)
    #select insecure logging
    do_tap(382, 471)
    # type user
    do_input_text(MOCK_USR)
    # tap pass
    do_tap(372, 601)
    # type pass
    do_input_text(MOCK_PASWD)
    # tap save
    do_tap(391, 703)