// Native BoringSSL bypass — hooks SSL_verify_cert_chain at the native layer
// Works regardless of Java-layer TrustManager

var ssl_verify_sym = null;
var conscrypt_lib = null;

// Find libconscrypt or libssl in the process
Process.enumerateModules().forEach(function(m) {
    if (m.name.indexOf("conscrypt") !== -1 || m.name.indexOf("libssl") !== -1) {
        console.log("[NATIVE] Found module: " + m.name + " @ " + m.base);
        conscrypt_lib = m.name;
        // Try to find SSL_verify_cert_chain or similar
        try {
            var exports = Module.enumerateExports(m.name);
            exports.forEach(function(exp) {
                if (exp.name.indexOf("verify") !== -1 || exp.name.indexOf("cert_chain") !== -1) {
                    console.log("[NATIVE] Export: " + exp.name);
                }
            });
        } catch(e) {}
    }
});

// Hook the universal Android SSL pinning bypass via Java fallback
Java.perform(function() {
    // Try the RN-specific okhttp trust manager
    try {
        var classes = Java.enumerateLoadedClassesSync();
        classes.forEach(function(c) {
            if (c.toLowerCase().indexOf("trustmanager") !== -1
