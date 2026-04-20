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
