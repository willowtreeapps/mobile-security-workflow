#!/usr/bin/env python3
"""
Attach-mode bypass: hooks SSL pinning + reCAPTCHA on already-running OHLQ process.
Works at call-time so attach is sufficient.
"""
import frida, signal, sys, os

BASE   = "/Users/cassio.junior/Desktop/mobile-dast/scripts"
ssl_js = open(f"{BASE}/ssl_bypass.js").read()
rc_js  = open(f"{BASE}/recaptcha_bypass.js").read()

def on_msg(label):
    def h(msg, _):
        p = msg.get("payload", msg)
        print(f"[{label}] {p}", flush=True)
    return h

device = frida.get_device("127.0.0.1:6555")
procs  = [p for p in device.enumerate_processes() if "ohlq" in p.name.lower()]
if not procs:
    print("[-] No ohlq process found", flush=True)
    sys.exit(1)

proc = procs[0]
print(f"[*] Attaching to PID {proc.pid} ({proc.name})", flush=True)

session = device.attach(proc.pid)
s1 = session.create_script(ssl_js); s1.on("message", on_msg("SSL")); s1.load()
s2 = session.create_script(rc_js);  s2.on("message", on_msg("RC"));  s2.load()
print(f"[*] SSL + reCAPTCHA bypass active on PID {proc.pid}", flush=True)
signal.pause()
