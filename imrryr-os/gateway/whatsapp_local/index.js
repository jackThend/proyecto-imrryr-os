// index.js — Sidecar local de WhatsApp (Fase 5.1, vía Local/QR)
// ================================================================
// Puente entre una sesión real de WhatsApp Web (whatsapp-web.js) y el
// gateway Python (gateway/webhook_server.py). No requiere cuenta de
// desarrollador Meta: se escanea un QR una sola vez (la sesión queda
// guardada en .wwebjs_auth/ para las siguientes veces).
//
// Solo lo arranca scripts/startup.py cuando el modo activo (gateway/
// gateway_config.json) es "local". Expone:
//   GET  /health  -> { conectado }
//   GET  /qr      -> imagen PNG del QR (si aún no se ha escaneado)
//   POST /send    -> { to, type: "text"|"audio", text?, file? } envía un mensaje
//
// Uso:
//   node index.js
//   WHATSAPP_LOCAL_PORT=5051 GATEWAY_PORT=5050 node index.js

const path = require("path");
const fs = require("fs");
const express = require("express");
const QRCode = require("qrcode");
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");

const PORT = parseInt(process.env.WHATSAPP_LOCAL_PORT || "5051", 10);
const GATEWAY_PORT = parseInt(process.env.GATEWAY_PORT || "5050", 10);
const GATEWAY_URL = `http://localhost:${GATEWAY_PORT}/webhook/local`;

const DATA_DIR = __dirname;
const QR_PATH = path.join(DATA_DIR, "qr.png");
const TMP_DIR = path.join(DATA_DIR, "tmp");
if (!fs.existsSync(TMP_DIR)) fs.mkdirSync(TMP_DIR, { recursive: true });

let conectado = false;

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: path.join(DATA_DIR, ".wwebjs_auth") }),
  puppeteer: { headless: true, args: ["--no-sandbox", "--disable-setuid-sandbox"] },
});

client.on("qr", async (qr) => {
  conectado = false;
  try {
    await QRCode.toFile(QR_PATH, qr, { width: 320 });
    console.log("[whatsapp_local] QR generado en", QR_PATH);
  } catch (err) {
    console.error("[whatsapp_local] Error generando QR:", err);
  }
});

client.on("ready", () => {
  conectado = true;
  if (fs.existsSync(QR_PATH)) fs.unlinkSync(QR_PATH);
  console.log("[whatsapp_local] Conectado y listo.");
});

client.on("disconnected", (reason) => {
  conectado = false;
  console.warn("[whatsapp_local] Desconectado:", reason);
});

client.on("message", async (msg) => {
  if (msg.fromMe || msg.isStatus || msg.from.endsWith("@g.us")) return; // ignora eco propio, estados y grupos

  const payload = { from: msg.from, type: "texto", text: msg.body || "" };

  if (msg.hasMedia && (msg.type === "ptt" || msg.type === "audio")) {
    try {
      const media = await msg.downloadMedia();
      const ext = (media.mimetype || "audio/ogg").includes("ogg") ? "ogg" : "audio";
      const filePath = path.join(TMP_DIR, `audio_${Date.now()}.${ext}`);
      fs.writeFileSync(filePath, Buffer.from(media.data, "base64"));
      payload.type = "audio";
      payload.text = "";
      payload.file = filePath;
    } catch (err) {
      console.error("[whatsapp_local] Error descargando audio:", err);
      payload.type = "audio";
      payload.text = "[audio recibido: no se pudo descargar]";
    }
  }

  try {
    const res = await fetch(GATEWAY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) console.error("[whatsapp_local] Gateway respondió", res.status);
  } catch (err) {
    console.error("[whatsapp_local] No se pudo reenviar al gateway:", err.message);
  }
});

client.initialize();

// ---------------------------------------------------------------------------
// API HTTP local
// ---------------------------------------------------------------------------
const app = express();
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ conectado });
});

app.get("/qr", (_req, res) => {
  if (!fs.existsSync(QR_PATH)) {
    return res.status(404).json({ error: conectado ? "ya conectado, no hay QR" : "QR aún no generado" });
  }
  res.sendFile(QR_PATH);
});

app.post("/send", async (req, res) => {
  const { to, type, text, file } = req.body || {};
  if (!to) return res.status(400).json({ error: "falta 'to'" });
  if (!conectado) return res.status(503).json({ error: "sesión de WhatsApp no conectada" });

  const chatId = to.includes("@") ? to : `${to}@c.us`;

  try {
    if (type === "audio" && file) {
      const media = MessageMedia.fromFilePath(file);
      await client.sendMessage(chatId, media, { sendAudioAsVoice: true });
    } else {
      await client.sendMessage(chatId, text || "");
    }
    res.json({ enviado: true });
  } catch (err) {
    console.error("[whatsapp_local] Error enviando:", err);
    res.status(500).json({ enviado: false, error: String(err) });
  }
});

app.listen(PORT, "127.0.0.1", () => {
  console.log(`[whatsapp_local] API local en http://localhost:${PORT}`);
});
