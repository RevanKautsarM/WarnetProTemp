"""
WarnetPro Operator GUI - Dashboard untuk mengontrol sesi PC secara lokal.
Entry point: jalankan file ini untuk memulai dashboard operator.
"""

import configparser
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

# Import local manager module dari folder yang sama
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_manager import WarnetProLocalManager

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


def load_config() -> dict:
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE)
    return {
        'default_duration': cfg.getint('session', 'default_duration', fallback=60),
    }


# ═══════════════════════════════════════════════════════════════════════
# Color palette
# ═══════════════════════════════════════════════════════════════════════
BG_DARK    = '#0f172a'
BG_CARD    = '#1e293b'
BG_INPUT   = '#0c1322'
FG_TITLE   = '#f1f5f9'
FG_TEXT    = '#94a3b8'
FG_DIM     = '#475569'
ACCENT     = '#38bdf8'
GREEN      = '#22c55e'
RED        = '#ef4444'
YELLOW     = '#f59e0b'
ORANGE     = '#f97316'


class OperatorGUI:
    """Dashboard operator lokal WarnetPro."""

    def __init__(self):
        self.config = load_config()
        self.server = WarnetProLocalManager()
        self.server.on_client_update = self._schedule_refresh
        self.server.on_log = self._schedule_log

        self._build_root()
        self._build_ui()
        self._start_manager()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Root window ──────────────────────────────────────────────────────

    def _build_root(self):
        self.root = tk.Tk()
        self.root.title('WarnetPro Operator Dashboard (Lokal)')
        self.root.minsize(700, 480)
        self.root.configure(bg=BG_DARK)
        # Center
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 850) // 2
        y = (sh - 580) // 2
        self.root.geometry(f'850x580+{x}+{y}')

    # ── UI ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BG_CARD, height=60)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text='⚡ WarnetPro Operator (Lokal)',
                 font=('Segoe UI', 15, 'bold'),
                 bg=BG_CARD, fg=ACCENT).pack(side='left', padx=16)

        self.lbl_status = tk.Label(
            hdr, text='Starting...',
            font=('Segoe UI', 9), bg=BG_CARD, fg=FG_DIM)
        self.lbl_status.pack(side='right', padx=16)

        self.lbl_online = tk.Label(
            hdr, text='● 0 aktif',
            font=('Segoe UI', 11, 'bold'), bg=BG_CARD, fg=GREEN)
        self.lbl_online.pack(side='right', padx=(0, 12))

        # ── Main paned ───────────────────────────────────────────────────
        main = tk.Frame(self.root, bg=BG_DARK)
        main.pack(fill='both', expand=True, padx=12, pady=8)

        # Left: PC list
        left = tk.Frame(main, bg=BG_DARK)
        left.pack(side='left', fill='both', expand=True)

        tk.Label(left, text='DAFTAR PC CLIENT (LOKAL)',
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

        cols = ('pc_name', 'status', 'session', 'start_time', 'duration')
        self.tree = ttk.Treeview(left, columns=cols, show='headings',
                                 style='Dark.Treeview', height=14)
        self.tree.heading('pc_name', text='PC Name')
        self.tree.heading('status', text='Status')
        self.tree.heading('session', text='Sisa Waktu')
        self.tree.heading('start_time', text='Mulai Sesi')
        self.tree.heading('duration', text='Durasi')
        
        self.tree.column('pc_name', width=120, anchor='center')
        self.tree.column('status', width=100, anchor='center')
        self.tree.column('session', width=120, anchor='center')
        self.tree.column('start_time', width=120, anchor='center')
        self.tree.column('duration', width=100, anchor='center')
        self.tree.pack(fill='both', expand=True)

        # Tag colors for status
        self.tree.tag_configure('locked', foreground=RED)
        self.tree.tag_configure('active', foreground=GREEN)
        self.tree.tag_configure('warning', foreground=YELLOW)
        self.tree.tag_configure('idle', foreground=FG_TEXT)

        # ── Right: controls ──────────────────────────────────────────────
        right = tk.Frame(main, bg=BG_DARK, width=200)
        right.pack(side='right', fill='y', padx=(12, 0))
        right.pack_propagate(False)

        tk.Label(right, text='KONTROL SESI',
                 font=('Segoe UI', 9, 'bold'),
                 bg=BG_DARK, fg=FG_DIM).pack(anchor='w', pady=(0, 8))

        # Session controls
        self._btn(right, '▶  Mulai Sesi', GREEN, self._cmd_start_session)
        self._btn(right, '■  Stop Sesi', RED, self._cmd_stop_session)
        self._btn(right, '+  Tambah Waktu', ACCENT, self._cmd_add_time)

        # ── Bottom: log ──────────────────────────────────────────────────
        bot = tk.Frame(self.root, bg=BG_DARK)
        bot.pack(fill='x', padx=12, pady=(0, 8))

        tk.Label(bot, text='LOG AKTIVITAS OPERATOR',
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
                      padx=10, pady=8, cursor='hand2', command=cmd)
        b.pack(fill='x', pady=4)
        return b

    # ── Manager start ─────────────────────────────────────────────────────

    def _start_manager(self):
        try:
            self.server.start()
            self.lbl_status.config(text='Mode Mandiri (Lokal) Aktif')
            self._refresh_client_list()
        except Exception as e:
            self.lbl_status.config(text=f'ERROR: {e}', fg=RED)
            messagebox.showerror('Error', f'Gagal memulai manajer lokal:\n{e}')

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
        active_count = 0
        
        for c in clients:
            status = c['status']
            remaining = c.get('remaining', 0)

            # Determine tag for row coloring
            if status == 'Time Up':
                tag = 'locked'
            elif status == 'Active' and remaining <= 60:
                tag = 'warning'
            elif status == 'Active':
                tag = 'active'
                active_count += 1
            else:
                tag = 'idle'

            iid = self.tree.insert('', 'end', values=(
                c['pc_name'], status, c['session'],
                c['start_time'], c['duration']),
                tags=(tag,))
            
            if sel and c['pc_name'] == sel:
                reselect = iid

        if reselect:
            self.tree.selection_set(reselect)

        self.lbl_online.config(text=f'● {active_count} aktif')

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
        
        # Cek jika PC sudah aktif
        clients = self.server.get_client_list()
        for c in clients:
            if c['pc_name'] == pc and c['status'] == 'Active':
                messagebox.showwarning('Peringatan', f'{pc} sedang aktif!')
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
        
        # Cek jika PC memang aktif
        clients = self.server.get_client_list()
        active = False
        for c in clients:
            if c['pc_name'] == pc and c['status'] in ('Active', 'Time Up'):
                active = True
                break
        if not active:
            messagebox.showwarning('Peringatan', f'{pc} tidak memiliki sesi aktif!')
            return
            
        if messagebox.askyesno('Konfirmasi', f'Hentikan sesi untuk {pc}?'):
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

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _on_close(self):
        if messagebox.askokcancel('Keluar', 'Keluar dari aplikasi operator?'):
            self.server.stop()
            self.root.destroy()

    def run(self):
        self.root.mainloop()


# ═════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app = OperatorGUI()
    app.run()
