#!/usr/bin/env python3
"""
WarnetPro Client GUI v2.0
Aplikasi client GUI yang berjalan di setiap PC warnet.

Fitur:
  - Heartbeat otomatis ke server
  - Polling status sesi (timer countdown)
  - Login/Logout member
  - Lock Screen fullscreen saat diperintah operator
  - Screenshot & upload ke server saat diminta operator
  - System tray icon (jika pystray tersedia)
"""

import configparser
import io
import os
import platform
import socket
import sys
import threading
import time
import uuid
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import requests

# ── Optional dependencies ──────────────────────────────────────────────────
try:
    from PIL import Image, ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

# ============================================================================
# Configuration
# ============================================================================

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


def load_config():
    """Load configuration from config.ini."""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return {
        'server_url':           config.get('server', 'url',                  fallback='http://127.0.0.1:8000'),
        'pc_name':              config.get('server', 'pc_name',               fallback=socket.gethostname()),
        'heartbeat_interval':   config.getint('client', 'heartbeat_interval', fallback=5),
        'status_poll_interval': config.getint('client', 'status_poll_interval', fallback=3),
        'command_poll_interval':config.getint('client', 'command_poll_interval', fallback=2),
        'screenshot_quality':   config.getint('client', 'screenshot_quality',  fallback=60),
    }


# ============================================================================
# Network Utilities
# ============================================================================

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def get_mac_address():
    try:
        mac_int = uuid.getnode()
        return ':'.join(f'{(mac_int >> (8 * i)) & 0xff:02x}' for i in reversed(range(6)))
    except Exception:
        return '00:00:00:00:00:00'


# ============================================================================
# Lock Screen
# ============================================================================

class LockScreen:
    """Fullscreen lock overlay — ditampilkan saat operator mengunci PC."""

    def __init__(self, parent_root: tk.Tk, pc_name: str):
        self.root     = parent_root
        self.pc_name  = pc_name
        self.window   = None
        self._job     = None

    # ── public ────────────────────────────────────────────────────────────

    def show(self):
        if self.window and self.window.winfo_exists():
            return
        self.window = tk.Toplevel(self.root)
        self._configure_window()
        self._build_ui()
        self._tick_clock()

    def hide(self):
        if self.window and self.window.winfo_exists():
            try:
                self.window.grab_release()
            except Exception:
                pass
            self.window.destroy()
        self.window = None

    def is_visible(self) -> bool:
        return self.window is not None and self.window.winfo_exists()

    # ── private ───────────────────────────────────────────────────────────

    def _configure_window(self):
        w = self.window
        w.attributes('-fullscreen', True)
        w.attributes('-topmost', True)
        w.configure(bg='#050814')
        w.overrideredirect(True)
        w.protocol("WM_DELETE_WINDOW", lambda: None)
        w.grab_set()
        w.focus_force()
        # Block common exit shortcuts
        for seq in ('<Alt-F4>', '<Escape>', '<Control-Escape>',
                    '<Super_L>', '<Super_R>', '<Alt-Tab>'):
            w.bind(seq, lambda e: 'break')

    def _build_ui(self):
        w = self.window
        scr_w = w.winfo_screenwidth()
        scr_h = w.winfo_screenheight()

        # Gradient-like dark overlay using canvas
        canvas = tk.Canvas(w, width=scr_w, height=scr_h,
                            bg='#050814', highlightthickness=0)
        canvas.place(x=0, y=0)

        # Glowing circle behind icon
        cx, cy = scr_w // 2, scr_h // 2 - 60
        for r, alpha in [(140, '#0d1a3a'), (110, '#0f2050'), (80, '#112268')]:
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                               fill=alpha, outline='')

        # Center content frame
        frame = tk.Frame(w, bg='#050814')
        frame.place(relx=0.5, rely=0.5, anchor='center')

        # Lock icon
        tk.Label(frame, text='🔒',
                 font=('Segoe UI Emoji', 72),
                 bg='#050814', fg='#ef4444').pack(pady=(0, 16))

        # Title
        tk.Label(frame,
                 text='PC DIKUNCI OLEH OPERATOR',
                 font=('Segoe UI', 22, 'bold'),
                 bg='#050814', fg='#ef4444').pack()

        # PC name
        tk.Label(frame,
                 text=self.pc_name,
                 font=('Segoe UI', 14),
                 bg='#050814', fg='#475569').pack(pady=(6, 30))

        # Separator
        tk.Frame(frame, width=420, height=1, bg='#1e293b').pack(pady=4)

        # Clock
        self.clock_lbl = tk.Label(frame,
                                   text='00:00:00',
                                   font=('Segoe UI', 40, 'bold'),
                                   bg='#050814', fg='#e2e8f0')
        self.clock_lbl.pack(pady=16)

        # Hint
        tk.Label(frame,
                 text='Hubungi operator untuk membuka kunci.',
                 font=('Segoe UI', 11),
                 bg='#050814', fg='#334155').pack(pady=(8, 0))

        # Corner watermark
        tk.Label(w, text='WarnetPro v2.0',
                 font=('Segoe UI', 8),
                 bg='#050814', fg='#1e293b').place(relx=1.0, rely=1.0,
                                                    anchor='se', x=-12, y=-8)

    def _tick_clock(self):
        if self.window and self.window.winfo_exists():
            self.clock_lbl.config(text=datetime.now().strftime('%H:%M:%S'))
            self._job = self.window.after(1000, self._tick_clock)


# ============================================================================
# Main Application
# ============================================================================

class WarnetProApp:
    """Aplikasi client utama dengan GUI Tkinter."""

    # ── init ──────────────────────────────────────────────────────────────

    def __init__(self):
        self.config      = load_config()
        self.base_url    = self.config['server_url'].rstrip('/')
        self.pc_name     = self.config['pc_name']
        self.ip_address  = get_ip_address()
        self.mac_address = get_mac_address()

        self.running              = False
        self.current_session      = None
        self.last_remaining_secs  = None
        self.warning_played       = False
        self.time_up_played       = False
        self.is_locked            = False

        self._build_root()
        self.lock_screen = LockScreen(self.root, self.pc_name)
        self._build_ui()
        self._setup_tray()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── root window ───────────────────────────────────────────────────────

    def _build_root(self):
        self.root = tk.Tk()
        self.root.title(f'WarnetPro Client — {self.pc_name}')
        self.root.geometry('420x540')
        self.root.resizable(False, False)
        self.root.configure(bg='#0f172a')
        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - 420) // 2
        y  = (sh - 540) // 2
        self.root.geometry(f'420x540+{x}+{y}')

    # ── UI building ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ─── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg='#1e293b', height=68)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text='WarnetPro Client',
                 font=('Segoe UI', 13, 'bold'),
                 bg='#1e293b', fg='#38bdf8').place(x=16, y=10)

        tk.Label(hdr, text=f'v2.0  ·  {self.pc_name}',
                 font=('Segoe UI', 9),
                 bg='#1e293b', fg='#475569').place(x=16, y=36)

        self.conn_dot = tk.Label(hdr, text='●',
                                  font=('Segoe UI', 13),
                                  bg='#1e293b', fg='#ef4444')
        self.conn_dot.place(relx=1.0, rely=0.5, anchor='e', x=-16)

        # ─── Info row ─────────────────────────────────────────────────────
        info = tk.Frame(self.root, bg='#0f172a')
        info.pack(fill='x', padx=16, pady=(14, 0))

        for lbl, val in [('Server', self.base_url),
                          ('IP', self.ip_address),
                          ('MAC', self.mac_address)]:
            row = tk.Frame(info, bg='#0f172a')
            row.pack(fill='x', pady=1)
            tk.Label(row, text=f'{lbl}:', width=7, anchor='w',
                     font=('Segoe UI', 9), bg='#0f172a', fg='#475569').pack(side='left')
            tk.Label(row, text=val, anchor='w',
                     font=('Segoe UI', 9, 'bold'),
                     bg='#0f172a', fg='#64748b').pack(side='left')

        # ─── Divider ──────────────────────────────────────────────────────
        tk.Frame(self.root, height=1, bg='#1e293b').pack(fill='x', padx=16, pady=14)

        # ─── Session card ─────────────────────────────────────────────────
        card = tk.Frame(self.root, bg='#1e293b')
        card.pack(fill='x', padx=16)

        tk.Label(card, text='STATUS SESI',
                 font=('Segoe UI', 8, 'bold'),
                 bg='#1e293b', fg='#475569').pack(anchor='w', padx=14, pady=(12, 0))

        self.lbl_session_name = tk.Label(card, text='PC Tersedia',
                                          font=('Segoe UI', 15, 'bold'),
                                          bg='#1e293b', fg='#22c55e')
        self.lbl_session_name.pack(anchor='w', padx=14, pady=(4, 0))

        self.lbl_timer = tk.Label(card, text='',
                                   font=('Courier New', 30, 'bold'),
                                   bg='#1e293b', fg='#38bdf8')
        self.lbl_timer.pack(anchor='w', padx=14, pady=(2, 12))

        # ─── Divider ──────────────────────────────────────────────────────
        tk.Frame(self.root, height=1, bg='#1e293b').pack(fill='x', padx=16, pady=14)

        # ─── Member buttons ───────────────────────────────────────────────
        btns = tk.Frame(self.root, bg='#0f172a')
        btns.pack(fill='x', padx=16)

        self.btn_login = tk.Button(
            btns, text='Login Member',
            font=('Segoe UI', 10, 'bold'),
            bg='#0ea5e9', fg='white', activebackground='#38bdf8',
            relief='flat', padx=12, pady=8, cursor='hand2',
            command=self._open_login_dialog)
        self.btn_login.pack(side='left', expand=True, fill='x', padx=(0, 6))

        self.btn_logout = tk.Button(
            btns, text='Logout',
            font=('Segoe UI', 10),
            bg='#1e293b', fg='#94a3b8', activebackground='#334155',
            relief='flat', padx=12, pady=8, cursor='hand2',
            command=self._do_logout)
        self.btn_logout.pack(side='left', expand=True, fill='x', padx=(6, 0))

        # ─── Divider ──────────────────────────────────────────────────────
        tk.Frame(self.root, height=1, bg='#1e293b').pack(fill='x', padx=16, pady=14)

        # ─── Log area ─────────────────────────────────────────────────────
        log_frame = tk.Frame(self.root, bg='#0f172a')
        log_frame.pack(fill='both', expand=True, padx=16, pady=(0, 14))

        tk.Label(log_frame, text='LOG AKTIVITAS',
                 font=('Segoe UI', 8, 'bold'),
                 bg='#0f172a', fg='#475569').pack(anchor='w', pady=(0, 4))

        self.txt_log = tk.Text(log_frame,
                                font=('Consolas', 8),
                                bg='#080d1a', fg='#64748b',
                                relief='flat', height=7,
                                state='disabled', wrap='word',
                                insertbackground='#64748b')
        self.txt_log.pack(fill='both', expand=True)

    # ── System Tray ───────────────────────────────────────────────────────

    def _setup_tray(self):
        if not PYSTRAY_AVAILABLE or not PIL_AVAILABLE:
            return
        try:
            # Create a simple colored icon
            img = Image.new('RGB', (64, 64), '#0ea5e9')
            menu = pystray.Menu(
                pystray.MenuItem('Tampilkan', lambda: self.root.after(0, self._show_window)),
                pystray.MenuItem('Keluar',    lambda: self.root.after(0, self._quit_app)),
            )
            self.tray = pystray.Icon('WarnetPro', img, f'WarnetPro — {self.pc_name}', menu)
            threading.Thread(target=self.tray.run, daemon=True, name='tray').start()
        except Exception:
            pass

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    # ── Logging ───────────────────────────────────────────────────────────

    def log(self, msg: str):
        ts = datetime.now().strftime('%H:%M:%S')
        line = f'[{ts}] {msg}\n'

        def _upd():
            self.txt_log.config(state='normal')
            self.txt_log.insert('end', line)
            self.txt_log.see('end')
            # Prune to 200 lines
            lines = int(self.txt_log.index('end-1c').split('.')[0])
            if lines > 200:
                self.txt_log.delete('1.0', f'{lines - 200}.0')
            self.txt_log.config(state='disabled')

        try:
            self.root.after(0, _upd)
        except Exception:
            pass

    # ── API helpers ───────────────────────────────────────────────────────

    def _api_url(self, path: str) -> str:
        return f'{self.base_url}/api/client{path}'

    def api_get(self, path: str):
        try:
            r = requests.get(self._api_url(path), timeout=5)
            return r.json(), r.status_code
        except requests.exceptions.ConnectionError:
            return None, 0
        except Exception:
            return None, 0

    def api_post(self, path: str, data=None):
        try:
            r = requests.post(self._api_url(path), json=data or {}, timeout=5)
            return r.json(), r.status_code
        except requests.exceptions.ConnectionError:
            return None, 0
        except Exception:
            return None, 0

    # ── Heartbeat ─────────────────────────────────────────────────────────

    def send_heartbeat(self) -> bool:
        result, status = self.api_post('/heartbeat', {
            'pc_name':    self.pc_name,
            'ip_address': self.ip_address,
            'mac_address':self.mac_address,
        })
        ok = status == 200
        color = '#22c55e' if ok else '#ef4444'
        try:
            self.root.after(0, lambda: self.conn_dot.config(fg=color))
        except Exception:
            pass
        return ok

    def _heartbeat_loop(self):
        iv = self.config['heartbeat_interval']
        while self.running:
            self.send_heartbeat()
            time.sleep(iv)

    # ── Status polling ────────────────────────────────────────────────────

    def _poll_status(self):
        result, status = self.api_get(f'/status/{self.pc_name}')
        if status != 200 or result is None:
            return

        session      = result.get('session')
        prev_session = self.current_session
        self.current_session = session

        if session:
            remaining = session.get('remaining_seconds', 0)
            customer  = session.get('customer_name', 'Guest')
            is_member = session.get('is_member', False)
            mins, secs = divmod(max(0, remaining), 60)
            timer_str  = f'{mins:02d}:{secs:02d}'

            if remaining <= 60:
                timer_col = '#ef4444'
            elif remaining <= 300:
                timer_col = '#f59e0b'
            else:
                timer_col = '#38bdf8'

            name_str = f'{"[M] " if is_member else ""}{customer}'

            if remaining <= 60 and not self.warning_played and remaining > 0:
                self.warning_played = True
                self.log('⚠ Waktu hampir habis!')
            if remaining <= 0 and not self.time_up_played:
                self.time_up_played = True
                self.log('🔔 WAKTU HABIS!')

            self.last_remaining_secs = remaining

            def _upd(n=name_str, t=timer_str, c=timer_col):
                self.lbl_session_name.config(text=n, fg='#e2e8f0')
                self.lbl_timer.config(text=t, fg=c)

        else:
            if prev_session is not None:
                self.log('Sesi berakhir. PC tersedia.')
                self.warning_played = False
                self.time_up_played = False
            self.last_remaining_secs = None

            def _upd():
                self.lbl_session_name.config(text='PC Tersedia', fg='#22c55e')
                self.lbl_timer.config(text='')

        try:
            self.root.after(0, _upd)
        except Exception:
            pass

    def _status_loop(self):
        iv = self.config['status_poll_interval']
        while self.running:
            self._poll_status()
            time.sleep(iv)

    # ── Command polling ───────────────────────────────────────────────────

    def _poll_commands(self):
        result, status = self.api_get(f'/commands/{self.pc_name}')
        if status != 200 or result is None:
            return

        for cmd in result.get('commands', []):
            cmd_id   = cmd.get('id')
            cmd_type = cmd.get('type')
            payload  = cmd.get('payload')

            # Acknowledge first
            self.api_post(f'/commands/{cmd_id}/ack')
            # Execute
            self._execute_command(cmd_type, payload)

    def _execute_command(self, cmd_type: str, payload=None):
        self.log(f'▶ Perintah: {cmd_type}')

        if cmd_type == 'shutdown':
            self._notify_offline()
            if platform.system() == 'Windows':
                os.system('shutdown /s /t 5 /c "WarnetPro: PC dimatikan oleh operator"')

        elif cmd_type == 'restart':
            self._notify_offline()
            if platform.system() == 'Windows':
                os.system('shutdown /r /t 5 /c "WarnetPro: PC di-restart oleh operator"')

        elif cmd_type == 'message':
            self.log(f'💬 Pesan: {payload}')
            self.root.after(0, lambda p=payload: messagebox.showinfo(
                'Pesan dari Operator', p or 'Ada pesan dari operator'))

        elif cmd_type == 'lock':
            self.is_locked = True
            self.log('🔒 PC dikunci oleh operator')
            self.root.after(0, self.lock_screen.show)

        elif cmd_type == 'unlock':
            self.is_locked = False
            self.log('🔓 PC dibuka oleh operator')
            self.root.after(0, self.lock_screen.hide)

        elif cmd_type == 'screenshot_request':
            self.log('📷 Mengambil screenshot...')
            threading.Thread(target=self._capture_and_upload,
                             daemon=True, name='screenshot').start()

    def _command_loop(self):
        iv = self.config['command_poll_interval']
        while self.running:
            self._poll_commands()
            time.sleep(iv)

    # ── Screenshot ────────────────────────────────────────────────────────

    def _capture_and_upload(self):
        if not PIL_AVAILABLE:
            self.log('[ERROR] Pillow tidak terinstal. Jalankan: pip install Pillow')
            return
        try:
            screenshot = ImageGrab.grab()
            buf = io.BytesIO()
            quality = self.config['screenshot_quality']
            # Scale down to reduce size (max 1280px wide)
            w, h = screenshot.size
            if w > 1280:
                ratio      = 1280 / w
                screenshot = screenshot.resize((1280, int(h * ratio)), Image.LANCZOS)
            screenshot.save(buf, format='JPEG', quality=quality, optimize=True)
            buf.seek(0)

            url   = f'{self.base_url}/api/client/screenshot/upload'
            files = {'screenshot': (f'{self.pc_name}.jpg', buf, 'image/jpeg')}
            data  = {'pc_name': self.pc_name}
            resp  = requests.post(url, files=files, data=data, timeout=15)

            if resp.status_code == 200:
                self.log('✓ Screenshot terkirim ke server')
            else:
                self.log(f'[WARN] Upload screenshot gagal ({resp.status_code})')
        except Exception as e:
            self.log(f'[ERROR] Screenshot: {e}')

    # ── Member Login / Logout ─────────────────────────────────────────────

    def _open_login_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title('Login Member')
        dlg.geometry('320x220')
        dlg.configure(bg='#1e293b')
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width()  - 320) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 220) // 2
        dlg.geometry(f'+{x}+{y}')

        tk.Label(dlg, text='Login Member',
                 font=('Segoe UI', 13, 'bold'),
                 bg='#1e293b', fg='white').pack(pady=(18, 10))

        frm = tk.Frame(dlg, bg='#1e293b')
        frm.pack(padx=22, fill='x')

        tk.Label(frm, text='Username', font=('Segoe UI', 9),
                 bg='#1e293b', fg='#94a3b8').pack(anchor='w')
        e_user = tk.Entry(frm, font=('Segoe UI', 11),
                          bg='#0f172a', fg='white', insertbackground='white',
                          relief='flat')
        e_user.pack(fill='x', ipady=5, pady=(2, 10))

        tk.Label(frm, text='Password', font=('Segoe UI', 9),
                 bg='#1e293b', fg='#94a3b8').pack(anchor='w')
        e_pass = tk.Entry(frm, font=('Segoe UI', 11), show='*',
                          bg='#0f172a', fg='white', insertbackground='white',
                          relief='flat')
        e_pass.pack(fill='x', ipady=5, pady=(2, 14))

        def _submit():
            u = e_user.get().strip()
            p = e_pass.get().strip()
            if not u or not p:
                messagebox.showerror('Error', 'Isi username & password!', parent=dlg)
                return
            dlg.destroy()
            threading.Thread(target=self._member_login, args=(u, p), daemon=True).start()

        tk.Button(frm, text='Login',
                  font=('Segoe UI', 10, 'bold'),
                  bg='#0ea5e9', fg='white', activebackground='#38bdf8',
                  relief='flat', padx=10, pady=7, cursor='hand2',
                  command=_submit).pack(fill='x')

        e_user.bind('<Return>', lambda _: e_pass.focus_set())
        e_pass.bind('<Return>', lambda _: _submit())
        e_user.focus_set()

    def _member_login(self, username: str, password: str):
        result, status = self.api_post('/member-login', {
            'pc_name':  self.pc_name,
            'username': username,
            'password': password,
        })
        if status == 200:
            self.log(f'✓ {result.get("message", "Login berhasil")}')
            self.warning_played = False
            self.time_up_played = False
        else:
            error = (result.get('error', 'Login gagal') if result else 'Koneksi gagal')
            self.log(f'[ERROR] Login: {error}')
            self.root.after(0, lambda e=error: messagebox.showerror('Login Gagal', e))

    def _do_logout(self):
        threading.Thread(target=self._member_logout, daemon=True).start()

    def _member_logout(self):
        result, status = self.api_post('/member-logout', {'pc_name': self.pc_name})
        if status == 200:
            self.log(f'✓ {result.get("message", "Logout berhasil")}')
            self.current_session = None
            self.warning_played  = False
            self.time_up_played  = False
        else:
            error = (result.get('error', 'Logout gagal') if result else 'Koneksi gagal')
            self.log(f'[ERROR] Logout: {error}')

    # ── Offline notification ──────────────────────────────────────────────

    def _notify_offline(self):
        self.api_post('/offline', {'pc_name': self.pc_name})

    # ── App lifecycle ─────────────────────────────────────────────────────

    def start(self):
        self.running = True
        self.log(f'Client dimulai  PC: {self.pc_name}')
        self.log(f'Server: {self.base_url}')

        if self.send_heartbeat():
            self.log('✓ Terhubung ke server')
        else:
            self.log('[WARN] Tidak dapat terhubung. Mencoba ulang...')

        # Background threads
        threading.Thread(target=self._heartbeat_loop,  daemon=True, name='heartbeat').start()
        threading.Thread(target=self._status_loop,     daemon=True, name='status').start()
        threading.Thread(target=self._command_loop,    daemon=True, name='commands').start()

        # Enter Tkinter main loop (blocks until window closed)
        self.root.mainloop()

    def _on_close(self):
        if messagebox.askokcancel('Keluar', 'Keluar dari WarnetPro Client?\nPC akan ditandai offline.'):
            self._quit_app()

    def _quit_app(self):
        self.running = False
        self._notify_offline()
        try:
            if PYSTRAY_AVAILABLE and hasattr(self, 'tray'):
                self.tray.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


# ============================================================================
# Entry Point
# ============================================================================

def main():
    if not os.path.exists(CONFIG_FILE):
        print(f'[ERROR] File konfigurasi tidak ditemukan: {CONFIG_FILE}')
        print('Buat file config.ini — lihat README.md untuk formatnya.')
        sys.exit(1)

    app = WarnetProApp()
    app.start()


if __name__ == '__main__':
    main()
