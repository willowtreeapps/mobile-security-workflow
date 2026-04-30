Java.perform(function () {
    var TrustAll;
    try {
        TrustAll = Java.registerClass({
            name: "com.dast.TrustAll",
            implements: [Java.use("javax.net.ssl.X509TrustManager")],
            methods: {
                checkClientTrusted: function () {},
                checkServerTrusted: function () {},
                getAcceptedIssuers: function () { return []; }
            }
        });
    } catch(e) { try { TrustAll = Java.use("com.dast.TrustAll"); } catch(e2) {} }
    try {
        var S = Java.use("javax.net.ssl.SSLContext");
        S.init.overload("[Ljavax.net.ssl.KeyManager;","[Ljavax.net.ssl.TrustManager;","java.security.SecureRandom").implementation = function(k,t,r) {
            console.log("[SSL] SSLContext.init -> TrustAll"); this.init(k,[TrustAll.$new()],r);
        };
    } catch(e) { console.log("[-] SSLContext.init: "+e); }
    try {
        var T = Java.use("com.android.org.conscrypt.TrustManagerImpl");
        T.verifyChain.implementation = function(u,a,h,c,o,s) { console.log("[SSL] verifyChain bypassed: "+h); return u; };
    } catch(e) { console.log("[-] TrustManagerImpl: "+e); }
    try {
        var N = Java.use("android.security.net.config.NetworkSecurityTrustManager");
        N.checkPins.overload("java.util.List").implementation = function(c) { console.log("[SSL] NSTM.checkPins bypassed"); };
    } catch(e) { console.log("[-] NSTM: "+e); }
    try {
        var X = Java.use("android.net.http.X509TrustManagerExtensions");
        X.checkServerTrusted.overload("[Ljava.security.cert.X509Certificate;","java.lang.String","java.lang.String").implementation = function(c,a,h) {
            console.log("[SSL] X509Ext bypassed: "+h);
            var L = Java.use("java.util.ArrayList").$new();
            for (var i=0; i<c.length; i++) L.add(c[i]);
            return L;
        };
    } catch(e) { console.log("[-] X509Ext: "+e); }
    console.log("[*] SSL bypass loaded");
});
