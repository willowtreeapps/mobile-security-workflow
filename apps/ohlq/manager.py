from dotenv import load_dotenv
from service.input_service import do_restart, do_open, do_close
from service import vulnerability_service as vuln_service
from apps.ohlq import mapping as ohlq
import os

load_dotenv()

def do_test(package):
    # -     Define the Mock Data    -
    MOCK_USR = os.getenv("MOCK_USER_NAME")
    MOCK_PASWD = os.getenv("MOCK_PASSWORD")

    # -     Open the App
    do_open(package)

    # -     Root and Emulator checks
    vuln_service.check_root(package)
    vuln_service.check_emulator(package)

    # -     Login in the application
    ohlq.login()

    # -     Look to Sensitive data in Shared Pref
    vuln_service.search_shared_pref(MOCK_PASWD, package)
    
    # -     Look to Sensitive data in SQLite
    vuln_service.search_sqlite(MOCK_USR, package)

    # -     Look to Sensitive data in Logs
    vuln_service.search_sensitive_log(MOCK_USR)
    vuln_service.search_sensitive_log(MOCK_PASWD)
    
    #       Look to Sensitive data in external storage
    vuln_service.search_sensitive_external(MOCK_USR)

    # -     Create the .sarif File Report
    vuln_service.build_report()

    do_close(package)



