from service.input_service import do_tap, do_input_text
from dotenv import load_dotenv
import os

# -    load the .env file   -
load_dotenv()

# -     DEFINE THE MOCK DATA    -
#MOCK_USR = os.getenv("MOCK_USER_NAME")
#MOCK_PASWD = os.getenv("MOCK_PASSWORD")

#Sign up
MOCK_EMAIL = os.getenv("MOCK_EMAIL")
MOCK_PASSWORD_SIGNUP = "Dekaigu9!"
MOCK_DATE = "03131998"
MOCK_FIRSTNAME = os.getenv("MOCK_FIRSTNAME")
MOCK_LASTNAME = os.getenv("MOCK_LASTNAME")

""""

   

"""

#def login():
    #click on red button
   # do_tap(724, 206)
    # type accont
   # do_input_text(MOCK_USR)
    # type continue
  #  do_tap(733, 204)
    # click input password
   # do_tap(724, 780)
    # type password
  #  do_input_text(MOCK_PASWD)
    # click continue button
   # do_tap(721, 2230)

def signup():

    #click on Create An Account button
    do_tap(377, 1058)
    # type email
    do_input_text(MOCK_EMAIL)
    # press continue
    do_tap(373, 1000)
    # type First name
    do_input_text(MOCK_FIRSTNAME)
    # press password
    do_tap(358, 580)
     # type last name
    do_input_text(MOCK_LASTNAME)
    # press continue
    do_tap(369, 946)
    # type date
    #do_input_text(MOCK_DATE)
    # press continue      
    #do_tap(380, 998)
    # click password field 
    do_tap(353, 486)
    # input password 
    do_input_text(MOCK_PASSWORD_SIGNUP)
    # press Confirm Password
    do_tap(363, 608)
    # input confirm password 
    do_input_text(MOCK_PASSWORD_SIGNUP)
    # press continue
    do_tap(382, 1007)


