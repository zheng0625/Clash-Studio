"""Unprivileged, process-scoped polkit GUI agent for a single TUN grant.

Run with system Python for GTK/GI. Passwords go only to PolkitAgent.Session;
neither the backend nor the desktop IPC receives them.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys


def main():
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('PolkitAgent', '1.0')
        gi.require_version('Polkit', '1.0')
        from gi.repository import Gio, GLib, Gtk, Polkit, PolkitAgent
    except (ImportError, ValueError):
        print('AUTH_AGENT_DEPENDENCIES_MISSING', file=sys.stderr, flush=True)
        return 69
    binary = Path(sys.argv[1]).resolve()
    chinese = len(sys.argv) > 2 and sys.argv[2] == 'zh-CN'
    def text(zh, en):
        return zh if chinese else en
    available, _ = Gtk.init_check()
    if not available:
        print('AUTH_AGENT_DISPLAY_UNAVAILABLE', file=sys.stderr, flush=True)
        return 69
    setcap = next((p for p in (Path('/usr/sbin/setcap'), Path('/sbin/setcap')) if p.is_file()), None)
    if setcap is None or not binary.is_file():
        return 69

    class Agent:
        def __init__(self):
            self.dialog = self.session = self.task = None

        def begin(self, action_id, message, icon_name, details, cookie, identities, invocation):
            self.task = invocation
            if action_id != 'org.freedesktop.policykit.exec' or details.get('polkit.caller-pid') != str(command.pid):
                self.task.return_dbus_error('org.freedesktop.PolicyKit1.Error.Cancelled', 'Unexpected authentication request')
                return
            identity = next((i for i in identities if isinstance(i, Polkit.UnixUser) and i.get_uid() == os.getuid()), identities[0])
            self.session = PolkitAgent.Session.new(identity, cookie)
            dialog = Gtk.Dialog(title='Clash Studio · Linux TUN', modal=True)
            self.dialog = dialog
            dialog.set_position(Gtk.WindowPosition.CENTER)
            dialog.set_default_size(460, -1)
            icon = Path(__file__).resolve().parents[1]/'icons/clash-studio.png'
            if icon.exists():
                dialog.set_icon_from_file(str(icon))
            dialog.add_button(text('取消', 'Cancel'), Gtk.ResponseType.CANCEL)
            dialog.add_button(text('授权', 'Authorize'), Gtk.ResponseType.OK)
            dialog.set_default_response(Gtk.ResponseType.OK)
            box = dialog.get_content_area()
            box.set_border_width(22)
            box.set_spacing(12)
            description = Gtk.Label(label=text('授权 Mihomo 使用 TUN 网络管理权限。\n仅修改下方内核文件的网络能力。', 'Authorize Mihomo to manage TUN networking.\nOnly this core executable receives network capabilities.'))
            description.set_line_wrap(True)
            box.add(description)
            path_label = Gtk.Label(label=str(binary))
            path_label.set_line_wrap(True)
            path_label.set_max_width_chars(58)
            box.add(path_label)
            user = identity.get_name() if isinstance(identity, Polkit.UnixUser) else str(identity)
            box.add(Gtk.Label(label=text('认证账户：', 'Authenticate as: ')+user))
            prompt = Gtk.Label()
            box.add(prompt)
            entry = Gtk.Entry()
            entry.set_visibility(False)
            entry.set_activates_default(True)
            box.add(entry)
            status = Gtk.Label()
            status.set_line_wrap(True)
            box.add(status)

            def request(session, message, echo_on):
                prompt.set_text(message)
                entry.set_text('')
                entry.set_visibility(echo_on)
                entry.set_sensitive(True)
                dialog.set_response_sensitive(Gtk.ResponseType.OK, True)
                entry.grab_focus()

            def respond(widget, response):
                if response == Gtk.ResponseType.OK:
                    answer = entry.get_text()
                    entry.set_text('')
                    entry.set_sensitive(False)
                    dialog.set_response_sensitive(Gtk.ResponseType.OK, False)
                    self.session.response(answer)
                    del answer
                else:
                    self.session.cancel()

            def completed(session, gained):
                entry.set_text('')
                dialog.destroy()
                self.dialog = None
                self.task.return_value(GLib.Variant('()', ()))
                self.task = self.session = None

            self.session.connect('request', request)
            self.session.connect('show-info', lambda session, message: status.set_text(message))
            self.session.connect('show-error', lambda session, message: status.set_text(message))
            self.session.connect('completed', completed)
            dialog.connect('response', respond)
            dialog.connect('delete-event', lambda *args: (self.session.cancel(), True)[1] if self.session else False)
            dialog.show_all()
            dialog.present()
            print('AUTH_DIALOG_SHOWN', file=sys.stderr, flush=True)
            self.session.initiate()

    agent = Agent()
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    object_path = '/studio/clash/TunAuthentication'
    authority_owner = bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'GetNameOwner', GLib.Variant('(s)', ('org.freedesktop.PolicyKit1',)), None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    interface = Gio.DBusNodeInfo.new_for_xml('''<node><interface name="org.freedesktop.PolicyKit1.AuthenticationAgent">
      <method name="BeginAuthentication"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="a{ss}" direction="in"/><arg type="s" direction="in"/><arg type="a(sa{sv})" direction="in"/></method>
      <method name="CancelAuthentication"><arg type="s" direction="in"/></method>
    </interface></node>''').interfaces[0]
    def method(connection, sender, path, interface_name, method_name, parameters, invocation):
        if sender != authority_owner:
            invocation.return_dbus_error('org.freedesktop.DBus.Error.AccessDenied', 'Only the polkit authority may request authentication')
            return
        if method_name == 'CancelAuthentication':
            if agent.session:
                agent.session.cancel()
            invocation.return_value(GLib.Variant('()', ()))
        elif method_name == 'BeginAuthentication':
            action, message, icon, details, cookie, raw_identities = parameters.unpack()
            identities = [Polkit.UnixUser.new(identity['uid']) for kind, identity in raw_identities if kind == 'unix-user']
            if not identities:
                invocation.return_dbus_error('org.freedesktop.PolicyKit1.Error.Failed', 'No supported administrator identity')
                return
            agent.begin(action, message, icon, details, cookie, identities, invocation)
    registration = bus.register_object(object_path, interface, method, None, None)
    start_time = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
    subject = ('unix-process', {'pid': GLib.Variant('u', os.getpid()), 'start-time': GLib.Variant('t', start_time), 'uid': GLib.Variant('i', os.getuid())})
    try:
        bus.call_sync('org.freedesktop.PolicyKit1', '/org/freedesktop/PolicyKit1/Authority',
            'org.freedesktop.PolicyKit1.Authority', 'RegisterAuthenticationAgent',
            GLib.Variant('((sa{sv})ss)', (subject, os.environ.get('LANG', 'en_US.UTF-8'), object_path)),
            None, Gio.DBusCallFlags.NONE, 5000, None)
    except GLib.Error as error:
        print('AUTH_AGENT_REGISTRATION_FAILED: '+str(error), file=sys.stderr, flush=True)
        return 69
    command = subprocess.Popen(['/usr/bin/pkexec', '--disable-internal-agent', str(setcap),
        'cap_net_admin,cap_net_raw,cap_net_bind_service=ep', str(binary)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=sys.stderr)
    def poll():
        if command.poll() is not None:
            Gtk.main_quit()
            return False
        return True
    def terminate():
        if agent.session:
            agent.session.cancel()
        if command.poll() is None:
            command.terminate()
        Gtk.main_quit()
        return False
    GLib.timeout_add(100, poll)
    GLib.timeout_add_seconds(85, terminate)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, terminate)
    try:
        Gtk.main()
    finally:
        if agent.dialog:
            agent.dialog.destroy()
        if command.poll() is None:
            command.terminate()
        try:
            command.wait(3)
        except subprocess.TimeoutExpired:
            command.kill()
            command.wait()
    return command.returncode if command.returncode >= 0 else 126


if __name__ == '__main__':
    raise SystemExit(main())
