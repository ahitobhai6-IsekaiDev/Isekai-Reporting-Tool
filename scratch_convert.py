import base64
import struct
from telethon.sessions import StringSession
from telethon.crypto import AuthKey

def convert(pyro_string):
    data = base64.urlsafe_b64decode(pyro_string + "=" * (-len(pyro_string) % 4))
    version = data[0]
    if version == 1:
        dc_id = data[1]
        auth_key = data[3:259]
    elif version == 2:
        dc_id = data[1]
        auth_key = data[22:278]
    elif version in (3, 4):
        dc_id = data[1]
        auth_key = data[26:282]
    else:
        print("Unknown version")
        return pyro_string
        
    dc_ips = {
        1: "149.154.175.50",
        2: "149.154.167.51",
        3: "149.154.175.100",
        4: "149.154.167.91",
        5: "91.108.56.130"
    }
    ip = dc_ips.get(dc_id, "149.154.167.51")
    
    session = StringSession()
    session.set_dc(dc_id, ip, 443)
    session.auth_key = AuthKey(auth_key)
    return session.save()

print("Script ready")
