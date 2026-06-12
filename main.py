import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
from aiohttp import web
import aiosqlite
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import io

load_dotenv()

TOKEN         = os.getenv("DISCORD_TOKEN")
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))
API_PORT      = int(os.getenv("API_PORT"))
DB_FILE       = "vortex_keys.db"

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

# ══════════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════════
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                key_id          TEXT PRIMARY KEY,
                hwid            TEXT,
                duration        TEXT,
                expiration_date TEXT,
                status          TEXT,
                created_by      TEXT,
                created_at      TEXT,
                rekeyed_from    TEXT
            )
        """)
        await db.commit()

async def search_keys(term: str = "", limit: int = 25,
                      columns: str = "key_id, expiration_date, hwid, status") -> list[tuple]:
    async with aiosqlite.connect(DB_FILE) as db:
        if term:
            async with db.execute(
                f"SELECT {columns} FROM keys WHERE key_id LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{term}%", limit),
            ) as cur:
                return await cur.fetchall()
        async with db.execute(
            f"SELECT {columns} FROM keys ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            return await cur.fetchall()

async def fetch_stats() -> dict:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT COUNT(*),"
            " SUM(CASE WHEN status='active'  THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN status='revoked' THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN hwid IS NOT NULL THEN 1 ELSE 0 END)"
            " FROM keys"
        ) as cur:
            t, a, r, b = await cur.fetchone()
    return {"total": t or 0, "active": a or 0, "revoked": r or 0, "bound": b or 0}

# ══════════════════════════════════════════════════════════════════
#  EMBED FACTORY
# ══════════════════════════════════════════════════════════════════
def make_embed(title: str, description: str = "", color: discord.Color = COLOR_PRIMARY,
               *, footer: str = "Vortex Security System", with_ts: bool = True) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text=footer)
    if with_ts:
        e.timestamp = datetime.now(timezone.utc)
    return e

def status_color(status: str) -> discord.Color:
    return COLOR_SUCCESS if status == "active" else COLOR_ERROR

# ══════════════════════════════════════════════════════════════════
#  FORMATTERS
# ══════════════════════════════════════════════════════════════════
def fmt_expiry(exp_date: str) -> tuple[str, str]:
    if exp_date == "permanent":
        return "🔓 Permanent", ""
    try:
        exp  = datetime.fromisoformat(exp_date)
        days = (exp - datetime.now()).days
        s    = exp.strftime("%b %d, %Y")
        if days < 0:  return f"❌ Expired ({s})", ""
        if days == 0: return "⚠️ Expires today", ""
        return f"📅 {s}", f" · {days}d left"
    except ValueError:
        return "❓ Unknown", ""

def fmt_hwid(hwid: str | None) -> str:
    if not hwid: return "○ Unbound"
    return f"● `{hwid[:18]}…`" if len(hwid) > 18 else f"● `{hwid}`"

def fmt_status(status: str) -> str:
    return "✅ Active" if status == "active" else "🚫 Revoked"

def fmt_created(ts: str | None) -> str:
    if not ts: return "N/A"
    try:    return datetime.fromisoformat(ts).strftime("%b %d, %Y %H:%M")
    except: return ts

def _select_option(key_id: str, exp_date: str, hwid: str | None, status: str) -> discord.SelectOption:
    exp_text, exp_suffix = fmt_expiry(exp_date)
    clean_exp = exp_text.replace("📅 ", "").replace("🔓 ", "").replace("❌ ", "").replace("⚠️ ", "")
    icon  = "✅" if status == "active" else "🚫"
    bound = "Bound" if hwid else "Free"
    desc  = f"{icon} {clean_exp}{exp_suffix} · {bound}"
    return discord.SelectOption(label=key_id, value=key_id, description=desc[:100])

def _key_detail_embed(row: tuple) -> discord.Embed:
    key_id, hwid, duration, exp_date, status, created_by, created_at, rekeyed_from = row
    exp_text, exp_suffix = fmt_expiry(exp_date)
    e = make_embed(
        "🔑  Key Details",
        f"`{key_id}`\n{DIV}",
        status_color(status),
    )
    e.add_field(name="Status",     value=fmt_status(status),         inline=True)
    e.add_field(name="Duration",   value=duration or "N/A",          inline=True)
    e.add_field(name="Expires",    value=f"{exp_text}{exp_suffix}",  inline=True)
    e.add_field(name="HWID",       value=fmt_hwid(hwid),             inline=True)
    e.add_field(name="Created By", value=f"`{created_by or 'N/A'}`", inline=True)
    e.add_field(name="Created At", value=fmt_created(created_at),    inline=True)
    if rekeyed_from:
        e.add_field(name="Rekeyed From", value=f"`{rekeyed_from}`", inline=False)
    return e

# ══════════════════════════════════════════════════════════════════
#  SHARED SEARCH MODAL  (re-used by both Delete and Info surfaces)
# ══════════════════════════════════════════════════════════════════
class SearchFilterModal(Modal):
    """
    Generic key-search modal.
    `view_factory(rows, term)` returns (embed, view) — called on submit.
    `fallback_rows` is shown when no results match (keeps the UI usable).
    """
    def __init__(self, view_factory, fallback_rows: list[tuple], modal_title: str = "🔍 Search Keys"):
        super().__init__(title=modal_title, timeout=120)
        self.view_factory  = view_factory
        self.fallback_rows = fallback_rows
        self.search_input  = TextInput(
            label="Key ID (partial match · blank = show all)",
            placeholder="e.g. VORTEX-1234 or just 1234",
            required=False,
            max_length=60,
        )
        self.add_item(self.search_input)

    async def on_submit(self, interaction: discord.Interaction):
        term = self.search_input.value.strip()
        rows = await search_keys(term=term, limit=25)

        if not rows:
            hint   = f"No keys matched `{term}`." if term else "No keys in the database."
            notice = make_embed("🔍  No Results", f"{hint}\n{DIV}\nShowing previous results.", COLOR_MUTED)
            embed, view = self.view_factory(self.fallback_rows, "")
            # Show the no-result notice briefly, then restore the list
            await interaction.response.edit_message(embed=notice, view=view)
            return

        embed, view = self.view_factory(rows, term)
        await interaction.response.edit_message(embed=embed, view=view)

# ══════════════════════════════════════════════════════════════════
#  KEY INFO  —  single-select, detail-on-pick
# ══════════════════════════════════════════════════════════════════
class KeyInfoSelect(Select):
    def __init__(self, rows: list[tuple]):
        options = [_select_option(*r) for r in rows]
        super().__init__(
            placeholder="Select a key to view its details…",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        key_id = self.values[0]
        rows   = await search_keys(
            term=key_id, limit=1,
            columns="key_id, hwid, duration, expiration_date, status, created_by, created_at, rekeyed_from",
        )
        if not rows:
            await interaction.response.send_message(
                embed=make_embed("❌ Not Found", f"Key `{key_id}` no longer exists.", COLOR_ERROR),
                ephemeral=True,
            )
            return
        # Update embed with detail; keep same view so user can pick another key
        await interaction.response.edit_message(embed=_key_detail_embed(rows[0]), view=self.view)


class KeyInfoView(View):
    def __init__(self, rows: list[tuple], term: str = ""):
        super().__init__(timeout=180)
        self.rows = rows
        self.term = term
        self.add_item(KeyInfoSelect(rows))

        search_btn          = Button(label="🔍 Search", style=discord.ButtonStyle.blurple,   row=1)
        close_btn           = Button(label="✕ Close",   style=discord.ButtonStyle.secondary, row=1)
        search_btn.callback = self._search_cb
        close_btn.callback  = self._close_cb
        self.add_item(search_btn)
        self.add_item(close_btn)

    async def _search_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            SearchFilterModal(make_info_ui, self.rows, modal_title="🔍 Search Keys — Info")
        )

    async def _close_cb(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(
            embed=make_embed("✕  Closed", "Key info panel closed.", COLOR_MUTED), view=None
        )

# ══════════════════════════════════════════════════════════════════
#  DELETE KEYS  —  multi-select, confirm required
# ══════════════════════════════════════════════════════════════════
class DeleteKeySelect(Select):
    def __init__(self, rows: list[tuple]):
        options = [_select_option(*r) for r in rows]
        super().__init__(
            placeholder="Select keys to delete (multi-select)…",
            min_values=1,
            max_values=len(options),
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        count    = len(self.values)
        key_list = "\n".join(f"> `{k}`" for k in self.values)
        e = make_embed(
            f"⚠️  Confirm — {count} Key{'s' if count > 1 else ''} Selected",
            f"Marked for permanent deletion:\n{DIV}\n{key_list}\n{DIV}\n"
            "This **cannot be undone**. Press **Confirm Delete** to proceed.",
            COLOR_WARN,
        )
        self.view.pending_keys          = self.values
        self.view.confirm_btn.disabled  = False
        await interaction.response.edit_message(embed=e, view=self.view)


class DeleteKeyView(View):
    def __init__(self, rows: list[tuple], term: str = ""):
        super().__init__(timeout=180)
        self.rows         = rows
        self.term         = term
        self.pending_keys: list[str] = []

        self.add_item(DeleteKeySelect(rows))

        search_btn          = Button(label="🔍 Search",         style=discord.ButtonStyle.blurple,   row=1)
        self.confirm_btn    = Button(label="🗑️ Confirm Delete", style=discord.ButtonStyle.danger,    row=1, disabled=True)
        cancel_btn          = Button(label="✕ Cancel",          style=discord.ButtonStyle.secondary, row=1)

        search_btn.callback       = self._search_cb
        self.confirm_btn.callback = self._confirm_cb
        cancel_btn.callback       = self._cancel_cb

        self.add_item(search_btn)
        self.add_item(self.confirm_btn)
        self.add_item(cancel_btn)

    async def _search_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            SearchFilterModal(make_delete_ui, self.rows, modal_title="🗑️ Search Keys — Delete")
        )

    async def _confirm_cb(self, interaction: discord.Interaction):
        if not self.pending_keys:
            return await interaction.response.send_message("No keys selected.", ephemeral=True)

        async with aiosqlite.connect(DB_FILE) as db:
            await db.executemany("DELETE FROM keys WHERE key_id = ?", [(k,) for k in self.pending_keys])
            await db.commit()

        count    = len(self.pending_keys)
        key_list = "\n".join(f"> ~~`{k}`~~" for k in self.pending_keys)
        e = make_embed(
            f"🗑️  {count} Key{'s' if count > 1 else ''} Deleted",
            f"{key_list}\n{DIV}\nRemoved permanently from the database.",
            COLOR_SUCCESS,
        )
        e.add_field(name="Deleted by", value=f"`{interaction.user}`", inline=True)
        e.add_field(name="Count",      value=str(count),              inline=True)
        self.stop()
        await interaction.response.edit_message(embed=e, view=None)

    async def _cancel_cb(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(
            embed=make_embed("✕  Cancelled", "No keys were deleted.", COLOR_MUTED), view=None
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ══════════════════════════════════════════════════════════════════
#  UI FACTORIES  —  (defined after views; called at interaction time)
# ══════════════════════════════════════════════════════════════════
def make_info_ui(rows: list[tuple], term: str = "") -> tuple[discord.Embed, KeyInfoView]:
    header = (f"Query: `{term}`  ·  **{len(rows)}** result{'s' if len(rows) > 1 else ''}"
              if term else f"Showing **{len(rows)}** most recent keys")
    e = make_embed(
        "🔍  Key Info",
        f"{header}\n{DIV}\nSelect a key from the dropdown to view its details.",
        COLOR_INFO,
    )
    return e, KeyInfoView(rows, term)


def make_delete_ui(rows: list[tuple], term: str = "") -> tuple[discord.Embed, DeleteKeyView]:
    header = (f"Query: `{term}`  ·  **{len(rows)}** result{'s' if len(rows) > 1 else ''}"
              if term else f"Showing **{len(rows)}** most recent keys")
    e = make_embed(
        "🗑️  Delete Keys",
        f"{header}\n{DIV}\nSelect one or more keys, then press **Confirm Delete**.",
        COLOR_ERROR,
    )
    return e, DeleteKeyView(rows, term)

# ══════════════════════════════════════════════════════════════════
#  KEY CREATION
# ══════════════════════════════════════════════════════════════════
class KeyAmountModal(Modal):
    def __init__(self, duration: str):
        super().__init__(title="Generate Keys", timeout=300)
        self.duration    = duration
        self.amount_input = TextInput(
            label="Amount (max 50 per batch)",
            placeholder="e.g. 1, 5, 10, 50",
            default="1",
            required=True,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value.strip())
            if not 1 <= amount <= 50: raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                embed=make_embed("❌ Invalid Amount", "Enter a whole number between **1 – 50**.", COLOR_ERROR),
                ephemeral=True,
            )

        days            = EXPIRATION_PRESETS[self.duration]
        expiration_date = "permanent" if days is None else (datetime.now() + timedelta(days=days)).isoformat()
        created_at      = datetime.now().isoformat()
        creator         = str(interaction.user)

        keys, records = [], []
        for _ in range(amount):
            k = f"VORTEX-{str(uuid.uuid4())[:8].upper()}"
            keys.append(k)
            records.append((k, self.duration, expiration_date, "active", creator, created_at))

        async with aiosqlite.connect(DB_FILE) as db:
            await db.executemany(
                "INSERT INTO keys (key_id, duration, expiration_date, status, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                records,
            )
            await db.commit()

        exp_text, exp_suffix = fmt_expiry(expiration_date)
        duration_label = {"1d": "1 Day", "3d": "3 Days", "7d": "7 Days",
                          "1m": "1 Month", "1y": "1 Year", "permanent": "Permanent"}.get(self.duration, self.duration)

        if amount <= 5:
            keys_block = "\n".join(f"`{k}`" for k in keys)
            e = make_embed(f"🔑  {amount} Key{'s' if amount > 1 else ''} Generated",
                           f"{DIV}\n{keys_block}", COLOR_SUCCESS)
        else:
            file_bytes = io.BytesIO("\n".join(keys).encode("utf-8"))
            file = discord.File(file_bytes, filename=f"VORTEX_KEYS_{amount}pcs_{self.duration}.txt")
            e = make_embed(f"🔑  {amount} Keys Generated",
                           f"Keys exported to the attached file.\n{DIV}", COLOR_SUCCESS)

        e.add_field(name="Duration",   value=duration_label,            inline=True)
        e.add_field(name="Expires",    value=f"{exp_text}{exp_suffix}", inline=True)
        e.add_field(name="Created By", value=f"`{creator}`",            inline=True)

        if amount <= 5:
            await interaction.response.send_message(embed=e, ephemeral=True)
        else:
            await interaction.response.send_message(embed=e, file=file, ephemeral=True)


class DurationSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="1 Day",     value="1d",        emoji="⏱️"),
            discord.SelectOption(label="3 Days",    value="3d",        emoji="📅"),
            discord.SelectOption(label="7 Days",    value="7d",        emoji="📅", default=True),
            discord.SelectOption(label="1 Month",   value="1m",        emoji="📆"),
            discord.SelectOption(label="1 Year",    value="1y",        emoji="📅"),
            discord.SelectOption(label="Permanent", value="permanent", emoji="🔓"),
        ]
        super().__init__(placeholder="Select key duration…", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(KeyAmountModal(self.values[0]))


class DurationSelectView(View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(DurationSelect())

# ══════════════════════════════════════════════════════════════════
#  RESET HWID
# ══════════════════════════════════════════════════════════════════
class ResetModal(Modal, title="🔄 Reset HWID"):
    key_input = TextInput(label="Key ID", placeholder="VORTEX-1234ABCD", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key_input.value.strip()
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT status FROM keys WHERE key_id = ?", (key,)) as cur:
                row = await cur.fetchone()

            if not row:
                return await interaction.response.send_message(
                    embed=make_embed("❌ Not Found", f"No key matching `{key}` exists.", COLOR_ERROR),
                    ephemeral=True,
                )
            if row[0] == "revoked":
                return await interaction.response.send_message(
                    embed=make_embed("❌ Already Revoked", "This key is revoked and cannot be reset.", COLOR_ERROR),
                    ephemeral=True,
                )

            new_key = f"VORTEX-{str(uuid.uuid4())[:8].upper()}"
            exp     = (datetime.now() + timedelta(days=7)).isoformat()
            await db.execute("UPDATE keys SET status = 'revoked' WHERE key_id = ?", (key,))
            await db.execute(
                "INSERT INTO keys (key_id, duration, expiration_date, status, created_by, created_at, rekeyed_from) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (new_key, "7d", exp, "active", str(interaction.user), datetime.now().isoformat(), key),
            )
            await db.commit()

        exp_text, exp_suffix = fmt_expiry(exp)
        e = make_embed("🔄  HWID Reset Complete", DIV, COLOR_SUCCESS)
        e.add_field(name="Old Key (Revoked)", value=f"~~`{key}`~~",           inline=False)
        e.add_field(name="New Key",           value=f"`{new_key}`",           inline=True)
        e.add_field(name="Expires",           value=f"{exp_text}{exp_suffix}", inline=True)
        e.add_field(name="Reset By",          value=f"`{interaction.user}`",  inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ══════════════════════════════════════════════════════════════════
class AdminPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _check(self, interaction: discord.Interaction) -> bool:
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                embed=make_embed("🔒  Access Denied", "You don't have the required role.", COLOR_ERROR),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="🔑 Generate Key", style=discord.ButtonStyle.success,   custom_id="btn_gen")
    async def btn_gen(self, interaction: discord.Interaction, button: Button):
        if await self._check(interaction):
            await interaction.response.send_message(
                embed=make_embed("🔑  Generate Keys", "Select key duration below.", COLOR_PRIMARY),
                view=DurationSelectView(), ephemeral=True,
            )

    @discord.ui.button(label="🔄 Reset HWID",  style=discord.ButtonStyle.secondary, custom_id="btn_reset")
    async def btn_reset(self, interaction: discord.Interaction, button: Button):
        if await self._check(interaction):
            await interaction.response.send_modal(ResetModal())

    @discord.ui.button(label="📋 Key List",    style=discord.ButtonStyle.blurple,   custom_id="btn_list")
    async def btn_list(self, interaction: discord.Interaction, button: Button):
        if not await self._check(interaction): return
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute(
                "SELECT key_id, expiration_date, hwid, status "
                "FROM keys WHERE status = 'active' ORDER BY created_at DESC LIMIT 10"
            ) as cur:
                keys = await cur.fetchall()
        stats = await fetch_stats()

        if not keys:
            return await interaction.response.send_message(
                embed=make_embed("📋  Key List", "No active keys in the database.", COLOR_MUTED),
                ephemeral=True,
            )

        pct_active = round(stats["active"] / stats["total"] * 100) if stats["total"] else 0
        e = make_embed(
            "📋  Active Keys  —  Latest 10",
            f"🔑 **{stats['total']}** total  ·  ✅ **{stats['active']}** active ({pct_active}%)"
            f"  ·  🚫 **{stats['revoked']}** revoked  ·  💻 **{stats['bound']}** bound\n{DIV}",
            COLOR_PRIMARY,
        )
        for key_id, exp_date, hwid, status in keys:
            exp_text, exp_suffix = fmt_expiry(exp_date)
            e.add_field(name=f"`{key_id}`", value=f"{exp_text}{exp_suffix}\n{fmt_hwid(hwid)}", inline=True)

        await interaction.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🔍 Key Info",    style=discord.ButtonStyle.blurple,   custom_id="btn_info")
    async def btn_info(self, interaction: discord.Interaction, button: Button):
        if not await self._check(interaction): return
        rows = await search_keys(limit=25)
        if not rows:
            return await interaction.response.send_message(
                embed=make_embed("🔍  No Keys", "No keys in the database.", COLOR_MUTED),
                ephemeral=True,
            )
        embed, view = make_info_ui(rows)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ Delete Keys", style=discord.ButtonStyle.danger,    custom_id="btn_delete")
    async def btn_delete(self, interaction: discord.Interaction, button: Button):
        if not await self._check(interaction): return
        rows = await search_keys(limit=25)
        if not rows:
            return await interaction.response.send_message(
                embed=make_embed("🗑️  No Keys", "No keys in the database.", COLOR_MUTED),
                ephemeral=True,
            )
        embed, view = make_delete_ui(rows)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ══════════════════════════════════════════════════════════════════
#  WEB API
# ══════════════════════════════════════════════════════════════════
def cors_headers():
    return {
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

async def handle_options(request):
    return web.Response(headers=cors_headers())

async def verify_key(request):
    try:
        data      = await request.json()
        user_key  = data.get("key",  "").strip()
        user_hwid = data.get("hwid", "").strip()

        if not user_key or not user_hwid:
            return web.json_response({"status": "fail", "message": "ต้องระบุ key และ hwid"},
                                     status=400, headers=cors_headers())

        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute(
                "SELECT hwid, expiration_date, status FROM keys WHERE key_id = ?", (user_key,)
            ) as cur:
                row = await cur.fetchone()

            if not row:
                return web.json_response({"status": "fail", "message": "ไม่พบคีย์นี้ในระบบ!"},
                                         status=404, headers=cors_headers())

            stored_hwid, expiration_date, status = row

            if status == "revoked":
                return web.json_response({"status": "fail", "message": "คีย์นี้ถูก revoke แล้ว!"},
                                         status=403, headers=cors_headers())

            days_remaining = None
            if expiration_date != "permanent":
                exp = datetime.fromisoformat(expiration_date)
                if exp < datetime.now():
                    return web.json_response(
                        {"status": "fail", "message": "คีย์นี้หมดอายุแล้ว!", "expiration_date": expiration_date},
                        status=403, headers=cors_headers(),
                    )
                days_remaining = max(0, (exp - datetime.now()).days)

            if stored_hwid is None:
                await db.execute("UPDATE keys SET hwid = ? WHERE key_id = ?", (user_hwid, user_key))
                await db.commit()
                return web.json_response({
                    "status": "success", "message": "ลงทะเบียนเครื่องสำเร็จ!",
                    "expiration_date": expiration_date, "days_remaining": days_remaining, "hwid_bound": True,
                }, headers=cors_headers())
            elif stored_hwid == user_hwid:
                return web.json_response({
                    "status": "success", "message": "ยินดีต้อนรับกลับ!",
                    "expiration_date": expiration_date, "days_remaining": days_remaining, "hwid_bound": True,
                }, headers=cors_headers())
            else:
                return web.json_response({"status": "fail", "message": "คีย์นี้ถูกใช้ไปแล้วกับเครื่องอื่น!"},
                                         status=403, headers=cors_headers())

    except Exception as e:
        logger.error(f"Error in /verify: {e}")
        return web.json_response({"status": "error", "message": "เกิดข้อผิดพลาดภายในเซิร์ฟเวอร์"},
                                 status=500, headers=cors_headers())

async def health_check(request):
    return web.json_response({"status": "ok", "message": "VORTEX API is running"}, headers=cors_headers())

async def get_stats(request):
    s = await fetch_stats()
    return web.json_response({"status": "ok", **s}, headers=cors_headers())

# ══════════════════════════════════════════════════════════════════
#  BOT
# ══════════════════════════════════════════════════════════════════
class VortexBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=discord.Intents.all())
        self.web_runner = None

    async def setup_hook(self):
        await init_db()
        app = web.Application()
        for path in ("/verify", "/health", "/stats"):
            app.router.add_options(path, handle_options)
        app.add_routes([
            web.post("/verify", verify_key),
            web.get("/health",  health_check),
            web.get("/stats",   get_stats),
        ])
        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        await web.TCPSite(self.web_runner, "0.0.0.0", API_PORT).start()
        logger.info(f"🌐 VORTEX API started on port {API_PORT}")
        await self.tree.sync()

    async def close(self):
        if self.web_runner:
            await self.web_runner.cleanup()
        await super().close()

bot = VortexBot()

@bot.event
async def on_ready():
    bot.add_view(AdminPanel())
    logger.info(f"✅ Bot logged in as {bot.user}")

@bot.tree.command(name="panel", description="Open the Vortex admin panel (admin only)")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
        return await interaction.response.send_message(
            embed=make_embed("🔒  Access Denied", "You don't have the required role.", COLOR_ERROR),
            ephemeral=True,
        )
    stats      = await fetch_stats()
    bound_pct  = round(stats["bound"]  / stats["total"] * 100) if stats["total"] else 0
    active_pct = round(stats["active"] / stats["total"] * 100) if stats["total"] else 0

    e = make_embed("⚙️  Vortex Admin Panel",
                   f"Key management and access control system.\n{DIV}", COLOR_PRIMARY)
    if interaction.guild.icon:
        e.set_thumbnail(url=interaction.guild.icon.url)

    e.add_field(name="🔑 Total",       value=f"**{stats['total']}**",                         inline=True)
    e.add_field(name="✅ Active",        value=f"**{stats['active']}** ({active_pct}%)",        inline=True)
    e.add_field(name="🚫 Revoked",       value=f"**{stats['revoked']}**",                       inline=True)
    e.add_field(name="💻 HWID Bound",    value=f"**{stats['bound']}** ({bound_pct}% of total)", inline=True)
    e.add_field(name="🔓 HWID Unbound",  value=f"**{stats['active'] - stats['bound']}**",       inline=True)
    e.add_field(name="\u200b",           value="\u200b",                                        inline=True)

    await interaction.response.send_message(embed=e, view=AdminPanel())

if __name__ == "__main__":
    if not TOKEN:
        logger.error("❌ ไม่พบ DISCORD_TOKEN ในไฟล์ .env")
    else:
        bot.run(TOKEN, log_handler=None)
