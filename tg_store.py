"""
tg_store.py — Telegram Channel as Persistent Storage

Uses the LOG_BOT_TOKEN to store & retrieve critical data from a pinned Telegram message.
This ensures session strings, user data, and accounts survive bot restarts.

Format: All data is stored as JSON in a single pinned message in the LOG channel.
The bot reads it on startup and writes to it on every change.
"""

import asyncio
import json
import aiohttp
from config import LOG_BOT_TOKEN, load_config

# The chat_id of the log channel/group — first admin in config
def _get_log_chat():
    cfg = load_config()
    admins = cfg.get("admins", [])
    if admins:
        return admins[0]
    return None

STORE_TAG = "#MASSREPORTER_DB"  # Unique tag to identify the storage message

class TelegramStore:
    """
    Uses a Telegram chat (log bot destination) as a key-value JSON store.
    On startup: loads data from a pinned/tagged message.
    On write: edits that message or sends a new one.
    """

    def __init__(self):
        self._data = {}
        self._message_id = None
        self._chat_id = _get_log_chat()
        self._base_url = f"https://api.telegram.org/bot{LOG_BOT_TOKEN}"

    async def _api(self, method, payload=None):
        async with aiohttp.ClientSession() as session:
            resp = await session.post(f"{self._base_url}/{method}", json=payload or {})
            return await resp.json()

    async def load(self):
        """On startup: scan recent messages for the DB tag and load JSON."""
        if not self._chat_id:
            return
        try:
            result = await self._api("getUpdates", {"limit": 100, "offset": -100})
            messages = result.get("result", [])
            for update in reversed(messages):
                msg = update.get("message") or update.get("channel_post")
                if msg and msg.get("text", "").startswith(STORE_TAG):
                    raw = msg["text"].replace(STORE_TAG, "").strip()
                    self._data = json.loads(raw)
                    self._message_id = msg["message_id"]
                    print(f"[TgStore] Loaded {len(self._data)} keys from Telegram store.")
                    return
            print("[TgStore] No existing store found. Starting fresh.")
        except Exception as e:
            print(f"[TgStore] Load error: {e}")

    async def save(self):
        """Write the current data dict back to Telegram."""
        if not self._chat_id:
            return
        text = f"{STORE_TAG}\n{json.dumps(self._data, ensure_ascii=False)}"
        try:
            if self._message_id:
                await self._api("editMessageText", {
                    "chat_id": self._chat_id,
                    "message_id": self._message_id,
                    "text": text
                })
            else:
                result = await self._api("sendMessage", {
                    "chat_id": self._chat_id,
                    "text": text
                })
                if result.get("ok"):
                    self._message_id = result["result"]["message_id"]
                    # Pin the message so it's easy to find
                    await self._api("pinChatMessage", {
                        "chat_id": self._chat_id,
                        "message_id": self._message_id,
                        "disable_notification": True
                    })
        except Exception as e:
            print(f"[TgStore] Save error: {e}")

    def get(self, key, default=None):
        return self._data.get(key, default)

    async def set(self, key, value):
        self._data[key] = value
        await self.save()

    async def delete(self, key):
        if key in self._data:
            del self._data[key]
            await self.save()


# Global store instance
tg_store = TelegramStore()
