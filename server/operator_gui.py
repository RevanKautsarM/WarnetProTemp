"""
WarnetPro Operator GUI - Dashboard untuk mengontrol semua client.
Entry point: jalankan file ini untuk memulai server + dashboard.

Fitur:
  - Daftar semua client yang terhubung
  - Mulai/Stop sesi + timer
  - Tambah waktu
  - Lock/Unlock PC
  - Shutdown/Restart PC
  - Kirim pesan / Broadcast
  - Visual indicator (warna merah saat waktu hampir habis)
"""

import configparser
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

# Import server module dari folder yang sama
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import WarnetProServer

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


def load_config() -> dict:
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    return {
        'host': cfg.get('server', 'host', fallback='0.0.0.0'),
        'port': cfg.getint('server', 'port', fallback=9999),
        'auto_firewall': cfg.getboolean('server', 'auto_firewall', fallback=True),
        'default_duration': cfg.getint('session', 'default_duration', fallback=60),
    }


# ═══════════════════════════════════════════════════════════════════════
# Color palette
# ═══════════════════════════════════════════════════════════════════════
BG_DARK    = '#0f172a'
BG_CARD    = '#1e293b'
BG_INPUT   = '#0c1322'
FG_TITLE   = '#f1f5f9'
FG_TEXT     = '#94a3b8'
FG_DIM     = '#475569'
ACCENT     = '#38bdf8'
GREEN      = '#22c55e'
RED        = '#ef4444'
YELLOW     = '#f59e0b'
ORANGE     = '#f97316'


class OperatorGUI:
    """Dashboard operator WarnetPro."""

    def __init__(self):
        self.config = load_config()
        self.server = WarnetProServer(
            host=self.config['host'],
            port=self.config['port'],
            auto_firewall=self.config['auto_firewall'],
        )
        self.server.on_client_update = self._schedule_refresh
        self.server.on_log = self._schedule_log

        self._build_root()
        self._build_ui()
        self._start_server()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Root window ──────────────────────────────────────────────────────

    def _build_root(self):
        self.root = tk.Tk()
        self.root.title('WarnetPro Operator Dashboard')
        self.root.geometry('920x650')
        self.root.minsize(750, 500)
        self.root.configure(bg=BG_DARK)
        # Center
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 920) // 2
        y = (sh - 650) // 2
        self.root.geometry(f'920x650+{x}+{y}')

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BG_CARD, height=60)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text='⚡ WarnetPro Operator',
                 font=('Segoe UI', 15, 'bold'),
                 bg=BG_CARD, fg=ACCENT).pack(side='left', padx=16)

        self.lbl_status = tk.Label(
            hdr, text='Starting...',
            font=('Segoe UI', 9), bg=BG_CARD, fg=FG_DIM)
        self.lbl_status.pack(side='right', padx=16)

        self.lbl_online = tk.Label(
            hdr, text='● 0 online',
            font=('Segoe UI', 11, 'bold'), bg=BG_CARD, fg=GREEN)
        self.lbl_online.pack(side='right', padx=(0, 12))

        # ── Main paned ───────────────────────────────────────────────────
        main = tk.Frame(self.root, bg=BG_DARK)
        main.pack(fill='both', expand=True, padx=12, pady=8)

        # Left: client list
        left = tk.Frame(main, bg=BG_DARK)
        left.pack(side='left', fill='both', expand=True)

        tk.Label(left, text='DAFTAR PC CLIENT',
                 font=('Segoe UI', 9, 'bold'),
                 bg=BG_DARK, fg=FG_DIM).pack(anchor='w', pady=(0, 4))

        # Treeview style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.Treeview',
                        background=BG_CARD, foreground=FG_TITLE,
                        fieldbackground=BG_CARD, borderwidth=0,
                        font=('Segoe UI', 10))
        style.configure('Dark.Treeview.Heading',
                        background=BG_DARK, foreground=ACCENT,
                        borderwidth=0, font=('Segoe UI', 9, 'bold'))
        style.map('Dark.Treeview',
                  background=[('selected', '#334155')],
                  foreground=[('selected', '#ffffff')])

        cols = ('pc_name', 'ip', 'status', 'session', 'connected')
        self.tree = ttk.Treeview(left, columns=cols, show='headings',
                                 style='Dark.Treeview', height=14)
        self.tree.heading('pc_name', text='PC Name')
        self.tree.heading('ip', text='IP Address')
        self.tree.heading('status', text='Status')
        self.tree.heading('session', text='Sisa Waktu')
        self.tree.heading('connected', text='Terhubung')
        self.tree.column('pc_name', width=100)
        self.tree.column('ip', width=130)
        self.tree.column('status', width=80)
        self.tree.column('session', width=90)
        self.tree.column('connected', width=90)
        self.tree.pack(fill='both', expand=True)

        # Tag colors for status
        self.tree.tag_configure('locked', foreground=RED)
        self.tree.tag_configure('active', foreground=GREEN)
        self.tree.tag_configure('warning', foreground=YELLOW)
        self.tree.tag_configure('idle', foreground=FG_TEXT)

        # ── Right: controls ──────────────────────────────────────────────
        right = tk.Frame(main, bg=BG_DARK, width=220)
        right.pack(side='right', fill='y', padx=(12, 0))
        right.pack_propagate(False)

        tk.Label(right, text='KONTROL SESI',
                 font=('Segoe UI', 9, 'bold'),
                 bg=BG_DARK, fg=FG_DIM).pack(anchor='w', pady=(0, 8))

        # Session controls
        self._btn(right, '▶  Mulai Sesi', GREEN, self._cmd_start_session)
        self._btn(right, '■  Stop Sesi', RED, self._cmd_stop_session)
        self._btn(right, '+  Tambah Waktu', ACCENT, self._cmd_add_time)

        tk.Frame(right, height=1, bg=FG_DIM).pack(fill='x', pady=10)

        tk.Label(right, text='KONTROL PC',
                 font=('Segoe UI', 9, 'bold'),
                 bg=BG_DARK, fg=FG_DIM).pack(anchor='w', pady=(0, 8))

        self._btn(right, '🔒  Lock PC', YELLOW, self._cmd_lock)
        self._btn(right, '🔓  Unlock PC', GREEN, self._cmd_unlock)

        tk.Frame(right, height=1, bg=FG_DIM).pack(fill='x', pady=10)

        tk.Label(right, text='KOMUNIKASI',
                 font=('Segoe UI', 9, 'bold'),
                 bg=BG_DARK, fg=FG_DIM).pack(anchor='w', pady=(0, 8))

        self._btn(right, '💬  Kirim Pesan', ACCENT, self._cmd_send_msg)
        self._btn(right, '📢  Broadcast', ORANGE, self._cmd_broadcast)

        tk.Frame(right, height=1, bg=FG_DIM).pack(fill='x', pady=10)

        tk.Label(right, text='POWER',
                 font=('Segoe UI', 9, 'bold'),
                 bg=BG_DARK, fg=FG_DIM).pack(anchor='w', pady=(0, 8))

        self._btn(right, '⏻  Shutdown PC', RED, self._cmd_shutdown)
        self._btn(right, '↻  Restart PC', YELLOW, self._cmd_restart)

        # ── Bottom: log ──────────────────────────────────────────────────
        bot = tk.Frame(self.root, bg=BG_DARK)
        bot.pack(fill='x', padx=12, pady=(0, 8))

        tk.Label(bot, text='LOG AKTIVITAS',
                 font=('Segoe UI', 8, 'bold'),
                 bg=BG_DARK, fg=FG_DIM).pack(anchor='w', pady=(0, 2))

        self.txt_log = tk.Text(
            bot, font=('Consolas', 8), bg=BG_INPUT, fg=FG_TEXT,
            relief='flat', height=6, state='disabled', wrap='word',
            insertbackground=FG_TEXT)
        self.txt_log.pack(fill='x')

    def _btn(self, parent, text, color, cmd):
        b = tk.Button(parent, text=text, font=('Segoe UI', 9, 'bold'),
                      bg=BG_CARD, fg=color, activebackground='#334155',
                      activeforeground=color, relief='flat', anchor='w',
                      padx=10, pady=6, cursor='hand2', command=cmd)
        b.pack(fill='x', pady=2)
        return b

    # ── Server start ─────────────────────────────────────────────────────

    def _start_server(self):
        try:
            self.server.start()
            port = self.config['port']
            self.lbl_status.config(text=f'Server aktif — port {port}')
        except Exception as e:
            self.lbl_status.config(text=f'ERROR: {e}', fg=RED)
            messagebox.showerror('Server Error',
                                 f'Gagal memulai server:\n{e}')

    # ── GUI callbacks ────────────────────────────────────────────────────

    def _schedule_refresh(self):
        try:
            self.root.after(0, self._refresh_client_list)
        except Exception:
            pass

    def _schedule_log(self, msg: str):
        try:
            self.root.after(0, lambda m=msg: self._append_log(m))
        except Exception:
            pass

    def _refresh_client_list(self):
        sel = None
        sel_items = self.tree.selection()
        if sel_items:
            sel = self.tree.item(sel_items[0], 'values')[0]

        for item in self.tree.get_children():
            self.tree.delete(item)

        clients = self.server.get_client_list()
        reselect = None
        for c in clients:
            status = c['status']
            remaining = c.get('remaining', 0)

            # Determine tag for row coloring
            if status == 'Locked':
                tag = 'locked'
            elif status == 'Active' and remaining <= 60:
                tag = 'warning'
            elif status == 'Active':
                tag = 'active'
            else:
                tag = 'idle'

            iid = self.tree.insert('', 'end', values=(
                c['pc_name'], c['ip'], status,
                c['session'], c['connected']),
                tags=(tag,))
            if sel and c['pc_name'] == sel:
                reselect = iid

        if reselect:
            self.tree.selection_set(reselect)

        count = len(clients)
        self.lbl_online.config(text=f'● {count} online')

    def _append_log(self, msg: str):
        ts = datetime.now().strftime('%H:%M:%S')
        line = f'[{ts}] {msg}\n'
        self.txt_log.config(state='normal')
        self.txt_log.insert('end', line)
        self.txt_log.see('end')
        # Prune
        lines = int(self.txt_log.index('end-1c').split('.')[0])
        if lines > 300:
            self.txt_log.delete('1.0', f'{lines - 300}.0')
        self.txt_log.config(state='disabled')

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_selected_pc(self) -> str:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('Peringatan', 'Pilih PC dari daftar!')
            return ''
        return self.tree.item(sel[0], 'values')[0]

    # ── Commands ─────────────────────────────────────────────────────────

    def _cmd_start_session(self):
        pc = self._get_selected_pc()
        if not pc:
            return
        default = self.config['default_duration']
        dur = simpledialog.askinteger(
            'Mulai Sesi', f'Durasi sesi untuk {pc} (menit):',
            initialvalue=default, minvalue=1, maxvalue=1440,
            parent=self.root)
        if dur:
            self.server.start_session(pc, dur)

    def _cmd_stop_session(self):
        pc = self._get_selected_pc()
        if not pc:
            return
        if messagebox.askyesno('Konfirmasi',
                               f'Hentikan sesi untuk {pc}?\n'
                               f'PC akan dikunci.'):
            self.server.stop_session(pc)

    def _cmd_add_time(self):
        pc = self._get_selected_pc()
        if not pc:
            return
        mins = simpledialog.askinteger(
            'Tambah Waktu', f'Tambah waktu untuk {pc} (menit):',
            initialvalue=30, minvalue=1, maxvalue=1440,
            parent=self.root)
        if mins:
            self.server.add_time(pc, mins)

    def _cmd_lock(self):
        pc = self._get_selected_pc()
        if pc:
            self.server.lock_client(pc)

    def _cmd_unlock(self):
        pc = self._get_selected_pc()
        if pc:
            self.server.unlock_client(pc)

    def _cmd_send_msg(self):
        pc = self._get_selected_pc()
        if not pc:
            return
        text = simpledialog.askstring(
            'Kirim Pesan', f'Pesan untuk {pc}:',
            parent=self.root)
        if text:
            self.server.send_message(pc, text)

    def _cmd_broadcast(self):
        text = simpledialog.askstring(
            'Broadcast', 'Pesan untuk semua client:',
            parent=self.root)
        if text:
            self.server.broadcast_message(text)

    def _cmd_shutdown(self):
        pc = self._get_selected_pc()
        if not pc:
            return
        if messagebox.askyesno('Konfirmasi',
                               f'Shutdown {pc}?'):
            self.server.shutdown_client(pc)

    def _cmd_restart(self):
        pc = self._get_selected_pc()
        if not pc:
            return
        if messagebox.askyesno('Konfirmasi',
                               f'Restart {pc}?'):
            self.server.restart_client(pc)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _on_close(self):
        if messagebox.askokcancel('Keluar',
                                  'Menutup server akan memutus semua client.\n'
                                  'Lanjutkan?'):
            self.server.stop()
            self.root.destroy()

    def run(self):
        self.root.mainloop()


# ═════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app = OperatorGUI()
    app.run()
