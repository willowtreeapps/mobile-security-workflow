from service.log_service import do_log_output
import subprocess
import time

"""

This file centralizes all the inputs and actions used to
intaract with the mobile device.

"""

def execute_command(command):
    try:                 
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE ,stderr=subprocess.PIPE, text=True)             

        output, error = process.communicate()

        if error:
            print(f"[-] Error while executing command {command} - output: {error}")     
                      
        return output
            
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print("Error Output:", e.stderr)


# -     Perform a Tap on the Device Based on X and Y Coordinades    -
def do_tap(x, y):    
    execute_command(f"adb shell input tap {x} {y}")
    do_sleep(4)

# -     Send input text to text fields     -
def do_input_text(data):        
    execute_command(f"adb shell input text {data}")

def do_sleep(amount):
    time.sleep(amount)

def do_restart(package):
    execute_command(f"adb shell am force-stop {package}")
    do_open(package)

def do_open(package):
    execute_command(f"adb shell monkey -p {package} -c android.intent.category.LAUNCHER 1")
    do_sleep(10)

# -    Execute a BACK/RETURN action on the device
def do_back():
    execute_command(f"adb shell input keyevent KEYCODE_BACK")

# -    Close the app
def do_close(package):
    execute_command(f"adb shell am force-stop {package}")

# -    Scroll down the screen a bit
def do_scroll_down():
    execute_command("adb shell input swipe 384 1000 384 300")
    