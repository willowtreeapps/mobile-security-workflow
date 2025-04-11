from dotenv import load_dotenv
from service.input_service import do_restart, do_open, do_close
from service import vulnerability_service as vuln_service
from apps.va_lottery import mapping as vallotery
import os

""""

    VaLottery test manager file. All the test structure for this app
    is centralized here.

"""

load_dotenv()

def do_test(package):
     # -     Define the Mock Data    -
    MOCK_USR = os.getenv("MOCK_USER_NAME")
    MOCK_PASWD = os.getenv("MOCK_PASSWORD")

    # -     Open the App     -
    do_open(package)    

    vuln_service.check_root(package)

    vuln_service.check_emulator(package)

    # -     Do Login     -
    vallotery.do_login()

    # -     Look to Sensitive data in Logs
    vuln_service.search_sensitive_log(MOCK_USR)

    # -     Search for Vulnerabilities       -
    vuln_service.search_shared_pref(MOCK_PASWD, package)

    # -     Create the .sarif File Report
    vuln_service.build_report()

    do_close(package)