"""Explicit Windows GUI integration check using synthetic accounts and a private cache.

Run from the repository with: python tests/native_session_check.py
Requires the built build/Xervexl-next.exe. Never touches the real account/cache.
"""
import ctypes
import json
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Arena, Handler, ThreadingHTTPServer

runtime = ROOT/'data'/('native-session-'+uuid.uuid4().hex[:8]);runtime.mkdir()
account_path = runtime/'accounts.json';cache_path = runtime/'client-login.bin'
creds = dict(username='NativeRemembered', email='native-remembered@example.com', password='test-passphrase')
arena = Arena(account_path, seed=6)
user = arena.account(**dict(name=creds['username'], email=creds['email'], password=creds['password']))
user.update(coins=654, skill=12, inventory=['knife','arming'], weapon='arming')
arena.users['nativeremembered'] = user;arena.save()

http = None;service = None;port = 0;routes = {};clients = [];windows = []
block_resume = False;resume_seen = threading.Event();resume_release = threading.Event()


class PreviewHandler(Handler):
    limits = {}

    def handle_api(self, body):
        routes[self.path] = routes.get(self.path, 0)+1
        if self.path == '/auth/resume' and block_resume:
            resume_seen.set();resume_release.wait(6)
        super().handle_api(body)


def start_server():
    global http, service, arena, port, routes
    arena = Arena(account_path, seed=6);PreviewHandler.arena = arena;PreviewHandler.limits = {};routes = {}
    http = ThreadingHTTPServer(('127.0.0.1', port), PreviewHandler);port = http.server_port
    service = threading.Thread(target=http.serve_forever, daemon=True);service.start()


def stop_server():
    global http, service
    if http:
        http.shutdown();http.server_close();service.join();http = None;service = None


u = ctypes.windll.user32
u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
u.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


class RECT(ctypes.Structure):
    _fields_ = [('left',ctypes.c_long),('top',ctypes.c_long),('right',ctypes.c_long),('bottom',ctypes.c_long)]


def launch(api='opengl', explicit_server=False, smoke=False):
    args = [str(ROOT/'build'/'Xervexl-next.exe'), '--'+api, '--session-file='+str(cache_path)]
    if explicit_server:args.append(f'--server=http://127.0.0.1:{port}')
    if smoke:args.append('--smoke')
    startup = subprocess.STARTUPINFO();startup.dwFlags = subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow = 0
    process = subprocess.Popen(args, cwd=ROOT, startupinfo=startup);clients.append(process);found = []

    @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    def collect(hwnd, _):
        pid = ctypes.c_ulong();u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = ctypes.create_unicode_buffer(256);u.GetClassNameW(ctypes.c_void_p(hwnd), name, 256)
        if pid.value == process.pid and name.value == 'XervexlArenaWindow':found.append(hwnd)
        return 1

    for _ in range(80):
        u.EnumWindows(collect, 0)
        if found:break
        time.sleep(.05)
    assert found, 'Native game window missing'
    u.ShowWindow(ctypes.c_void_p(found[0]), 0);windows.append(found[0]);time.sleep(.6)
    return process, found[0]


def click(hwnd, x, y):
    rect = RECT();u.GetClientRect(hwnd, ctypes.byref(rect));x = int(x*rect.right/1280);y = int(y*rect.bottom/800)
    u.SendMessageW(hwnd, 0x200, 0, x|(y<<16));u.SendMessageW(hwnd, 0x201, 1, x|(y<<16));time.sleep(.3)


def type_text(hwnd, value):
    for char in value:u.SendMessageW(hwnd, 0x102, ord(char), 0)


def capture(hwnd, name):
    u.SendMessageW(hwnd, 0x100, 0x7b, 0);time.sleep(.35)
    shutil.copyfile(ROOT/'screenshots'/'capture.bmp', ROOT/'screenshots'/(name+'.bmp'))


def wait_for(condition):
    for _ in range(140):
        if condition():return
        time.sleep(.05)
    raise AssertionError('Native sign-in action did not reach expected state')


def signed_in():
    return any(s['user']['username'] == creds['username'] for s in arena.sessions.values())


def sign_in(hwnd):
    click(hwnd, 1170, 42);click(hwnd, 450, 326);type_text(hwnd, creds['username'])
    click(hwnd, 450, 411);type_text(hwnd, creds['password']);click(hwnd, 580, 493)
    wait_for(signed_in);time.sleep(.35)


def close(process, hwnd):
    u.SendMessageW(hwnd, 0x10, 0, 0);process.wait(timeout=10)


def finish_smoke(process):
    process.wait(timeout=10)
    report = json.loads((ROOT/'screenshots'/'opengl-home.json').read_text())
    assert not report['signed_in'], report


try:
    start_server();p,w = launch(explicit_server=True);sign_in(w);capture(w, 'session-signed-in')
    bearer = next(iter(arena.sessions));encrypted = cache_path.read_bytes()
    assert bearer.encode() not in encrypted and creds['password'].encode() not in encrypted
    close(p,w);stop_server();start_server()
    p,w = launch('vulkan');wait_for(signed_in);time.sleep(.35);capture(w, 'session-restored-vulkan')
    assert routes.get('/auth/resume',0) >= 1 and routes.get('/auth/login',0) == 0
    assert all(f['bot'] for f in arena.fighters.values())
    close(p,w);stop_server()

    # An unavailable server must not destroy the saved sign-in.
    saved_bytes = cache_path.read_bytes();p,w = launch();time.sleep(.4)
    assert cache_path.read_bytes() == saved_bytes;capture(w, 'session-temporarily-offline')
    start_server();wait_for(signed_in);time.sleep(.35);capture(w, 'session-reconnected')
    click(w,1170,42);wait_for(lambda:not arena.remembered.tokens);close(p,w)
    stop_server();start_server();p,w = launch(smoke=True);finish_smoke(p)
    assert not arena.sessions and routes.get('/auth/resume',0) == 0

    # Logout while offline stays logged out on reopening and retries revocation.
    p,w = launch();sign_in(w);stop_server();click(w,1170,42);capture(w, 'session-offline-logout');close(p,w)
    start_server();assert arena.remembered.tokens
    p,w = launch(smoke=True);wait_for(lambda:not arena.remembered.tokens);finish_smoke(p)
    assert not arena.sessions and routes.get('/auth/resume',0) == 0 and routes.get('/auth/logout',0) >= 1

    # A restore response arriving after Logout must never sign the user back in.
    p,w = launch();sign_in(w);close(p,w)
    block_resume = True;resume_release.clear();resume_seen.clear()
    p,w = launch(smoke=True);assert resume_seen.wait(3)
    click(w,1170,42);resume_release.set()
    wait_for(lambda:not arena.remembered.tokens);finish_smoke(p)
    assert not arena.sessions
    print(json.dumps(dict(native_sign_in=True,encrypted_cache=True,automatic_restore_without_password=True,
                          server_restart=True,temporary_outage_retry=True,logout_survives_restart=True,
                          offline_logout_and_revocation_retry=True,late_restore_cannot_undo_logout=True,
                          renderers=['OpenGL','Vulkan'],real_accounts_untouched=True)))
finally:
    resume_release.set()
    for process,hwnd in zip(clients,windows):
        if process.poll() is None:
            u.SendMessageW(hwnd,0x10,0,0)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.terminate();process.wait()
    stop_server()
