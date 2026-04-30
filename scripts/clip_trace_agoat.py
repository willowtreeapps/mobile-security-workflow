import frida, signal, sys

PACKAGE = "owasp.sat.agoat"

SCRIPT = """
Java.perform(function () {
    var CM = Java.use("android.content.ClipboardManager");
    CM.setPrimaryClip.overload("android.content.ClipData").implementation = function(clip) {
        var text = clip.getItemAt(0).getText();
        console.log("[CLIPBOARD] setPrimaryClip text: " + text);
        return this.setPrimaryClip(clip);
    };
    console.log("[*] Clipboard tracer active");
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
print(f"[*] Clipboard tracer active on PID {pid}")
signal.pause()
