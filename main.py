import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from account_manager import AccountManager
from proxy_manager import ProxyManager
from reporter import Reporter
from config import load_config, save_config

console = Console()

async def main_menu():
    acc_mgr = AccountManager()
    prox_mgr = ProxyManager()
    cfg = load_config()
    
    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]TELEGRAM MASS REPORTER[/bold cyan]\n"
            "[white]Developed for Premium Performance[/white]",
            border_style="cyan"
        ))
        
        console.print(f"[bold white]Accounts:[/bold white] {len(acc_mgr.accounts)} | [bold white]Proxies:[/bold white] {len(prox_mgr.working_proxies)}")
        console.print("\n1. Add Account (Session String)")
        console.print("2. Add/Hunt Proxy")
        console.print("3. Start Mass Reporter")
        console.print("4. Settings (API ID/Hash)")
        console.print("5. Exit")
        
        choice = Prompt.ask("\nChoose an option", choices=["1", "2", "3", "4", "5"])
        
        if choice == "1":
            session = Prompt.ask("Enter Telethon Session String")
            if session:
                await acc_mgr.add_account(session)
            input("\nPress Enter to continue...")
            
        elif choice == "2":
            console.print("\n1. Hunt Proxies (Auto)")
            console.print("2. Check Working Proxies")
            sub_choice = Prompt.ask("Choose", choices=["1", "2"])
            if sub_choice == "1":
                prox_mgr.hunt_proxies()
                prox_mgr.check_all_proxies(limit=50)
            elif sub_choice == "2":
                prox_mgr.check_all_proxies()
            input("\nPress Enter to continue...")
            
        elif choice == "3":
            if not acc_mgr.accounts:
                console.print("[red][!] Add some accounts first![/red]")
                input("\nPress Enter to continue...")
                continue
            
            console.print("\n[bold]Mass Reporter Menu:[/bold]")
            console.print("1. Report Group")
            console.print("2. Report Channel")
            console.print("3. Back")
            
            target_type = Prompt.ask("Choose", choices=["1", "2", "3"])
            if target_type == "3": continue
            
            link = Prompt.ask("Enter Target Link (Username or t.me link)")
            msg_attack = Prompt.ask("Specific message IDs? (Optional, comma separated e.g. 123,124)", default="")
            message_ids = [int(i.strip()) for i in msg_attack.split(",")] if msg_attack else None
            
            # --- Nested Reasons Menu ---
            from reporter import types
            
            REASONS_STRUCTURE = {
                "1": ("I don't Like it", types.InputReportReasonOther(), None),
                "2": ("Child abuse", types.InputReportReasonChildAbuse(), {
                    "1": "Child Sexual abuse",
                    "2": "Child physical abuse"
                }),
                "3": ("Violence", types.InputReportReasonViolence(), {
                    "1": "Insults or false information",
                    "2": "Graphic or disturbing content",
                    "3": "Extreme violence, dismemberment",
                    "4": "Hate speech or symbols",
                    "5": "Calling for violence",
                    "6": "Organized crime",
                    "7": "Terrorism",
                    "8": "Animal abuse"
                }),
                "4": ("Illegal goods and service", types.InputReportReasonOther(), {
                    "1": "Weapons (Firearms, Melee, Non-lethel, Other)",
                    "2": "Drugs (Nicotine, Illegal, Other)",
                    "3": "Fake documents",
                    "4": "Counterfeit money",
                    "5": "Hacking tools and malware",
                    "6": "Counterfeit merchandise",
                    "7": "Other goods and services"
                }),
                "5": ("Illegal adult content", types.InputReportReasonPornography(), {
                    "1": "Child abuse (Sexual/Physical)",
                    "2": "Illegal sexual services",
                    "3": "Animal abuse",
                    "4": "Non-consensual sexual imagery",
                    "5": "Pornography",
                    "6": "Other Illegal sexual content"
                }),
                "6": ("Personal data", types.InputReportReasonPersonalDetails(), {
                    "1": "Private images",
                    "2": "Phone number",
                    "3": "Address",
                    "4": "Stolen data or credentials",
                    "5": "Other Personal information"
                }),
                "7": ("Scam or fraud", types.InputReportReasonOther(), {
                    "1": "Impersonation",
                    "2": "Deceptive or unrealistic financial claims",
                    "3": "Malware, phishing",
                    "4": "Fraudulent seller, product or service"
                }),
                "8": ("Copyright", types.InputReportReasonCopyright(), None),
                "9": ("Spam", types.InputReportReasonSpam(), {
                    "1": "Insult or false information",
                    "2": "Promoting Illegal content",
                    "3": "Promoting other content"
                }),
                "10": ("Other", types.InputReportReasonOther(), None),
                "11": ("It's not illegal, but must be take down", types.InputReportReasonOther(), None),
            }

            console.print("\n[bold]Select Main Reason:[/bold]")
            for k, v in REASONS_STRUCTURE.items():
                console.print(f"{k}. {v[0]}")
            
            main_key = Prompt.ask("Choose reason", choices=list(REASONS_STRUCTURE.keys()))
            main_reason_name, reason_type, sub_reasons = REASONS_STRUCTURE[main_key]
            
            final_reason_text = main_reason_name
            if sub_reasons:
                console.print(f"\n[bold]Select Specific Reason for {main_reason_name}:[/bold]")
                for sk, sv in sub_reasons.items():
                    console.print(f"{sk}. {sv}")
                sub_key = Prompt.ask("Choose", choices=list(sub_reasons.keys()))
                final_reason_text = f"{main_reason_name} - {sub_reasons[sub_key]}"
            
            # --- Custom Prompt ---
            custom_prompt = Prompt.ask("\nEnter Custom Prompt (Message for reporting)", default=f"Reported for {final_reason_text}")
            
            count = int(Prompt.ask("Enter Total Report Count", default="1000"))
            
            reporter = Reporter(acc_mgr.accounts, cfg["api_id"], cfg["api_hash"])
            await reporter.start_mass_report(link, count, reason_type, custom_prompt, prox_mgr.working_proxies, message_ids)
            input("\nPress Enter to continue...")

        elif choice == "4":
            new_id = Prompt.ask("Enter API ID", default=str(cfg["api_id"]))
            new_hash = Prompt.ask("Enter API Hash", default=cfg["api_hash"])
            save_config(int(new_id), new_hash)
            cfg = load_config()
            console.print("[green][+] Settings Saved![/green]")
            input("\nPress Enter to continue...")
            
        elif choice == "5":
            console.print("[cyan]Goodbye![/cyan]")
            sys.exit()

if __name__ == "__main__":
    try:
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting...[/yellow]")
