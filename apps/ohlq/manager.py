from dotenv import load_dotenv
from service.input_service import do_restart, do_open, do_close
from service import vulnerability_service as vuln_service
from apps.ohlq import mapping as ohlq
import os

load_dotenv()


def do_test(package):
    # -     Define the Mock Data  (Login)   -
    MOCK_USR = os.getenv("MOCK_USER_NAME")
    MOCK_PASWD = os.getenv("MOCK_PASSWORD")


    # -     Define the Mock Data  (Signup)  -
    MOCK_EMAIL = os.getenv("MOCK_EMAIL")
    MOCK_PASSWORD_SIGNUP = "Dekaigu9!"
    MOCK_DATE = "03131998"
    MOCK_FIRSTNAME = os.getenv("MOCK_FIRSTNAME")
    MOCK_LASTNAME = os.getenv("MOCK_LASTNAME")


    # -     Open the App     -
    do_open(package)

    vuln_service.check_root(package)

    vuln_service.check_emulator(package)

    # --- Login function ------

    ohlq.login()

    vuln_service.search_shared_pref(MOCK_USR, package)

    vuln_service.search_sqlite(MOCK_USR, package)

    vuln_service.search_sqlite(MOCK_PASWD, package)

    vuln_service.search_sensitive_log(MOCK_USR)
    vuln_service.search_sensitive_log(MOCK_PASWD)

    # ---- Sinup function -------

    vuln_service.search_shared_pref(MOCK_USR, package)

    vuln_service.search_shared_pref(MOCK_PASSWORD_SIGNUP, package)

    vuln_service.search_shared_pref(MOCK_EMAIL, package)

    vuln_service.search_sqlite(MOCK_EMAIL, package)

    vuln_service.search_sqlite(MOCK_PASSWORD_SIGNUP, package)

    # -     Look to Sensitive data in Logs
    vuln_service.search_sensitive_log(MOCK_PASSWORD_SIGNUP)

    vuln_service.search_sensitive_log(MOCK_FIRSTNAME)

    vuln_service.search_sensitive_log(MOCK_EMAIL)

    # -     Create the .sarif File Report
    vuln_service.build_report()

    do_close(package)



