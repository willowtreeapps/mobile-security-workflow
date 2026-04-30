#!/usr/bin/env python3
import frida, signal, sys

PACKAGE  = "com.ohlq.app.dev"
PROC_NAME = "OHLQ (Dev)"

JS = """
Java.perform(function () {
    console.log("[*] reCAPTCHA Enterprise bypass loading...");

    // Hook RecaptchaEnterpriseReactNativeModule - the RN bridge
    try {
        var Mod = Java.use("com.google.recaptchaenterprisereactnative.RecaptchaEnterpriseReactNativeModule");
        var methods = Mod.class.getDeclaredMethods();
        methods.forEach(function(m) {
            console.log("[MOD METHOD] " + m.getName() + " params=" + m.getParameterCount());
        });
    } catch(e) { console.log("[-] Module inspect: " + e); }

    // Hook RecaptchaTasksClient.executeTask to return a fake token
    try {
        var Client = Java.use("com.google.android.recaptcha.RecaptchaTasksClient");
        var methods = Client.class.getDeclaredMethods();
        methods.forEach(function(m) {
            console.log("[CLIENT METHOD] " + m.getName() + " -> " + m.getReturnType().getName());
        });
    } catch(e) { console.log("[-] Client inspect: " + e); }

    // Hook RecaptchaClient.execute
    try {
        var RC = Java.use("com.google.android.recaptcha.RecaptchaClient");
        var methods = RC.class.getDeclaredMethods();
        methods.forEach(function(m) {
            console.log("[RC METHOD] " + m.getName() + " -> " + m.toString().substring(0,150));
        });
    } catch(e) { console.log("[-] RecaptchaClient: " + e); }

    console.log("[*] Inspection done");
});
"""

def on_msg(msg, _):
    print(msg.get("payload", msg), flush=True)

device = frida.get_device("127.0.0.1:6555")
pid = None
for p in device.enumerate_processes():
    if p.name == PROC_NAME:
        pid = p.pid
        break
if not pid:
    pid = device.spawn([PACKAGE])
    s = device.attach(pid)
    sc = s.create_script(JS)
    sc.on("message", on_msg)
    sc.load()
    device.resume(pid)
else:
    s = device.attach(pid)
    sc = s.create_script(JS)
    sc.on("message", on_msg)
    sc.load()
print(f"Active on {pid}", flush=True)
signal.pause()
