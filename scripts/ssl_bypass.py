#!/usr/bin/env python3
"""
SSL/TLS bypass for OHLQ — SPAWN mode.
Hooks load before app initializes OkHttpClient, eliminating the race condition
that caused dev.ohlq.com to bypass our attach-mode hooks.
"""
import frida, signal, sys, time

PACKAGE = "com.ohlq.app.dev"

SCRIPT = r"""
Java.perform(function () {
    console.log("[*] SSL bypass loading (spawn mode)...");

    // --- TrustAll TrustManager ---
    var TrustAll;
    try {
        TrustAll = Java.registerClass({
            name: "com.dast.TrustAll",
            implements: [Java.use("javax.net.ssl.X509TrustManager")],
            methods: {
                checkClientTrusted: function (chain, authType) {},
                checkServerTrusted: function (chain, authType) {},
                getAcceptedIssuers: function () { return []; }
            }
        });
        console.log("[+] TrustAll registered");
    } catch(e) {
        try { TrustAll = Java.use("com.dast.TrustAll"); console.log("[+] TrustAll reused"); }
        catch(e2) { console.log("[-] TrustAll: " + e); }
    }

    // --- SSLContext.init ---
    try {
        var SSLContext = Java.use("javax.net.ssl.SSLContext");
        SSLContext.init.overload(
            "[Ljavax.net.ssl.KeyManager;",
            "[Ljavax.net.ssl.TrustManager;",
            "java.security.SecureRandom"
        ).implementation = function (km, tm, sr) {
            console.log("[+] SSLContext.init intercepted — injecting TrustAll");
            this.init(km, [TrustAll.$new()], sr);
        };
        console.log("[+] SSLContext.init hooked");
    } catch(e) { console.log("[-] SSLContext.init: " + e); }

    // --- Conscrypt TrustManagerImpl.verifyChain ---
    try {
        var TrustManagerImpl = Java.use("com.android.org.conscrypt.TrustManagerImpl");
        TrustManagerImpl.verifyChain.implementation = function (untrustedChain, trustAnchorChain, host, clientAuth, ocspData, tlsSctData) {
            console.log("[+] TrustManagerImpl.verifyChain bypassed: " + host);
            return untrustedChain;
        };
        console.log("[+] TrustManagerImpl.verifyChain hooked");
    } catch(e) { console.log("[-] TrustManagerImpl.verifyChain: " + e); }

    // --- NetworkSecurityTrustManager.checkPins ---
    try {
        var NSTM = Java.use("android.security.net.config.NetworkSecurityTrustManager");
        NSTM.checkPins.overload("java.util.List").implementation = function (chain) {
            console.log("[+] NSTM.checkPins bypassed");
        };
        console.log("[+] NSTM.checkPins hooked");
    } catch(e) { console.log("[-] NSTM.checkPins: " + e); }

    // --- OkHttp3 CertificatePinner ---
    try {
        var CP = Java.use("okhttp3.CertificatePinner");
        CP.check.overload("java.lang.String","java.util.List").implementation = function (host, certs) {
            console.log("[+] OkHttp3 CertificatePinner bypassed: " + host);
        };
        console.log("[+] OkHttp3 CertificatePinner hooked");
    } catch(e) { console.log("[-] OkHttp3 CertificatePinner: " + e); }

    // --- X509TrustManagerExtensions ---
    try {
        var Ext = Java.use("android.net.http.X509TrustManagerExtensions");
        Ext.checkServerTrusted.overload(
            "[Ljava.security.cert.X509Certificate;","java.lang.String","java.lang.String"
        ).implementation = function (chain, authType, host) {
            console.log("[+] X509TrustManagerExtensions bypassed: " + host);
            var ArrayList = Java.use("java.util.ArrayList");
            var list = ArrayList.$new();
            for (var i = 0; i < chain.length; i++) list.add(chain[i]);
            return list;
        };
        console.log("[+] X509TrustManagerExtensions hooked");
    } catch(e) { console.log("[-] X509TrustManagerExtensions: " + e); }

    // --- OpenSSLSocketImpl ---
    try {
        var OpenSSLSocket = Java.use("com.android.org.conscrypt.OpenSSLSocketImpl");
        OpenSSLSocket.verifyCertificateChain.implementation = function (certRefs, authMethod) {
            console.log("[+] OpenSSLSocketImpl.verifyCertificateChain bypassed");
        };
        console.log("[+] OpenSSLSocketImpl.verifyCertificateChain hooked");
    } catch(e) { console.log("[-] OpenSSLSocketImpl: " + e); }

    // --- ConscryptEngineSocket ---
    try {
        var CESocket = Java.use("com.android.org.conscrypt.ConscryptEngineSocket");
        CESocket.verifyCertificateChain.implementation = function (certRefs, authMethod) {
            console.log("[+] ConscryptEngineSocket.verifyCertificateChain bypassed");
        };
        console.log("[+] ConscryptEngineSocket.verifyCertificateChain hooked");
    } catch(e) { console.log("[-] ConscryptEngineSocket: " + e); }

    // --- React Native OkHttpClientProvider ---
    try {
        var RNProvider = Java.use("com.facebook.react.modules.network.OkHttpClientProvider");
        RNProvider.createClientBuilder.overload().implementation = function () {
            var builder = this.createClientBuilder();
            try {
                var SSLCtx = Java.use("javax.net.ssl.SSLContext");
                var ctx = SSLCtx.getInstance("TLS");
                ctx.init(null, [TrustAll.$new()], null);
                builder.sslSocketFactory(ctx.getSocketFactory(), TrustAll.$new());
                console.log("[+] RN OkHttpClientProvider patched with TrustAll");
            } catch(e2) { console.log("[-] RN OkHttpClientProvider patch: " + e2); }
            return builder;
        };
        console.log("[+] RN OkHttpClientProvider hooked");
    } catch(e) { console.log("[-] RN OkHttpClientProvider: " + e); }

    console.log("[*] SSL bypass fully loaded — app resuming");
});
"""

def on_msg(msg, _):
    if msg.get("type") == "send":
        print(msg.get("payload", ""), flush=True)
    elif msg.get("type") == "error":
        print("[SCRIPT ERROR]", msg.get("description",""), flush=True)
    else:
        print(msg, flush=True)

print(f"[*] Spawning {PACKAGE} with SSL hooks pre-loaded...", flush=True)
device = frida.get_device("127.0.0.1:6555")

pid = device.spawn([PACKAGE])
print(f"[*] Spawned PID {pid} — attaching before resume...", flush=True)
session = device.attach(pid)
script = session.create_script(SCRIPT)
script.on("message", on_msg)
script.load()
print(f"[*] Hooks loaded — resuming app...", flush=True)
device.resume(pid)
print(f"[*] SSL bypass active on PID {pid}", flush=True)
signal.pause()
