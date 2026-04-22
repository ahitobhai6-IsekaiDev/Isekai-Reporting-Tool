import asyncio
import time
import random
import re
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, PeerFloodError, UserPrivacyRestrictedError
from database_manager import db
from utils import format_speed, log_to_admin
from proxy_manager import proxy_manager

active_tasks = {} # Global registry: {task_id: Reporter_instance}

class Reporter:
    def __init__(self, user_id, api_id, api_hash):
        self.user_id = user_id
        self.api_id = api_id
        self.api_hash = api_hash
        self.success_count = 0
        self.fail_count = 0
        self.start_time = None
        self.is_running = True
        self.task_id = None
        # --- Live Stats (for 11-point dashboard) ---
        self.total_reports_target = 0
        self.target_link = ""
        self.accounts_used = set()       # set of phone numbers
        self.proxies_used = set()        # set of proxy strings
        self.specific_message = False    # True if targeting a message, not peer

    def stop(self):
        self.is_running = False

    def get_live_stats(self):
        """Returns a dict of all 11 stats for the live dashboard."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        return {
            "target": self.target_link,
            "specific_message": self.specific_message,
            "live_count": self.success_count,
            "total_requested": self.total_reports_target,
            "accounts_used": len(self.accounts_used),
            "proxies_used": len(self.proxies_used),
            "total_time": elapsed,
            "speed": format_speed(self.success_count, elapsed),
            "failed": self.fail_count,
        }

    async def report_once(self, client, peer, reason_type, message_ids=None, custom_message="Violation report"):
        try:
            if message_ids:
                await client(functions.messages.ReportRequest(
                    peer=peer, id=message_ids, reason=reason_type, message=custom_message
                ))
            else:
                await client(functions.account.ReportPeerRequest(
                    peer=peer, reason=reason_type, message=custom_message
                ))
            return True, None
        except FloodWaitError as e:
            return False, f"FloodWait ({e.seconds}s)"
        except PeerFloodError:
            return False, "Account Limited"
        except Exception as e:
            return False, str(e)

    async def account_worker(self, acc_data, target_link, reports_per_acc, reason, msg_ids, custom_msg, start_delay):
        if not self.is_running: return
        
        await asyncio.sleep(start_delay)
        
        proxy_config = proxy_manager.get_proxy_for_telethon()
        proxy_str = f"{proxy_config.get('addr')}:{proxy_config.get('port')}" if proxy_config else None

        client = TelegramClient(
            StringSession(acc_data["session"]),
            self.api_id,
            self.api_hash,
            device_model=acc_data["device"]["device_model"],
            system_version=acc_data["device"]["system_version"],
            app_version=acc_data["device"]["app_version"],
            proxy=proxy_config
        )
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                await log_to_admin(f"User {self.user_id}: Account {acc_data['phone']} session expired.")
                return

            # Track which account and proxy are active
            self.accounts_used.add(acc_data['phone'])
            if proxy_str:
                self.proxies_used.add(proxy_str)

            # Extract message ID and clean link
            msg_id_extract = None
            if "t.me/c/" in target_link:
                parts = target_link.split("/")
                if len(parts) >= 6:
                    msg_id_extract = int(parts[-1])
                    target_link = "/".join(parts[:-1])
            elif "t.me/" in target_link and "joinchat" not in target_link and "+" not in target_link:
                parts = target_link.split("/")
                if len(parts) >= 4 and parts[-1].isdigit():
                    msg_id_extract = int(parts[-1])
                    target_link = "/".join(parts[:-1])
                    
            # Override message_ids if extracted from link
            if msg_id_extract and not msg_ids:
                msg_ids = [msg_id_extract]
            if msg_ids:
                self.specific_message = True

            # Auto-Join logic
            from telethon.tl.functions.channels import JoinChannelRequest
            from telethon.tl.functions.messages import ImportChatInviteRequest
            
            try:
                if "+" in target_link or "joinchat" in target_link:
                    hash_str = target_link.split("+")[-1] if "+" in target_link else target_link.split("joinchat/")[-1]
                    await client(ImportChatInviteRequest(hash_str))
                else:
                    await client(JoinChannelRequest(target_link))
            except Exception:
                pass # Already joined or can't join, continue anyway

            peer = await client.get_input_entity(target_link)
            
            successful_here = 0
            while successful_here < reports_per_acc and self.is_running:
                # Check credits before each report
                user = db.get_user(self.user_id)
                if user[1] < 0.5:
                    self.is_running = False
                    await log_to_admin(f"User {self.user_id}: Out of credits. Stopping task.")
                    break

                success, error = await self.report_once(client, peer, reason, msg_ids, custom_msg)
                if success:
                    successful_here += 1
                    self.success_count += 1
                    # Deduct 0.5 credits (1 Credit = 2 Reports)
                    db.set_user_credits(self.user_id, user[1] - 0.5)
                    # Update DB progress every 5 successful reports
                    if self.success_count % 5 == 0:
                        db.update_task_progress(self.task_id, self.success_count, "running")
                    
                    await asyncio.sleep(random.uniform(4, 8)) # Random stealth delay
                else:
                    self.fail_count += 1
                    if error and "FloodWait" in error:
                        wait_time = int(re.search(r'\((\d+)s\)', error).group(1)) if "(" in error else 60
                        await asyncio.sleep(wait_time)
                    elif error and "Account Limited" in error:
                        break
                    else:
                        await asyncio.sleep(10)
        except Exception as e:
            await log_to_admin(f"User {self.user_id} Task Error: {e}")
        finally:
            await client.disconnect()

    async def start_mass_report(self, target_link, total_reports, reason_type, custom_message, message_ids=None):
        accounts = db.get_user_accounts(self.user_id)
        if not accounts:
            return "No accounts added."

        # Check if user has enough credits initially
        user = db.get_user(self.user_id)
        required_credits = total_reports * 0.5
        if user[1] < required_credits:
            return f"Insufficient credits. Need {required_credits}, have {user[1]}."

        # Set task metadata for live stats
        self.total_reports_target = total_reports
        self.target_link = target_link

        # Create Task record
        self.task_id = db.create_task(self.user_id, target_link, total_reports)
        active_tasks[self.task_id] = self
        db.update_task_status(self.task_id, "running")

        self.start_time = time.time()
        reports_per_account = max(1, total_reports // len(accounts))
        
        await log_to_admin(f"User {self.user_id} started attack on {target_link} | reports: {total_reports} | task_id: {self.task_id}")

        workers = []
        for i, acc in enumerate(accounts):
            workers.append(self.account_worker(acc, target_link, reports_per_account, reason_type, message_ids, custom_message, i * 1.5))

        # Run all account workers concurrently
        await asyncio.gather(*workers)

        # Cleanup
        status = "finished" if self.is_running else "stopped"
        db.update_task_status(self.task_id, status)
        db.update_task_progress(self.task_id, self.success_count, status)
        if self.task_id in active_tasks:
            del active_tasks[self.task_id]

        total_time = time.time() - self.start_time
        msg = (
            f"Attack {status.upper()} for {self.user_id}\n"
            f"Target: {target_link}\n"
            f"Success: {self.success_count} | Failed: {self.fail_count}\n"
            f"Accounts Used: {len(self.accounts_used)} | Proxies Used: {len(self.proxies_used)}\n"
            f"Time: {total_time:.2f}s | Speed: {format_speed(self.success_count, total_time)}"
        )
        await log_to_admin(msg)
        return msg
