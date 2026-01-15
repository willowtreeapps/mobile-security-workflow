from dotenv import load_dotenv
from service.input_service import do_restart, do_open, do_close
from service import vulnerability_service as vuln_service
from apps.dfd import mapping as dfd
import os

import time

""""

    DFD test manager file. All the test structure for this app
    is centralized here.

"""

load_dotenv()

def do_test(package):
    # -     Define the Mock Data    -
    MOCK_USR = os.getenv("MOCK_USER_NAME") 
    MOCK_PASWD = os.getenv("MOCK_PASSWORD")
    MOCK_EMAIL = os.getenv("MOCK_EMAIL")
    MOCK_FIRST_NAME = os.getenv("MOCK_FIRST_NAME")

    # -     Open the App     -
    do_open(package)        

    vuln_service.check_root(package)

    vuln_service.check_emulator(package)
    
    # -     Give the pentester some time to chat a bit (3 minutes)   -
    time.sleep(160)
    
    vuln_service.search_sensitive_external(MOCK_USR)        

    # -     Search for Vulnerabilities       -
    vuln_service.search_shared_pref(MOCK_PASWD, package)


    # -     Look to Sensitive Data at SQLite
    vuln_service.search_sqlite(MOCK_EMAIL, package)
  

    # -     Look to Sensitive data in Logs
    vuln_service.search_sensitive_log(MOCK_PASWD)  
    vuln_service.search_sensitive_log(MOCK_FIRST_NAME)    
    vuln_service.search_sensitive_log(MOCK_EMAIL)     
    
    
    time.sleep(10)    

    # -     Create the .sarif File Report
    vuln_service.build_report()

    do_close(package)

