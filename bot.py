import os
import asyncio
import logging
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from config import load_config, MAIN_BOT_TOKEN, LOG_BOT_TOKEN
from database_manager import db
from reporter import Reporter
from utils import get_random_device, log_to_admin, convert_to_telethon

# Setup Logging
logging.basicConfig(level=logging.INFO)

# Load Configuration
cfg = load_config()
ADMIN_IDS = cfg.get("admins", [])

# Initialize Client
bot = TelegramClient('main_bot', cfg['api_id'], cfg['api_hash']).start(bot_token=MAIN_BOT_TOKEN)

# --- UI Helpers ---

def get_main_menu(user_id):
    is_admin = user_id in ADMIN_IDS
    user = db.get_user(user_id)
    
    if is_admin:
        return [
            [Button.inline("➕ Add Member", b"admin_add_member"), Button.inline("💰 Set Credits", b"admin_set_credits")],
            [Button.inline("📊 Global Stats", b"admin_stats"), Button.inline("📣 Broadcast", b"admin_broadcast")],
            [Button.inline("👤 User Menu", b"user_menu")]
        ]
    
    if not db.is_member(user_id):
        return [[Button.url("Contact Admin to Buy", "https://t.me/+sHKpff6xBJ44Zjk1")]]
    
    # Standard User Menu
    return [
        [Button.inline("➕ Add Account", b"add_acc"), Button.inline("📱 My Accounts", b"my_accs")],
        [Button.inline("🚀 Start Report", b"start_report"), Button.inline("📋 Active Tasks", b"active_tasks")],
        [Button.inline("📈 My Balance", b"my_balance"), Button.inline("📖 How to Use", b"user_help")],
        [Button.url("Contact Support", "https://t.me/+sHKpff6xBJ44Zjk1")]
    ]

# --- Event Handlers ---

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    db.add_user(user_id, is_admin=(user_id in ADMIN_IDS))
    
    user = db.get_user(user_id)
    is_member = db.is_member(user_id)
    
    welcome_text = (
        "🔥 **WELCOME TO MASS REPORTER PREMIUM** 🔥\n\n"
        f"🆔 **Your ID:** `{user_id}`\n"
        f"💰 **Credits:** `{round(user[1], 2)}`\n"
        f"📅 **Expiry:** `{user[3] or 'N/A'}`\n\n"
    )
    
    if user_id in ADMIN_IDS:
        welcome_text += "👑 **YOU ARE A SUPER ADMIN**"
    elif not is_member:
        welcome_text += "⚠️ **You do not have an active membership.**"
    
    await event.respond(welcome_text, buttons=get_main_menu(user_id))
    await log_to_admin(f"User {user_id} opened the bot.")

# --- Admin Handlers ---

@bot.on(events.CallbackQuery(data=b"admin_add_member"))
async def admin_add_member(event):
    if event.sender_id not in ADMIN_IDS: return
    try:
        async with bot.conversation(event.sender_id, timeout=300) as conv:
            await conv.send_message("Send User ID:")
            res = await conv.get_response(); uid = int(res.text)
            await conv.send_message("Plan (weekly/monthly/yearly):")
            res = await conv.get_response(); plan = res.text.lower()
            plan_map = {"weekly": 2500, "monthly": 15000, "yearly": 150000}
            db.update_membership(uid, plan, plan_map.get(plan, 0))
            await conv.send_message("✅ Success")
    except asyncio.TimeoutError:
        await bot.send_message(event.sender_id, "❌ Error: Conversation timed out (5 mins). Please try again.")
    except Exception as e:
        await bot.send_message(event.sender_id, f"❌ Error: {e}")

@bot.on(events.CallbackQuery(data=b"admin_broadcast"))
async def admin_broadcast(event):
    if event.sender_id not in ADMIN_IDS: return
    try:
        async with bot.conversation(event.sender_id, timeout=300) as conv:
            await conv.send_message("Send the message (Text/Photo/Video) you want to broadcast:")
            msg = await conv.get_response()
            users = db.get_all_users()
            count = 0
            for u in users:
                try:
                    await bot.send_message(u, msg)
                    count += 1
                except: pass
            await conv.send_message(f"✅ Broadcast finished. Sent to {count} users.")
    except asyncio.TimeoutError:
        await bot.send_message(event.sender_id, "❌ Error: Broadcast cancelled due to timeout.")
    except Exception as e:
        await bot.send_message(event.sender_id, f"❌ Error: {e}")

@bot.on(events.CallbackQuery(data=b"admin_stats"))
async def admin_stats(event):
    users = len(db.get_all_users())
    await event.answer(f"📊 Global Stats:\nTotal Users: {users}", alert=True)

# --- User Handlers ---

@bot.on(events.CallbackQuery(data=b"add_acc"))
async def add_account_flow(event):
    if not db.is_member(event.sender_id): return await event.answer("No Membership", alert=True)
    try:
        async with bot.conversation(event.sender_id, timeout=300) as conv:
            await conv.send_message("📥 Send Telethon Session String:")
            res = await conv.get_response(); sess = res.text.strip()
            sess = convert_to_telethon(sess)
            try:
                device = get_random_device()
                temp = TelegramClient(StringSession(sess), cfg['api_id'], cfg['api_hash'], 
                                       device_model=device['device_model'], system_version=device['system_version'])
                await temp.connect()
                if await temp.is_user_authorized():
                    me = await temp.get_me()
                    db.add_account(event.sender_id, sess, me.phone, me.username, device)
                    await conv.send_message("✅ Added")
                else: await conv.send_message("❌ Invalid Session")
                await temp.disconnect()
            except Exception as e: await conv.send_message(f"❌ Connection Error: {e}")
    except asyncio.TimeoutError:
        await bot.send_message(event.sender_id, "❌ Error: Session link wait timed out. Please click 'Add Account' again.")
    except Exception as e:
        await bot.send_message(event.sender_id, f"❌ Error: {e}")
        logging.error(f"Conversation error: {e}", exc_info=True)

@bot.on(events.CallbackQuery(data=b"active_tasks"))
async def active_tasks_flow(event):
    tasks = db.get_active_tasks(event.sender_id)
    if not tasks: return await event.answer("No active tasks.", alert=True)
    
    text = "📋 **ACTIVE TASKS**\n\n"
    buttons = []
    from reporter import active_tasks
    for t in tasks:
        text += f"🔹 **Task ID {t['id']}**\nTarget: {t['target']}\nProgress: {t['done']}/{t['requested']}\n\n"
        buttons.append([Button.inline(f"Stop Task {t['id']}", f"stop_{t['id']}".encode())])
    
    await event.respond(text, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r"stop_(\d+)"))
async def stop_task_handler(event):
    task_id = int(event.data_match.group(1).decode())
    from reporter import active_tasks
    if task_id in active_tasks:
        active_tasks[task_id].stop()
        await event.answer(f"🛑 Task {task_id} stopping...", alert=True)
        await log_to_admin(f"User {event.sender_id} manually STOPPED Task {task_id}")
    else:
        await event.answer("Task not found or already finished.", alert=True)

@bot.on(events.CallbackQuery(data=b"my_accs"))
async def list_accounts_flow(event):
    accs = db.get_user_accounts(event.sender_id)
    if not accs: return await event.answer("No accounts.", alert=True)
    text = "📱 **YOUR ACCOUNTS**\n\n"
    for i, a in enumerate(accs, 1):
        text += f"**{i}.** `{a['phone']}` (@{a['username']})\n"
    await event.respond(text, buttons=[[Button.inline("🗑️ Remove Account", b"remove_acc")]])

@bot.on(events.CallbackQuery(data=b"remove_acc"))
async def remove_account_flow(event):
    try:
        async with bot.conversation(event.sender_id, timeout=300) as conv:
            await conv.send_message("🔢 Send index (e.g. 1):")
            res = await conv.get_response()
            try:
                accs = db.get_user_accounts(event.sender_id)
                idx = int(res.text)-1
                db.remove_account(accs[idx]['id'], event.sender_id)
                await conv.send_message("✅ Removed")
            except: await conv.send_message("❌ Error: Invalid index or account not found.")
    except asyncio.TimeoutError:
        await bot.send_message(event.sender_id, "❌ Error: Timed out.")

@bot.on(events.CallbackQuery(data=b"user_help"))
async def user_help_handler(event):
    await event.respond(
        "📖 **HOW TO USE**\n\n"
        "1. **Add Account**: Send Telethon session string.\n"
        "2. **Start Report**: Enter target and count.\n"
        "3. **Isolation**: Each user uses only THEIR accounts.\n"
        "4. **Credits**: 1 Credit = 2 Reports.\n"
        "5. **Stop**: Use 'Active Tasks' to stop anytime."
    )

@bot.on(events.CallbackQuery(data=b"start_report"))
async def start_report_flow(event):
    if not db.is_member(event.sender_id): return
    try:
        async with bot.conversation(event.sender_id, timeout=300) as conv:
            await conv.send_message("🔗 Target link:")
            res = await conv.get_response(); target = res.text
            await conv.send_message("🔢 Count:")
            res = await conv.get_response(); count = int(res.text)
            from telethon.types import InputReportReasonSpam
            reporter = Reporter(event.sender_id, cfg['api_id'], cfg['api_hash'])
            await conv.send_message("🚀 Attack Started")
            asyncio.create_task(reporter.start_mass_report(target, count, InputReportReasonSpam(), "Violation report"))
    except asyncio.TimeoutError:
        await bot.send_message(event.sender_id, "❌ Error: Report setup timed out.")
    except Exception as e:
        await bot.send_message(event.sender_id, f"❌ Error: {e}")
        logging.error(f"Report flow error: {e}")

@bot.on(events.CallbackQuery(data=b"my_balance"))
async def my_balance(event):
    user = db.get_user(event.sender_id)
    await event.answer(f"💰 Balance: {round(user[1], 2)} Credits\n📅 Expiry: {user[3]}", alert=True)

@bot.on(events.CallbackQuery(data=b"user_menu"))
async def user_menu_redirect(event):
    await event.edit("👤 **USER MENU**", buttons=get_main_menu(event.sender_id))

print("Bot is running...")
bot.run_until_disconnected()
