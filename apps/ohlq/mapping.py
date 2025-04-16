from service.input_service import do_tap, do_input_text, do_sleep
from dotenv import load_dotenv
import os

# -    load the .env file   -
load_dotenv()

#-     DEFINE THE MOCK DATA    -
MOCK_USR = os.getenv("MOCK_USER_NAME")
MOCK_PASWD = os.getenv("MOCK_PASSWORD")

#Sign up
MOCK_EMAIL = os.getenv("MOCK_EMAIL")
MOCK_PASSWORD_SIGNUP = "Dekaigu9!"
MOCK_DATE = "03131998"
MOCK_FIRSTNAME = os.getenv("MOCK_FIRSTNAME")
MOCK_LASTNAME = os.getenv("MOCK_LASTNAME")

""""

   

"""

#def login():
#    #click on red button
#    do_tap(389, 961)
#    # type accont
#    do_input_text(MOCK_USR)
#    # type continue
#    do_tap(397, 907)
#    # click input password
#    do_tap(385, 473)
#    # type password
#    do_input_text(MOCK_PASWD)
#    # click continue button
#    do_tap(385, 1009)
#    # wait for login complete
#    do_sleep(10)
#    # tap skip
#    do_tap(375, 1102)
#    # tap skip
#    do_tap(375, 1102)

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
     do_tap(382, 1007) # issue solved
     # type date
     do_input_text(MOCK_DATE)
     # press continue      
     do_tap(404, 1044)
     # click password field 
     do_tap(378, 486)
     # input password 
     do_input_text(MOCK_PASSWORD_SIGNUP)
     # press Confirm Password
     do_tap(381, 619)
     # input confirm password 
     do_input_text(MOCK_PASSWORD_SIGNUP)
     # # press continue
     do_tap(396, 1053)

#     do_sleep(20)


