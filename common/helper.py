from service.input_service import execute_command
from service import webhook_service
import re
import sys
import hashlib


#
# -    Checks if there are Devices Connected   -
#

def check_device():    
    devices = execute_command("adb devices")  
    if not has_device(devices):
        print("[-] Mobile Device is not connected")
        sys.exit()    

def has_device(devices):
    dvc = "device"
    matches = re.findall(dvc, devices)
    return len(matches) > 1

# -    Set proxy for Burp Suite integration   -
def set_proxy(host, port):
    execute_command(f"adb shell settings put global http_proxy {host}:{port}")

def start_webhook():
    webhook_service.start_webhook()    

def close_webhook():
    print("[-] Closing the Webhook ..")
    webhook_service.stop_webhook()
    
# -     Make a simple md5 hashing
def make_hash(data):
    return hashlib.md5(data.encode('utf-8')).hexdigest()