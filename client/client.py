"""
WarnetPro Client - Core TCP Client Module
Menangani koneksi ke server, heartbeat response, auto-reconnect,
dan penerimaan perintah dari operator.
Menggunakan pure Python standard library.

Fitur:
  - Auto-reconnect jika koneksi putus
  - Handle session timer dari server
  - Auto-lock saat waktu habis
  - Peringatan waktu hampir habis
"""

import socket
import threading
import json
import time
import os
import sys
import platform
import uuid
from datetime import datetime
from typing import Optional, Callable

MSG_DELIMITER = b'\n'


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def get_mac_address() -> str:
    try:
        mac = uuid.getnode()
        return ':'.join(f'{(mac >> (8 * i)) & 0xff:02x}'
                        for i in reversed(range(6)))
    except Exception:
        return '00:00:00:00:00:00'


class WarnetProClient:
    """TCP client yang terhubung ke WarnetPro Server."""

    def __init__(self, server_host: str = '127.0.0.1', server_port: int = 9999,
                 pc_name: str = 'PC-01', reconnect_interval: int = 5):
        self.server_host = server_host
        self.server_port = server_port
        self.pc_name = pc_name
        self.reconnect_interval = reconnect_interval

        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.running = False
        self._reconnecting = False

        # GUI callbacks
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_session_update: Optional[Callable[[dict], None]] = None
        self.on_session_end: Optional[Callable] = None
        self.on_lock: Optional[Callable] = None
        self.on_unlock: Optional[Callable] = None
        self.on_shutdown: Optional[Callable] = None
        self.on_restart: Optional[Callable] = None
        self.on_message: Optional[Callable[[str], None]] = None
        self.on_time_warning: Optional[Callable[[dict], None]] = None
        self.on_log: Optional[Callable[[str], None]] = None

    # ── Logging ──────────────────────────────────────────────────────────

    def log(self, msg: str):
        if self.on_log:
            try:
                self.on_log(msg)
            except Exception:
                pass

    # ── Connection ───────────────────────────────────────────────────────

    def connect(self):
        """Mulai koneksi ke server (non-blocking, jalankan di thread)."""
        self.running = True
        threading.Thread(target=self._connect_loop, daemon=True).start()

    def disconnect(self):
        """Putuskan koneksi secara manual."""
        self.running = False
        self._close_socket()
        self.log('Koneksi diputus')

    def _close_socket(self):
        if self.sock:
            try:
                self._send_msg('disconnect', {})
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.connected:
            self.connected = False
            if self.on_disconnected:
                self.on_disconnected()

    def _connect_loop(self):
        """Loop utama: connect → receive → reconnect jika putus."""
        while self.running:
            try:
                self.log(f'Menghubungkan ke {self.server_host}:{self.server_port}...')
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5.0)
                self.sock.connect((self.server_host, self.server_port))
                self.sock.settimeout(10.0)
                self.connected = True
                self._reconnecting = False

                # Register
                self._send_msg('register', {
                    'pc_name': self.pc_name,
                    'ip': get_local_ip(),
                    'mac': get_mac_address(),
                    'os': f'{platform.system()} {platform.release()}',
                })

                self.log(f'✓ Terhubung ke server')
                if self.on_connected:
                    self.on_connected()

                # Receive loop
                self._receive_loop()

            except (ConnectionRefusedError, ConnectionResetError,
                    TimeoutError, OSError) as e:
                self.log(f'Koneksi gagal: {e}')
            except Exception as e:
                self.log(f'Error: {e}')
            finally:
                self._close_socket()

            # Reconnect
            if self.running:
                self._reconnecting = True
                self.log(f'Reconnect dalam {self.reconnect_interval} detik...')
                for _ in range(self.reconnect_interval * 10):
                    if not self.running:
                        return
                    time.sleep(0.1)

    def _receive_loop(self):
        """Terima pesan dari server sampai koneksi putus."""
        buf = b''
        while self.running and self.connected:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while MSG_DELIMITER in buf:
                    line, buf = buf.split(MSG_DELIMITER, 1)
                    try:
                        msg = json.loads(line.decode('utf-8'))
                    except json.JSONDecodeError:
                        continue
                    self._handle_message(msg)
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                break

    # ── Message handling ─────────────────────────────────────────────────

    def _handle_message(self, msg: dict):
        mt = msg.get('type', '')
        md = msg.get('data', {})

        if mt == 'ping':
            self._send_msg('pong', {})

        elif mt == 'welcome':
            self.log(f'Server: {md.get("message", "")}')

        elif mt == 'session_update':
            if self.on_session_update:
                self.on_session_update(md)

        elif mt == 'session_end':
            self.log('⏰ Waktu habis!')
            if self.on_session_end:
                self.on_session_end()

        elif mt == 'time_warning':
            self.log(f'⚠ {md.get("message", "Waktu hampir habis!")}')
            if self.on_time_warning:
                self.on_time_warning(md)

        elif mt == 'lock':
            self.log('🔒 PC dikunci')
            if self.on_lock:
                self.on_lock()

        elif mt == 'unlock':
            self.log('🔓 PC dibuka')
            if self.on_unlock:
                self.on_unlock()

        elif mt == 'shutdown':
            self.log('⏻ Shutdown dari operator')
            if self.on_shutdown:
                self.on_shutdown()
            if platform.system() == 'Windows':
                os.system('shutdown /s /t 5 /c "WarnetPro: Dimatikan oleh operator"')

        elif mt == 'restart':
            self.log('↻ Restart dari operator')
            if self.on_restart:
                self.on_restart()
            if platform.system() == 'Windows':
                os.system('shutdown /r /t 5 /c "WarnetPro: Restart oleh operator"')

        elif mt == 'message':
            text = md.get('text', '')
            self.log(f'💬 Pesan: {text}')
            if self.on_message:
                self.on_message(text)

        elif mt == 'server_shutdown':
            self.log('Server dimatikan')

    # ── Send ─────────────────────────────────────────────────────────────

    def _send_msg(self, msg_type: str, data: dict) -> bool:
        if not self.sock:
            return False
        try:
            raw = json.dumps({'type': msg_type, 'data': data}) + '\n'
            self.sock.sendall(raw.encode('utf-8'))
            return True
        except Exception:
            return False
