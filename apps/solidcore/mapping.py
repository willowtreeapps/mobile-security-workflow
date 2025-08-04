from service.input_service import do_tap, do_input_text, do_scroll_down, do_sleep
from dotenv import load_dotenv
import os

# -    load the .env file   -
load_dotenv()

# -     DEFINE THE MOCK DATA    -
MOCK_FIRST_NAME = os.getenv("MOCK_FIRST_NAME")
MOCK_LAST_NAME = os.getenv("MOCK_LAST_NAME")
MOCK_EMAIL = os.getenv("MOCK_EMAIL")
MOCK_PHONE = os.getenv("MOCK_PHONE")
MOCK_CODE = os.getenv("MOCK_CODE")
MOCK_NUMBER = os.getenv("MOCK_NUMBER")
#DATE_YEAR = os.getenv("DATE_YEAR")
#MOCK_CARD_NUMBER = os.getenv("MOCK_CARD_NUMBER")
#MOCK_EXPIRATION_DATE = os.getenv("MOCK_EXPIRATION_DATE")
#MOCK_CARD_ADDRESS = os.getenv("MOCK_CARD_ADDRESS")
MOCK_ADDRESS = os.getenv("MOCK_ADDRESS")
ZIP_CODE = os.getenv("77449")

""""
   Application: Solidcore
   This file maps the relevant flows of the application
"""

def do_create():
    # -- First Screen --
    # tap email field
    do_tap(322, 836)
    # Enter email address
    do_input_text(MOCK_EMAIL)
    # tap continue
    do_tap(375, 1006)
    # verify it's you
    do_tap(690, 577)
    #Sleep
    do_sleep(20) 
   
    # tap squares
    #do_tap(93, 543)
    # tap squares
    #do_tap(93, 543)
    # tap squares
    #do_tap(105, 542)
    # tap squares
    #do_tap(105, 542)
    #Put Code
    #do_input_text(MOCK_CODE)
    # tap continue
    #do_tap(376, 1068)
    #Sleep
    #do_sleep(8) 
    # tap continue
    #do_tap(376, 1068)
   
    # Select California
    do_tap(119, 575)
    # tap continue
    do_tap(392, 1133)
    # Enter Cell Phone
    do_tap(352, 775)
    #Cell phone input
    do_input_text(MOCK_NUMBER)
    # tap First Name
    do_tap(123, 1006)
    # input name
    do_input_text(MOCK_FIRST_NAME)
    # Scroll down
    do_scroll_down("adb shell input swipe 384 800 384 300")
    # Tap Last Name Field
    do_tap(173, 513)
    # Input Last Name
    do_input_text(MOCK_LAST_NAME)
    # Tap Date Field
    do_tap(120, 794)
    #Sleep
    do_sleep(20) 
   
    #Tap Year selection
    #do_tap(540, 552)
    #do_tap(540, 552)
    #do_tap(540, 552)
    # Enter Date Year
    #do_input_text(DATE_YEAR)
    #Select Ok

    do_tap(547,812)
    # Tap Gender Field
    do_tap(689,988)
    #Select Male Gender
    do_tap(103,942)
    # Scroll down
    do_scroll_down("adb shell input swipe 384 800 384 300")
    # Select Terms and conditions
    do_tap(121,926)
    #Sleep
    do_sleep(5)
    # Select Terms and conditions
    do_tap(391, 1120)
    # Select Terms and conditions
    do_tap(391, 1120)
    # Select Street Adress
    do_tap(270, 533)
    # Enter Adress
    do_input_text(MOCK_ADDRESS)
    # Select City
    do_tap(114, 932)
    # Enter City
    do_input_text("Katy")
    # Tap State Arrow 
    do_tap(329, 1116)
    # Select State
    do_tap(113, 551)
    # Select State
    do_tap(113, 551)
    # Scroll down
    do_scroll_down("adb shell input swipe 384 800 384 300")
    #Sleep
    do_sleep(5)
    # Tap ZipCode 
    do_tap(439, 885)
    # Enter ZipCode
    do_input_text(ZIP_CODE)
   # Tap Continoue 
    do_tap(388, 1176)
    # Tap Arrow 
    do_tap(667, 550)
    # Select Another Client
    do_tap(143, 672)
    # Select Complete Sign Up
    do_tap(366, 1124)

def do_login():
    #-- First Screen --
    #tap email field
   do_tap(322, 836)
    #Enter email address
   do_input_text(MOCK_EMAIL)
    #tap continue
   do_tap(375, 1006)
    #verify it's you
   do_tap(690, 577)
    #tap squares
   do_tap(93, 543)
    #Put Code
   do_input_text(MOCK_CODE)
    #tap continue
   do_tap(386, 1180)

#def do_payment():
    # -- First Screen --
    # tap email field
#    do_tap(322, 836)
    # Enter email address
#    do_input_text(MOCK_EMAIL)
    # tap continue
#    do_tap(375, 1006)
    # verify it's you
#    do_tap(690, 577)
    # tap squares
#    do_tap(105, 542)
    #Sleep
#    do_sleep(10) 
    # tap squares
#    do_tap(105, 542)
    #Put Code
#    do_input_text(CODE)
    # tap continue
#    do_tap(376, 1068)
    #Sleep
#    do_sleep(3) 
    # tap account
#    do_tap(632, 1085)
    #Sleep
#    do_sleep(2) 
    # tap payment method
#    do_tap(310, 721)
    #Sleep
#    do_sleep(3) 
    # tap add credit card
#    do_tap(372, 608)
    #Sleep
#    do_sleep(3) 
    # tap card number 
#    do_tap(154, 365)
    # Enter card number
#    do_input_text(MOCK_CARD_NUMBER)
    # tap Expiration Date  
#    do_tap(194, 828)
    # tap Expiration Date  
#    do_tap(64, 873)
    #Put digits
#    do_input_text(MOCK_EXPIRATION_DATE)
    # Save card Button  
#    do_tap(360, 1161)
    #Sleep
#    do_sleep(2) 
    # Save card Button  
#    do_tap(365, 1164)


# Main execution

if __name__ == "__main__":
    do_create()
