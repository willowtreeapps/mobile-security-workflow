#!/usr/bin/env python3
"""Combined SSL + reCAPTCHA bypass — spawn mode, loads JS from files."""
import frida, signal, os

PACKAGE = "com.ohlq.app.dev"
BASE    = "/Users/cassio.junior/Desktop/mobile-dast/scripts"

ssl_js = open(f"{BASE}/ssl_bypass.js").read()
rc_js  = open(f"{BASE}/recaptcha_bypass.js").read()

def on_msg(label):
    def h(msg, _):
        p = msg.get("payload", msg)
        print(f"[{label}] {p}", flush=True)
    return h

print("[*] Spawning app...", flush=True)
device = frida.get_device("127.0.0.1:6555")
pid = device.spawn([PACKAGE])
print(f"[*] Spawned PID {pid} — attaching...", flush=True)
session = device.attach(pid)

s1 = session.create_script(ssl_js)
s1.on("message", on_msg("SSL"))
s1.load()
print("[*] SSL bypass loaded", flush=True)

s2 = session.create_script(rc_js)
s2.on("message", on_msg("RC"))
s2.load()
print("[*] reCAPTCHA bypass loaded", flush=True)

device.resume(pid)
print(f"[*] App resumed — all hooks active on PID {pid}", flush=True)
signal.pause()
