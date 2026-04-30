import frida, sys, time

SCRIPT = """
Java.perform(function () {
    Java.choose('owasp.sat.agoat.BinaryPatchingActivity', {
        onMatch: function(activity) {
            console.log('[+] Found BinaryPatchingActivity');
            Java.scheduleOnMainThread(function() {
                try {
                    var decorView = activity.getWindow().getDecorView();
                    function findAllViews(view) {
                        try {
                            var cls = view.getClass().getName();
                            var enabled = view.isEnabled();
                            var visible = view.getVisibility();
                            if (cls.indexOf('Button') >= 0 || cls.indexOf('TextView') >= 0) {
                                var txt = '';
                                try { txt = view.getText().toString(); } catch(ee) {}
                                var tag = '';
                                try { var t = view.getTag(); if(t) tag = t.toString(); } catch(ee) {}
                                var id = view.getId();
                                console.log('[VIEW] cls=' + cls.split('.').pop() + ' id=' + id + ' text="' + txt + '" tag="' + tag + '" enabled=' + enabled + ' visible=' + visible);
                                if (!enabled) {
                                    console.log('[+] Enabling disabled view id=' + id);
                                    view.setEnabled(true);
                                    view.setAlpha(1.0);
                                    view.setClickable(true);
                                }
                            }
                            try {
                                var vg = Java.cast(view, Java.use('android.view.ViewGroup'));
                                var count = vg.getChildCount();
                                for (var i = 0; i < count; i++) {
                                    findAllViews(vg.getChildAt(i));
                                }
                            } catch(ee) {}
                        } catch(e) { console.log('err: ' + e); }
                    }
                    findAllViews(decorView);
                    console.log('[*] Done enabling buttons');
                } catch(e) {
                    console.log('[-] error: ' + e);
                }
            });
        },
        onComplete: function() { console.log('[*] scan complete'); }
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
time.sleep(5)
script.unload()
session.detach()
print('[*] Done')
