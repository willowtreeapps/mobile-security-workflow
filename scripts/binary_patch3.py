import frida, sys, time

# Set isAdmin=true then call activity.recreate() so onCreate re-runs with updated value
SCRIPT = """
Java.perform(function () {
    Java.choose('owasp.sat.agoat.BinaryPatchingActivity', {
        onMatch: function(activity) {
            console.log('[+] Found activity');
            // Modify isAdmin via reflection
            try {
                var cls = activity.getClass();
                var field = cls.getDeclaredField('isAdmin');
                field.setAccessible(true);
                field.setBoolean(activity, true);
                console.log('[+] isAdmin set to: ' + field.getBoolean(activity));
            } catch(e) { console.log('[-] reflection error: ' + e); }

            // Recreate so onCreate runs again with isAdmin=true
            Java.scheduleOnMainThread(function() {
                try {
                    activity.recreate();
                    console.log('[+] Activity recreated');
                } catch(e) { console.log('[-] recreate error: ' + e); }
            });
        },
        onComplete: function() { console.log('[*] done'); }
    });
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
time.sleep(4)
script.unload()
session.detach()
print('[*] Done')
