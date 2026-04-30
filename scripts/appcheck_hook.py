#!/usr/bin/env python3
"""Hook Firebase App Check to capture/bypass token generation."""
import frida, signal, sys, time

PACKAGE = "com.ohlq.app.dev"

SCRIPT = r"""
Java.perform(function () {
    console.log("[*] Firebase App Check hooks loading...");

    // Hook AppCheckTokenResult to capture tokens
    try {
        var AppCheckTokenResult = Java.use("com.google.firebase.appcheck.AppCheckTokenResult");
        AppCheckTokenResult.getToken.implementation = function () {
            var token = this.getToken();
            console.log("[APPCHECK] getToken() = " + token);
            return token;
        };
        console.log("[+] AppCheckTokenResult.getToken hooked");
    } catch(e) { console.log("[-] AppCheckTokenResult: " + e); }

    // Hook debug provider specifically
    try {
        var classes = Java.enumerateLoadedClassesSync();
        classes.forEach(function(cls) {
            if (cls.indexOf("appcheck") > -1 || cls.indexOf("AppCheck") > -1) {
                console.log("[APPCHECK CLASS] " + cls);
            }
        });
    } catch(e) { console.log("[-] Class enum: " + e); }

    // Hook OkHttp Request builder to see all headers including any App Check
    try {
        var Request = Java.use("okhttp3.Request$Builder");
        Request.addHeader.implementation = function (name, value) {
            if (name.toLowerCase().indexOf("appcheck") > -1 ||
                name.toLowerCase().indexOf("firebase") > -1 ||
                name.toLowerCase().indexOf("recaptcha") > -1 ||
                name.toLowerCase().indexOf("x-") > -1) {
                console.log("[HTTP HEADER] " + name + ": " + value.substring(0, 80));
            }
            return this.addHeader(name, value);
        };
        console.log("[+] OkHttp Request.addHeader hooked");
    } catch(e) { console.log("[-] OkHttp Request.addHeader: " + e); }

    // Hook OkHttp to capture full request to initiate-signin
    try {
        var OkHttpClient = Java.use("okhttp3.OkHttpClient");
        OkHttpClient.newCall.implementation = function (request) {
            var url = request.url().toString();
            if (url.indexOf("ohlq") > -1 || url.indexOf("auth") > -1) {
                console.log("[OKHTTP] " + request.method() + " " + url);
                var headers = request.headers();
                for (var i = 0; i < headers.size(); i++) {
                    console.log("  " + headers.name(i) + ": " + headers.value(i).substring(0, 100));
                }
                if (request.body() != null) {
                    console.log("  [body present, size: " + request.body().contentLength() + "]");
                }
            }
            return this.newCall(request);
        };
        console.log("[+] OkHttpClient.newCall hooked");
    } catch(e) { console.log("[-] OkHttpClient.newCall: " + e); }

    console.log("[*] App Check hooks active");
});
"""

def on_msg(msg, _):
    if msg.get("type") == "send":
        print(msg.get("payload", ""), flush=True)
    elif msg.get("type") == "error":
        print("[ERR]", msg.get("description",""), flush=True)
    else:
        print(msg, flush=True)

device = frida.get_device("127.0.0.1:6555")
pid = None
for p in device.enumerate_processes():
    if p.name == PACKAGE:
        pid = p.pid
        break
if not pid:
    print(f"[*] Spawning {PACKAGE}...", flush=True)
    pid = device.spawn([PACKAGE])
    session = device.attach(pid)
    script = session.create_script(SCRIPT)
    script.on("message", on_msg)
    script.load()
    device.resume(pid)
else:
    print(f"[*] Attaching to PID {pid}...", flush=True)
    session = device.attach(pid)
    script = session.create_script(SCRIPT)
    script.on("message", on_msg)
    script.load()
print(f"[*] Hooks active on PID {pid}", flush=True)
signal.pause()
