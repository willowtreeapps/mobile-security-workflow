from dotenv import load_dotenv
from service.input_service import do_restart, do_open, do_close
from service import vulnerability_service as vuln_service
from apps.scooters import mapping as scooters
import os

""""

    Androgoat test manager file. All the test structure for this app
    is centralized here.

"""

load_dotenv()

def do_test(package):
    
    MOCK_FIRST_NAME = os.getenv("MOCK_FIRST_NAME")
    MOCK_LAST_NAME = os.getenv("MOCK_LAST_NAME")
    MOCK_EMAIL = os.getenv("MOCK_EMAIL")
    MOCK_PHONE = os.getenv("MOCK_PHONE")
    
    # -     Open the App     -
    do_open(package)    

    vuln_service.check_root(package)
    vuln_service.check_emulator(package)
    
    scooters.do_login()
    
    # -     Search for Vulnerabilities at Shared pref 
    vuln_service.search_shared_pref(MOCK_EMAIL, package)
    vuln_service.search_shared_pref(MOCK_FIRST_NAME, package)
    vuln_service.search_shared_pref(MOCK_PHONE, package)
    
    # -     Look to Sensitive Data at SQLite
    vuln_service.search_sqlite(MOCK_EMAIL, package)
    vuln_service.search_sqlite(MOCK_LAST_NAME, package)
    
    # -     Look to Sensitive data in Logs
    vuln_service.search_sensitive_log(MOCK_EMAIL)
    vuln_service.search_sensitive_log(MOCK_FIRST_NAME)
    
    # -     Look to Sensitive data at External storage
    vuln_service.search_sensitive_external(MOCK_EMAIL)
    vuln_service.search_sensitive_external(MOCK_FIRST_NAME)
    vuln_service.search_sensitive_external(MOCK_LAST_NAME)
        
    # -     Create the .sarif File Report
    vuln_service.build_report()    

    do_close(package)
    
    
    
    