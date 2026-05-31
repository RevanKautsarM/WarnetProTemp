"""
WarnetPro Client GUI - Tampilan untuk PC Client warnet.
Entry point: jalankan file ini untuk memulai client.

Fitur:
  - Auto-connect ke server saat dijalankan
  - Auto-lock (PC terkunci saat pertama connect)
  - Timer countdown besar saat sesi aktif
  - Peringatan saat waktu hampir habis
  - Lock screen fullscreen saat terkunci
"""

import configparser
import os
import sys
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import WarnetProClient

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')

# ═══════════════════════════════════════════════════════════════════════
# Colors
# ═══════════════════════════════════════════════════════════════════════
BG_DARK  = '#0f172a'
BG_CARD  = '#1e293b'
BG_INPUT = '#0c1322'
FG_TITLE = '#f1f5f9'
FG_TEXT  = '#94a3b8'
FG_DIM   = '#475569'
ACCENT   = '#38bdf8'
GREEN    = '#22c55e'
RED      = '#ef4444'
YELLOW   = '#f59e0b'


def load_config() -> dict:
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    return {
        'host': cfg.get('server', 'host', fallback='127.0.0.1'),
        'port': cfg.getint('server', 'port', fallback=9999),
        'pc_name': cfg.get('client', 'pc_name', fallback='PC-01'),
        'reconnect_interval': cfg.getint('client', 'reconnect_interval',
                                         fallback=5),
    }


# ═══════════════════════════════════════════════════════════════════════
# Lock Screen
# ═══════════════════════════════════════════════════════════════════════

class LockScreen:
    """Fullscreen overlay saat operator mengunci PC."""

    def __init__(self, parent: tk.Tk, pc_name: str):
        self.parent = parent
        self.pc_name = pc_name
        self.window = None

    def show(self):
        if self.window and self.window.winfo_exists():
            return
        self.window = tk.Toplevel(self.parent)
        w = self.window
        w.attributes('-fullscreen', True)
        w.attributes('-topmost', True)
        w.configure(bg='#050814')
        w.overrideredirect(True)
        w.protocol("WM_DELETE_WINDOW", lambda: None)
        try:
            w.grab_set()
        except Exception:
            pass
        w.focus_force()
        for seq in ('<Alt-F4>', '<Escape>', '<Control-Escape>',
                    '<Super_L>', '<Super_R>', '<Alt-Tab>'):
            w.bind(seq, lambda e: 'break')

        scr_w = w.winfo_screenwidth()
        scr_h = w.winfo_screenheight()

        # Background canvas with glow effect
        canvas = tk.Canvas(w, width=scr_w, height=scr_h,
                           bg='#050814', highlightthickness=0)
        canvas.place(x=0, y=0)

        cx, cy = scr_w // 2, scr_h // 2 - 60
        for r, color in [(160, '#0d1a3a'), (120, '#0f2050'), (90, '#112268')]:
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                               fill=color, outline='')

        frame = tk.Frame(w, bg='#050814')
        frame.place(relx=0.5, rely=0.5, anchor='center')

        tk.Label(frame, text='🔒',
                 font=('Segoe UI Emoji', 72),
                 bg='#050814', fg=RED).pack(pady=(0, 16))

        tk.Label(frame, text='PC DIKUNCI',
                 font=('Segoe UI', 26, 'bold'),
                 bg='#050814', fg=RED).pack()

        tk.Label(frame, text=self.pc_name,
                 font=('Segoe UI', 14),
                 bg='#050814', fg=FG_DIM).pack(pady=(4, 30))

        tk.Frame(frame, width=420, height=1, bg='#1e293b').pack(pady=4)

        self.clock_lbl = tk.Label(frame, text='00:00:00',
                                  font=('Segoe UI', 44, 'bold'),
                                  bg='#050814', fg=FG_TITLE)
        self.clock_lbl.pack(pady=16)

        tk.Label(frame, text='Hubungi operator untuk membuka kunci.',
                 font=('Segoe UI', 12),
                 bg='#050814', fg=FG_DIM).pack()

        # Watermark
        tk.Label(w, text='WarnetPro v3.0',
                 font=('Segoe UI', 8),
                 bg='#050814', fg='#1e293b').place(relx=1.0, rely=1.0,
                                                    anchor='se', x=-12, y=-8)
        self._tick()

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

    def _tick(self):
        if self.window and self.window.winfo_exists():
            self.clock_lbl.config(
                text=datetime.now().strftime('%H:%M:%S'))
            self.window.after(1000, self._tick)


# ═══════════════════════════════════════════════════════════════════════
# Client GUI
# ═══════════════════════════════════════════════════════════════════════

class ClientGUI:
    """GUI utama client — auto-connect, tanpa input manual."""

    def __init__(self):
        self.config = load_config()
        self.client = None
        self._build_root()
        self.lock_screen = LockScreen(self.root, self.config['pc_name'])
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Root ─────────────────────────────────────────────────────────────

    def _build_root(self):
        self.root = tk.Tk()
        self.root.title(f'WarnetPro — {self.config["pc_name"]}')
        self.root.geometry('420x480')
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 420) // 2
        y = (sh - 480) // 2
        self.root.geometry(f'420x480+{x}+{y}')

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BG_CARD, height=56)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text='⚡ WarnetPro Client',
                 font=('Segoe UI', 13, 'bold'),
                 bg=BG_CARD, fg=ACCENT).pack(side='left', padx=14)

        self.dot = tk.Label(hdr, text='●',
                            font=('Segoe UI', 13),
                            bg=BG_CARD, fg=RED)
        self.dot.pack(side='right', padx=14)

        self.lbl_conn_status = tk.Label(
            hdr, text='Menghubungkan...',
            font=('Segoe UI', 9), bg=BG_CARD, fg=YELLOW)
        self.lbl_conn_status.pack(side='right')

        # ── Info row ──────────────────────────────────────────────────────
        info = tk.Frame(self.root, bg=BG_DARK)
        info.pack(fill='x', padx=16, pady=(12, 0))

        for lbl, val in [('PC Name', self.config['pc_name']),
                          ('Server', f'{self.config["host"]}:{self.config["port"]}')]:
            row = tk.Frame(info, bg=BG_DARK)
            row.pack(fill='x', pady=1)
            tk.Label(row, text=f'{lbl}:', width=8, anchor='w',
                     font=('Segoe UI', 9), bg=BG_DARK, fg=FG_DIM).pack(side='left')
            tk.Label(row, text=val, anchor='w',
                     font=('Segoe UI', 9, 'bold'),
                     bg=BG_DARK, fg=FG_TEXT).pack(side='left')

        # ── Divider ──────────────────────────────────────────────────────
        tk.Frame(self.root, height=1, bg='#1e293b').pack(
            fill='x', padx=16, pady=12)

        # ── Session card ─────────────────────────────────────────────────
        card = tk.Frame(self.root, bg=BG_CARD)
        card.pack(fill='x', padx=16)

        tk.Label(card, text='STATUS SESI',
                 font=('Segoe UI', 8, 'bold'),
                 bg=BG_CARD, fg=FG_DIM).pack(anchor='w', padx=14, pady=(12, 0))

        self.lbl_session = tk.Label(
            card, text='Menunggu...',
            font=('Segoe UI', 15, 'bold'),
            bg=BG_CARD, fg=FG_DIM)
        self.lbl_session.pack(anchor='w', padx=14, pady=(4, 0))

        self.lbl_timer = tk.Label(
            card, text='--:--',
            font=('Courier New', 42, 'bold'),
            bg=BG_CARD, fg=ACCENT)
        self.lbl_timer.pack(padx=14, pady=(4, 14))

        # ── Divider ──────────────────────────────────────────────────────
        tk.Frame(self.root, height=1, bg='#1e293b').pack(
            fill='x', padx=16, pady=12)

        # ── Log ──────────────────────────────────────────────────────────
        log_frame = tk.Frame(self.root, bg=BG_DARK)
        log_frame.pack(fill='both', expand=True, padx=16, pady=(0, 12))

        tk.Label(log_frame, text='LOG AKTIVITAS',
                 font=('Segoe UI', 8, 'bold'),
                 bg=BG_DARK, fg=FG_DIM).pack(anchor='w', pady=(0, 2))

        self.txt_log = tk.Text(
            log_frame, font=('Consolas', 8), bg=BG_INPUT, fg=FG_TEXT,
            relief='flat', height=7, state='disabled', wrap='word',
            insertbackground=FG_TEXT)
        self.txt_log.pack(fill='both', expand=True)

    # ── Auto Connect ─────────────────────────────────────────────────────

    def _auto_connect(self):
        """Otomatis connect ke server saat aplikasi start."""
        self.client = WarnetProClient(
            server_host=self.config['host'],
            server_port=self.config['port'],
            pc_name=self.config['pc_name'],
            reconnect_interval=self.config['reconnect_interval'],
        )
        # Wire callbacks
        self.client.on_connected = lambda: self.root.after(0, self._on_connected)
        self.client.on_disconnected = lambda: self.root.after(0, self._on_disconnected)
        self.client.on_session_update = lambda d: self.root.after(
            0, self._on_session_update, d)
        self.client.on_session_end = lambda: self.root.after(0, self._on_session_end)
        self.client.on_lock = lambda: self.root.after(0, self.lock_screen.show)
        self.client.on_unlock = lambda: self.root.after(0, self._on_unlock)
        self.client.on_message = lambda t: self.root.after(
            0, lambda txt=t: messagebox.showinfo('Pesan dari Operator', txt))
        self.client.on_time_warning = lambda d: self.root.after(
            0, self._on_time_warning, d)
        self.client.on_log = lambda m: self.root.after(0, self._append_log, m)

        self.client.connect()
        self._append_log(f'Auto-connect ke {self.config["host"]}:{self.config["port"]}')

    # ── Callbacks ────────────────────────────────────────────────────────

    def _on_connected(self):
        self.dot.config(fg=GREEN)
        self.lbl_conn_status.config(text='Terhubung', fg=GREEN)
        self.lbl_session.config(text='PC Terkunci', fg=RED)
        self.lbl_timer.config(text='--:--', fg=FG_DIM)

    def _on_disconnected(self):
        self.dot.config(fg=RED)
        self.lbl_conn_status.config(text='Terputus', fg=RED)
        self.lbl_session.config(text='Tidak terhubung', fg=RED)
        self.lbl_timer.config(text='--:--', fg=FG_DIM)
        if self.client and self.client.running:
            self.lbl_conn_status.config(text='Reconnecting...', fg=YELLOW)
            self.dot.config(fg=YELLOW)

    def _on_unlock(self):
        """Dipanggil saat PC di-unlock (sesi dimulai atau manual unlock)."""
        self.lock_screen.hide()
        self.lbl_session.config(text='Sesi Aktif', fg=GREEN)

    def _on_session_update(self, data: dict):
        remaining = data.get('remaining_secs', 0)
        total = data.get('total_secs', 0)
        mins, secs = divmod(max(0, remaining), 60)
        hrs, mins_r = divmod(mins, 60)

        if hrs > 0:
            timer_str = f'{hrs:02d}:{mins_r:02d}:{secs:02d}'
        else:
            timer_str = f'{mins:02d}:{secs:02d}'

        if remaining <= 60:
            color = RED
            self.lbl_session.config(text='⚠ Waktu Hampir Habis!', fg=RED)
        elif remaining <= 300:
            color = YELLOW
            self.lbl_session.config(text='Sesi Aktif', fg=GREEN)
        else:
            color = ACCENT
            self.lbl_session.config(text='Sesi Aktif', fg=GREEN)

        self.lbl_timer.config(text=timer_str, fg=color)

    def _on_session_end(self):
        self.lbl_session.config(text='Waktu Habis!', fg=RED)
        self.lbl_timer.config(text='00:00', fg=RED)
        # Beep warning
        try:
            self.root.bell()
        except Exception:
            pass

    def _on_time_warning(self, data: dict):
        """Peringatan saat waktu hampir habis (≤60 detik)."""
        try:
            self.root.bell()
            self.root.bell()
        except Exception:
            pass

    def _append_log(self, msg: str):
        ts = datetime.now().strftime('%H:%M:%S')
        line = f'[{ts}] {msg}\n'
        self.txt_log.config(state='normal')
        self.txt_log.insert('end', line)
        self.txt_log.see('end')
        lines = int(self.txt_log.index('end-1c').split('.')[0])
        if lines > 200:
            self.txt_log.delete('1.0', f'{lines - 200}.0')
        self.txt_log.config(state='disabled')

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _on_close(self):
        if self.client:
            self.client.disconnect()
        self.lock_screen.hide()
        self.root.destroy()

    def run(self):
        # Auto-connect setelah GUI tampil
        self.root.after(500, self._auto_connect)
        self.root.mainloop()


# ═════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    if not os.path.exists(CONFIG_FILE):
        print(f'[ERROR] Config tidak ditemukan: {CONFIG_FILE}')
        print('Buat file config.ini dulu.')
        sys.exit(1)
    app = ClientGUI()
    app.run()
