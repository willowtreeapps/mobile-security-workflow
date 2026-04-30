import frida, signal, sys

PACKAGE = "owasp.sat.agoat"

SCRIPT = """
Java.perform(function () {
    var MessageDigest = Java.use("java.security.MessageDigest");
    MessageDigest.getInstance.overload("java.lang.String").implementation = function(a) {
        console.log("[HASH] MessageDigest.getInstance(" + a + ")");
        return this.getInstance(a);
    };
    MessageDigest.digest.overload("[B").implementation = function(b) {
        var result = this.digest(b);
        var hex = "";
        for (var i = 0; i < result.length; i++) hex += ("0" + (result[i] & 0xff).toString(16)).slice(-2);
        console.log("[HASH] digest result: " + hex);
        return result;
    };
    console.log("[*] Crypto inspector active");
});
"""

def on_msg(msg, _):
    print(msg.get("payload", msg))
    sys.stdout.flush()

device = frida.get_device("127.0.0.1:6555")
pid = next(p.pid for p in device.enumerate_processes() if "AndroGoat" in p.name or PACKAGE in p.name)
s = device.attach(pid)
script = s.create_script(SCRIPT)
script.on("message", on_msg)
script.load()
print(f"[*] Crypto inspector active on PID {pid}")
signal.pause()
