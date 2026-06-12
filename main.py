import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select, Modal, TextInput
from aiohttp import web
import aiosqlite
import os
import uuid
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncio
import io

# ================= CONFIG & SETUP =================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 0))
API_PORT = int(os.getenv("API_PORT", 30184))
DB_FILE = "vortex_keys.db"

# ตั้งค่า Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VORTEX")

# Color codes
COLOR_PRIMARY = discord.Color.from_rgb(255, 87, 34)
COLOR_SUCCESS = discord.Color.from_rgb(76, 175, 80)
COLOR_ERROR = discord.Color.from_rgb(244, 67, 54)
COLOR_INFO = discord.Color.from_rgb(33, 150, 243)

EXPIRATION_PRESETS = {
    "1d": 1, "3d": 3, "7d": 7,
    "1m": 30, "1y": 365, "permanent": None,
}

# ================= DATABASE (SQLite) =================
async def init_db():
    """สร้างตารางใน Database หากยังไม่มี"""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                key_id TEXT PRIMARY KEY,
                hwid TEXT,
                duration TEXT,
                expiration_date TEXT,
                status TEXT,
                created_by TEXT,
                created_at TEXT,
                rekeyed_from TEXT
            )
        ''')
        await db.commit()

# ================= WEB API (aiohttp) =================
def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

async def handle_options(request):
    """รองรับ CORS Preflight"""
    return web.Response(headers=cors_headers())

async def verify_key(request):
    """API: ตรวจสอบและผูก HWID"""
    try:
        data = await request.json()
        user_key = data.get("key", "").strip()
        user_hwid = data.get("hwid", "").strip()

        if not user_key or not user_hwid:
            return web.json_response({"status": "fail", "message": "ต้องระบุ key และ hwid"}, status=400, headers=cors_headers())

        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT hwid, expiration_date, status FROM keys WHERE key_id = ?", (user_key,)) as cursor:
                row = await cursor.fetchone()

            if not row:
                return web.json_response({"status": "fail", "message": "ไม่พบคีย์นี้ในระบบ!"}, status=404, headers=cors_headers())

            stored_hwid, expiration_date, status = row

            if status == "revoked":
                return web.json_response({"status": "fail", "message": "คีย์นี้ถูก revoke แล้ว!"}, status=403, headers=cors_headers())

            # เช็ควันหมดอายุ
            is_expired = False
            days_remaining = None
            if expiration_date != "permanent":
                exp_date = datetime.fromisoformat(expiration_date)
                if exp_date < datetime.now():
                    is_expired = True
                else:
                    days_remaining = max(0, (exp_date - datetime.now()).days)

            if is_expired:
                return web.json_response({"status": "fail", "message": "คีย์นี้หมดอายุแล้ว!", "expiration_date": expiration_date}, status=403, headers=cors_headers())

            # จัดการ HWID
            if stored_hwid is None:
                await db.execute("UPDATE keys SET hwid = ? WHERE key_id = ?", (user_hwid, user_key))
                await db.commit()
                return web.json_response({
                    "status": "success", "message": "ลงทะเบียนเครื่องสำเร็จ!",
                    "expiration_date": expiration_date, "days_remaining": days_remaining, "hwid_bound": True
                }, headers=cors_headers())
            elif stored_hwid == user_hwid:
                return web.json_response({
                    "status": "success", "message": "ยินดีต้อนรับกลับ!",
                    "expiration_date": expiration_date, "days_remaining": days_remaining, "hwid_bound": True
                }, headers=cors_headers())
            else:
                return web.json_response({"status": "fail", "message": "คีย์นี้ถูกใช้ไปแล้วกับเครื่องอื่น!"}, status=403, headers=cors_headers())

    except Exception as e:
        logger.error(f"Error in /verify: {e}")
        return web.json_response({"status": "error", "message": "เกิดข้อผิดพลาดภายในเซิร์ฟเวอร์"}, status=500, headers=cors_headers())

async def health_check(request):
    return web.json_response({"status": "ok", "message": "VORTEX API is running"}, headers=cors_headers())

async def get_stats(request):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT COUNT(*), SUM(CASE WHEN status='active' THEN 1 ELSE 0 END), SUM(CASE WHEN status='revoked' THEN 1 ELSE 0 END), SUM(CASE WHEN hwid IS NOT NULL THEN 1 ELSE 0 END) FROM keys") as cursor:
            total, active, revoked, bound = await cursor.fetchone()
            
    return web.json_response({
        "status": "ok",
        "total_keys": total or 0,
        "active_keys": active or 0,
        "revoked_keys": revoked or 0,
        "bound_keys": bound or 0
    }, headers=cors_headers())

# ================= DISCORD UI =================
class KeyAmountModal(Modal):
    """หน้าต่างกรอกจำนวนคีย์ที่ต้องการสร้าง"""
    def __init__(self, duration: str):
        super().__init__(title='ระบุจำนวนคีย์ที่ต้องการสร้าง', timeout=300)
        self.duration = duration
        
        self.amount_input = TextInput(
            label='จำนวน (สูงสุด 50 คีย์ต่อครั้ง)',
            placeholder='เช่น 1, 5, 10, 50',
            default='1',
            required=True
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value.strip())
            if amount < 1 or amount > 50:
                raise ValueError
        except ValueError:
            embed = discord.Embed(title="❌ ข้อผิดพลาด", description="กรุณาระบุตัวเลขจำนวนเต็มระหว่าง 1 ถึง 50 เท่านั้น", color=COLOR_ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        days = EXPIRATION_PRESETS[self.duration]
        expiration_date = "permanent" if days is None else (datetime.now() + timedelta(days=days)).isoformat()
        created_at = datetime.now().isoformat()
        creator = str(interaction.user)

        generated_keys = []
        db_records = []
        
        for _ in range(amount):
            new_key = f"VORTEX-{str(uuid.uuid4())[:8].upper()}"
            generated_keys.append(new_key)
            db_records.append((new_key, self.duration, expiration_date, "active", creator, created_at))

        async with aiosqlite.connect(DB_FILE) as db:
            await db.executemany('''
                INSERT INTO keys (key_id, duration, expiration_date, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', db_records)
            await db.commit()

        exp_text = "🔓 Permanent" if expiration_date == "permanent" else f"📅 {datetime.fromisoformat(expiration_date).strftime('%Y-%m-%d')}"
        
        if amount <= 5:
            keys_str = "\n".join([f"`{k}`" for k in generated_keys])
            embed = discord.Embed(
                title=f"✅ สร้างสำเร็จ {amount} คีย์", 
                description=f"**ระยะเวลา:** {self.duration.upper()}\n**หมดอายุ:** {exp_text}\n\n**รายการคีย์:**\n{keys_str}", 
                color=COLOR_SUCCESS
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            keys_str = "\n".join(generated_keys)
            file_content = io.BytesIO(keys_str.encode('utf-8'))
            file = discord.File(file_content, filename=f"VORTEX_KEYS_{amount}pcs_{self.duration}.txt")
            
            embed = discord.Embed(
                title=f"✅ สร้างสำเร็จ {amount} คีย์", 
                description=f"**ระยะเวลา:** {self.duration.upper()}\n**หมดอายุ:** {exp_text}\n\n📥 *กรุณาดาวน์โหลดไฟล์ด้านล่างเพื่อดูคีย์ทั้งหมด*", 
                color=COLOR_SUCCESS
            )
            await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

class DurationSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="1 Day", value="1d", emoji="⏱️"),
            discord.SelectOption(label="3 Days", value="3d", emoji="📅"),
            discord.SelectOption(label="7 Days", value="7d", emoji="📅", default=True),
            discord.SelectOption(label="1 Month", value="1m", emoji="📆"),
            discord.SelectOption(label="1 Year", value="1y", emoji="📅"),
            discord.SelectOption(label="Permanent", value="permanent", emoji="🔓"),
        ]
        super().__init__(placeholder="เลือกระยะเวลาคีย์...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        duration = self.values[0]
        await interaction.response.send_modal(KeyAmountModal(duration))

class DurationSelectView(View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(DurationSelect())

class ResetModal(Modal, title='🔄 รีเซ็ต HWID'):
    key_input = TextInput(label='ใส่คีย์ที่ต้องการรีเซ็ต', placeholder='เช่น VORTEX-1234ABCD', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key_input.value.strip()
        
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT status FROM keys WHERE key_id = ?", (key,)) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                return await interaction.response.send_message(embed=discord.Embed(title="❌ ไม่พบคีย์", description=f"ไม่พบคีย์ `{key}` ในระบบ", color=COLOR_ERROR), ephemeral=True)
            
            if row[0] == "revoked":
                return await interaction.response.send_message(embed=discord.Embed(title="❌ คีย์ถูกระงับ", description="คีย์นี้ถูก Revoke ไปแล้ว", color=COLOR_ERROR), ephemeral=True)

            new_key = f"VORTEX-{str(uuid.uuid4())[:8].upper()}"
            expiration_date = (datetime.now() + timedelta(days=7)).isoformat()

            await db.execute("UPDATE keys SET status = 'revoked' WHERE key_id = ?", (key,))
            await db.execute('''
                INSERT INTO keys (key_id, duration, expiration_date, status, created_by, created_at, rekeyed_from)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (new_key, "7d", expiration_date, "active", str(interaction.user), datetime.now().isoformat(), key))
            await db.commit()

        embed = discord.Embed(title="✅ รีเซ็ตคีย์สำเร็จ", description=f"**คีย์เก่า (Revoked):** `{key}`\n**คีย์ใหม่ (Active):** `{new_key}`\n**หมดอายุ:** 📅 {datetime.fromisoformat(expiration_date).strftime('%Y-%m-%d')}", color=COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class DeleteKeyModal(Modal, title='🗑️ ลบคีย์ออกจากระบบ'):
    """หน้าต่างสำหรับกรอกคีย์ที่ต้องการลบแบบถาวร"""
    key_input = TextInput(
        label='ใส่คีย์ที่ต้องการลบ',
        placeholder='เช่น VORTEX-1234ABCD',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key_input.value.strip()
        
        async with aiosqlite.connect(DB_FILE) as db:
            # ตรวจสอบก่อนว่ามีคีย์นี้หรือไม่
            async with db.execute("SELECT key_id FROM keys WHERE key_id = ?", (key,)) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                embed = discord.Embed(title="❌ ไม่พบคีย์", description=f"ไม่พบคีย์ `{key}` ในระบบ ไม่สามารถลบได้", color=COLOR_ERROR)
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            # ทำการลบข้อมูลออกจากระบบ
            await db.execute("DELETE FROM keys WHERE key_id = ?", (key,))
            await db.commit()

        embed = discord.Embed(title="✅ ลบคีย์สำเร็จ", description=f"ลบคีย์ `{key}` ออกจากฐานข้อมูลถาวรแล้ว", color=COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AdminPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def check_admin(self, interaction: discord.Interaction) -> bool:
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(embed=discord.Embed(title="❌ ไม่มีสิทธิ์", description="คุณไม่มีสิทธิ์ใช้งานคำสั่งนี้!", color=COLOR_ERROR), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔑 สร้างคีย์ใหม่", style=discord.ButtonStyle.success, custom_id="btn_gen")
    async def btn_gen(self, interaction: discord.Interaction, button: Button):
        if await self.check_admin(interaction):
            await interaction.response.send_message(embed=discord.Embed(title="🔑 สร้างคีย์ใหม่", description="เลือกระยะเวลาคีย์:", color=COLOR_PRIMARY), view=DurationSelectView(), ephemeral=True)

    @discord.ui.button(label="🔄 รีเซ็ต HWID", style=discord.ButtonStyle.secondary, custom_id="btn_reset")
    async def btn_reset(self, interaction: discord.Interaction, button: Button):
        if await self.check_admin(interaction):
            await interaction.response.send_modal(ResetModal())

    @discord.ui.button(label="📋 รายการคีย์", style=discord.ButtonStyle.blurple, custom_id="btn_list")
    async def btn_list(self, interaction: discord.Interaction, button: Button):
        if not await self.check_admin(interaction): return
        
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT key_id, expiration_date, hwid, status FROM keys WHERE status = 'active' ORDER BY created_at DESC LIMIT 10") as cursor:
                keys = await cursor.fetchall()
            async with db.execute("SELECT COUNT(*) FROM keys") as cursor:
                total_keys = (await cursor.fetchone())[0]

        if not keys:
            return await interaction.response.send_message(embed=discord.Embed(title="📋 รายการคีย์", description="ยังไม่มีคีย์ Active ในระบบ", color=COLOR_INFO), ephemeral=True)

        embed = discord.Embed(title="📋 10 รายการคีย์ล่าสุด (Active)", description=f"รวมทั้งหมดในระบบ: **{total_keys}** คีย์", color=COLOR_PRIMARY)
        
        for key_id, exp_date, hwid, status in keys:
            if exp_date == "permanent":
                exp_text = "🔓 Permanent"
            else:
                try:
                    exp = datetime.fromisoformat(exp_date)
                    days = (exp - datetime.now()).days
                    exp_text = f"📅 {exp.strftime('%Y-%m-%d')} ({max(0, days)}d)"
                except:
                    exp_text = "❓ Unknown"
            
            hwid_text = "🔓 Not Bound" if not hwid else "✅ Bound"
            embed.add_field(name=f"🔑 `{key_id}`", value=f"{exp_text}\n{hwid_text}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🗑️ ลบคีย์", style=discord.ButtonStyle.danger, custom_id="btn_delete")
    async def btn_delete(self, interaction: discord.Interaction, button: Button):
        if await self.check_admin(interaction):
            await interaction.response.send_modal(DeleteKeyModal())

# ================= BOT CLASS =================
class VortexBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=discord.Intents.all())
        self.web_runner = None

    async def setup_hook(self):
        await init_db()
        
        app = web.Application()
        app.router.add_options('/verify', handle_options)
        app.router.add_options('/health', handle_options)
        app.router.add_options('/stats', handle_options)
        
        app.add_routes([
            web.post('/verify', verify_key),
            web.get('/health', health_check),
            web.get('/stats', get_stats)
        ])
        
        self.web_runner = web.AppRunner(app)
        await self.web_runner.setup()
        site = web.TCPSite(self.web_runner, '0.0.0.0', API_PORT)
        await site.start()
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

@bot.tree.command(name="panel", description="เปิดแผงควบคุมระบบจัดการคีย์ (เฉพาะแอดมิน)")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
        return await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้งาน!", ephemeral=True)
        
    embed = discord.Embed(
        title="⚙️ VORTEX ADMIN PANEL",
        description="แผงควบคุมระบบจัดการคีย์\nกรุณากดปุ่มด้านล่างเพื่อทำรายการ",
        color=COLOR_PRIMARY
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text="Vortex Security System")
    
    await interaction.response.send_message(embed=embed, view=AdminPanel(), ephemeral=False)

# ================= START =================
if __name__ == "__main__":
    if not TOKEN:
        logger.error("❌ ไม่พบ DISCORD_TOKEN ในไฟล์ .env")
    else:
        bot.run(TOKEN, log_handler=None)