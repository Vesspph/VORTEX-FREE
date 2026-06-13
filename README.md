# Vortex Security Bot — README

ระบบ Discord Bot สำหรับจัดการ **License Key / HWID** ของซอฟต์แวร์ (เช่น cheat loader, app licensing, premium tool ฯลฯ) มาพร้อม:

- 🤖 **Discord Bot** (slash commands `/panel`, `/giveaway`) + ปุ่ม Admin Panel แบบ interactive
- 🌐 **Web API + Dashboard** (aiohttp) สำหรับสร้าง/ลบ/แบน/ตรวจสอบคีย์
- 💾 **ฐานข้อมูล SQLite** (`vortex_keys.db`) — ไม่ต้องติดตั้ง DB ภายนอก
- 🖥️ **Terminal UI** สีสันด้วย `rich` พร้อมล็อกอินด้วยรหัสผ่าน
- 🔐 ระบบความปลอดภัย: rate limit, CSRF, security headers, IP whitelist สำหรับ admin API
- 🎁 ฟังก์ชันแจกคีย์ (giveaway) ในช่อง Discord

> ไฟล์หลัก: `main.py` (เดิมชื่อ `vortex_bot.py` / `main (4).py`) — ~1737 บรรทัด

---

## 📑 สารบัญ

1. [คุณสมบัติเด่น](#-คุณสมบัติเด่น)
2. [โครงสร้างโค้ดคร่าวๆ](#-โครงสร้างโค้ดคร่าวๆ)
3. [ความต้องการของระบบ](#-ความต้องการของระบบ)
4. [การติดตั้ง](#-การติดตั้ง)
5. [การตั้งค่า (.env)](#-การตั้งค่า-env)
6. [การรัน](#-การรัน)
7. [การใช้งาน](#-การใช้งาน)
   - [Discord Commands](#discord-commands)
   - [Admin Panel](#admin-panel-bot)
   - [Web Dashboard](#web-dashboard)
   - [Terminal Console](#terminal-console)
8. [Web API Reference](#-web-api-reference)
9. [ฐานข้อมูล](#-ฐานข้อมูล)
10. [Security Model](#-security-model)
11. [Deploy บน VPS / Server](#-deploy-บน-vps--server)
12. [แก้ปัญหาที่พบบ่อย (Troubleshooting)](#-แก้ปัญหาที่พบบ่อย-troubleshooting)
13. [FAQ](#-faq)

---

## ✨ คุณสมบัติเด่น

| หมวด | รายละเอียด |
|---|---|
| Key Management | สร้าง / ลบ / revoke / pause-resume / reset HWID / blacklist HWID |
| Duration | 1 วัน, 3 วัน, 7 วัน, 1 เดือน, 1 ปี, ถาวร (permanent) |
| Giveaway | สร้างคีย์แจกในช่อง Discord พร้อมปุ่มกดรับ |
| Dashboard | หน้าเว็บแสดงสถิติ + ตารางคีย์ (เปิดอัตโนมัติเมื่อกดปุ่มใน bot) |
| Verify API | endpoint `POST /api/verify` ให้แอป client เรียกเช็คสิทธิ์ + ผูก HWID อัตโนมัติ |
| Logs | บันทึก terminal log อัตโนมัติเมื่อปิดโปรแกรม (atexit) |

---

## 🏗️ โครงสร้างโค้ดคร่าวๆ

```
main.py
├── Config / ENV         (บรรทัด ~32–40)   TOKEN, ADMIN_ROLE_ID, TERMINAL_PASSWORD
├── Network helpers      (บรรทัด ~42–125)  _get_api_port, _get_lan_ip, _detect_host_url
├── Database layer       (บรรทัด ~815–875) init_db, search_keys, fetch_stats
├── Terminal UI (rich)   (บรรทัด ~881–998) banner, menu, terminal_loop, _terminal_login
├── Discord UI (embeds)  (บรรทัด ~999–1160) make_embed, KeyInfoView, DeleteKeyView
├── Modals & Selects     (บรรทัด ~1164–1272) KeyAmountModal, ResetModal, PauseResumeModal...
├── AdminPanel View      (บรรทัด ~1273–1339) ปุ่มทั้งหมดของ admin panel
├── Web server (aiohttp) (บรรทัด ~1340–1640) security middleware + REST endpoints
├── Bot class & events   (บรรทัด ~1645–1697) VortexBot, on_ready
└── Slash commands       (บรรทัด ~1698–end)  /panel, /giveaway
```

---

## 🧰 ความต้องการของระบบ

- **Python 3.10+** (แนะนำ 3.11 หรือ 3.12)
- **pip** สำหรับติดตั้ง dependency
- **Discord Bot Token** (จาก https://discord.com/developers/applications)
- ระบบปฏิบัติการ: Windows / Linux / macOS

### Python packages
```
discord.py>=2.3
aiohttp
aiosqlite
python-dotenv
rich
```

---

## ⚙️ การติดตั้ง

### 1) Clone หรือดาวน์โหลดไฟล์
```bash
mkdir vortex-bot && cd vortex-bot
# วางไฟล์ main.py ไว้ในโฟลเดอร์นี้
```

### 2) สร้าง Virtual Environment (แนะนำ)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3) ติดตั้ง dependency
```bash
pip install -U discord.py aiohttp aiosqlite python-dotenv rich
```

หรือสร้าง `requirements.txt`:
```txt
discord.py>=2.3
aiohttp>=3.9
aiosqlite>=0.19
python-dotenv>=1.0
rich>=13.0
```
แล้ว:
```bash
pip install -r requirements.txt
```

---

## 🔧 การตั้งค่า (.env)

สร้างไฟล์ `.env` ในโฟลเดอร์เดียวกับ `main.py`:

```env
# จำเป็น
DISCORD_TOKEN=ใส่_token_ของบอท_ที่นี่
ADMIN_ROLE_ID=123456789012345678

# (เลือกได้) บังคับพอร์ตของ web API/dashboard
# ถ้าไม่ตั้ง จะใช้ PORT/SERVER_PORT/WEB_PORT/TASK_PORT/API_PORT ตามลำดับ
# ค่า default = 30184
API_PORT=30184

# (เลือกได้) บังคับ host/IP ที่ใช้แสดงในลิงก์ dashboard
# DASHBOARD_HOST=mybot.example.com
# HOST_IP=127.0.0.1
# PUBLIC_HOST=mybot.example.com
```

### วิธีหา `DISCORD_TOKEN`
1. ไป https://discord.com/developers/applications → **New Application**
2. แท็บ **Bot** → กด **Reset Token** → copy
3. เปิด **Privileged Gateway Intents** → ติ๊ก `MESSAGE CONTENT INTENT` และ `SERVER MEMBERS INTENT`
4. แท็บ **OAuth2 → URL Generator** → เลือก `bot` + `applications.commands` → permission: `Administrator` (หรือเฉพาะที่จำเป็น) → เชิญบอทเข้าเซิร์ฟเวอร์

### วิธีหา `ADMIN_ROLE_ID`
- ใน Discord เปิด **Developer Mode** (User Settings → Advanced)
- คลิกขวาที่ role admin → **Copy ID**

### รหัสผ่าน Terminal
แก้ในไฟล์ `main.py` บรรทัด ~40:
```python
TERMINAL_PASSWORD = "vortex2026"   # 🔑 เปลี่ยนรหัสตรงนี้
```

---

## ▶️ การรัน

```bash
python main.py
```

ถ้าทุกอย่างถูกต้องจะเห็น:
```
✓ Logged in as VortexBot#1234
🌐 API + Dashboard → http://127.0.0.1:30184/dashboard  (port from default)
```

จากนั้น:
- เปิดเบราว์เซอร์ไปที่ลิงก์ที่แสดง → ใช้งาน Dashboard
- ใน Discord พิมพ์ `/panel` → ใช้งาน Admin Panel

---

## 🎮 การใช้งาน

### Discord Commands

| Command | สิทธิ์ | คำอธิบาย |
|---|---|---|
| `/panel` | Administrator | เปิด Admin Panel (ปุ่มจัดการคีย์ทั้งหมด) |
| `/giveaway duration:1d` | Administrator | สร้างปุ่มแจกคีย์ในช่องปัจจุบัน (ค่าที่รับ: `1d`, `3d`, `7d`, `1m`, `1y`, `permanent`) |

### Admin Panel (Bot)

ปุ่มในแผง `/panel`:
- 🟢 **Generate Keys** — สร้างคีย์ใหม่ (เลือกจำนวน + ระยะเวลา)
- 🔍 **Info / Search** — ค้นหา + ดูรายละเอียดคีย์
- 🗑️ **Delete Key** — ลบคีย์
- 🔄 **Reset HWID** — ล้าง HWID ที่ผูกอยู่
- ⏸️ **Pause / ▶️ Resume** — หยุด/เริ่มใช้คีย์ชั่วคราว
- 🛑 **Blacklist HWID** — แบน HWID
- 🌐 **Open Dashboard** — แสดงลิงก์เปิด dashboard

### Web Dashboard

URL: `http://<host>:<port>/dashboard`

มีตารางสถิติ, รายการคีย์, ปุ่มจัดการ — กดปุ่มเรียก REST API ใต้ฝา

### Terminal Console

หลังบอทรัน หน้าต่าง terminal จะแสดงเมนู — ต้องล็อกอินด้วย `TERMINAL_PASSWORD` ก่อน
ฟีเจอร์ตามใน `terminal_loop()` (บรรทัด ~944): ดูสถิติ, list keys, จัดการคีย์, ออกจากระบบ

---

## 🔌 Web API Reference

> Base URL: `http://<host>:<port>`
> Admin endpoints จำกัดเฉพาะ IP local (loopback/LAN) — ดู [Security Model](#-security-model)

| Method | Path | คำอธิบาย |
|---|---|---|
| GET  | `/dashboard` | หน้า dashboard (HTML) |
| GET  | `/health`    | health check |
| GET  | `/api/stats` | สถิติคีย์ (total, active, expired, paused, banned) |
| GET  | `/api/keys?term=&status=&offset=&limit=` | ค้นหาคีย์ |
| POST | `/api/keys/generate` | สร้างคีย์ใหม่ `{ amount, duration }` |
| POST | `/api/keys/delete`   | ลบคีย์ `{ key_id }` |
| POST | `/api/keys/revoke`   | revoke คีย์ |
| POST | `/api/keys/pause`    | pause/resume |
| GET  | `/api/blacklist`     | รายการ HWID ที่แบน |
| POST | `/api/blacklist/ban` | แบน HWID |
| POST | `/api/blacklist/unban` | ปลดแบน |
| POST | `/api/verify`        | **เรียกจาก client app**: ตรวจคีย์ + ผูก HWID |

### ตัวอย่าง `POST /api/verify`
```json
// request
{ "key": "VTX-XXXX-XXXX-XXXX", "hwid": "abc123hash" }

// response (ok)
{ "valid": true, "expires_at": "2026-12-31T23:59:59Z" }

// response (fail)
{ "valid": false, "reason": "expired" }
```

---

## 💾 ฐานข้อมูล

ไฟล์: `vortex_keys.db` (SQLite) — สร้างอัตโนมัติเมื่อรันครั้งแรก

ตารางหลัก (ดูใน `init_db()` ~บรรทัด 815):
- `keys` — key_id, hwid, status (active/paused/expired/revoked), created_at, expires_at, duration
- `blacklist` — hwid, reason, banned_at
- `terminal_logs` — log การใช้งาน terminal

**Backup**: copy ไฟล์ `vortex_keys.db` เก็บไว้ — แค่นี้พอ

---

## 🔐 Security Model

| ชั้น | รายละเอียด |
|---|---|
| Discord | slash commands ต้อง `default_permissions(administrator=True)` |
| Terminal | ล็อกอินด้วย `TERMINAL_PASSWORD` |
| Web admin endpoints | จำกัดเฉพาะ IP local (`_ip_is_local`): 127.0.0.1, ::1, 10.x, 172.16–31.x, 192.168.x และ LAN ของเครื่อง |
| Rate limit | ต่อ IP — กันยิงถี่ๆ |
| CSRF | ตรวจ origin/header สำหรับ POST จาก dashboard |
| Security Headers | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` |
| `/api/verify` | เปิดให้ทุก IP เพราะ client ทั่วโลกต้องเรียก — ป้องกันด้วยตัวคีย์เอง |

> ⚠️ อย่า expose พอร์ต admin ออก internet ตรงๆ — ใช้ reverse proxy + auth หรือ VPN

---

## 🌍 Deploy บน VPS / Server

### ตัวเลือก 1: รันด้วย `screen` / `tmux`
```bash
screen -S vortex
python main.py
# Ctrl+A แล้ว D เพื่อ detach
```

### ตัวเลือก 2: systemd service (Linux)
สร้าง `/etc/systemd/system/vortex-bot.service`:
```ini
[Unit]
Description=Vortex Security Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/vortex-bot
EnvironmentFile=/home/ubuntu/vortex-bot/.env
ExecStart=/home/ubuntu/vortex-bot/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```
แล้ว:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vortex-bot
sudo journalctl -u vortex-bot -f      # ดู log
```

### ตัวเลือก 3: Docker (สร้างเอง)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV API_PORT=30184
EXPOSE 30184
CMD ["python", "main.py"]
```

### เปิด dashboard ผ่าน domain
ตั้ง env `DASHBOARD_HOST=mybot.example.com` แล้วใช้ Nginx/Caddy reverse proxy ไปยัง `127.0.0.1:30184`

---

## 🛠️ แก้ปัญหาที่พบบ่อย (Troubleshooting)

### ❌ `discord.errors.LoginFailure: Improper token has been passed`
- `DISCORD_TOKEN` ผิด → reset ใหม่จาก Developer Portal
- ตรวจว่าไฟล์ `.env` อยู่โฟลเดอร์เดียวกับ `main.py`

### ❌ `Privileged intent ... is not enabled`
- ไปเปิด **MESSAGE CONTENT INTENT** + **SERVER MEMBERS INTENT** ใน Bot settings

### ❌ Slash command `/panel` ไม่ขึ้น
- รอ ~1 ชั่วโมง (global sync) หรือลบ + เชิญบอทใหม่ด้วย scope `applications.commands`

### ❌ `OSError: [Errno 98] Address already in use`
- พอร์ตซ้ำกับโปรเซสอื่น
- แก้: เปลี่ยน `API_PORT` ใน `.env` หรือฆ่าโปรเซสเก่า
  ```bash
  lsof -i :30184          # หา PID
  kill -9 <PID>
  ```

### ❌ เปิด dashboard บนคอมตัวเองไม่ได้ (ลิงก์เป็น public IP)
- ตั้ง `HOST_IP=127.0.0.1` หรือ `DASHBOARD_HOST=localhost` ใน `.env`
- โค้ดจะ fallback เป็น `127.0.0.1` อยู่แล้วเมื่อไม่มี env เหล่านี้

### ❌ Dashboard เปิดได้ แต่กดปุ่มแล้ว 403 Forbidden
- IP ที่เข้าไม่อยู่ใน whitelist ของ `_ip_is_local`
- ใช้จาก LAN เดียวกัน หรือ SSH tunnel:
  ```bash
  ssh -L 30184:127.0.0.1:30184 user@server
  # แล้วเปิด http://127.0.0.1:30184/dashboard บนเครื่องตัวเอง
  ```

### ❌ `aiosqlite.OperationalError: database is locked`
- มีหลายโปรเซสเปิดไฟล์ DB เดียวกัน → รันแค่ตัวเดียว

### ❌ Terminal ขึ้น "Invalid password"
- ตรวจตัวพิมพ์เล็ก/ใหญ่ ใน `TERMINAL_PASSWORD` (case-sensitive)

### ❌ `ModuleNotFoundError: No module named 'discord'`
- ลืม activate venv หรือยังไม่ได้ติดตั้ง dependency
  ```bash
  pip install -U discord.py aiohttp aiosqlite python-dotenv rich
  ```

### ❌ Bot รันแล้วปิดเอง / ไม่มี error
- รันใน foreground เพื่อดู log: `python main.py`
- ตรวจไฟล์ log ที่ `save_terminal_log()` เขียนตอนปิด

### ❌ Client app เรียก `/api/verify` แล้วได้ `valid: false`
- เช็คคีย์หมดอายุหรือยัง (`/api/keys` ใน dashboard)
- HWID เปลี่ยน → ใช้ปุ่ม **Reset HWID** ใน admin panel
- HWID อยู่ใน blacklist → ปลดที่ **Blacklist** tab

### ❌ พอร์ตถูก firewall block (VPS)
```bash
sudo ufw allow 30184/tcp
```

---

## ❓ FAQ

**Q: เปลี่ยนรูปแบบคีย์ได้ไหม?**
A: ได้ — แก้ฟังก์ชันที่ใช้ `uuid` ใน `api_generate_keys` (~บรรทัด 1550)

**Q: ใช้กับหลายเซิร์ฟเวอร์ Discord พร้อมกันได้ไหม?**
A: ได้ บอทรับ DM/Guild แบบ global แต่ `ADMIN_ROLE_ID` มีค่าเดียว — ถ้าต้องการแยกตาม guild ต้องแก้โค้ดเอง

**Q: อยากเปลี่ยนเป็น MySQL / PostgreSQL ได้ไหม?**
A: ได้ แต่ต้องเขียน DB layer ใหม่ (`init_db`, `search_keys`, ฯลฯ) เพราะปัจจุบันใช้ `aiosqlite`

**Q: ปลอดภัยพอที่จะใช้ commercial หรือยัง?**
A: เพียงพอสำหรับโปรเจกต์เล็ก-กลาง แต่ก่อน production แนะนำ:
- ใส่ reverse proxy + HTTPS (Caddy/Nginx)
- เพิ่ม auth สำหรับ `/api/verify` (เช่น HMAC signature)
- audit log แยกไฟล์
- backup `vortex_keys.db` อัตโนมัติ

---

## 📜 License

Internal use — เพิ่ม license ที่ต้องการเอง (MIT / Proprietary / ฯลฯ)

---

**Made with 🖤 by Vortex Security System**
