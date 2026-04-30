import frida, sys, time

# Hook the BinaryPatchingActivity constructor to set isAdmin=true after super() call
SCRIPT = """
Java.perform(function () {
    var BPA = Java.use('owasp.sat.agoat.BinaryPatchingActivity');

    // Hook constructor to flip isAdmin after it's set
    BPA.$init.overload('android.os.Bundle').implementation = function(bundle) {
        // Note: $init is not normally called this way for Activity; use onCreate hook instead
        this.$init(bundle);
        console.log('[+] constructor called');
    };

    // Hook onCreate — this is where isAdmin is read
    BPA.onCreate.overload('android.os.Bundle').implementation = function(bundle) {
        // First flip the field
        try {
            var field = this.getClass().getDeclaredField('isAdmin');
            field.setAccessible(true);
            field.setBoolean(this, true);
            console.log('[+] isAdmin flipped to true before onCreate runs');
        } catch(e) {
            console.log('[-] field error: ' + e);
        }
        // Now call super onCreate — it will see isAdmin=true
        this.onCreate(bundle);
        console.log('[+] onCreate complete');
    };
    console.log('[*] Hooks installed — waiting for activity (re)create...');
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

# Now trigger recreate while hooks are active
RECREATE_SCRIPT = """
Java.perform(function () {
    Java.choose('owasp.sat.agoat.BinaryPatchingActivity', {
        onMatch: function(activity) {
            Java.scheduleOnMainThread(function() {
                activity.recreate();
                console.log('[+] recreate triggered');
            });
        },
        onComplete: function() {}
    });
});
"""
s2 = session.create_script(RECREATE_SCRIPT)
s2.on('message', on_msg)
s2.load()

time.sleep(5)
script.unload()
s2.unload()
session.detach()
print('[*] Done')
