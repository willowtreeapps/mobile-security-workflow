from dotenv import load_dotenv
from service.input_service import do_restart, do_open, do_close
from service import vulnerability_service as vuln_service
from apps.solidcore import mapping as solidcore
import os
import time

""""
    solidcore test manager file. All the test structure for this app
    is centralized here.
"""

load_dotenv()

def do_test(package):

    MOCK_FIRST_NAME = os.getenv("MOCK_FIRST_NAME")
    MOCK_LAST_NAME = os.getenv("MOCK_LAST_NAME")
    MOCK_EMAIL = os.getenv("MOCK_EMAIL")
    MOCK_PHONE = os.getenv("MOCK_PHONE")
    ZIP_CODE = os.getenv("ZIP_CODE")
    MOCK_ADDRESS = os.getenv("MOCK_ADDRESS")

    # -     Open the App     -
    do_open(package)    

    # -     Root and Emulator checks
    vuln_service.check_root(package)
    vuln_service.check_emulator(package)

    #-       do login/create
    solidcore.do_create()
    #solidcore.do_login()
    #solidcore.do_payment()

    # -     Search for Vulnerabilities at Shared pref 
    vuln_service.search_shared_pref(MOCK_EMAIL, package)
    vuln_service.search_shared_pref(MOCK_FIRST_NAME, package)
    vuln_service.search_shared_pref(MOCK_LAST_NAME, package)
    vuln_service.search_shared_pref(MOCK_PHONE, package)
    vuln_service.search_shared_pref(ZIP_CODE)
    vuln_service.search_shared_pref(MOCK_ADDRESS)
    #vuln_service.search_shared_pref(MOCK_CARD_NUMBER, package)
    #vuln_service.search_shared_pref(MOCK_EXPIRATION_DATE, package)
    
    # -     Look to Sensitive Data at SQLite
    vuln_service.search_sensitive_sqlite(MOCK_EMAIL)
    vuln_service.search_sensitive_sqlite(MOCK_FIRST_NAME)
    vuln_service.search_sensitive_sqlite(MOCK_LAST_NAME)
    vuln_service.search_sensitive_sqlite(MOCK_PHONE)
    vuln_service.search_sensitive_sqliteg(ZIP_CODE)
    vuln_service.search_sensitive_sqlite(MOCK_ADDRESS)
    #vuln_service.search_sensitive_log(MOCK_CARD_NUMBER)
    #vuln_service.search_sensitive_log(MOCK_EXPIRATION_DATE)

    # -     Look to Sensitive data in Logs
    vuln_service.search_sensitive_log(MOCK_EMAIL)
    vuln_service.search_sensitive_log(MOCK_FIRST_NAME)
    vuln_service.search_sensitive_log(MOCK_LAST_NAME)
    vuln_service.search_sensitive_log(MOCK_PHONE)
    vuln_service.search_sensitive_log(ZIP_CODE)
    vuln_service.search_sensitive_log(MOCK_ADDRESS)
    #vuln_service.search_sensitive_log(MOCK_CARD_NUMBER)
    #vuln_service.search_sensitive_log(MOCK_EXPIRATION_DATE)

    # -     Look to Sensitive data at External storage
    vuln_service.search_sensitive_external(MOCK_EMAIL)
    vuln_service.search_sensitive_external(MOCK_FIRST_NAME)
    vuln_service.search_sensitive_external(MOCK_LAST_NAME)
    vuln_service.search_sensitive_external(MOCK_PHONE)
    vuln_service.search_sensitive_external(ZIP_CODE)
    vuln_service.search_sensitive_external(MOCK_ADDRESS)
    #vuln_service.search_sensitive_external(MOCK_CARD_NUMBER)
    #vuln_service.search_sensitive_external(MOCK_EXPIRATION_DATE)
    #vuln_service.search_sensitive_external(MOCK_CARD_ADDRESS)
    #vuln_service.search_sensitive_external(ZIP_CODE)

    time.sleep(20)

    # -     Create the .sarif File Report
    vuln_service.build_report()    

    do_close(package)
