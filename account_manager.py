import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import load_accounts, save_accounts, load_config
from utils import get_random_device
from rich.console import Console

console = Console()

class AccountManager:
    def __init__(self):
        self.accounts = load_accounts()
        cfg = load_config()
        self.api_id = cfg["api_id"]
        self.api_hash = cfg["api_hash"]

    async def add_account(self, session_string):
        try:
            device = get_random_device()
            client = TelegramClient(
                StringSession(session_string),
                self.api_id,
                self.api_hash,
                device_model=device["device_model"],
                system_version=device["system_version"],
                app_version=device["app_version"]
            )
            await client.connect()
            if not await client.is_user_authorized():
                console.print("[red][!] Session string is invalid or expired.[/red]")
                return False
            
            me = await client.get_me()
            phone = me.phone if me.phone else "Unknown"
            
            # Check for existing
            for acc in self.accounts:
                if acc["session"] == session_string:
                    console.print("[yellow][!] Account already exists.[/yellow]")
                    return True

            self.accounts.append({
                "session": session_string,
                "phone": phone,
                "username": me.username or "No Username",
                "device": device
            })
            save_accounts(self.accounts)
            console.print(f"[green][+] Account added: {phone} (@{me.username})[/green]")
            await client.disconnect()
            return True
        except Exception as e:
            console.print(f"[red][!] Error adding account: {e}[/red]")
            return False

    def list_accounts(self):
        if not self.accounts:
            console.print("[yellow][!] No accounts added yet.[/yellow]")
            return
        
        console.print("\n[bold cyan]Added Accounts:[/bold cyan]")
        for i, acc in enumerate(self.accounts, 1):
            console.print(f"{i}. {acc['phone']} (@{acc['username']}) - Device: {acc['device']['device_model']}")
        console.print("")

    def remove_account(self, index):
        if 0 <= index < len(self.accounts):
            removed = self.accounts.pop(index)
            save_accounts(self.accounts)
            console.print(f"[green][+] Removed account: {removed['phone']}[/green]")
        else:
            console.print("[red][!] Invalid index.[/red]")
