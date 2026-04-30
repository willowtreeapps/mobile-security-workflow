import frida, signal, sys

PACKAGE = "owasp.sat.agoat"

SCRIPT = """
Java.perform(function () {
    var WebView = Java.use("android.webkit.WebView");
    WebView.loadUrl.overload("java.lang.String").implementation = function(u) {
        console.log("[WEBVIEW] loadUrl: " + u);
        return this.loadUrl(u);
    };
    WebView.loadData.overload("java.lang.String","java.lang.String","java.lang.String").implementation = function(d, m, e) {
        console.log("[WEBVIEW] loadData mime=" + m + " data_preview=" + d.substring(0,200));
        return this.loadData(d, m, e);
    };
    var WebSettings = Java.use("android.webkit.WebSettings");
    WebSettings.setJavaScriptEnabled.implementation = function(b) {
        console.log("[WEBVIEW] setJavaScriptEnabled(" + b + ")");
        return this.setJavaScriptEnabled(b);
    };
    console.log("[*] WebView tracer active");
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
print(f"[*] WebView tracer active on PID {pid}")
signal.pause()
