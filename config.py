import os
import json

# Telegram API Credentials
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

# Bot Tokens
MAIN_BOT_TOKEN = "8470946419:AAHqqVO2hEIDzOmNHUNMvCzMU8-IhP9IzV0"
LOG_BOT_TOKEN = "8519073040:AAEIjjTQL4kyIUpF53HsAQn0iQgezJkkUvI"

# Admin Configuration
ADMIN_IDS = [8700286093] # Super Admin ID

# Credits System
CREDITS_PER_REPORT = 0.5  # 1 Credit = 2 Reports (0.5 credit per report)

CONFIG_FILE = "config.json"
ACCOUNTS_FILE = "accounts.json"
PROXIES_FILE = "proxies.txt"
DB_FILE = "reporter.db"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            # Ensure new keys are present
            cfg.setdefault("api_id", DEFAULT_API_ID)
            cfg.setdefault("api_hash", DEFAULT_API_HASH)
            cfg.setdefault("main_token", MAIN_BOT_TOKEN)
            cfg.setdefault("log_token", LOG_BOT_TOKEN)
            cfg.setdefault("admins", ADMIN_IDS)
            return cfg
    return {
        "api_id": DEFAULT_API_ID, 
        "api_hash": DEFAULT_API_HASH,
        "main_token": MAIN_BOT_TOKEN,
        "log_token": LOG_BOT_TOKEN,
        "admins": ADMIN_IDS
    }

def save_config(api_id, api_hash, admins=None):
    cfg = load_config()
    cfg["api_id"] = api_id
    cfg["api_hash"] = api_hash
    if admins is not None:
        cfg["admins"] = admins
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    return []

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=4)
