Java.perform(function () {
    try {
        var Mod = Java.use("com.google.recaptchaenterprisereactnative.RecaptchaEnterpriseReactNativeModule");
        Mod.execute.overloads.forEach(function(ov) {
            console.log("[RC] hooking execute: " + ov.argumentTypes.map(function(t){return t.name;}).join(","));
            ov.implementation = function() {
                var args = Array.from(arguments);
                console.log("[RC] execute called action=" + args[0]);
                var promise = args[args.length-1];
                try { promise.resolve("DAST-BYPASS-TOKEN"); console.log("[+] reCAPTCHA promise resolved"); }
                catch(e) { console.log("[-] resolve failed: "+e); }
            };
        });
        console.log("[*] reCAPTCHA bypass loaded");
    } catch(e) { console.log("[-] reCAPTCHA bypass failed: " + e); }
});
