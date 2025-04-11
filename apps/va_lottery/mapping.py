from service.input_service import do_tap, do_input_text, do_back
from dotenv import load_dotenv
import os

# -    load the .env file   -
load_dotenv()

# -     DEFINE THE MOCK DATA    -
MOCK_USR = os.getenv("MOCK_USER_NAME")
MOCK_PASWD = os.getenv("MOCK_PASSWORD")

""""

   Application: VaLottery
   This file maps the relevant flows of the application

"""

# ------ login workflow ------
def do_login():
    # tap login button
    do_tap(260, 475)
    # select email
    do_tap(210, 427)
    # type user
    do_input_text(MOCK_USR)
    # select pas
    do_tap(147, 583)
    # type pass
    do_input_text(MOCK_PASWD)
    # close the keyboard
    do_back()
     # tap login
    do_tap(393, 847)
