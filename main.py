import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
from aiohttp import web
import aiosqlite
import os
import uuid
import logging
import webbrowser
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import io
import asyncio
import secrets as _secrets
import hmac as _hmac
import socket as _socket
import ipaddress as _ipaddress
import time as _time
from collections import defaultdict as _defaultdict, deque as _deque
import logging
from datetime import datetime
import atexit

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align

load_dotenv()

TOKEN         = os.getenv("DISCORD_TOKEN")
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 0))
DB_FILE       = "vortex_keys.db"


# ── Hardcoded terminal password ──
TERMINAL_PASSWORD = "vortex2026"   # 🔑 เปลี่ยนรหัสตรงนี้

def _get_api_port():
    """ใช้พอร์ตจริงของ task/runtime ก่อน แล้วค่อย fallback เป็น API_PORT/30184."""
    for name in ("PORT", "SERVER_PORT", "WEB_PORT", "TASK_PORT", "API_PORT"):
        raw = os.getenv(name)
        if not raw:
            continue
        try:
            port = int(raw)
            if 1 <= port <= 65535:
                return port, name
        except ValueError:
            continue
    return 30184, "default"

def _get_lan_ip():
    """LAN IP ของเครื่อง (ใช้กับ home/personal PC)."""
    import socket as _s
    sock = _s.socket(_s.AF_INET, _s.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        try:
            return _s.gethostbyname(_s.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        sock.close()

def _get_public_ip():
    """Public IP (ใช้กับ VPS / dedicated server)."""
    import urllib.request as _u
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            with _u.urlopen(url, timeout=2) as r:
                ip = r.read().decode().strip()
                if ip and all(c in "0123456789." for c in ip):
                    return ip
        except Exception:
            continue
    return None

def _is_private_ip(ip):
    import ipaddress as _i
    try:
        a = _i.ip_address(ip)
        return a.is_private or a.is_loopback or a.is_link_local
    except Exception:
        return True

def _detect_host_url():
    """ลิงก์แดชบอร์ดต้องเข้าได้จากเครื่องที่รัน task นี้ก่อนเสมอ."""
    env = os.getenv("DASHBOARD_HOST") or os.getenv("HOST_IP") or os.getenv("PUBLIC_HOST")
    if env:
        return env.strip().removeprefix("http://").removeprefix("https://").split("/")[0].split(":")[0], "env"

    # browser.open() และ Chrome บนเครื่องเดียวกันควรใช้ loopback ไม่ใช่ public IP บ้าน
    if os.getenv("USE_LAN_DASHBOARD_URL", "").lower() in ("1", "true", "yes", "on"):
        lan = _get_lan_ip()
        return lan, "lan-env"
    return "127.0.0.1", "loopback"

API_PORT, _PORT_SRC = _get_api_port()
HOST_IP, _HOST_SRC = _detect_host_url()
BASE_URL      = f"http://{HOST_IP}:{API_PORT}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VORTEX")

COLOR_PRIMARY = discord.Color.from_rgb(99,  102, 241)
COLOR_SUCCESS = discord.Color.from_rgb(34,  197,  94)
COLOR_ERROR   = discord.Color.from_rgb(239,  68,  68)
COLOR_WARN    = discord.Color.from_rgb(245, 158,  11)
COLOR_INFO    = discord.Color.from_rgb(56,  189, 248)
COLOR_MUTED   = discord.Color.from_rgb(100, 116, 139)

DIV = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

EXPIRATION_PRESETS = {
    "1d": 1, "3d": 3, "7d": 7,
    "1m": 30, "1y": 365, "permanent": None,
}

console = Console(record=True)
def save_terminal_log():
    try:
        filename = f"terminal_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        console.save_text(filename, clear=False)
        # หรือถ้าอยากได้สีสวย ๆ เป็น HTML:
        # console.save_html(filename.replace('.txt', '.html'), clear=False)
    except Exception as e:
        print(f"Save log error: {e}")
        
atexit.register(save_terminal_log)
# ══════════════════════════════════════════════════════════════════
#  DASHBOARD HTML
# ══════════════════════════════════════════════════════════════════
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vortex Admin</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#070710;--bg-2:#0d0d1f;--surface:#10101f;--card:#15152a;
    --border:rgba(120,125,200,.18);--border-strong:rgba(140,145,230,.35);
    --indigo:#818cf8;--indigo-2:#6366f1;--indigo-deep:#4338ca;
    --green:#22c55e;--red:#ef4444;--amber:#f59e0b;--sky:#38bdf8;--pink:#ec4899;--muted:#64748b;
    --text:#e8ecff;--text-dim:#9aa3c7;--text-faint:#5b6488;
    --glow-indigo:0 0 24px rgba(99,102,241,.55);
    --shadow-card:0 8px 28px -10px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.02) inset;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%}
  body{
    display:flex;background:var(--bg);color:var(--text);
    font-family:'Inter','Segoe UI',system-ui,sans-serif;font-size:14px;overflow:hidden;
    position:relative;isolation:isolate;
  }
  /* Aurora background */
  body::before,body::after{
    content:'';position:fixed;z-index:-2;border-radius:50%;filter:blur(80px);
    pointer-events:none;
  }
  body::before{
    width:380px;height:380px;top:-120px;left:-100px;
    background:radial-gradient(circle,#6366f1 0%,transparent 70%);
    opacity:.35;
  }
  body::after{
    width:420px;height:420px;bottom:-160px;right:-120px;
    background:radial-gradient(circle,#38bdf8 0%,#ec4899 60%,transparent 80%);
    opacity:.22;
  }50%{transform:translate(80px,60px) scale(1.15)}}50%{transform:translate(-90px,-50px) scale(1.1)}}
  /* Subtle grid overlay */
  body::before{}
  .grid-overlay{display:none}

  /* ── Sidebar ── */
  #sidebar{
    width:236px;min-width:236px;background:var(--surface);
    border-right:1px solid var(--border);display:flex;flex-direction:column;
    padding:0;position:relative;
  }
  .logo{padding:22px 20px 18px;border-bottom:1px solid var(--border);position:relative}
  .logo-title{
    font-size:19px;font-weight:800;letter-spacing:.6px;
    background:linear-gradient(135deg,#a5b4fc,#38bdf8 55%,#ec4899);
    -webkit-background-clip:text;background-clip:text;color:transparent;
    filter:drop-shadow(0 0 12px rgba(99,102,241,.45));
  }
  .logo-sub{font-size:11px;color:var(--text-faint);margin-top:3px;letter-spacing:.5px;text-transform:uppercase}
  .nav{flex:1;padding:14px 10px;display:flex;flex-direction:column;gap:2px}
  .nav-item{
    display:flex;align-items:center;gap:11px;padding:10px 14px;cursor:pointer;
    border-radius:9px;color:var(--text-dim);font-size:13.5px;font-weight:500;
    position:relative;transition:color .2s,background .2s,transform .2s;
  }
  .nav-item::before{
    content:'';position:absolute;left:0;top:50%;transform:translateY(-50%);
    width:3px;height:0;border-radius:3px;background:linear-gradient(180deg,#818cf8,#38bdf8);
    transition:height .25s ease;box-shadow:0 0 10px rgba(129,140,248,.7);
  }
  .nav-item:hover{background:rgba(129,140,248,.08);color:var(--text);transform:translateX(2px)}
  .nav-item.active{
    background:linear-gradient(90deg,rgba(99,102,241,.22),rgba(56,189,248,.05));
    color:#fff;
  }
  .nav-item.active::before{height:22px}
  .nav-icon{font-size:15px;width:22px;text-align:center;filter:drop-shadow(0 0 6px rgba(129,140,248,.4))}
  .sidebar-footer{padding:14px 20px;border-top:1px solid var(--border);font-size:11px;color:var(--text-faint);letter-spacing:.4px}

  /* ── Main ── */
  #main{flex:1;display:flex;flex-direction:column;overflow:hidden}
  #topbar{
    height:58px;min-height:58px;background:var(--surface);
    border-bottom:1px solid var(--border);
    display:flex;align-items:center;justify-content:space-between;padding:0 28px;
  }
  #page-title{font-size:16px;font-weight:700;color:#fff;letter-spacing:.2px}
  .page-sub{font-size:12px;color:var(--text-faint);margin-top:3px}
  #topbar-actions{display:flex;gap:8px;align-items:center}
  #content{flex:1;overflow-y:auto;padding:28px;animation:fadeIn .35s ease}
  @keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

  /* ── Cards (Glass) ── */
  .card{
    background:var(--card);border:1px solid var(--border);border-radius:14px;
    padding:20px 22px;
    box-shadow:var(--shadow-card);position:relative;overflow:hidden;
  }

  .stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px;margin-bottom:26px}
  .stat-card{
    background:var(--card);border:1px solid var(--border);border-radius:14px;
    padding:18px 20px;
    box-shadow:var(--shadow-card);position:relative;overflow:hidden;
    transition:transform .25s ease,border-color .25s ease,box-shadow .25s ease;
    cursor:default;
  }
  .stat-card:hover{
    transform:translateY(-3px);border-color:var(--border-strong);
    box-shadow:0 14px 40px -12px rgba(99,102,241,.35),0 0 0 1px rgba(129,140,248,.25) inset;
  }
  .stat-label{font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px;font-weight:600}
  .stat-value{font-size:30px;font-weight:800;letter-spacing:-.5px;position:relative;z-index:1}
  .c-indigo{background:linear-gradient(135deg,#a5b4fc,#6366f1);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 10px rgba(99,102,241,.4))}
  .c-green{background:linear-gradient(135deg,#86efac,#22c55e);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 10px rgba(34,197,94,.35))}
  .c-red{background:linear-gradient(135deg,#fca5a5,#ef4444);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 10px rgba(239,68,68,.35))}
  .c-amber{background:linear-gradient(135deg,#fcd34d,#f59e0b);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 10px rgba(245,158,11,.35))}
  .c-sky{background:linear-gradient(135deg,#7dd3fc,#38bdf8);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 0 10px rgba(56,189,248,.4))}
  .c-muted{color:var(--text-faint)}

  /* ── Buttons ── */
  .btn{
    display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:9px;
    border:1px solid transparent;cursor:pointer;font-size:13px;font-weight:600;
    transition:transform .15s ease,box-shadow .2s ease,background .2s ease,filter .2s ease;
    position:relative;overflow:hidden;font-family:inherit;
  }
  .btn:hover:not(:disabled){transform:translateY(-1px)}
  .btn:active:not(:disabled){transform:translateY(0)}
  .btn-primary{background:linear-gradient(135deg,#6366f1,#4338ca);color:#fff;box-shadow:0 4px 14px -4px rgba(99,102,241,.6)}
  .btn-primary:hover{box-shadow:0 6px 22px -4px rgba(99,102,241,.8)}
  .btn-success{background:linear-gradient(135deg,#22c55e,#15803d);color:#fff;box-shadow:0 4px 14px -4px rgba(34,197,94,.55)}
  .btn-success:hover{box-shadow:0 6px 22px -4px rgba(34,197,94,.75)}
  .btn-danger{background:linear-gradient(135deg,#ef4444,#b91c1c);color:#fff;box-shadow:0 4px 14px -4px rgba(239,68,68,.5)}
  .btn-danger:hover{box-shadow:0 6px 22px -4px rgba(239,68,68,.7)}
  .btn-ghost{background:rgba(255,255,255,.04);color:var(--text-dim);border:1px solid var(--border)}
  .btn-ghost:hover{background:rgba(129,140,248,.12);color:#fff;border-color:var(--border-strong)}
  .btn-sm{padding:6px 11px;font-size:12px;border-radius:7px}
  .btn:disabled{opacity:.4;cursor:not-allowed}

  /* ── Table ── */
  .tbl-wrap{
    overflow-x:auto;border-radius:14px;border:1px solid var(--border);
    background:var(--card);
    box-shadow:var(--shadow-card);
  }
  table{width:100%;border-collapse:collapse}
  thead{background:rgba(129,140,248,.06)}
  th{padding:12px 16px;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--text-faint);font-weight:700;white-space:nowrap;border-bottom:1px solid var(--border)}
  td{padding:12px 16px;border-top:1px solid rgba(120,130,220,.06);color:var(--text-dim);font-size:13px;vertical-align:middle;transition:background .15s,color .15s}
  tbody tr{transition:background .15s ease}
  tbody tr:hover td{background:rgba(129,140,248,.06);color:var(--text)}

  .badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.3px;border:1px solid transparent}
  .badge-green{background:rgba(34,197,94,.14);color:#86efac;border-color:rgba(34,197,94,.35);box-shadow:0 0 12px -2px rgba(34,197,94,.4)}
  .badge-red{background:rgba(239,68,68,.14);color:#fca5a5;border-color:rgba(239,68,68,.35);box-shadow:0 0 12px -2px rgba(239,68,68,.35)}
  .badge-amber{background:rgba(245,158,11,.14);color:#fcd34d;border-color:rgba(245,158,11,.35);box-shadow:0 0 12px -2px rgba(245,158,11,.35)}
  .badge-muted{background:rgba(100,116,139,.18);color:#94a3b8;border-color:rgba(100,116,139,.3)}
  .badge-sky{background:rgba(56,189,248,.14);color:#7dd3fc;border-color:rgba(56,189,248,.35);box-shadow:0 0 12px -2px rgba(56,189,248,.4)}
  code{font-size:12px;background:rgba(56,189,248,.08);padding:3px 8px;border-radius:6px;font-family:'JetBrains Mono','Cascadia Code',monospace;color:#7dd3fc;border:1px solid rgba(56,189,248,.18)}

  /* ── Toolbar ── */
  .toolbar{display:flex;gap:10px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
  .search-input,select.filter-select{
    background:var(--card);border:1px solid var(--border);border-radius:9px;
    padding:9px 14px;color:var(--text);font-size:13px;outline:none;
    transition:border-color .2s,box-shadow .2s,background .2s;font-family:inherit;
  }
  .search-input{width:280px}
  .search-input:focus,select.filter-select:focus{
    border-color:var(--indigo);box-shadow:0 0 0 3px rgba(99,102,241,.18),var(--glow-indigo);
  }
  .search-input::placeholder{color:var(--text-faint)}
  select.filter-select{cursor:pointer;color:var(--text-dim)}

  /* ── Modal ── */
  .overlay{
    display:none;position:fixed;inset:0;background:rgba(5,5,15,.7);z-index:100;align-items:center;justify-content:center;
    animation:overlayIn .2s ease;
  }
  .overlay.open{display:flex}
  @keyframes overlayIn{from{opacity:0}to{opacity:1}}
  .modal{
    background:linear-gradient(160deg,rgba(30,30,55,.92),rgba(18,18,38,.92));
    border:1px solid var(--border-strong);border-radius:18px;
    padding:28px 30px;width:480px;max-width:95vw;
    box-shadow:0 30px 80px -20px rgba(0,0,0,.7),0 0 0 1px rgba(255,255,255,.04) inset,
               0 0 60px -10px rgba(99,102,241,.4);
    animation:modalIn .25s cubic-bezier(.2,.9,.3,1.4);
  }
  @keyframes modalIn{from{opacity:0;transform:scale(.92) translateY(10px)}to{opacity:1;transform:none}}
  .modal-title{font-size:17px;font-weight:700;color:#fff;margin-bottom:5px;letter-spacing:.2px}
  .modal-sub{font-size:13px;color:var(--text-faint);margin-bottom:22px;line-height:1.5}
  .form-group{margin-bottom:16px}
  .form-label{font-size:11px;color:var(--text-dim);margin-bottom:7px;display:block;font-weight:600;text-transform:uppercase;letter-spacing:.6px}
  .form-input{
    width:100%;background:rgba(10,10,22,.7);border:1px solid var(--border);
    border-radius:9px;padding:10px 14px;color:var(--text);font-size:13px;outline:none;
    transition:border-color .2s,box-shadow .2s;font-family:inherit;
  }
  .form-input:focus{border-color:var(--indigo);box-shadow:0 0 0 3px rgba(99,102,241,.18)}
  .modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:22px}
  .radio-group{display:flex;flex-wrap:wrap;gap:8px}
  .radio-opt{
    cursor:pointer;padding:7px 14px;border-radius:8px;border:1px solid var(--border);
    font-size:12px;color:var(--text-dim);font-weight:600;letter-spacing:.3px;
    transition:all .2s ease;background:rgba(255,255,255,.02);
  }
  .radio-opt:hover{color:#fff;border-color:var(--border-strong);transform:translateY(-1px)}
  .radio-opt.sel{
    border-color:var(--indigo);color:#fff;
    background:linear-gradient(135deg,rgba(99,102,241,.3),rgba(56,189,248,.15));
    box-shadow:0 0 18px -4px rgba(99,102,241,.6);
  }

  /* ── Toast ── */
  #toast-root{position:fixed;bottom:24px;right:24px;display:flex;flex-direction:column;gap:10px;z-index:200}
  .toast{
    padding:12px 18px;border-radius:11px;font-size:13px;font-weight:600;
    display:flex;align-items:center;gap:10px;
    border:1px solid;box-shadow:0 10px 30px -8px rgba(0,0,0,.5);
    animation:toastIn .35s cubic-bezier(.2,.9,.3,1.4);
  }
  .toast-ok{background:rgba(20,60,35,.7);border-color:rgba(34,197,94,.5);color:#86efac}
  .toast-err{background:rgba(60,15,15,.7);border-color:rgba(239,68,68,.5);color:#fca5a5}
  .toast-info{background:rgba(15,30,55,.7);border-color:rgba(56,189,248,.5);color:#7dd3fc}
  @keyframes toastIn{from{transform:translateX(60px) scale(.9);opacity:0}to{transform:none;opacity:1}}

  /* ── Misc ── */
  .section{display:none;animation:fadeIn .35s ease}
  .section.active{display:block}
  .row{display:flex;gap:12px;align-items:center}
  .spacer{flex:1}
  .mt8{margin-top:8px}.mt16{margin-top:16px}.mt24{margin-top:24px}
  .empty{padding:50px;text-align:center;color:var(--text-faint);font-size:13px;letter-spacing:.3px}
  ::-webkit-scrollbar{width:8px;height:8px}
  ::-webkit-scrollbar-track{background:transparent}
  ::-webkit-scrollbar-thumb{background:linear-gradient(180deg,#4338ca,#6366f1);border-radius:8px;border:2px solid transparent;background-clip:padding-box}
  ::-webkit-scrollbar-thumb:hover{background:linear-gradient(180deg,#6366f1,#818cf8);background-clip:padding-box;border:2px solid transparent}
  .checkbox{width:16px;height:16px;cursor:pointer;accent-color:#6366f1}
  .key-output{
    background:rgba(5,8,20,.75);border:1px solid var(--border);border-radius:10px;
    padding:16px;font-family:'JetBrains Mono','Cascadia Code',monospace;font-size:12.5px;
    color:#7dd3fc;max-height:240px;overflow-y:auto;line-height:1.8;word-break:break-all;
    white-space:pre-wrap;box-shadow:inset 0 0 30px rgba(56,189,248,.07);
  }
  /* Section card title helper (keeps existing inline styles working) */
</style>
</head>
<body>
<div class="grid-overlay"></div>

<!-- SIDEBAR -->
<div id="sidebar">
  <div class="logo">
    <div class="logo-title">⚡ Vortex</div>
    <div class="logo-sub">Admin Dashboard</div>
  </div>
  <nav class="nav">
    <div class="nav-item active" onclick="nav('stats')"><span class="nav-icon">📊</span>Overview</div>
    <div class="nav-item" onclick="nav('keys')"><span class="nav-icon">🔑</span>Key Manager</div>
    <div class="nav-item" onclick="nav('generate')"><span class="nav-icon">✨</span>Generate Keys</div>
    <div class="nav-item" onclick="nav('blacklist')"><span class="nav-icon">🛑</span>Blacklist</div>
  </nav>
  <div class="sidebar-footer">Vortex Security System</div>
</div>

<!-- MAIN -->
<div id="main">
  <div id="topbar">
    <div>
      <div id="page-title">Overview</div>
      <div class="page-sub" id="page-sub">System statistics</div>
    </div>
    <div id="topbar-actions"></div>
  </div>
  <div id="content">

    <!-- ── STATS ── -->
    <div id="sec-stats" class="section active">
      <div class="stat-grid" id="stat-grid">
        <div class="stat-card"><div class="stat-label">Total Keys</div><div class="stat-value c-indigo" id="s-total">—</div></div>
        <div class="stat-card"><div class="stat-label">Active</div><div class="stat-value c-green" id="s-active">—</div></div>
        <div class="stat-card"><div class="stat-label">Paused</div><div class="stat-value c-amber" id="s-paused">—</div></div>
        <div class="stat-card"><div class="stat-label">Revoked</div><div class="stat-value c-red" id="s-revoked">—</div></div>
        <div class="stat-card"><div class="stat-label">HWID Bound</div><div class="stat-value c-sky" id="s-bound">—</div></div>
        <div class="stat-card"><div class="stat-label">Blacklisted HWIDs</div><div class="stat-value c-red" id="s-blacklisted">—</div></div>
      </div>
      <div class="card mt8">
        <div style="font-size:13px;color:var(--muted);margin-bottom:14px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Recent Keys</div>
        <div id="recent-keys-wrap"></div>
      </div>
    </div>

    <!-- ── KEYS ── -->
    <div id="sec-keys" class="section">
      <div class="toolbar">
        <input id="key-search" class="search-input" placeholder="Search key ID…" oninput="debounceKeySearch()" />
        <select class="filter-select" id="key-status-filter" onchange="loadKeys()">
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="revoked">Revoked</option>
        </select>
        <div class="spacer"></div>
        <button class="btn btn-danger btn-sm" id="bulk-delete-btn" onclick="bulkDelete()" disabled>🗑 Delete Selected</button>
        <button class="btn btn-ghost btn-sm" id="bulk-revoke-btn" onclick="bulkRevoke()" disabled>🚫 Revoke Selected</button>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead>
            <tr>
              <th><input type="checkbox" class="checkbox" id="select-all" onchange="toggleAll(this)"></th>
              <th>Key ID</th><th>Status</th><th>Duration</th>
              <th>Expires</th><th>HWID</th><th>Created By</th><th>Actions</th>
            </tr>
          </thead>
          <tbody id="keys-body"><tr><td colspan="8" class="empty">Loading…</td></tr></tbody>
        </table>
      </div>
      <div id="keys-pagination" class="row mt16" style="justify-content:flex-end;gap:6px"></div>
    </div>

    <!-- ── GENERATE ── -->
    <div id="sec-generate" class="section">
      <div style="max-width:520px">
        <div class="card">
          <div style="font-size:13px;color:var(--muted);margin-bottom:18px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Key Configuration</div>
          <div class="form-group">
            <div class="form-label">Duration</div>
            <div class="radio-group" id="dur-opts">
              <div class="radio-opt sel" data-val="1d" onclick="selDur(this)">1 Day</div>
              <div class="radio-opt" data-val="3d" onclick="selDur(this)">3 Days</div>
              <div class="radio-opt" data-val="7d" onclick="selDur(this)">7 Days</div>
              <div class="radio-opt" data-val="1m" onclick="selDur(this)">1 Month</div>
              <div class="radio-opt" data-val="1y" onclick="selDur(this)">1 Year</div>
              <div class="radio-opt" data-val="permanent" onclick="selDur(this)">Permanent</div>
            </div>
          </div>
          <div class="form-group">
            <div class="form-label">Amount (1–50)</div>
            <input type="number" class="form-input" id="gen-amount" value="1" min="1" max="50" style="width:120px">
          </div>
          <button class="btn btn-success" onclick="generateKeys()">✨ Generate</button>
        </div>
        <div id="gen-result" class="mt16"></div>
      </div>
    </div>

    <!-- ── BLACKLIST ── -->
    <div id="sec-blacklist" class="section">
      <div class="toolbar">
        <input id="bl-search" class="search-input" placeholder="Search HWID…" oninput="filterBlacklist()" />
        <div class="spacer"></div>
        <button class="btn btn-danger btn-sm" onclick="openBanModal()">🛑 Ban HWID</button>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead>
            <tr><th>HWID</th><th>Reason</th><th>Banned At</th><th>Banned By</th><th>Actions</th></tr>
          </thead>
          <tbody id="bl-body"><tr><td colspan="5" class="empty">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>

  </div>
</div>

<!-- MODALS -->
<div class="overlay" id="ban-modal">
  <div class="modal">
    <div class="modal-title">🛑 Ban HWID</div>
    <div class="modal-sub">Device will be permanently blacklisted. All keys revoked.</div>
    <div class="form-group"><div class="form-label">HWID</div><input class="form-input" id="ban-hwid" placeholder="Paste HWID here"></div>
    <div class="form-group"><div class="form-label">Reason</div><input class="form-input" id="ban-reason" placeholder="e.g. Cheating, Chargeback"></div>
    <div class="modal-actions">
      <button class="btn btn-ghost" onclick="closeModal('ban-modal')">Cancel</button>
      <button class="btn btn-danger" onclick="submitBan()">Ban HWID</button>
    </div>
  </div>
</div>

<div class="overlay" id="key-action-modal">
  <div class="modal">
    <div class="modal-title" id="ka-title">Confirm Action</div>
    <div class="modal-sub" id="ka-sub"></div>
    <div class="modal-actions">
      <button class="btn btn-ghost" onclick="closeModal('key-action-modal')">Cancel</button>
      <button class="btn btn-danger" id="ka-confirm" onclick="">Confirm</button>
    </div>
  </div>
</div>

<!-- TOAST -->
<div id="toast-root"></div>

<script>
const API = '';
let allBlacklistRows = [];
let selectedKeys = new Set();
let currentDur = '1d';
let keysOffset = 0;
const PAGE_SIZE = 50;

// ── Navigation ──────────────────────────────────────────────────
const sections = {
  stats:     {el:'sec-stats',     title:'Overview',     sub:'System statistics',   actions:''},
  keys:      {el:'sec-keys',      title:'Key Manager',  sub:'Search, manage and bulk-operate keys', actions:''},
  generate:  {el:'sec-generate',  title:'Generate Keys',sub:'Create new access keys', actions:''},
  blacklist: {el:'sec-blacklist', title:'Blacklist',    sub:'Banned HWID management', actions:''},
};
function nav(id) {
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('sec-'+id).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n=>{
    if(n.getAttribute('onclick')===`nav('${id}')`) n.classList.add('active');
  });
  const s=sections[id];
  document.getElementById('page-title').textContent=s.title;
  document.getElementById('page-sub').textContent=s.sub;
  if(id==='stats')     loadStats();
  if(id==='keys')      loadKeys();
  if(id==='blacklist') loadBlacklist();
}

// ── Toast ────────────────────────────────────────────────────────
function toast(msg,type='ok') {
  const t=document.createElement('div');
  t.className=`toast toast-${type}`;
  t.textContent= type==='ok'?'✓ '+msg : type==='err'?'✗ '+msg : 'ℹ '+msg;
  document.getElementById('toast-root').appendChild(t);
  setTimeout(()=>t.remove(),3000);
}

// ── Stats ────────────────────────────────────────────────────────
async function loadStats() {
  const r=await fetch(`${API}/stats`);
  const d=await r.json();
  document.getElementById('s-total').textContent=d.total_keys??d.total??0;
  document.getElementById('s-active').textContent=d.active_keys??d.active??0;
  document.getElementById('s-paused').textContent=d.paused??0;
  document.getElementById('s-revoked').textContent=d.revoked_keys??d.revoked??0;
  document.getElementById('s-bound').textContent=d.bound_keys??d.bound??0;
  document.getElementById('s-blacklisted').textContent=d.blacklisted??0;

  const r2=await fetch(`${API}/api/keys?limit=10`);
  const d2=await r2.json();
  const wrap=document.getElementById('recent-keys-wrap');
  if(!d2.keys||d2.keys.length===0){wrap.innerHTML='<div class="empty">No keys yet</div>';return;}
  wrap.innerHTML=`<div class="tbl-wrap"><table>
    <thead><tr><th>Key ID</th><th>Status</th><th>Expires</th><th>HWID</th></tr></thead>
    <tbody>${d2.keys.map(k=>`<tr>
      <td><code>${k.key_id}</code></td>
      <td>${statusBadge(k.status,k.paused_at)}</td>
      <td>${fmtExp(k.expiration_date)}</td>
      <td>${k.hwid?'<span class="badge badge-green">● Bound</span>':'<span class="badge badge-muted">○ Free</span>'}</td>
    </tr>`).join('')}</tbody>
  </table></div>`;
}

// ── Keys ─────────────────────────────────────────────────────────
let _keyTimer=null;
function debounceKeySearch(){clearTimeout(_keyTimer);_keyTimer=setTimeout(()=>{keysOffset=0;loadKeys()},300)}

async function loadKeys() {
  const q=document.getElementById('key-search').value.trim();
  const st=document.getElementById('key-status-filter').value;
  let url=`${API}/api/keys?limit=${PAGE_SIZE}&offset=${keysOffset}`;
  if(q) url+=`&search=${encodeURIComponent(q)}`;
  if(st) url+=`&status=${st}`;
  const r=await fetch(url);
  const d=await r.json();
  const tbody=document.getElementById('keys-body');
  if(!d.keys||d.keys.length===0){
    tbody.innerHTML='<tr><td colspan="8" class="empty">No keys found</td></tr>';
    buildPagination(0);return;
  }
  tbody.innerHTML=d.keys.map(k=>{
    const chk=`<input type="checkbox" class="checkbox key-chk" data-id="${k.key_id}" onchange="toggleSel(this)">`;
    const acts=`
      <button class="btn btn-ghost btn-sm" onclick="openKeyAction('revoke','${k.key_id}')">🚫</button>
      <button class="btn btn-ghost btn-sm" onclick="openKeyAction('pause','${k.key_id}')">⏸</button>
      <button class="btn btn-danger btn-sm" onclick="openKeyAction('delete','${k.key_id}')">🗑</button>`;
    return `<tr>
      <td>${chk}</td>
      <td><code>${k.key_id}</code></td>
      <td>${statusBadge(k.status,k.paused_at)}</td>
      <td>${k.duration||'—'}</td>
      <td>${fmtExp(k.expiration_date)}</td>
      <td>${k.hwid?`<code title="${k.hwid}">${k.hwid.slice(0,14)}…</code>`:'<span style="color:var(--muted)">—</span>'}</td>
      <td style="color:var(--text-faint)">${(k.created_by||'').slice(0,20)}</td>
      <td><div class="row" style="gap:4px">${acts}</div></td>
    </tr>`;
  }).join('');
  buildPagination(d.total||0);
  selectedKeys.clear();
  updateBulkBtns();
}

function buildPagination(total){
  const pages=Math.ceil(total/PAGE_SIZE);
  const cur=Math.floor(keysOffset/PAGE_SIZE);
  const el=document.getElementById('keys-pagination');
  if(pages<=1){el.innerHTML='';return;}
  let html=`<span style="color:var(--muted);font-size:12px">${total} keys</span>`;
  html+=`<button class="btn btn-ghost btn-sm" onclick="goPage(${cur-1})" ${cur===0?'disabled':''}>‹</button>`;
  for(let i=0;i<pages;i++) html+=`<button class="btn btn-sm ${i===cur?'btn-primary':'btn-ghost'}" onclick="goPage(${i})">${i+1}</button>`;
  html+=`<button class="btn btn-ghost btn-sm" onclick="goPage(${cur+1})" ${cur===pages-1?'disabled':''}>›</button>`;
  el.innerHTML=html;
}
function goPage(p){keysOffset=p*PAGE_SIZE;loadKeys()}
function toggleAll(cb){document.querySelectorAll('.key-chk').forEach(c=>{c.checked=cb.checked;toggleSel(c)});updateBulkBtns()}
function toggleSel(cb){cb.checked?selectedKeys.add(cb.dataset.id):selectedKeys.delete(cb.dataset.id);updateBulkBtns()}
function updateBulkBtns(){
  const has=selectedKeys.size>0;
  document.getElementById('bulk-delete-btn').disabled=!has;
  document.getElementById('bulk-revoke-btn').disabled=!has;
  if(has){
    document.getElementById('bulk-delete-btn').textContent=`🗑 Delete (${selectedKeys.size})`;
    document.getElementById('bulk-revoke-btn').textContent=`🚫 Revoke (${selectedKeys.size})`;
  }else{
    document.getElementById('bulk-delete-btn').textContent='🗑 Delete Selected';
    document.getElementById('bulk-revoke-btn').textContent='🚫 Revoke Selected';
  }
}
async function bulkDelete(){
  if(!selectedKeys.size) return;
  if(!confirm(`Delete ${selectedKeys.size} key(s)?`)) return;
  await Promise.all([...selectedKeys].map(k=>fetch(`${API}/api/keys/${k}`,{method:'DELETE'})));
  toast(`Deleted ${selectedKeys.size} key(s)`,'ok');
  selectedKeys.clear();loadKeys();
}
async function bulkRevoke(){
  if(!selectedKeys.size) return;
  await Promise.all([...selectedKeys].map(k=>fetch(`${API}/api/keys/${k}/revoke`,{method:'POST'})));
  toast(`Revoked ${selectedKeys.size} key(s)`,'ok');
  selectedKeys.clear();loadKeys();
}

// Key single actions
function openKeyAction(action,keyId){
  const labels={revoke:'Revoke Key',delete:'Delete Key',pause:'Pause / Resume Key'};
  const subs={
    revoke:`Key <code>${keyId}</code> will be permanently revoked.`,
    delete:`Key <code>${keyId}</code> will be permanently deleted from the database.`,
    pause:`Toggle pause state for key <code>${keyId}</code>.`,
  };
  document.getElementById('ka-title').textContent=labels[action];
  document.getElementById('ka-sub').innerHTML=subs[action];
  document.getElementById('ka-confirm').className=`btn ${action==='delete'?'btn-danger':action==='revoke'?'btn-danger':'btn-primary'}`;
  document.getElementById('ka-confirm').textContent=action==='pause'?'Toggle Pause':'Confirm';
  document.getElementById('ka-confirm').onclick=()=>execKeyAction(action,keyId);
  document.getElementById('key-action-modal').classList.add('open');
}
async function execKeyAction(action,keyId){
  closeModal('key-action-modal');
  let url=`${API}/api/keys/${keyId}`, method='DELETE';
  if(action==='revoke'){url=`${API}/api/keys/${keyId}/revoke`;method='POST';}
  if(action==='pause') {url=`${API}/api/keys/${keyId}/pause`;method='POST';}
  const r=await fetch(url,{method});
  const d=await r.json();
  if(d.status==='success') toast(d.message||'Done','ok');
  else toast(d.message||'Error','err');
  loadKeys();
}

// ── Generate ─────────────────────────────────────────────────────
function selDur(el){
  document.querySelectorAll('.radio-opt').forEach(o=>o.classList.remove('sel'));
  el.classList.add('sel');currentDur=el.dataset.val;
}
async function generateKeys(){
  const amount=parseInt(document.getElementById('gen-amount').value)||1;
  if(amount<1||amount>50){toast('Amount must be 1–50','err');return;}
  const r=await fetch(`${API}/api/keys/generate`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({duration:currentDur,amount})
  });
  const d=await r.json();
  if(d.status!=='success'){toast(d.message||'Error','err');return;}
  const el=document.getElementById('gen-result');
  el.innerHTML=`<div class="card">
    <div style="font-size:12px;color:var(--muted);margin-bottom:10px">${d.keys.length} key${d.keys.length>1?'s':''} · ${currentDur} · Expires ${d.expiration_date==='permanent'?'Never':new Date(d.expiration_date).toLocaleDateString()}</div>
    <div class="key-output">${d.keys.join('\n')}</div>
    <div class="row mt8" style="gap:8px">
      <button class="btn btn-ghost btn-sm" onclick="copyKeys(${JSON.stringify(d.keys).replace(/"/g,'&quot;')})">📋 Copy All</button>
    </div>
  </div>`;
  toast(`Generated ${d.keys.length} key(s)`,'ok');
}
function copyKeys(keys){navigator.clipboard.writeText(keys.join('\n'));toast('Copied to clipboard','info')}

// ── Blacklist ────────────────────────────────────────────────────
async function loadBlacklist(){
  const r=await fetch(`${API}/api/blacklist`);
  const d=await r.json();
  allBlacklistRows=d.entries||[];
  renderBlacklist(allBlacklistRows);
}
function filterBlacklist(){
  const q=document.getElementById('bl-search').value.toLowerCase();
  renderBlacklist(allBlacklistRows.filter(e=>e.hwid.toLowerCase().includes(q)||(e.reason||'').toLowerCase().includes(q)));
}
function renderBlacklist(rows){
  const tbody=document.getElementById('bl-body');
  if(!rows.length){tbody.innerHTML='<tr><td colspan="5" class="empty">Blacklist is empty</td></tr>';return;}
  tbody.innerHTML=rows.map(e=>`<tr>
    <td><code>${e.hwid}</code></td>
    <td>${e.reason||'—'}</td>
    <td style="color:var(--text-faint)">${fmtTs(e.banned_at)}</td>
    <td style="color:var(--text-faint)">${e.banned_by||'—'}</td>
    <td><button class="btn btn-ghost btn-sm" onclick="unban('${e.hwid}')">✅ Unban</button></td>
  </tr>`).join('');
}
function openBanModal(){document.getElementById('ban-modal').classList.add('open')}
async function submitBan(){
  const hwid=document.getElementById('ban-hwid').value.trim();
  const reason=document.getElementById('ban-reason').value.trim()||'No reason';
  if(!hwid){toast('HWID required','err');return;}
  const r=await fetch(`${API}/api/blacklist`,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({hwid,reason})
  });
  const d=await r.json();
  closeModal('ban-modal');
  document.getElementById('ban-hwid').value='';document.getElementById('ban-reason').value='';
  if(d.status==='success'){toast('HWID banned','ok');loadBlacklist();}
  else toast(d.message||'Error','err');
}
async function unban(hwid){
  const r=await fetch(`${API}/api/blacklist/${encodeURIComponent(hwid)}`,{method:'DELETE'});
  const d=await r.json();
  if(d.status==='success'){toast('HWID unbanned','ok');loadBlacklist();}
  else toast(d.message||'Error','err');
}

// ── Modals ───────────────────────────────────────────────────────
function closeModal(id){document.getElementById(id).classList.remove('open')}
document.querySelectorAll('.overlay').forEach(o=>o.addEventListener('click',e=>{if(e.target===o)o.classList.remove('open')}));

// ── Helpers ──────────────────────────────────────────────────────
function statusBadge(status,paused_at){
  if(paused_at) return '<span class="badge badge-amber">⏸ Paused</span>';
  if(status==='active') return '<span class="badge badge-green">✅ Active</span>';
  return '<span class="badge badge-red">🚫 Revoked</span>';
}
function fmtExp(exp){
  if(!exp) return '—';
  if(exp==='permanent') return '<span class="badge badge-sky">🔓 Permanent</span>';
  const d=new Date(exp),diff=Math.floor((d-Date.now())/86400000);
  const label=d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
  if(diff<0) return `<span class="badge badge-red">Expired</span>`;
  if(diff===0) return `<span class="badge badge-amber">Today</span>`;
  if(diff<=3) return `<span class="badge badge-amber">${label}</span>`;
  return `<span style="color:var(--text-dim)">${label}</span>`;
}
function fmtTs(ts){
  if(!ts) return '—';
  return new Date(ts).toLocaleString('en-US',{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'});
}

// ── Hash routing ─────────────────────────────────────────────────
function applyHash(){
  const h=location.hash.replace('#','');
  if(sections[h]) nav(h); else loadStats();
}
window.addEventListener('hashchange',applyHash);
applyHash();
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════════
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS keys (
            key_id TEXT PRIMARY KEY, hwid TEXT, duration TEXT, expiration_date TEXT,
            status TEXT, created_by TEXT, created_at TEXT, rekeyed_from TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS blacklist (
            hwid TEXT PRIMARY KEY, reason TEXT, banned_at TEXT, banned_by TEXT)""")
        async with db.execute("PRAGMA table_info(keys)") as cur:
            cols = [r[1] for r in await cur.fetchall()]
            if "paused_at" not in cols:
                await db.execute("ALTER TABLE keys ADD COLUMN paused_at TEXT")
        await db.commit()

async def search_keys(term="", limit=25, offset=0, status="",
                      columns="key_id, expiration_date, hwid, status") -> list[tuple]:
    async with aiosqlite.connect(DB_FILE) as db:
        conds, params = [], []
        if term:   conds.append("key_id LIKE ?");   params.append(f"%{term}%")
        if status: conds.append("status = ?");      params.append(status)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        async with db.execute(
            f"SELECT {columns} FROM keys {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ) as cur: rows = await cur.fetchall()
        async with db.execute(f"SELECT COUNT(*) FROM keys {where}", params) as cur:
            total = (await cur.fetchone())[0]
    return rows, total

async def fetch_stats() -> dict:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT COUNT(*), SUM(CASE WHEN status='active' THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN status='revoked' THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN hwid IS NOT NULL THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN paused_at IS NOT NULL THEN 1 ELSE 0 END) FROM keys"
        ) as cur: t,a,r,b,p = await cur.fetchone()
        async with db.execute("SELECT COUNT(*) FROM blacklist") as cur:
            bl = (await cur.fetchone())[0]
    return {"total":t or 0,"active":a or 0,"revoked":r or 0,"bound":b or 0,"paused":p or 0,"blacklisted":bl or 0}

# ══════════════════════════════════════════════════════════════════
#  TERMINAL (rich)
# ══════════════════════════════════════════════════════════════════
BANNER = """
 ██╗   ██╗ ██████╗ ██████╗ ████████╗███████╗██╗  ██╗
 ██║   ██║██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝
 ██║   ██║██║   ██║██████╔╝   ██║   █████╗   ╚███╔╝
 ╚██╗ ██╔╝██║   ██║██╔══██╗   ██║   ██╔══╝   ██╔██╗
  ╚████╔╝ ╚██████╔╝██║  ██║   ██║   ███████╗██╔╝ ██╗
   ╚═══╝   ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝"""

MENU_ITEMS = [
    ("1", "📊", "Overview & Stats",    "bold green",   "#stats"),
    ("2", "🔑", "Key Manager",         "bold cyan",    "#keys"),
    ("3", "🔍", "Search Keys",         "bold cyan",    "#keys"),
    ("4", "✨", "Generate Keys",       "bold magenta", "#generate"),
    ("5", "🛑", "Blacklist",           "bold red",     "#blacklist"),
    ("6", "🧹", "Clear Screen",        "bold white",   None),
    ("0", "🚪", "Exit Terminal",       "bold bright_black", None),
]

def _open_web(hash_path: str):
    url = f"{BASE_URL}/dashboard{hash_path}"
    webbrowser.open(url)
    console.print(f"  [bold bright_black]→[/]  [bright_black]Opened[/] [bold cyan]{url}[/]")

def _print_banner():
    console.print(Text(BANNER, style="bold bright_magenta"), justify="center")
    console.print(Align.center(Text("KEY MANAGEMENT TERMINAL  ·  v3.0", style="bold white on grey23")))
    console.print()

def _print_menu():
    table = Table(box=box.ROUNDED, border_style="bright_black", show_header=False, padding=(0, 2))
    table.add_column("key", width=4, justify="center")
    table.add_column("icon", width=3)
    table.add_column("label", min_width=22)
    table.add_column("url", style="bright_black")
    for key, icon, label, color, path in MENU_ITEMS:
        url_text = f"{BASE_URL}/dashboard{path}" if path else ""
        table.add_row(
            Text(f"[{key}]", style="bold bright_white on grey23"),
            icon,
            Text(label, style=color),
            url_text,
        )
    console.print(Panel(
        Align.center(table),
        title="[bold bright_magenta]⚙  COMMAND MENU  —  Opens browser tab[/]",
        border_style="bright_magenta", padding=(1, 4),
    ))

def _ok(msg): console.print(f"  [bold green]✓[/]  {msg}")
def _err(msg): console.print(f"  [bold red]✗[/]  {msg}")
def _prompt(label): return console.input(f"  [bold bright_white]{label}[/] [bright_black]›[/] ").strip()


# ── Terminal password gate ──
BANNED_IPS = set()       # IPs ที่โดนแบนถาวร (ภายในเซสชัน)
INTRUDER_LOG = []        # log การพยายามเข้าจาก IP ภายนอก

def _terminal_login():
    """แสดงหน้า login บน terminal — ต้องใส่รหัสก่อนถึงจะเข้าเมนูได้."""
    import getpass
    os.system("cls" if os.name == "nt" else "clear")
    _print_banner()
    console.print()
    console.print(Panel(
        Align.center(Text("🔒  AUTHENTICATION REQUIRED\n\nกรุณาใส่รหัสผ่านเพื่อเข้าใช้งาน Terminal", style="bold bright_white"), vertical="middle"),
        title="[bold bright_magenta]🛡  SECURE LOGIN[/]",
        border_style="bright_magenta", padding=(1, 4), width=70,
    ))
    fails = 0
    while True:
        try:
            pwd = getpass.getpass("  🔑 Password › ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [bold red]✗[/]  ยกเลิก — ปิด terminal")
            return False
        import hmac as _h
        if _h.compare_digest(pwd, TERMINAL_PASSWORD):
            console.print("  [bold green]✓[/]  ยืนยันสำเร็จ — เข้าสู่ระบบ...\n")
            import time as _t; _t.sleep(0.6)
            return True
        fails += 1
        console.print(f"  [bold red]✗[/]  รหัสผ่านไม่ถูกต้อง  [bright_black](ครั้งที่ {fails})[/]")
        if fails >= 5:
            console.print("  [bold red]🚫 ใส่ผิดเกิน 5 ครั้ง — ล็อค terminal[/]")
            return False

async def terminal_loop():
    await asyncio.sleep(2)
    # ── เรียก login ก่อน ──
    ok = await asyncio.to_thread(_terminal_login)
    if not ok:
        return
    asyncio.sleep(10)
    os.system("cls" if os.name == "nt" else "clear")
    _print_banner()
    console.print()
    _print_menu()

    while True:
        try:
            cmd = await asyncio.to_thread(
                lambda: console.input("\n  [bold bright_magenta]VORTEX[/] [bright_black]›[/] ").strip()
            )

            if cmd == "1":
                _open_web("#stats")

            elif cmd == "2":
                _open_web("#keys")

            elif cmd == "3":
                _open_web("#keys")
                _ok("Dashboard opened — use the search box in Key Manager.")

            elif cmd == "4":
                _open_web("#generate")

            elif cmd == "5":
                _open_web("#blacklist")

            elif cmd == "6":
                os.system("cls" if os.name == "nt" else "clear")
                _print_banner()
                console.print()
                _print_menu()

            elif cmd == "0":
                console.print(Panel(Align.center(Text("Terminal session closed.", style="bold bright_black")), border_style="bright_black"))
                break

            else:
                _err(f"Unknown command '[bold]{cmd}[/]' — enter 0-6.")

        except (EOFError, KeyboardInterrupt):
            break
        except Exception as ex:
            _err(f"Terminal error: {ex}")

# ══════════════════════════════════════════════════════════════════
#  EMBED FACTORY & FORMATTERS
# ══════════════════════════════════════════════════════════════════
def make_embed(title, description="", color=COLOR_PRIMARY, *, footer="Vortex Security System", with_ts=True):
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text=footer)
    if with_ts: e.timestamp = datetime.now(timezone.utc)
    return e

def status_color(status, paused_at=None):
    if paused_at: return COLOR_WARN
    return COLOR_SUCCESS if status == "active" else COLOR_ERROR

def fmt_expiry(exp_date):
    if exp_date == "permanent": return "🔓 Permanent", ""
    try:
        exp  = datetime.fromisoformat(exp_date)
        days = (exp - datetime.now()).days
        s    = exp.strftime("%b %d, %Y")
        if days < 0:  return f"❌ Expired ({s})", ""
        if days == 0: return "⚠️ Expires today", ""
        return f"📅 {s}", f" · {days}d left"
    except: return "❓ Unknown", ""

def fmt_hwid(hwid):
    if not hwid: return "○ Unbound"
    return f"● `{hwid[:18]}…`" if len(hwid) > 18 else f"● `{hwid}`"

def fmt_status(status, paused_at=None):
    if paused_at: return "⏸️ Paused"
    return "✅ Active" if status == "active" else "🚫 Revoked"

def fmt_created(ts):
    if not ts: return "N/A"
    try:    return datetime.fromisoformat(ts).strftime("%b %d, %Y %H:%M")
    except: return ts

def _select_option(key_id, exp_date, hwid, status):
    exp_text, exp_suffix = fmt_expiry(exp_date)
    clean = exp_text.replace("📅 ","").replace("🔓 ","").replace("❌ ","").replace("⚠️ ","")
    return discord.SelectOption(
        label=key_id, value=key_id,
        description=f"{'✅' if status=='active' else '🚫'} {clean}{exp_suffix} · {'Bound' if hwid else 'Free'}"[:100],
    )

def _key_detail_embed(row):
    key_id, hwid, duration, exp_date, status, created_by, created_at, rekeyed_from, paused_at = row
    exp_text, exp_suffix = fmt_expiry(exp_date)
    e = make_embed("🔑  Key Details", f"`{key_id}`\n{DIV}", status_color(status, paused_at))
    e.add_field(name="Status",     value=fmt_status(status, paused_at),   inline=True)
    e.add_field(name="Duration",   value=duration or "N/A",               inline=True)
    e.add_field(name="Expires",    value=f"{exp_text}{exp_suffix}",       inline=True)
    e.add_field(name="HWID",       value=fmt_hwid(hwid),                  inline=True)
    e.add_field(name="Created By", value=f"`{created_by or 'N/A'}`",     inline=True)
    e.add_field(name="Created At", value=fmt_created(created_at),         inline=True)
    if paused_at:    e.add_field(name="Paused At",    value=fmt_created(paused_at), inline=False)
    if rekeyed_from: e.add_field(name="Rekeyed From", value=f"`{rekeyed_from}`",   inline=False)
    return e

# ══════════════════════════════════════════════════════════════════
#  SHARED SEARCH MODAL
# ══════════════════════════════════════════════════════════════════
class SearchFilterModal(Modal):
    def __init__(self, view_factory, fallback_rows, modal_title="🔍 Search Keys"):
        super().__init__(title=modal_title, timeout=120)
        self.view_factory  = view_factory
        self.fallback_rows = fallback_rows
        self.search_input  = TextInput(label="Key ID (partial · blank = all)", placeholder="e.g. VORTEX-1234", required=False, max_length=60)
        self.add_item(self.search_input)

    async def on_submit(self, interaction):
        term = self.search_input.value.strip()
        rows, _ = await search_keys(term=term, limit=25)
        if not rows:
            embed, view = self.view_factory(self.fallback_rows, "")
            await interaction.response.edit_message(embed=make_embed("🔍  No Results", f"No keys matched `{term}`.\n{DIV}\nShowing previous results.", COLOR_MUTED), view=view)
            return
        embed, view = self.view_factory(rows, term)
        await interaction.response.edit_message(embed=embed, view=view)

# ══════════════════════════════════════════════════════════════════
#  KEY INFO UI
# ══════════════════════════════════════════════════════════════════
class KeyInfoSelect(Select):
    def __init__(self, rows):
        super().__init__(placeholder="Select a key to view its details…", min_values=1, max_values=1, options=[_select_option(*r) for r in rows], row=0)

    async def callback(self, interaction):
        key_id = self.values[0]
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute(
                "SELECT key_id, hwid, duration, expiration_date, status, created_by, created_at, rekeyed_from, paused_at FROM keys WHERE key_id = ?", (key_id,)
            ) as cur: row = await cur.fetchone()
        if not row:
            return await interaction.response.send_message(embed=make_embed("❌ Not Found", f"Key `{key_id}` no longer exists.", COLOR_ERROR), ephemeral=True)
        await interaction.response.edit_message(embed=_key_detail_embed(row), view=self.view)

class KeyInfoView(View):
    def __init__(self, rows, term=""):
        super().__init__(timeout=180)
        self.rows = rows; self.term = term
        self.add_item(KeyInfoSelect(rows))
        s = Button(label="🔍 Search", style=discord.ButtonStyle.blurple, row=1)
        c = Button(label="✕ Close",   style=discord.ButtonStyle.secondary, row=1)
        s.callback = self._search_cb
        c.callback = self._close_cb
        self.add_item(s); self.add_item(c)

    async def _search_cb(self, i): await i.response.send_modal(SearchFilterModal(make_info_ui, self.rows, "🔍 Search Keys — Info"))
    async def _close_cb(self, i):
        self.stop()
        await i.response.edit_message(embed=make_embed("✕  Closed", "Key info panel closed.", COLOR_MUTED), view=None)

# ══════════════════════════════════════════════════════════════════
#  DELETE KEYS UI
# ══════════════════════════════════════════════════════════════════
class DeleteKeySelect(Select):
    def __init__(self, rows):
        super().__init__(placeholder="Select keys to delete…", min_values=1, max_values=len(rows), options=[_select_option(*r) for r in rows], row=0)

    async def callback(self, interaction):
        count = len(self.values)
        key_list = "\n".join(f"> `{k}`" for k in self.values)
        e = make_embed(f"⚠️  Confirm — {count} Key{'s' if count > 1 else ''} Selected",
                       f"Marked for permanent deletion:\n{DIV}\n{key_list}\n{DIV}\nThis **cannot be undone**.", COLOR_WARN)
        self.view.pending_keys = self.values
        self.view.confirm_btn.disabled = False
        await interaction.response.edit_message(embed=e, view=self.view)

class DeleteKeyView(View):
    def __init__(self, rows, term=""):
        super().__init__(timeout=180)
        self.rows = rows; self.term = term; self.pending_keys = []
        self.add_item(DeleteKeySelect(rows))
        s = Button(label="🔍 Search", style=discord.ButtonStyle.blurple, row=1)
        self.confirm_btn = Button(label="🗑️ Confirm Delete", style=discord.ButtonStyle.danger, row=1, disabled=True)
        c = Button(label="✕ Cancel", style=discord.ButtonStyle.secondary, row=1)
        s.callback = self._search_cb; self.confirm_btn.callback = self._confirm_cb; c.callback = self._cancel_cb
        self.add_item(s); self.add_item(self.confirm_btn); self.add_item(c)

    async def _search_cb(self, i): await i.response.send_modal(SearchFilterModal(make_delete_ui, self.rows, "🗑️ Search Keys — Delete"))
    async def _confirm_cb(self, interaction):
        if not self.pending_keys: return await interaction.response.send_message("No keys selected.", ephemeral=True)
        async with aiosqlite.connect(DB_FILE) as db:
            await db.executemany("DELETE FROM keys WHERE key_id = ?", [(k,) for k in self.pending_keys])
            await db.commit()
        count = len(self.pending_keys)
        e = make_embed(f"🗑️  {count} Key{'s' if count > 1 else ''} Deleted",
                       "\n".join(f"> ~~`{k}`~~" for k in self.pending_keys) + f"\n{DIV}\nRemoved permanently.", COLOR_SUCCESS)
        e.add_field(name="Deleted by", value=f"`{interaction.user}`", inline=True)
        self.stop(); await interaction.response.edit_message(embed=e, view=None)
    async def _cancel_cb(self, i):
        self.stop(); await i.response.edit_message(embed=make_embed("✕  Cancelled", "No keys were deleted.", COLOR_MUTED), view=None)

# ══════════════════════════════════════════════════════════════════
#  UI FACTORIES
# ══════════════════════════════════════════════════════════════════
def make_info_ui(rows, term=""):
    header = f"Query: `{term}`  ·  **{len(rows)}** result{'s' if len(rows) > 1 else ''}" if term else f"Showing **{len(rows)}** most recent keys"
    return make_embed("🔍  Key Info", f"{header}\n{DIV}\nSelect a key to view its details.", COLOR_INFO), KeyInfoView(rows, term)

def make_delete_ui(rows, term=""):
    header = f"Query: `{term}`  ·  **{len(rows)}** result{'s' if len(rows) > 1 else ''}" if term else f"Showing **{len(rows)}** most recent keys"
    return make_embed("🗑️  Delete Keys", f"{header}\n{DIV}\nSelect keys, then press **Confirm Delete**.", COLOR_ERROR), DeleteKeyView(rows, term)

# ══════════════════════════════════════════════════════════════════
#  MODALS
# ══════════════════════════════════════════════════════════════════
class KeyAmountModal(Modal):
    def __init__(self, duration):
        super().__init__(title="Generate Keys", timeout=300)
        self.duration = duration
        self.amount_input = TextInput(label="Amount (max 50)", default="1", required=True)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction):
        try:
            amount = int(self.amount_input.value.strip())
            if not 1 <= amount <= 50: raise ValueError
        except ValueError:
            return await interaction.response.send_message(embed=make_embed("❌ Invalid Amount","Enter 1–50.",COLOR_ERROR),ephemeral=True)
        days = EXPIRATION_PRESETS[self.duration]
        exp  = "permanent" if days is None else (datetime.now() + timedelta(days=days)).isoformat()
        created_at = datetime.now().isoformat(); creator = str(interaction.user)
        keys, records = [], []
        for _ in range(amount):
            k = f"VORTEX-{str(uuid.uuid4())[:8].upper()}"
            keys.append(k); records.append((k, self.duration, exp, "active", creator, created_at))
        async with aiosqlite.connect(DB_FILE) as db:
            await db.executemany("INSERT INTO keys (key_id,duration,expiration_date,status,created_by,created_at) VALUES(?,?,?,?,?,?)", records)
            await db.commit()
        exp_text, exp_suffix = fmt_expiry(exp)
        dur_map = {"1d":"1 Day","3d":"3 Days","7d":"7 Days","1m":"1 Month","1y":"1 Year","permanent":"Permanent"}
        if amount <= 5:
            e = make_embed(f"🔑  {amount} Key{'s' if amount>1 else ''} Generated", f"{DIV}\n"+"\n".join(f"`{k}`" for k in keys), COLOR_SUCCESS)
        else:
            file_bytes = io.BytesIO("\n".join(keys).encode()); file = discord.File(file_bytes, filename=f"VORTEX_{amount}_{self.duration}.txt")
            e = make_embed(f"🔑  {amount} Keys Generated", f"Exported to file.\n{DIV}", COLOR_SUCCESS)
        e.add_field(name="Duration", value=dur_map.get(self.duration,self.duration), inline=True)
        e.add_field(name="Expires",  value=f"{exp_text}{exp_suffix}", inline=True)
        e.add_field(name="By",       value=f"`{creator}`", inline=True)
        if amount <= 5: await interaction.response.send_message(embed=e, ephemeral=True)
        else:           await interaction.response.send_message(embed=e, file=file, ephemeral=True)

class ResetModal(Modal, title="🔄 Reset HWID"):
    key_input = TextInput(label="Key ID", placeholder="VORTEX-1234ABCD", required=True)
    async def on_submit(self, interaction):
        key = self.key_input.value.strip()
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT status FROM keys WHERE key_id=?",(key,)) as cur: row=await cur.fetchone()
            if not row: return await interaction.response.send_message(embed=make_embed("❌ Not Found",f"No key `{key}`.",COLOR_ERROR),ephemeral=True)
            if row[0]=="revoked": return await interaction.response.send_message(embed=make_embed("❌ Already Revoked","Key is revoked.",COLOR_ERROR),ephemeral=True)
            new_key=f"VORTEX-{str(uuid.uuid4())[:8].upper()}"; exp=(datetime.now()+timedelta(days=7)).isoformat()
            await db.execute("UPDATE keys SET status='revoked' WHERE key_id=?",(key,))
            await db.execute("INSERT INTO keys (key_id,duration,expiration_date,status,created_by,created_at,rekeyed_from) VALUES(?,?,?,?,?,?,?)",
                             (new_key,"7d",exp,"active",str(interaction.user),datetime.now().isoformat(),key))
            await db.commit()
        exp_text,exp_suffix=fmt_expiry(exp)
        e=make_embed("🔄  HWID Reset Complete",DIV,COLOR_SUCCESS)
        e.add_field(name="Old Key",value=f"~~`{key}`~~",inline=False)
        e.add_field(name="New Key",value=f"`{new_key}`",inline=True)
        e.add_field(name="Expires",value=f"{exp_text}{exp_suffix}",inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

class PauseResumeModal(Modal, title="⏸️ Pause / Resume Key"):
    key_input = TextInput(label="Key ID", placeholder="VORTEX-1234ABCD", required=True)
    async def on_submit(self, interaction):
        key=self.key_input.value.strip()
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT expiration_date,paused_at FROM keys WHERE key_id=?",(key,)) as cur: row=await cur.fetchone()
            if not row: return await interaction.response.send_message(embed=make_embed("❌ Not Found","Key not found.",COLOR_ERROR),ephemeral=True)
            exp_date,paused_at=row; now=datetime.now()
            if paused_at is None:
                if exp_date=="permanent": return await interaction.response.send_message(embed=make_embed("⚠️ Cannot Pause","Permanent keys cannot be paused.",COLOR_WARN),ephemeral=True)
                await db.execute("UPDATE keys SET paused_at=? WHERE key_id=?",(now.isoformat(),key))
                await db.commit()
                e=make_embed("⏸️ Key Paused",f"Key `{key}` frozen.",COLOR_INFO)
            else:
                elapsed=now-datetime.fromisoformat(paused_at)
                new_exp=(datetime.fromisoformat(exp_date)+elapsed).isoformat()
                await db.execute("UPDATE keys SET paused_at=NULL,expiration_date=? WHERE key_id=?",(new_exp,key))
                await db.commit()
                e=make_embed("▶️ Key Resumed",f"Key `{key}` resumed. +{elapsed.days}d added back.",COLOR_SUCCESS)
        await interaction.response.send_message(embed=e, ephemeral=True)

class BlacklistModal(Modal, title="🛑 Blacklist HWID"):
    hwid_input   = TextInput(label="Target HWID", placeholder="Paste HWID here", required=True)
    reason_input = TextInput(label="Reason", placeholder="e.g. Cheating, Chargeback", required=False)
    async def on_submit(self, interaction):
        hwid=self.hwid_input.value.strip(); reason=self.reason_input.value.strip() or "No reason provided"
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("INSERT OR REPLACE INTO blacklist (hwid,reason,banned_at,banned_by) VALUES(?,?,?,?)",(hwid,reason,datetime.now().isoformat(),str(interaction.user)))
            await db.execute("UPDATE keys SET status='revoked' WHERE hwid=?",(hwid,))
            await db.commit()
        e=make_embed("🛑 HWID Blacklisted",f"Device `{hwid}` banned.\nAll associated keys revoked.",COLOR_ERROR)
        e.add_field(name="Reason",value=reason,inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ══════════════════════════════════════════════════════════════════
class DurationSelect(Select):
    def __init__(self):
        options=[
            discord.SelectOption(label="1 Day",value="1d",emoji="⏱️"),
            discord.SelectOption(label="3 Days",value="3d",emoji="📅"),
            discord.SelectOption(label="7 Days",value="7d",emoji="📅",default=True),
            discord.SelectOption(label="1 Month",value="1m",emoji="📆"),
            discord.SelectOption(label="1 Year",value="1y",emoji="📅"),
            discord.SelectOption(label="Permanent",value="permanent",emoji="🔓"),
        ]
        super().__init__(placeholder="Select key duration…",min_values=1,max_values=1,options=options)
    async def callback(self,interaction): await interaction.response.send_modal(KeyAmountModal(self.values[0]))

class DurationSelectView(View):
    def __init__(self): super().__init__(timeout=180); self.add_item(DurationSelect())

class AdminPanel(View):
    def __init__(self): super().__init__(timeout=None)
    async def _check(self, i):
        if ADMIN_ROLE_ID not in [r.id for r in i.user.roles]:
            await i.response.send_message(embed=make_embed("🔒  Access Denied","You don't have the required role.",COLOR_ERROR),ephemeral=True); return False
        return True

    @discord.ui.button(label="🔑 Gen",          style=discord.ButtonStyle.success,   custom_id="btn_gen",       row=1)
    async def btn_gen(self,i,b):
        if await self._check(i): await i.response.send_message(embed=make_embed("🔑  Generate Keys","Select duration.",COLOR_PRIMARY),view=DurationSelectView(),ephemeral=True)

    @discord.ui.button(label="🔄 Reset HWID",   style=discord.ButtonStyle.secondary, custom_id="btn_reset",     row=1)
    async def btn_reset(self,i,b):
        if await self._check(i): await i.response.send_modal(ResetModal())

    @discord.ui.button(label="📋 List Active",  style=discord.ButtonStyle.blurple,   custom_id="btn_list",      row=1)
    async def btn_list(self,i,b):
        if not await self._check(i): return
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT key_id,expiration_date,hwid,status FROM keys WHERE status='active' ORDER BY created_at DESC LIMIT 10") as cur: keys=await cur.fetchall()
        stats=await fetch_stats()
        if not keys: return await i.response.send_message(embed=make_embed("📋  Key List","No active keys.",COLOR_MUTED),ephemeral=True)
        e=make_embed("📋  Active Keys  —  Latest 10",f"Total: **{stats['total']}** | Active: **{stats['active']}** | Banned: **{stats['blacklisted']}**\n{DIV}",COLOR_PRIMARY)
        for key_id,exp_date,hwid,status in keys:
            exp_text,exp_suffix=fmt_expiry(exp_date)
            e.add_field(name=f"`{key_id}`",value=f"{exp_text}{exp_suffix}\n{fmt_hwid(hwid)}",inline=True)
        await i.response.send_message(embed=e,ephemeral=True)

    @discord.ui.button(label="🔍 Info",         style=discord.ButtonStyle.blurple,   custom_id="btn_info",      row=2)
    async def btn_info(self,i,b):
        if not await self._check(i): return
        rows, _ = await search_keys(limit=25)
        if not rows: return await i.response.send_message(embed=make_embed("🔍  No Keys","No keys in DB.",COLOR_MUTED),ephemeral=True)
        embed,view=make_info_ui(rows)
        await i.response.send_message(embed=embed,view=view,ephemeral=True)

    @discord.ui.button(label="🗑️ Delete",       style=discord.ButtonStyle.danger,    custom_id="btn_delete",    row=2)
    async def btn_delete(self,i,b):
        if not await self._check(i): return
        rows, _ = await search_keys(limit=25)
        if not rows: return await i.response.send_message(embed=make_embed("🗑️  No Keys","No keys in DB.",COLOR_MUTED),ephemeral=True)
        embed,view=make_delete_ui(rows)
        await i.response.send_message(embed=embed,view=view,ephemeral=True)

    @discord.ui.button(label="⏸️ Pause/Resume", style=discord.ButtonStyle.secondary, custom_id="btn_pause",     row=2)
    async def btn_pause(self,i,b):
        if await self._check(i): await i.response.send_modal(PauseResumeModal())

    @discord.ui.button(label="🛑 Blacklist",    style=discord.ButtonStyle.danger,    custom_id="btn_blacklist", row=3)
    async def btn_blacklist(self,i,b):
        if await self._check(i): await i.response.send_modal(BlacklistModal())

# ══════════════════════════════════════════════════════════════════
#  WEB API + DASHBOARD
# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
#  🔒 SECURITY LAYER
# ══════════════════════════════════════════════════════════════════
RATE_BUCKET     = _defaultdict(lambda: _deque(maxlen=60))  # IP -> request timestamps
RATE_LIMIT_N    = 30                                    # max 30 req
RATE_LIMIT_WIN  = 60                                    # per 60s on /verify

# Public endpoints reachable from outside (clients calling /verify must not be blocked)
PUBLIC_PATHS = {"/verify", "/health", "/favicon.ico"}
# State-changing methods that require CSRF + auth
WRITE_METHODS = {"POST", "DELETE", "PUT", "PATCH"}

def _detect_local_ips():
    """All IPs that belong to the host machine itself."""
    ips = {"127.0.0.1", "171.5.245.80", "localhost"}
    try:
        hostname = _socket.gethostname()
        ips.add(hostname)
        for info in _socket.getaddrinfo(hostname, None):
            ips.add(info[4][0])
        # All bound interface addrs
        for fam in (_socket.AF_INET, _socket.AF_INET6):
            try:
                for info in _socket.getaddrinfo(_socket.gethostname(), None, fam):
                    ips.add(info[4][0])
            except Exception:
                pass
    except Exception as ex:
        logger.warning(f"local IP detect: {ex}")
    return ips

ALLOWED_IPS = _detect_local_ips()
ALLOWED_IPS.add(HOST_IP)
logger.info(f"🌐 Host IP detected: {HOST_IP}  (source: {_HOST_SRC})")
logger.info(f"🔒 Allowed admin IPs (this machine only): {sorted(ALLOWED_IPS)}")

def _client_ip(request):
    # Trust only direct peer; ignore X-Forwarded-For (no trusted proxy)
    peer = request.transport.get_extra_info("peername") if request.transport else None
    return peer[0] if peer else ""

def _ip_is_local(ip):
    if ip in ALLOWED_IPS:
        return True
    try:
        addr = _ipaddress.ip_address(ip)
        # อนุญาต loopback (127.x), private LAN (192.168.x, 10.x, 172.16-31.x),
        # และ link-local — เหมาะกับการรัน self-host บนเครื่องตัวเอง / ใน LAN
        return addr.is_loopback or addr.is_private or addr.is_link_local
    except Exception:
        return False

def _security_headers():
    return {
        "Content-Security-Policy":
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data:; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-XSS-Protection": "0",
    }

def cors_headers():
    # Locked down: no wildcard origin, same-origin only.
    return {
        "Vary": "Origin",
        "Access-Control-Allow-Methods": "POST,GET,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-CSRF-Token",
        "Access-Control-Allow-Credentials": "true",
    }

async def handle_options(request):
    return web.Response(headers={**cors_headers(), **_security_headers()})

def _check_rate(ip):
    now = _time.monotonic()
    bucket = RATE_BUCKET[ip]
    while bucket and now - bucket[0] > RATE_LIMIT_WIN:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_N:
        return False
    bucket.append(now)
    return True


def _check_csrf(request):
    """Same-origin enforcement for state-changing requests."""
    origin  = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")
    host    = request.headers.get("Host", "")
    if not host:
        return False
    expected = {f"http://{host}", f"https://{host}"}
    if origin and origin in expected: return True
    if referer and any(referer.startswith(e + "/") or referer == e for e in expected): return True
    # No Origin/Referer at all → reject for writes
    return False

@web.middleware
async def security_middleware(request, handler):
    ip   = _client_ip(request)
    path = request.path

    # Always attach security headers, even on error
    async def _respond(resp):
        for k, v in _security_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    # ── 1. Public endpoints: only rate-limit ──
    if path in PUBLIC_PATHS or path.startswith("/verify"):
        if not _check_rate(ip):
            return await _respond(web.json_response(
                {"status": "fail", "message": "Rate limit exceeded"}, status=429))
        return await _respond(await handler(request))

    # ── 2. Admin endpoints: IP allowlist ──
    if ip in BANNED_IPS or not _ip_is_local(ip):
        BANNED_IPS.add(ip)
        ua = request.headers.get("User-Agent", "?")
        entry = {"ip": ip, "path": path, "method": request.method, "ua": ua, "ts": _time.time()}
        INTRUDER_LOG.append(entry)
        logger.warning("=" * 70)
        logger.warning(f"🚨🚨🚨 INTRUDER DETECTED 🚨🚨🚨")
        logger.warning(f"   IP        : {ip}")
        logger.warning(f"   Path      : {request.method} {path}")
        logger.warning(f"   User-Agent: {ua}")
        logger.warning(f"   Action    : PERMANENTLY BANNED (this session)")
        logger.warning("=" * 70)
        try:
            console.print(Panel(
                Text(f"🚨 INTRUDER BANNED\nIP: {ip}\n{request.method} {path}\nUA: {ua[:60]}",
                     style="bold bright_white on red"),
                border_style="red", title="[bold red blink]⚠  SECURITY ALERT[/]"))
        except Exception: pass
        return await _respond(web.json_response(
            {"status": "fail", "message": "Forbidden — your IP has been banned and logged."}, status=403))

    # ── 4. CSRF on writes ──
    if request.method in WRITE_METHODS and not _check_csrf(request):
        logger.warning(f"🚨 CSRF check failed: {request.method} {path} from {ip}")
        return await _respond(web.json_response(
            {"status": "fail", "message": "CSRF check failed"}, status=403))

    return await _respond(await handler(request))


# Dashboard HTML
async def serve_dashboard(request):
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")

# GET /stats
async def get_stats(request):
    s = await fetch_stats()
    return web.json_response({"status":"ok","total_keys":s["total"],"active_keys":s["active"],
                               "revoked_keys":s["revoked"],"bound_keys":s["bound"],"paused":s["paused"],"blacklisted":s["blacklisted"]}, headers=cors_headers())

# GET /api/keys
async def api_get_keys(request):
    q      = request.rel_url.query.get("search","").strip()
    status = request.rel_url.query.get("status","").strip()
    limit  = min(int(request.rel_url.query.get("limit", 50)), 200)
    offset = int(request.rel_url.query.get("offset", 0))
    rows, total = await search_keys(
        term=q, limit=limit, offset=offset, status=status,
        columns="key_id, expiration_date, hwid, status, duration, created_by, created_at, paused_at",
    )
    keys = [{"key_id":r[0],"expiration_date":r[1],"hwid":r[2],"status":r[3],"duration":r[4],"created_by":r[5],"created_at":r[6],"paused_at":r[7]} for r in rows]
    return web.json_response({"status":"ok","keys":keys,"total":total}, headers=cors_headers())

# DELETE /api/keys/{key_id}
async def api_delete_key(request):
    key_id = request.match_info["key_id"]
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT key_id FROM keys WHERE key_id=?",(key_id,)) as cur:
            if not await cur.fetchone():
                return web.json_response({"status":"fail","message":"Key not found"},status=404,headers=cors_headers())
        await db.execute("DELETE FROM keys WHERE key_id=?",(key_id,))
        await db.commit()
    return web.json_response({"status":"success","message":f"Key {key_id} deleted"},headers=cors_headers())

# POST /api/keys/{key_id}/revoke
async def api_revoke_key(request):
    key_id = request.match_info["key_id"]
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT status FROM keys WHERE key_id=?",(key_id,)) as cur:
            row=await cur.fetchone()
            if not row: return web.json_response({"status":"fail","message":"Key not found"},status=404,headers=cors_headers())
        await db.execute("UPDATE keys SET status='revoked' WHERE key_id=?",(key_id,))
        await db.commit()
    return web.json_response({"status":"success","message":f"Key {key_id} revoked"},headers=cors_headers())

# POST /api/keys/{key_id}/pause
async def api_pause_key(request):
    key_id = request.match_info["key_id"]
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT expiration_date,paused_at FROM keys WHERE key_id=?",(key_id,)) as cur:
            row=await cur.fetchone()
            if not row: return web.json_response({"status":"fail","message":"Key not found"},status=404,headers=cors_headers())
        exp_date,paused_at=row; now=datetime.now()
        if paused_at is None:
            await db.execute("UPDATE keys SET paused_at=? WHERE key_id=?",(now.isoformat(),key_id))
            msg="Key paused"
        else:
            elapsed=now-datetime.fromisoformat(paused_at)
            new_exp=(datetime.fromisoformat(exp_date)+elapsed).isoformat()
            await db.execute("UPDATE keys SET paused_at=NULL,expiration_date=? WHERE key_id=?",(new_exp,key_id))
            msg="Key resumed"
        await db.commit()
    return web.json_response({"status":"success","message":msg},headers=cors_headers())

# POST /api/keys/generate
async def api_generate_keys(request):
    try:
        data     = await request.json()
        duration = data.get("duration","7d")
        amount   = int(data.get("amount",1))
        if duration not in EXPIRATION_PRESETS: return web.json_response({"status":"fail","message":"Invalid duration"},status=400,headers=cors_headers())
        if not 1 <= amount <= 50:              return web.json_response({"status":"fail","message":"Amount must be 1-50"},status=400,headers=cors_headers())
        days = EXPIRATION_PRESETS[duration]
        exp  = "permanent" if days is None else (datetime.now()+timedelta(days=days)).isoformat()
        created_at = datetime.now().isoformat()
        keys, records = [], []
        for _ in range(amount):
            k = f"VORTEX-{str(uuid.uuid4())[:8].upper()}"
            keys.append(k); records.append((k,duration,exp,"active","Web Dashboard",created_at))
        async with aiosqlite.connect(DB_FILE) as db:
            await db.executemany("INSERT INTO keys (key_id,duration,expiration_date,status,created_by,created_at) VALUES(?,?,?,?,?,?)",records)
            await db.commit()
        return web.json_response({"status":"success","keys":keys,"expiration_date":exp,"duration":duration},headers=cors_headers())
    except Exception as ex:
        return web.json_response({"status":"error","message":str(ex)},status=500,headers=cors_headers())

# GET /api/blacklist
async def api_get_blacklist(request):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT hwid,reason,banned_at,banned_by FROM blacklist ORDER BY banned_at DESC") as cur:
            rows=await cur.fetchall()
    entries=[{"hwid":r[0],"reason":r[1],"banned_at":r[2],"banned_by":r[3]} for r in rows]
    return web.json_response({"status":"ok","entries":entries},headers=cors_headers())

# POST /api/blacklist
async def api_ban_hwid(request):
    data   = await request.json()
    hwid   = data.get("hwid","").strip()
    reason = data.get("reason","No reason provided")
    if not hwid: return web.json_response({"status":"fail","message":"HWID required"},status=400,headers=cors_headers())
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR REPLACE INTO blacklist (hwid,reason,banned_at,banned_by) VALUES(?,?,?,?)",(hwid,reason,datetime.now().isoformat(),"Web Dashboard"))
        await db.execute("UPDATE keys SET status='revoked' WHERE hwid=?",(hwid,))
        await db.commit()
    return web.json_response({"status":"success","message":f"HWID {hwid} banned"},headers=cors_headers())

# DELETE /api/blacklist/{hwid}
async def api_unban_hwid(request):
    hwid = request.match_info["hwid"]
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM blacklist WHERE hwid=?",(hwid,))
        await db.commit()
    return web.json_response({"status":"success","message":f"HWID {hwid} unbanned"},headers=cors_headers())

# POST /verify
async def verify_key(request):
    try:
        data=await request.json(); user_key=data.get("key","").strip(); user_hwid=data.get("hwid","").strip()
        if not user_key or not user_hwid: return web.json_response({"status":"fail","message":"ต้องระบุ key และ hwid"},status=400,headers=cors_headers())
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT reason FROM blacklist WHERE hwid=?",(user_hwid,)) as cur:
                banned=await cur.fetchone()
            if banned: return web.json_response({"status":"fail","message":f"เครื่องนี้ถูกแบน! ({banned[0]})"},status=403,headers=cors_headers())
            async with db.execute("SELECT hwid,expiration_date,status,paused_at FROM keys WHERE key_id=?",(user_key,)) as cur:
                row=await cur.fetchone()
            if not row: return web.json_response({"status":"fail","message":"ไม่พบคีย์นี้ในระบบ!"},status=404,headers=cors_headers())
            stored_hwid,exp_date,status,paused_at=row
            if status=="revoked": return web.json_response({"status":"fail","message":"คีย์นี้ถูก revoke แล้ว!"},status=403,headers=cors_headers())
            if paused_at: return web.json_response({"status":"fail","message":"คีย์นี้ถูกระงับชั่วคราว!"},status=403,headers=cors_headers())
            days_remaining=None
            if exp_date!="permanent":
                exp=datetime.fromisoformat(exp_date)
                if exp<datetime.now(): return web.json_response({"status":"fail","message":"คีย์หมดอายุแล้ว!"},status=403,headers=cors_headers())
                days_remaining=max(0,(exp-datetime.now()).days)
            if stored_hwid is None:
                await db.execute("UPDATE keys SET hwid=? WHERE key_id=?",(user_hwid,user_key)); await db.commit()
                return web.json_response({"status":"success","message":"ลงทะเบียนเครื่องสำเร็จ!","expiration_date":exp_date,"days_remaining":days_remaining,"hwid_bound":True},headers=cors_headers())
            elif stored_hwid==user_hwid:
                return web.json_response({"status":"success","message":"ยินดีต้อนรับกลับ!","expiration_date":exp_date,"days_remaining":days_remaining,"hwid_bound":True},headers=cors_headers())
            else:
                return web.json_response({"status":"fail","message":"คีย์ถูกใช้กับเครื่องอื่น!"},status=403,headers=cors_headers())
    except Exception as ex:
        logger.error(f"/verify: {ex}")
        return web.json_response({"status":"error","message":"เกิดข้อผิดพลาด"},status=500,headers=cors_headers())

async def health_check(request):
    return web.json_response({"status":"ok","message":"VORTEX API is running"},headers=cors_headers())

# ══════════════════════════════════════════════════════════════════
#  DISCORD EMBEDS FOR PANEL
# ══════════════════════════════════════════════════════════════════
def _select_option(key_id, exp_date, hwid, status):
    exp_text,exp_suffix=fmt_expiry(exp_date)
    clean=exp_text.replace("📅 ","").replace("🔓 ","").replace("❌ ","").replace("⚠️ ","")
    return discord.SelectOption(label=key_id,value=key_id,
                                description=f"{'✅' if status=='active' else '🚫'} {clean}{exp_suffix} · {'Bound' if hwid else 'Free'}"[:100])

# ══════════════════════════════════════════════════════════════════
#  BOT
# ══════════════════════════════════════════════════════════════════
class VortexBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=discord.Intents.all())
        self.web_runner = None

    async def setup_hook(self):
        await init_db()
        app = web.Application(middlewares=[security_middleware])

        app.add_routes([
        ])

        # CORS preflight
        for path in ("/verify","/health","/stats","/dashboard",
                     "/api/keys","/api/keys/{key_id}","/api/keys/{key_id}/revoke",
                     "/api/keys/{key_id}/pause","/api/keys/generate",
                     "/api/blacklist","/api/blacklist/{hwid}"):
            try: app.router.add_options(path, handle_options)
            except: pass

        app.add_routes([
            web.get("/dashboard",              serve_dashboard),
            web.get("/stats",                  get_stats),
            web.get("/health",                 health_check),
            web.post("/verify",                verify_key),
            web.get("/api/keys",               api_get_keys),
            web.delete("/api/keys/{key_id}",   api_delete_key),
            web.post("/api/keys/{key_id}/revoke", api_revoke_key),
            web.post("/api/keys/{key_id}/pause",  api_pause_key),
            web.post("/api/keys/generate",     api_generate_keys),
            web.get("/api/blacklist",          api_get_blacklist),
            web.post("/api/blacklist",         api_ban_hwid),
            web.delete("/api/blacklist/{hwid}",api_unban_hwid),
        ])

        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        await web.TCPSite(self.web_runner, "0.0.0.0", API_PORT).start()
        logger.info(f"🌐 API + Dashboard → {BASE_URL}/dashboard  (port from {_PORT_SRC})")
        self.loop.create_task(terminal_loop())
        await self.tree.sync()

    async def close(self):
        if self.web_runner: await self.web_runner.cleanup()
        await super().close()

bot = VortexBot()

@bot.event
async def on_ready():
    bot.add_view(AdminPanel())
    logger.info(f"✅ {bot.user} online")

@bot.tree.command(name="panel", description="Open the Vortex admin panel")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
        return await interaction.response.send_message(embed=make_embed("🔒  Access Denied","You don't have the required role.",COLOR_ERROR),ephemeral=True)
    stats=await fetch_stats()
    bound_pct=round(stats["bound"]/stats["total"]*100) if stats["total"] else 0
    active_pct=round(stats["active"]/stats["total"]*100) if stats["total"] else 0
    e=make_embed("⚙️  Vortex Admin Panel",f"Key management and access control.\n{DIV}",COLOR_PRIMARY)
    if interaction.guild.icon: e.set_thumbnail(url=interaction.guild.icon.url)
    e.add_field(name="🔑 Total",       value=f"**{stats['total']}**",                          inline=True)
    e.add_field(name="✅ Active",       value=f"**{stats['active']}** ({active_pct}%)",         inline=True)
    e.add_field(name="⏸️ Paused",       value=f"**{stats['paused']}**",                         inline=True)
    e.add_field(name="💻 HWID Bound",   value=f"**{stats['bound']}** ({bound_pct}% of total)",  inline=True)
    e.add_field(name="🛑 Blacklisted",  value=f"**{stats['blacklisted']}**",                    inline=True)
    e.add_field(name="🚫 Revoked",      value=f"**{stats['revoked']}**",                        inline=True)
    await interaction.response.send_message(embed=e, view=AdminPanel())

@bot.tree.command(name="giveaway", description="สร้างคีย์แจกฟรีในช่องปัจจุบัน")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(duration="ระยะเวลา: 1d, 3d, 7d, 1m, 1y, permanent")
async def giveaway(interaction: discord.Interaction, duration: str = "1d"):
    if duration not in EXPIRATION_PRESETS:
        return await interaction.response.send_message("❌ ระยะเวลาไม่ถูกต้อง", ephemeral=True)
    days=EXPIRATION_PRESETS[duration]
    exp="permanent" if days is None else (datetime.now()+timedelta(days=days)).isoformat()
    key_id=f"VORTEX-GW-{str(uuid.uuid4())[:6].upper()}"
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO keys (key_id,duration,expiration_date,status,created_by,created_at) VALUES(?,?,?,?,?,?)",
                         (key_id,duration,exp,"active",str(interaction.user),datetime.now().isoformat()))
        await db.commit()
    e=make_embed("🎁 VORTEX KEY GIVEAWAY",f"รีบนำไปลงทะเบียน — ใครเร็วกว่าได้ไป!\n\n🔑 **`{key_id}`**\n\n⏱️ Duration: **{duration}**",discord.Color.gold())
    if interaction.guild.icon: e.set_thumbnail(url=interaction.guild.icon.url)
    await interaction.response.send_message(embed=e)

if __name__ == "__main__":
    if not TOKEN:
        logger.error("❌ ไม่พบ DISCORD_TOKEN")
    else:
        bot.run(TOKEN, log_handler=None)
