import frida, signal, sys

PACKAGE = "owasp.sat.agoat"

SCRIPT = """
Java.perform(function () {
    var Editor = Java.use("android.content.SharedPreferences$Editor");
    ["putString", "putInt", "putLong", "putFloat", "putBoolean"].forEach(function(m) {
        try {
            Editor[m].overloads.forEach(function(ov) {
                ov.implementation = function(k, v) {
                    console.log("[PREFS] " + m + "(" + k + ", " + v + ")");
                    return ov.call(this, k, v);
                };
            });
        } catch(e) {}
    });
    console.log("[*] SharedPreferences writer hook active");
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
print(f"[*] Prefs writer hook active on PID {pid}")
signal.pause()
