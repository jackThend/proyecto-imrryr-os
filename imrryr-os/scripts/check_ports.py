import socket

services = [
    (4000, "LiteLLM"),
    (4040, "OpenCode"),
    (3000, "Dashboard"),
    (5050, "Gateway"),
]
for port, name in services:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        r = s.connect_ex(("127.0.0.1", port))
        print(f"Port {port} ({name}): {'in use' if r == 0 else 'free'}")
    finally:
        s.close()
