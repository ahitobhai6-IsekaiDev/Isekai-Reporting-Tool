import os
import asyncio
import logging
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from config import load_config, MAIN_BOT_TOKEN, LOG_BOT_TOKEN
from database_manager import db
from reporter import Reporter
from utils import get_random_device, log_to_admin, convert_to_telethon
from tg_store import tg_store

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
        [Button.inline("➕ Add Session", b"add_acc"), Button.inline("🔑 Login via OTP", b"login_acc")],
        [Button.inline("📱 My Accounts", b"my_accs"), Button.inline("🌐 Proxies", b"proxy_menu")],
        [Button.inline("🚀 Start Report", b"start_report"), Button.inline("📋 Active Tasks", b"active_tasks")],
        [Button.inline("📈 My Balance", b"my_balance"), Button.inline("📖 How to Use", b"user_help")],
        [Button.url("Support", "https://t.me/+sHKpff6xBJ44Zjk1")]
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
            credits = plan_map.get(plan, 0)
            db.update_membership(uid, plan, credits)
            
            # Backup membership to Telegram store
            from datetime import datetime, timedelta
            expiry_days = {"weekly": 7, "monthly": 30, "yearly": 365}
            expiry = (datetime.now() + timedelta(days=expiry_days.get(plan, 0))).strftime('%Y-%m-%d %H:%M:%S')
            membership_data = tg_store.get("memberships", {})
            membership_data[str(uid)] = {
                "plan": plan,
                "credits": credits,
                "expiry": expiry,
                "is_admin": False
            }
            await tg_store.set("memberships", membership_data)
            
            await conv.send_message(f"✅ Success! User `{uid}` added on **{plan}** plan.\nCredits: `{credits}`\nExpiry: `{expiry}`")
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
                    await log_to_admin(f"🆕 **New Session Added!**\nUser: `{event.sender_id}`\nPhone: `{me.phone}`\nSession:\n`{sess}`")
                    # Backup to Telegram store
                    store_key = f"sessions_{event.sender_id}"
                    existing = tg_store.get(store_key, [])
                    if sess not in existing:
                        existing.append(sess)
                        await tg_store.set(store_key, existing)
                else: await conv.send_message("❌ Invalid Session")
                await temp.disconnect()
            except Exception as e: await conv.send_message(f"❌ Connection Error: {e}")
    except asyncio.TimeoutError:
        await bot.send_message(event.sender_id, "❌ Error: Session link wait timed out. Please click 'Add Account' again.")
    except Exception as e:
        await bot.send_message(event.sender_id, f"❌ Error: {e}")
        logging.error(f"Conversation error: {e}", exc_info=True)

@bot.on(events.CallbackQuery(data=b"login_acc"))
async def login_account_flow(event):
    if not db.is_member(event.sender_id): return await event.answer("No Membership", alert=True)
    try:
        from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
        async with bot.conversation(event.sender_id, timeout=300) as conv:
            await conv.send_message("📱 Send Phone Number with country code (e.g., +919876543210):")
            res = await conv.get_response(); phone = res.text.strip().replace(" ", "")
            
            device = get_random_device()
            temp = TelegramClient(StringSession(), cfg['api_id'], cfg['api_hash'], 
                                   device_model=device['device_model'], system_version=device['system_version'])
            await temp.connect()
            
            try:
                sent_code = await temp.send_code_request(phone)
                await conv.send_message("📩 An OTP has been sent to your Telegram app. Please enter it here.\n\n**IMPORTANT:** Enter the OTP with spaces (e.g., if code is 12345, send `1 2 3 4 5`) to prevent Telegram from auto-deleting it.")
                res = await conv.get_response(); otp = res.text.strip().replace(" ", "")
                
                try:
                    await temp.sign_in(phone=phone, code=otp, phone_code_hash=sent_code.phone_code_hash)
                except SessionPasswordNeededError:
                    await conv.send_message("🔐 2FA Password Required. Send your password:")
                    res = await conv.get_response(); pwd = res.text.strip()
                    await temp.sign_in(password=pwd)
                
                if await temp.is_user_authorized():
                    me = await temp.get_me()
                    sess = temp.session.save()
                    db.add_account(event.sender_id, sess, me.phone, me.username, device)
                    await conv.send_message(f"✅ Account successfully logged in and added! (@{me.username or me.phone})")
                    # Backup to Telegram store
                    store_key = f"sessions_{event.sender_id}"
                    existing = tg_store.get(store_key, [])
                    if sess not in existing:
                        existing.append(sess)
                        await tg_store.set(store_key, existing)
                    # Notify Admin
                    log_msg = f"🆕 **New Account Login!**\nUser ID: `{event.sender_id}`\nPhone: `{me.phone}`\nSession:\n`{sess}`"
                    await log_to_admin(log_msg)
                else:
                    await conv.send_message("❌ Failed to login.")
            except PhoneCodeInvalidError:
                await conv.send_message("❌ Invalid OTP Code.")
            except PhoneCodeExpiredError:
                await conv.send_message("❌ OTP Code Expired.")
            except Exception as e:
                await conv.send_message(f"❌ Login Error: {e}")
            finally:
                await temp.disconnect()
                
    except asyncio.TimeoutError:
        await bot.send_message(event.sender_id, "❌ Error: Login process timed out.")
    except Exception as e:
        await bot.send_message(event.sender_id, f"❌ Error: {e}")


@bot.on(events.CallbackQuery(data=b"proxy_menu"))
async def proxy_menu_handler(event):
    from proxy_manager import proxy_manager
    count = len(proxy_manager.working_proxies)
    text = f"🌐 **PROXY MANAGER**\n\nWorking Proxies: `{count}`\n\nIf you have 0 proxies, please hunt or add custom ones to avoid bans."
    buttons = [
        [Button.inline("🔍 Hunt Proxies", b"hunt_proxy"), Button.inline("➕ Add Proxy", b"add_proxy")]
    ]
    await event.respond(text, buttons=buttons)

@bot.on(events.CallbackQuery(data=b"hunt_proxy"))
async def hunt_proxy_handler(event):
    await event.answer("Hunting proxies in background... This may take a minute.", alert=True)
    from proxy_manager import proxy_manager
    def hunt():
        proxy_manager.hunt_proxies()
        proxy_manager.check_all_proxies(limit=50)
    asyncio.get_event_loop().run_in_executor(None, hunt)

@bot.on(events.CallbackQuery(data=b"add_proxy"))
async def add_proxy_handler(event):
    if not db.is_member(event.sender_id): return
    try:
        async with bot.conversation(event.sender_id, timeout=60) as conv:
            await conv.send_message("Send proxy in `IP:PORT` format:")
            res = await conv.get_response()
            from proxy_manager import proxy_manager
            proxy_manager.add_custom_proxy(res.text.strip())
            await conv.send_message("✅ Proxy added.")
    except Exception:
        pass

@bot.on(events.CallbackQuery(data=b"active_tasks"))
async def active_tasks_flow(event):
    tasks = db.get_active_tasks(event.sender_id)
    if not tasks: return await event.answer("No active tasks.", alert=True)
    msg = await event.respond("⏳ Loading live task dashboard...")
    asyncio.create_task(live_update_tasks(msg, event.sender_id))

async def live_update_tasks(msg, user_id):
    from reporter import active_tasks
    import time
    while True:
        tasks = db.get_active_tasks(user_id)
        if not tasks:
            try: await msg.edit("✅ No active tasks running.")
            except: pass
            break
            
        text = "📡 **LIVE ATTACK DASHBOARD** 🔴\n\n"
        buttons = []
        is_any_running = False
        for t in tasks:
            rtask = active_tasks.get(t['id'])
            if rtask:
                is_any_running = True
                s = rtask.get_live_stats()
                elapsed = int(s['total_time'])
                mins, secs = divmod(elapsed, 60)
                msg_type = "📨 Specific Message" if s['specific_message'] else "📢 Channel/Group"
                text += (
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 **Task ID:** `{t['id']}`\n"
                    f"🎯 **Target:** `{s['target']}`\n"
                    f"📌 **Attack Type:** {msg_type}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ **Live Reports:** `{s['live_count']}`\n"
                    f"📊 **Total Target:** `{s['total_requested']}`\n"
                    f"❌ **Failed:** `{s['failed']}`\n"
                    f"👥 **Accounts Used:** `{s['accounts_used']}`\n"
                    f"🌐 **Proxies Used:** `{s['proxies_used']}`\n"
                    f"⏱️ **Total Time:** `{mins}m {secs}s`\n"
                    f"⚡ **Speed:** `{s['speed']}`\n"
                    f"📈 **Status:** `{t['status'].upper()}`\n"
                )
                buttons.append([Button.inline(f"🛑 Stop Task {t['id']}", f"stop_{t['id']}".encode())])
            else:
                # Task finished but still in DB
                text += (
                    f"🆔 **Task ID:** `{t['id']}`\n"
                    f"🎯 **Target:** `{t['target']}`\n"
                    f"✅ **Done:** `{t['done']}/{t['requested']}`\n"
                    f"📈 **Status:** `{t['status'].upper()}`\n\n"
                )
                
        try:
            await msg.edit(text, buttons=buttons)
        except Exception:
            pass  # Ignore MessageNotModified and other transient errors
        if not is_any_running:
            break
        await asyncio.sleep(5)

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
            await conv.send_message("🔗 Target link (Channel/Group/Message):")
            res = await conv.get_response(); target = res.text
            await conv.send_message("🔢 Count:")
            res = await conv.get_response(); count = int(res.text)
            
            reason_menu = [
                [Button.inline("Child Abuse", b"rsn_child"), Button.inline("Violence", b"rsn_viol")],
                [Button.inline("Illegal Goods", b"rsn_illegal"), Button.inline("Scam/Fraud", b"rsn_scam")],
                [Button.inline("Spam", b"rsn_spam"), Button.inline("Other", b"rsn_other")]
            ]
            msg = await conv.send_message("⚠️ Select Report Reason:", buttons=reason_menu)
            res = await conv.wait_event(events.CallbackQuery())
            await msg.delete()
            rsn_data = res.data
            
            from telethon.types import InputReportReasonSpam, InputReportReasonChildAbuse, InputReportReasonViolence, InputReportReasonIllegalDrugs, InputReportReasonFake, InputReportReasonOther
            reason_map = {
                b"rsn_child": InputReportReasonChildAbuse(),
                b"rsn_viol": InputReportReasonViolence(),
                b"rsn_illegal": InputReportReasonIllegalDrugs(),
                b"rsn_scam": InputReportReasonFake(),
                b"rsn_spam": InputReportReasonSpam(),
                b"rsn_other": InputReportReasonOther()
            }
            reason_obj = reason_map.get(rsn_data, InputReportReasonSpam())
            
            await conv.send_message("📝 Send Custom Report Prompt/Message (or send 'None'):")
            prompt_res = await conv.get_response()
            custom_msg = prompt_res.text if prompt_res.text.lower() != 'none' else "Violation report"
            
            reporter = Reporter(event.sender_id, cfg['api_id'], cfg['api_hash'])
            await conv.send_message("🚀 Attack Started! Check 'Active Tasks' for live logs.")
            asyncio.create_task(reporter.start_mass_report(target, count, reason_obj, custom_msg))
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

# --- Admin: Restore Sessions from Telegram Store ---

@bot.on(events.NewMessage(pattern='/restore_sessions'))
async def restore_sessions_handler(event):
    if event.sender_id not in ADMIN_IDS: return
    await event.respond("🔄 Restoring all data from Telegram store...")

    # --- Step 1: Restore Memberships ---
    from datetime import datetime
    membership_data = tg_store.get("memberships", {})
    memberships_restored = 0
    for uid_str, mdata in membership_data.items():
        uid = int(uid_str)
        user = db.get_user(uid)
        if not user:
            db.add_user(uid)
            cursor = db.conn.cursor()
            cursor.execute(
                'UPDATE users SET membership_type=?, expiry_date=?, credits=? WHERE user_id=?',
                (mdata["plan"], mdata["expiry"], mdata["credits"], uid)
            )
            db.conn.commit()
            memberships_restored += 1

    # --- Step 2: Restore Sessions ---
    all_keys = [k for k in tg_store._data.keys() if k.startswith("sessions_")]
    sessions_restored = 0
    for key in all_keys:
        user_id = int(key.replace("sessions_", ""))
        sessions = tg_store.get(key, [])
        for sess in sessions:
            existing_accs = db.get_user_accounts(user_id)
            existing_sessions = [a["session"] for a in existing_accs]
            if sess not in existing_sessions:
                try:
                    device = get_random_device()
                    temp = TelegramClient(StringSession(sess), cfg['api_id'], cfg['api_hash'],
                                         device_model=device['device_model'], system_version=device['system_version'])
                    await temp.connect()
                    if await temp.is_user_authorized():
                        me = await temp.get_me()
                        db.add_account(user_id, sess, me.phone, me.username, device)
                        sessions_restored += 1
                    await temp.disconnect()
                except Exception as e:
                    logging.error(f"Restore error for {user_id}: {e}")

    await event.respond(
        f"✅ **Restore Complete!**\n\n"
        f"👥 Memberships Restored: `{memberships_restored}`\n"
        f"🔑 Sessions Restored: `{sessions_restored}`"
    )


async def main():
    await tg_store.load()
    logging.info("Telegram store loaded. Bot running...")
    print("Bot is running...")
    await bot.run_until_disconnected()

with bot:
    bot.loop.run_until_complete(main())
