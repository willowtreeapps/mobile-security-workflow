#!/usr/bin/env python3
import frida, signal

PACKAGE   = "com.ohlq.app.dev"
PROC_NAME = "OHLQ (Dev)"

JS = """
Java.perform(function () {
    console.log("[*] reCAPTCHA Enterprise force-resolve loading...");

    // Hook the RN bridge execute method to resolve the promise with a fake token
    try {
        var Mod = Java.use("com.google.recaptchaenterprisereactnative.RecaptchaEnterpriseReactNativeModule");
        Mod.execute.overload("java.lang.String", "double", "com.facebook.react.bridge.Promise").implementation = function(action, timeout, promise) {
            console.log("[RECAPTCHA] execute called with action=" + action + " timeout=" + timeout);
            // Resolve with a fake bypass token
            promise.resolve("BYPASS-DAST-TOKEN-" + action);
            console.log("[RECAPTCHA] Promise resolved with fake token for action: " + action);
        };
        console.log("[+] execute(String, double, Promise) hooked");
    } catch(e) {
        console.log("[-] execute(String, double, Promise): " + e);
        // Try other overloads
        try {
            var Mod2 = Java.use("com.google.recaptchaenterprisereactnative.RecaptchaEnterpriseReactNativeModule");
            var methods = Mod2.execute.overloads;
            console.log("[RECAPTCHA] execute overloads: " + methods.length);
            methods.forEach(function(ov, i) {
                console.log("  [" + i + "] " + ov.argumentTypes.map(function(t){return t.name;}).join(", "));
                ov.implementation = function() {
                    var args = Array.from(arguments);
                    console.log("[RECAPTCHA] execute called args: " + args.slice(0,2).join(", "));
                    // Last arg is Promise
                    var promise = args[args.length-1];
                    try {
                        promise.resolve("BYPASS-DAST-TOKEN");
                        console.log("[+] Resolved promise with fake token");
                    } catch(e2) { console.log("[-] resolve: "+e2); return ov.apply(this, args); }
                };
            });
        } catch(e2) { console.log("[-] execute overloads: " + e2); }
    }

    // Also hook initClient to ensure it succeeds
    try {
        var Mod3 = Java.use("com.google.recaptchaenterprisereactnative.RecaptchaEnterpriseReactNativeModule");
        Mod3.initClient.overloads.forEach(function(ov, i) {
            console.log("[INIT] initClient overload [" + i + "]: " + ov.argumentTypes.map(function(t){return t.name;}).join(", "));
            ov.implementation = function() {
                var args = Array.from(arguments);
                console.log("[RECAPTCHA] initClient called");
                // Try original first
                try {
                    var result = ov.apply(this, args);
                    console.log("[RECAPTCHA] initClient succeeded");
                    return result;
                } catch(e2) {
                    // If it fails, resolve the promise with success
                    var promise = args[args.length-1];
                    try { promise.resolve(null); console.log("[+] initClient promise resolved"); }
                    catch(e3) { console.log("[-] initClient resolve: "+e3); }
                }
            };
        });
    } catch(e) { console.log("[-] initClient hook: " + e); }

    console.log("[*] reCAPTCHA bypass active");
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
