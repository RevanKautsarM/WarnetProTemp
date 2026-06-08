"""
WarnetPro Local Manager - Core Local Session Tracker Module
Mengelola status sesi untuk semua PC secara lokal tanpa koneksi jaringan.
"""

import os
import time
import threading
import logging
import configparser
from datetime import datetime
from typing import Dict, List, Optional, Callable

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
WARNING_THRESHOLD = 60  # Peringatan sisa waktu 60 detik


class LocalPCInfo:
    """Informasi sesi lokal untuk sebuah PC."""

    def __init__(self, pc_name: str):
        self.pc_name = pc_name
        self.session_remaining = 0
        self.session_total = 0
        self.session_active = False
        self.session_started_at: Optional[datetime] = None
        self.warning_sent = False


class WarnetProLocalManager:
    """Manajer sesi lokal untuk mencatat dan menghitung mundur waktu penggunaan PC."""

    def __init__(self):
        self.pcs: Dict[str, LocalPCInfo] = {}
        self.lock = threading.Lock()
        self.running = False
        self.on_client_update: Optional[Callable] = None
        self.on_log: Optional[Callable[[str], None]] = None

        self._setup_logging()
        self._load_pcs()

    # ── Logging ──────────────────────────────────────────────────────────

    def _setup_logging(self):
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'operator_activity.log')
        self.logger = logging.getLogger('warnetpro_local')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
            self.logger.addHandler(fh)

    def log(self, msg: str):
        self.logger.info(msg)
        if self.on_log:
            try:
                self.on_log(msg)
            except Exception:
                pass

    # ── Load PCs from Config ─────────────────────────────────────────────

    def _load_pcs(self):
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_FILE)
        pc_str = cfg.get('pcs', 'pc_list', fallback='PC-01,PC-02,PC-03,PC-04,PC-05')
        pc_names = [name.strip() for name in pc_str.split(',') if name.strip()]
        for name in pc_names:
            self.pcs[name] = LocalPCInfo(name)
        self.log(f'Memuat {len(pc_names)} PC dari konfigurasi: {", ".join(pc_names)}')

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self):
        self.running = True
        self.log("Aplikasi Operator (Lokal) dimulai.")
        threading.Thread(target=self._timer_loop, daemon=True).start()

    def stop(self):
        self.running = False
        self.log("Aplikasi Operator (Lokal) dihentikan.")

    # ── Timer loop ───────────────────────────────────────────────────────

    def _timer_loop(self):
        while self.running:
            time.sleep(1)
            updated = False
            with self.lock:
                for pc in self.pcs.values():
                    if pc.session_active and pc.session_remaining > 0:
                        pc.session_remaining -= 1
                        updated = True

                        # ── Peringatan waktu hampir habis ──
                        if pc.session_remaining <= WARNING_THRESHOLD and not pc.warning_sent:
                            pc.warning_sent = True
                            self.log(f'⚠ Peringatan: Sisa waktu {pc.pc_name} tinggal {pc.session_remaining} detik!')

                        # ── Waktu habis ──
                        if pc.session_remaining <= 0:
                            pc.session_active = False
                            pc.warning_sent = False
                            self.log(f'🔔 Sesi selesai untuk {pc.pc_name}!')
            if updated:
                self._notify_gui()

    # ── Session Commands ─────────────────────────────────────────────────

    def start_session(self, pc_name: str, duration_minutes: int):
        with self.lock:
            pc = self.pcs.get(pc_name)
            if pc:
                pc.session_total = duration_minutes * 60
                pc.session_remaining = pc.session_total
                pc.session_active = True
                pc.session_started_at = datetime.now()
                pc.warning_sent = False
                self.log(f'▶ Sesi dimulai: {pc_name} ({duration_minutes} menit)')
        self._notify_gui()

    def stop_session(self, pc_name: str):
        with self.lock:
            pc = self.pcs.get(pc_name)
            if pc:
                pc.session_active = False
                pc.session_remaining = 0
                pc.session_total = 0
                pc.session_started_at = None
                pc.warning_sent = False
                self.log(f'■ Sesi dihentikan: {pc_name}')
        self._notify_gui()

    def add_time(self, pc_name: str, minutes: int):
        with self.lock:
            pc = self.pcs.get(pc_name)
            if pc:
                if pc.session_active:
                    pc.session_remaining += minutes * 60
                    pc.session_total += minutes * 60
                    pc.warning_sent = False  # Reset warning status
                    self.log(f'+ Tambah waktu: {pc_name} (+{minutes} menit)')
                else:
                    # Mulai sesi baru jika belum aktif
                    pc.session_total = minutes * 60
                    pc.session_remaining = pc.session_total
                    pc.session_active = True
                    pc.session_started_at = datetime.now()
                    pc.warning_sent = False
                    self.log(f'▶ Sesi baru (tambah waktu): {pc_name} ({minutes} menit)')
        self._notify_gui()

    # ── GUI Helpers ──────────────────────────────────────────────────────

    def _notify_gui(self):
        if self.on_client_update:
            try:
                self.on_client_update()
            except Exception:
                pass

    def get_client_list(self) -> List[dict]:
        """Mengembalikan daftar PC beserta status sesinya untuk kebutuhan tabel GUI."""
        with self.lock:
            result = []
            for pc in self.pcs.values():
                mins, secs = divmod(max(0, pc.session_remaining), 60)
                hrs, mins_r = divmod(mins, 60)
                
                if hrs > 0:
                    timer_str = f'{hrs:02d}:{mins_r:02d}:{secs:02d}'
                else:
                    timer_str = f'{mins:02d}:{secs:02d}'

                start_str = pc.session_started_at.strftime('%H:%M:%S') if pc.session_started_at else '-'
                dur_str = f'{pc.session_total // 60}m' if pc.session_active else '-'

                status = 'Active' if pc.session_active else 'Idle'
                if pc.session_active and pc.session_remaining <= 0:
                    status = 'Time Up'

                result.append({
                    'pc_name': pc.pc_name,
                    'status': status,
                    'session': timer_str if pc.session_active else '-',
                    'remaining': pc.session_remaining,
                    'start_time': start_str,
                    'duration': dur_str
                })
            return result
