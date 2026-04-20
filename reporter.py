import asyncio
import time
import random
import re
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, PeerFloodError, UserPrivacyRestrictedError
from database_manager import db
from utils import format_speed, log_to_admin

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

    def stop(self):
        self.is_running = False

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
        
        client = TelegramClient(
            StringSession(acc_data["session"]),
            self.api_id,
            self.api_hash,
            device_model=acc_data["device"]["device_model"],
            system_version=acc_data["device"]["system_version"],
            app_version=acc_data["device"]["app_version"]
        )
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                await log_to_admin(f"User {self.user_id}: Account {acc_data['phone']} session expired.")
                return

            peer = await client.get_input_entity(target_link)
            
            successful_here = 0
            while successful_here < reports_per_acc and self.is_running:
                # Check credits before each report
                user = db.get_user(self.user_id)
                if user[1] < 0.5: # 1:2 ratio
                    self.is_running = False
                    await log_to_admin(f"User {self.user_id}: Out of credits. Stopping task.")
                    break

                success, error = await self.report_once(client, peer, reason, msg_ids, custom_msg)
                if success:
                    successful_here += 1
                    self.success_count += 1
                    # Deduct 0.5 credits (1 Credit = 2 Reports ratio)
                    db.set_user_credits(self.user_id, user[1] - 0.5)
                    # Update progress in DB every 5 successful reports
                    if self.success_count % 5 == 0:
                        db.update_task_progress(self.task_id, self.success_count, "running")
                    
                    await asyncio.sleep(random.uniform(5, 10)) # Random humanity delay
                else:
                    self.fail_count += 1
                    if "FloodWait" in error:
                        wait_time = int(re.search(r'\((\d+)s\)', error).group(1)) if "(" in error else 60
                        await asyncio.sleep(wait_time)
                    elif "Account Limited" in error:
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

        # Create Task record
        self.task_id = db.create_task(self.user_id, target_link, total_reports)
        active_tasks[self.task_id] = self
        db.update_task_status(self.task_id, "running")

        self.start_time = time.time()
        reports_per_account = max(1, total_reports // len(accounts))
        
        await log_to_admin(f"User {self.user_id} started attack on {target_link} | reports: {total_reports} | task_id: {self.task_id}")

        tasks = []
        for i, acc in enumerate(accounts):
            tasks.append(self.account_worker(acc, target_link, reports_per_account, reason_type, message_ids, custom_message, i * 1.5))

        # Run workers
        await asyncio.gather(*tasks)

        # Cleanup
        status = "finished" if self.is_running else "stopped"
        db.update_task_status(self.task_id, status)
        db.update_task_progress(self.task_id, self.success_count, status)
        if self.task_id in active_tasks:
            del active_tasks[self.task_id]

        total_time = time.time() - self.start_time
        msg = f"Attack {status.upper()} for {self.user_id}\nTarget: {target_link}\nSuccess: {self.success_count}\nFailed: {self.fail_count}\nTime: {total_time:.2f}s"
        await log_to_admin(msg)
        return msg
