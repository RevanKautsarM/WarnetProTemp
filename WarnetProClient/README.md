# WarnetPro Client GUI v2.0

Aplikasi client Python (GUI) yang berjalan di setiap PC warnet. Berkomunikasi dengan server WarnetPro untuk mengelola sesi, menerima perintah operator, dan mengirim screenshot.

## Fitur

| Fitur | Deskripsi |
|-------|-----------|
| **Heartbeat** | Kirim status online ke server setiap 5 detik |
| **Status Sesi** | Timer countdown sisa waktu sesi aktif |
| **Member Login/Logout** | Login/logout langsung dari PC client |
| **🔒 Lock Screen** | Layar kunci fullscreen saat operator mengunci PC |
| **📷 Screenshot** | Capture & upload layar ke server saat diminta operator |
| **System Tray** | Berjalan di background (system tray) |

## Persyaratan

- Python 3.7+
- Pip packages: `requests`, `Pillow`, `pystray`

## Instalasi

### 1. Install Python
Download dari [python.org](https://www.python.org/downloads/) — centang **"Add Python to PATH"**

### 2. Install Dependensi
```bash
cd WarnetProClient
pip install -r requirements.txt
```

### 3. Konfigurasi `config.ini`
```ini
[server]
url = http://192.168.1.100:8000   ; IP server WarnetPro
pc_name = PC-01                    ; Nama PC (harus terdaftar di dashboard)

[client]
heartbeat_interval = 5
status_poll_interval = 3
command_poll_interval = 2
screenshot_quality = 60
```

### 4. Persiapan Server
Jalankan perintah ini di folder WarnetPro server:
```bash
php artisan storage:link
```
Ini diperlukan agar screenshot yang diupload bisa diakses via URL publik.

## Menjalankan

### Cara Mudah (Windows)
Klik dua kali **`start.bat`** — otomatis install dependensi dan jalankan client.

### Manual
```bash
python warnetpro_client_gui.py
```

## Perintah dari Operator (Dashboard)

| Perintah | Aksi di Client |
|----------|---------------|
| 🔒 Kunci | Tampilkan layar kunci fullscreen |
| 🔓 Buka | Tutup layar kunci |
| 📷 Lihat Layar | Capture screenshot & kirim ke dashboard |
| 💬 Pesan | Tampilkan popup pesan |
| Shutdown | Matikan PC dalam 5 detik |
| Restart | Restart PC dalam 5 detik |

## Auto-Start saat Windows Startup

1. Buat shortcut `start.bat`
2. Tekan `Win + R`, ketik `shell:startup`, Enter
3. Pindahkan shortcut ke folder Startup

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Tidak terhubung ke server | Cek IP di `config.ini` dan pastikan server berjalan |
| PC tidak ditemukan | Pastikan `pc_name` terdaftar di dashboard WarnetPro |
| Screenshot tidak muncul | Jalankan `php artisan storage:link` di server |
| Lock screen tidak muncul | Pastikan Python bisa mengakses display |
| `pystray` error | Jalankan `pip install pystray` |
