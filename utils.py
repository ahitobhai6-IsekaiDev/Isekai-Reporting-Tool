import random

# Realistic Android Device Profiles
DEVICES = [
    {"brand": "Samsung", "model": "SM-S901B", "system": "Android 12", "sdk": 31},
    {"brand": "Samsung", "model": "SM-G998B", "system": "Android 11", "sdk": 30},
    {"brand": "Google", "model": "Pixel 7 Pro", "system": "Android 13", "sdk": 33},
    {"brand": "Google", "model": "Pixel 6a", "system": "Android 12", "sdk": 31},
    {"brand": "Xiaomi", "model": "M2102J20SG", "system": "Android 11", "sdk": 30},
    {"brand": "Xiaomi", "model": "2201116SG", "system": "Android 12", "sdk": 31},
    {"brand": "OnePlus", "model": "LE2113", "system": "Android 11", "sdk": 30},
    {"brand": "OnePlus", "model": "NE2213", "system": "Android 12", "sdk": 31},
    {"brand": "Oppo", "model": "CPH2307", "system": "Android 12", "sdk": 31},
    {"brand": "Vivo", "model": "V2105", "system": "Android 11", "sdk": 30},
    {"brand": "Realme", "model": "RMX3363", "system": "Android 12", "sdk": 31},
    {"brand": "Sony", "model": "XQ-BC52", "system": "Android 11", "sdk": 30},
    {"brand": "Asus", "model": "AI2202", "system": "Android 12", "sdk": 31},
    {"brand": "Motorola", "model": "XT2125-4", "system": "Android 11", "sdk": 30}
]

APP_VERSIONS = ["9.1.3", "9.2.2", "9.3.0", "9.4.1", "10.0.1"]
LANG_CODES = ["en", "hi", "ru", "es", "tr", "id"]

def get_random_device():
    device = random.choice(DEVICES)
    lang = random.choice(LANG_CODES)
    return {
        "device_model": f"{device['brand']} {device['model']}",
        "system_version": f"{device['system']} (SDK {device['sdk']})",
        "app_version": random.choice(APP_VERSIONS),
        "lang_code": lang,
        "system_lang_code": f"{lang}-{lang.upper()}"
    }

def format_speed(count, seconds):
    if seconds == 0:
        return "0.00 R/s"
    return f"{count / seconds:.2f} R/s"

async def log_to_admin(message):
    import aiohttp
    from config import LOG_BOT_TOKEN, load_config
    cfg = load_config()
    # If possible, we send it to all admins or a specific group
    # For now, let's assume we send to the bot itself or a chat_id
    # Since the user gave a bot token, we can use it to send message to a channel/group if we have its ID
    # But he said "me os bot me mile", so maybe we send to all admins.
    for admin_id in cfg.get("admins", []):
        url = f"https://api.telegram.org/bot{LOG_BOT_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={"chat_id": admin_id, "text": f"🔔 LOG: {message}"})

def convert_to_telethon(session_string: str):
    """
    Converts a Pyrogram session string to a Telethon StringSession.
    If the string is already a Telethon session, returns it as is.
    """
    session_string = session_string.strip()
    
    # Telethon strings are typically shorter and start with a version (1)
    # Pyrogram strings are long and start with different bytes.
    if len(session_string) < 100:
        return session_string
        
    try:
        import base64
        import struct
        
        # Parse Pyrogram session
        # Structure: [Version (1 byte)][DC ID (1 byte)][Test Mode (1 byte)][Auth Key (256 bytes)][User ID (8 bytes)][Is Bot (1 byte)]
        # Pyrogram uses urlsafe base64
        data = base64.urlsafe_b64decode(session_string + "=" * (-len(session_string) % 4))
        
        version = data[0]
        if version == 1:
            dc_id = data[1]
            auth_key = data[3:259]
        elif version == 2:
            # Version 2 has API_ID and other stuff
            dc_id = data[1]
            auth_key = data[22:278]
        elif version in (3, 4):
            # Version 3/4
            dc_id = data[1]
            auth_key = data[26:282]
        else:
            return session_string

        # Map DC IDs to official Telegram IPs
        dc_ips = {
            1: "149.154.175.50",
            2: "149.154.167.51",
            3: "149.154.175.100",
            4: "149.154.167.91",
            5: "91.108.56.130"
        }
        ip = dc_ips.get(dc_id, "149.154.167.51")
        
        from telethon.sessions import StringSession
        from telethon.crypto import AuthKey
        session = StringSession()
        session.set_dc(dc_id, ip, 443)
        session.auth_key = AuthKey(auth_key)
        return session.save()
        
    except Exception as e:
        print(f"Conversion error: {e}")
        return session_string
