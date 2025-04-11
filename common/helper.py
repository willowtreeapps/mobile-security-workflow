from service.input_service import execute_command
import re
import sys
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