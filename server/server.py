"""
WarnetPro Server - Core TCP Server Module
Menangani koneksi multi-client, heartbeat, session timer, dan command dispatch.
Menggunakan pure Python standard library (socket + threading).

Fitur:
  - Auto-lock saat client baru connect
  - Timer countdown yang dikelola server
  - Auto-lock saat waktu habis
  - Peringatan saat waktu hampir habis (≤60 detik)
"""

import socket
import threading
import json
import time
import os
import sys
import subprocess
import logging
from datetime import datetime
from typing import Dict, Optional, Callable

MSG_DELIMITER = b'\n'
HEARTBEAT_INTERVAL = 5
HEARTBEAT_TIMEOUT = 18
WARNING_THRESHOLD = 60  # Detik sebelum peringatan


class ClientInfo:
    """Data untuk setiap client yang terhubung."""

    def __init__(self, pc_name: str, ip_address: str, mac_address: str,
                 os_info: str, conn: socket.socket, addr: tuple):
        self.pc_name = pc_name
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.os_info = os_info
        self.conn = conn
        self.addr = addr
        self.connected_at = datetime.now()
        self.last_heartbeat = datetime.now()
        # Session
        self.session_remaining = 0
        self.session_total = 0
        self.session_active = False
        self.session_started_at: Optional[datetime] = None
        self.warning_sent = False  # Peringatan waktu hampir habis
        # State
        self.is_locked = True  # Default: TERKUNCI saat connect


class WarnetProServer:
    """TCP server utama yang mengelola semua client."""

    def __init__(self, host: str = '0.0.0.0', port: int = 9999,
                 auto_firewall: bool = True):
        self.host = host
        self.port = port
        self.auto_firewall = auto_firewall
        self.clients: Dict[str, ClientInfo] = {}
        self.lock = threading.Lock()
        self.running = False
        self.server_socket: Optional[socket.socket] = None

        # GUI callbacks — di-set oleh operator_gui.py
        self.on_client_update: Optional[Callable] = None
        self.on_log: Optional[Callable[[str], None]] = None

        self._setup_logging()

    # ── Logging ──────────────────────────────────────────────────────────

    def _setup_logging(self):
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'connections.log')
        self.logger = logging.getLogger('warnetpro_server')
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

    # ── Firewall ─────────────────────────────────────────────────────────

    def setup_firewall(self) -> bool:
        if sys.platform != 'win32' or not self.auto_firewall:
            return True
        try:
            flags = 0x08000000  # CREATE_NO_WINDOW
            # Hapus rule lama jika ada
            subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'delete', 'rule',
                 'name=WarnetPro Server'],
                capture_output=True, text=True, creationflags=flags
            )
            # Tambah rule baru
            result = subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                 'name=WarnetPro Server', 'dir=in', 'action=allow',
                 'protocol=TCP', f'localport={self.port}',
                 'profile=private,domain,public'],
                capture_output=True, text=True, creationflags=flags
            )
            if result.returncode == 0:
                self.log(f'✓ Firewall rule ditambahkan (port {self.port})')
                return True
            else:
                self.log(f'⚠ Gagal menambah firewall rule. '
                         f'Jalankan sebagai Administrator.')
                return False
        except Exception as e:
            self.log(f'⚠ Firewall error: {e}')
            return False

    # ── Server lifecycle ─────────────────────────────────────────────────

    def start(self):
        self.setup_firewall()
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        self.server_socket.settimeout(1.0)
        self.log(f'Server berjalan di {self.host}:{self.port}')
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._timer_loop, daemon=True).start()

    def stop(self):
        self.running = False
        with self.lock:
            for info in list(self.clients.values()):
                try:
                    self._send_raw(info.conn, 'server_shutdown', {})
                    info.conn.close()
                except Exception:
                    pass
            self.clients.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        self.log('Server dihentikan')

    # ── Low-level send ───────────────────────────────────────────────────

    def _send_raw(self, conn: socket.socket, msg_type: str, data: dict) -> bool:
        try:
            raw = json.dumps({'type': msg_type, 'data': data}) + '\n'
            conn.sendall(raw.encode('utf-8'))
            return True
        except Exception:
            return False

    def send_to_client(self, pc_name: str, msg_type: str, data: dict) -> bool:
        with self.lock:
            info = self.clients.get(pc_name)
            if info:
                return self._send_raw(info.conn, msg_type, data)
        return False

    def broadcast(self, msg_type: str, data: dict):
        with self.lock:
            for info in list(self.clients.values()):
                try:
                    self._send_raw(info.conn, msg_type, data)
                except Exception:
                    pass

    # ── Accept loop ──────────────────────────────────────────────────────

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                conn.settimeout(10.0)
                threading.Thread(target=self._handle_client,
                                 args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    # ── Per-client handler ───────────────────────────────────────────────

    def _handle_client(self, conn: socket.socket, addr: tuple):
        buf = b''
        pc_name = None
        try:
            while self.running:
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while MSG_DELIMITER in buf:
                        line, buf = buf.split(MSG_DELIMITER, 1)
                        msg = json.loads(line.decode('utf-8'))
                        mt = msg.get('type', '')
                        md = msg.get('data', {})

                        if mt == 'register':
                            pc_name = md.get('pc_name', f'PC-{addr[0]}')
                            ci = ClientInfo(
                                pc_name=pc_name,
                                ip_address=md.get('ip', addr[0]),
                                mac_address=md.get('mac', ''),
                                os_info=md.get('os', ''),
                                conn=conn, addr=addr,
                            )
                            with self.lock:
                                old = self.clients.get(pc_name)
                                if old:
                                    try:
                                        old.conn.close()
                                    except Exception:
                                        pass
                                self.clients[pc_name] = ci
                            self.log(f'✓ Client terhubung: {pc_name} '
                                     f'({addr[0]}:{addr[1]})')
                            self._send_raw(conn, 'welcome', {
                                'message': f'Terhubung sebagai {pc_name}'
                            })
                            # ── AUTO-LOCK: PC langsung terkunci saat connect ──
                            self._send_raw(conn, 'lock', {})
                            self.log(f'🔒 Auto-lock: {pc_name} (baru terhubung)')
                            self._notify_gui()

                        elif mt == 'pong':
                            with self.lock:
                                if pc_name and pc_name in self.clients:
                                    self.clients[pc_name].last_heartbeat = \
                                        datetime.now()

                        elif mt == 'disconnect':
                            break

                except socket.timeout:
                    continue
                except (ConnectionResetError, ConnectionAbortedError):
                    break
                except json.JSONDecodeError:
                    continue
                except Exception:
                    break
        finally:
            if pc_name:
                with self.lock:
                    if pc_name in self.clients and \
                       self.clients[pc_name].conn is conn:
                        del self.clients[pc_name]
                self.log(f'✗ Client terputus: {pc_name}')
                self._notify_gui()
            try:
                conn.close()
            except Exception:
                pass

    # ── Heartbeat loop ───────────────────────────────────────────────────

    def _heartbeat_loop(self):
        while self.running:
            time.sleep(HEARTBEAT_INTERVAL)
            now = datetime.now()
            dead = []
            with self.lock:
                for name, info in list(self.clients.items()):
                    diff = (now - info.last_heartbeat).total_seconds()
                    if diff > HEARTBEAT_TIMEOUT:
                        dead.append(name)
                    else:
                        try:
                            self._send_raw(info.conn, 'ping', {})
                        except Exception:
                            dead.append(name)
            for name in dead:
                with self.lock:
                    info = self.clients.pop(name, None)
                    if info:
                        try:
                            info.conn.close()
                        except Exception:
                            pass
                self.log(f'✗ Client timeout: {name}')
                self._notify_gui()

    # ── Timer loop ───────────────────────────────────────────────────────

    def _timer_loop(self):
        while self.running:
            time.sleep(1)
            updated = False
            with self.lock:
                for info in list(self.clients.values()):
                    if info.session_active and info.session_remaining > 0:
                        info.session_remaining -= 1
                        self._send_raw(info.conn, 'session_update', {
                            'remaining_secs': info.session_remaining,
                            'total_secs': info.session_total,
                            'status': 'active',
                        })
                        updated = True

                        # ── Peringatan waktu hampir habis ──
                        if (info.session_remaining <= WARNING_THRESHOLD
                                and not info.warning_sent):
                            info.warning_sent = True
                            self._send_raw(info.conn, 'time_warning', {
                                'remaining_secs': info.session_remaining,
                                'message': f'Waktu tersisa {info.session_remaining} detik!'
                            })
                            self.log(f'⚠ Peringatan waktu: {info.pc_name} '
                                     f'({info.session_remaining} detik)')

                        # ── Waktu habis → auto-lock ──
                        if info.session_remaining <= 0:
                            info.session_active = False
                            info.warning_sent = False
                            info.is_locked = True
                            self._send_raw(info.conn, 'session_end', {})
                            self._send_raw(info.conn, 'lock', {})
                            self.log(f'🔒 Waktu habis, auto-lock: {info.pc_name}')
            if updated:
                self._notify_gui()

    # ── Session commands ─────────────────────────────────────────────────

    def start_session(self, pc_name: str, duration_minutes: int):
        with self.lock:
            info = self.clients.get(pc_name)
            if info:
                info.session_total = duration_minutes * 60
                info.session_remaining = info.session_total
                info.session_active = True
                info.session_started_at = datetime.now()
                info.warning_sent = False
                info.is_locked = False  # Unlock saat sesi dimulai
                self._send_raw(info.conn, 'unlock', {})
                self._send_raw(info.conn, 'session_update', {
                    'remaining_secs': info.session_remaining,
                    'total_secs': info.session_total,
                    'status': 'active',
                })
        self.log(f'▶ Sesi dimulai: {pc_name} ({duration_minutes} menit)')
        self._notify_gui()

    def stop_session(self, pc_name: str):
        with self.lock:
            info = self.clients.get(pc_name)
            if info:
                info.session_active = False
                info.session_remaining = 0
                info.session_total = 0
                info.session_started_at = None
                info.warning_sent = False
                info.is_locked = True  # Lock saat sesi dihentikan
                self._send_raw(info.conn, 'session_end', {})
                self._send_raw(info.conn, 'lock', {})
        self.log(f'■ Sesi dihentikan & PC dikunci: {pc_name}')
        self._notify_gui()

    def add_time(self, pc_name: str, minutes: int):
        with self.lock:
            info = self.clients.get(pc_name)
            if info:
                if info.session_active:
                    info.session_remaining += minutes * 60
                    info.session_total += minutes * 60
                    info.warning_sent = False  # Reset warning
                    self._send_raw(info.conn, 'session_update', {
                        'remaining_secs': info.session_remaining,
                        'total_secs': info.session_total,
                        'status': 'active',
                    })
                else:
                    # Jika belum ada sesi, mulai sesi baru
                    info.session_total = minutes * 60
                    info.session_remaining = info.session_total
                    info.session_active = True
                    info.session_started_at = datetime.now()
                    info.warning_sent = False
                    info.is_locked = False
                    self._send_raw(info.conn, 'unlock', {})
                    self._send_raw(info.conn, 'session_update', {
                        'remaining_secs': info.session_remaining,
                        'total_secs': info.session_total,
                        'status': 'active',
                    })
        self.log(f'+ Tambah waktu: {pc_name} (+{minutes} menit)')
        self._notify_gui()

    # ── Client commands ──────────────────────────────────────────────────

    def lock_client(self, pc_name: str):
        with self.lock:
            info = self.clients.get(pc_name)
            if info:
                info.is_locked = True
        self.send_to_client(pc_name, 'lock', {})
        self.log(f'🔒 Lock: {pc_name}')
        self._notify_gui()

    def unlock_client(self, pc_name: str):
        with self.lock:
            info = self.clients.get(pc_name)
            if info:
                info.is_locked = False
        self.send_to_client(pc_name, 'unlock', {})
        self.log(f'🔓 Unlock: {pc_name}')
        self._notify_gui()

    def shutdown_client(self, pc_name: str):
        self.send_to_client(pc_name, 'shutdown', {})
        self.log(f'⏻ Shutdown: {pc_name}')

    def restart_client(self, pc_name: str):
        self.send_to_client(pc_name, 'restart', {})
        self.log(f'↻ Restart: {pc_name}')

    def send_message(self, pc_name: str, text: str):
        self.send_to_client(pc_name, 'message', {'text': text})
        self.log(f'💬 Pesan ke {pc_name}: {text}')

    def broadcast_message(self, text: str):
        self.broadcast('message', {'text': text})
        self.log(f'📢 Broadcast: {text}')

    # ── Helpers ──────────────────────────────────────────────────────────

    def _notify_gui(self):
        if self.on_client_update:
            try:
                self.on_client_update()
            except Exception:
                pass

    def get_client_list(self) -> list:
        with self.lock:
            result = []
            for info in self.clients.values():
                mins, secs = divmod(max(0, info.session_remaining), 60)
                result.append({
                    'pc_name': info.pc_name,
                    'ip': info.ip_address,
                    'status': 'Locked' if info.is_locked
                              else ('Active' if info.session_active
                                    else 'Idle'),
                    'session': f'{mins:02d}:{secs:02d}'
                              if info.session_active else '-',
                    'remaining': info.session_remaining,
                    'connected': info.connected_at.strftime('%H:%M:%S'),
                })
            return result

    def get_online_count(self) -> int:
        with self.lock:
            return len(self.clients)
