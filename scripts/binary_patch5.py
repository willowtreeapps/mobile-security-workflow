import frida, sys, time

# Strategy: hook onCreate to flip isAdmin before the method body runs
SCRIPT = """
Java.perform(function () {
    var BPA = Java.use('owasp.sat.agoat.BinaryPatchingActivity');

    BPA.onCreate.implementation = function(bundle) {
        // Flip isAdmin before onCreate body runs
        try {
            var field = this.getClass().getDeclaredField('isAdmin');
            field.setAccessible(true);
            field.setBoolean(this, true);
            var val = field.getBoolean(this);
            console.log('[+] isAdmin set to: ' + val);
        } catch(e) {
            console.log('[-] field err: ' + e);
        }
        this.onCreate(bundle);
        console.log('[+] onCreate complete, isAdmin should be true');
    };
    console.log('[*] onCreate hook installed');
});
"""

device = frida.get_device('127.0.0.1:6555')
procs = device.enumerate_processes()
pid = next(p.pid for p in procs if 'AndroGoat' in p.name)
print('[*] PID', pid)
session = device.attach(pid)
script = session.create_script(SCRIPT)

def on_msg(msg, data):
    if msg.get('payload'): print(msg['payload'])
    elif msg.get('type') == 'error': print('ERR:', msg.get('description'))

script.on('message', on_msg)
script.load()
time.sleep(1)
print('[*] Hook loaded, triggering recreate...')

RECREATE = """
Java.perform(function () {
    Java.choose('owasp.sat.agoat.BinaryPatchingActivity', {
        onMatch: function(activity) {
            Java.scheduleOnMainThread(function() {
                activity.recreate();
                console.log('[+] recreate called');
            });
        },
        onComplete: function() {}
    });
});
"""
s2 = session.create_script(RECREATE)
s2.on('message', on_msg)
s2.load()
time.sleep(5)
print('[*] Done')
