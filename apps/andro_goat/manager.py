from dotenv import load_dotenv
from service.input_service import do_restart, do_open, do_close
from service import vulnerability_service as vuln_service
from apps.andro_goat import mapping as androgoat
import os

import time

""""

    Androgoat test manager file. All the test structure for this app
    is centralized here.

"""

load_dotenv()

def do_test(package):
    # -     Define the Mock Data    -
    MOCK_USR = os.getenv("MOCK_USER_NAME")
    MOCK_PASWD = os.getenv("MOCK_PASSWORD")

    # -     Open the App     -
    # do_open(package)        

    vuln_service.check_root(package)

    vuln_service.check_emulator(package)
    
    vuln_service.search_sensitive_external(MOCK_USR)
    
    time.sleep(20)

    # # -     Perform Shared Preferences Flow     -
    # androgoat.login_shared_pref_1()

    # # -     Search for Vulnerabilities       -
    # vuln_service.search_shared_pref(MOCK_PASWD, package)

    # # -     Restart the App     -
    # do_restart(package)

    # # -     Perform the SQLite Flow
    # androgoat.login_sqlite()

    # # -     Look to Sensitive Data at SQLite
    # vuln_service.search_sqlite(MOCK_USR, package)

    # do_restart(package)

    # # -     Perform the Logging Flow 
    # androgoat.login_insecure_logging()    

    # # -     Look to Sensitive data in Logs
    # vuln_service.search_sensitive_log(MOCK_USR)
    # vuln_service.search_sensitive_log(MOCK_PASWD)        

    # -     Create the .sarif File Report
    vuln_service.build_report()

    do_close(package)

