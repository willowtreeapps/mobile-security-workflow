import os
from common import helper
from apps.andro_goat import manager as androgoat
from apps.va_lottery import manager as vallotery
from apps.ohlq import manager as ohql
from service.log_service import log_splash
from dotenv import load_dotenv
import os
import sys

import time

""""

    Main file. Responsible for centralize all the supported applications

"""

# -    load the .env file   -
load_dotenv()

PROXY_HOST = os.getenv("PROXY_HOST")
PROXY_PORT = os.getenv("PROXY_PORT")
PACKAGE_NAME = os.getenv("PACKAGE_NAME")

def do_test():

    helper.check_device()    
    
    print(f"[+] Initiating tests on: {PACKAGE_NAME}")

    helper.set_proxy(PROXY_HOST, PROXY_PORT)
    helper.start_webhook()

    match PACKAGE_NAME:
        case "owasp.sat.agoat":
            androgoat.do_test(PACKAGE_NAME)
        case "com.va.lottery.uat":
            vallotery.do_test(PACKAGE_NAME)
        case "com.ohlq.app.stage":
            ohql.do_test(PACKAGE_NAME)          
        case _:
            print(f"[-] Error: This application is not mapped: {PACKAGE_NAME}")    

    time.sleep(50)

    helper.close_webhook() 
    sys.exit()

def main():
    log_splash()
    do_test()
    
main()