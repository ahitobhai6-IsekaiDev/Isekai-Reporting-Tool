import requests
import re
import threading
import time
from rich.console import Console

console = Console()

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.working_proxies = []
        self.sources = [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all",
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/proxy.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
        ]

    def hunt_proxies(self):
        console.print("[cyan][*] Hunting proxies from public sources...[/cyan]")
        new_proxies = []
        for source in self.sources:
            try:
                response = requests.get(source, timeout=10)
                if response.status_code == 200:
                    found = re.findall(r'\d+\.\d+\.\d+\.\d+:\d+', response.text)
                    new_proxies.extend(found)
            except:
                continue
        
        self.proxies = list(set(new_proxies))
        console.print(f"[green][+] Found {len(self.proxies)} unique proxies.[/green]")
        return self.proxies

    def check_proxy(self, proxy):
        try:
            # Simple check using requests
            url = "http://httpbin.org/ip"
            proxies = {"http": proxy, "https": proxy}
            response = requests.get(url, proxies=proxies, timeout=5)
            if response.status_code == 200:
                self.working_proxies.append(proxy)
                return True
        except:
            pass
        return False

    def check_all_proxies(self, limit=100):
        console.print(f"[cyan][*] Checking top {limit} proxies...[/cyan]")
        self.working_proxies = []
        threads = []
        for proxy in self.proxies[:limit]:
            t = threading.Thread(target=self.check_proxy, args=(proxy,))
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        console.print(f"[green][+] Found {len(self.working_proxies)} working proxies.[/green]")
        return self.working_proxies

    def get_proxy_for_telethon(self):
        import random
        if not self.working_proxies:
            return None
        proxy = random.choice(self.working_proxies)
        # Parse IP:PORT format
        try:
            ip, port = proxy.split(":")
            # Assuming HTTP proxies from scrapes by default for Telethon compatibility
            return {
                'proxy_type': 'http',
                'addr': ip,
                'port': int(port)
            }
        except:
            return None
            
    def add_custom_proxy(self, proxy_str):
        """Adds a custom proxy and assumes it's working."""
        self.working_proxies.append(proxy_str)

proxy_manager = ProxyManager()
