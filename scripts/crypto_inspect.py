import frida, signal, sys

PACKAGE = "com.ohlq.app.dev"

SCRIPT = """
Java.perform(function () {
    try {
        var Cipher = Java.use("javax.crypto.Cipher");
        Cipher.getInstance.overload("java.lang.String").implementation = function (t) {
            console.log("[CIPHER] getInstance(" + t + ")");
            return this.getInstance(t);
        };
    } catch(e) { console.log("[CIPHER] hook err: " + e); }
    try {
        var SecretKeySpec = Java.use("javax.crypto.spec.SecretKeySpec");
        SecretKeySpec.$init.overload("[B", "java.lang.String").implementation = function (k, alg) {
            var hex = ""; for (var i=0;i<k.length;i++) hex += ("0"+(k[i]&0xff).toString(16)).slice(-2);
            console.log("[KEY] " + alg + " = " + hex);
            return this.$init(k, alg);
        };
    } catch(e) { console.log("[KEY] hook err: " + e); }
    try {
        var IvParameterSpec = Java.use("javax.crypto.spec.IvParameterSpec");
        IvParameterSpec.$init.overload("[B").implementation = function (iv) {
            var hex = ""; for (var i=0;i<iv.length;i++) hex += ("0"+(iv[i]&0xff).toString(16)).slice(-2);
            console.log("[IV] " + hex);
            return this.$init(iv);
        };
    } catch(e) { console.log("[IV] hook err: " + e); }
    try {
        var MessageDigest = Java.use("java.security.MessageDigest");
        MessageDigest.getInstance.overload("java.lang.String").implementation = function (a) {
            console.log("[HASH] " + a);
            return this.getInstance(a);
        };
    } catch(e) {}
    console.log("[*] Crypto inspector active");
});
"""

def on_msg(msg, _):
    if msg.get("type") == "send":
        print(msg["payload"]); sys.stdout.flush()
    elif msg.get("type") == "log":
        print(msg.get("payload", "")); sys.stdout.flush()
    else:
        print(msg); sys.stdout.flush()

device = frida.get_device("127.0.0.1:6555")
# Always attach — never spawn; app is assumed running
pid = next((p.pid for p in device.enumerate_processes() if p.name == PACKAGE), None)
if not pid:
    print("[-] Process not found, spawning...")
    sys.stdout.flush()
    pid = device.spawn([PACKAGE])
    device.resume(pid)
    import time; time.sleep(1)
s = device.attach(pid)
script = s.create_script(SCRIPT)
script.on("message", on_msg)
script.load()
print(f"[*] Crypto inspector hooked PID {pid}")
sys.stdout.flush()
signal.pause()
