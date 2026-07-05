#!/usr/bin/env python3
"""Debug: Prueba el flujo de chat real contra OpenCode API."""
import base64, json, time
import httpx

PASSWORD = "imryyr-local-pass"
PORT = 4040

auth = base64.b64encode(f"opencode:{PASSWORD}".encode()).decode()
h = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

# Crear sesion
r = httpx.post(f"http://localhost:{PORT}/api/session", headers=h, json={"agentID": "build"}, timeout=15)
sid = r.json().get("data", {}).get("id")
print(f"Session: {sid}")

# Enviar prompt
r = httpx.post(f"http://localhost:{PORT}/api/session/{sid}/prompt", headers=h, json={"prompt": {"text": "Responde solo: HOLA"}}, timeout=30)
print(f"Prompt enviado: {r.status_code}")

# Esperar usando /wait
print("Esperando respuesta (wait)...")
r = httpx.post(f"http://localhost:{PORT}/api/session/{sid}/wait", headers=h, timeout=180)
print(f"Wait: HTTP {r.status_code}")

# Obtener mensajes
r = httpx.get(f"http://localhost:{PORT}/api/session/{sid}/message", headers=h, timeout=15)
data = r.json()
msgs = data.get("data", [])
print(f"Mensajes: {len(msgs)}")
for m in msgs:
    role = m.get("role", "?")
    parts = m.get("parts", [])
    for p in parts:
        if p.get("type") == "text":
            print(f"  [{role}] {p.get('text', '')[:300]}")
