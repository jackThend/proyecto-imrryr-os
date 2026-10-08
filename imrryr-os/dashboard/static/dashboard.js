
// --- Toast ---
let toastTimer = null;
function mostrarToast(msg, tipo) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + (tipo || 'success');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3500);
}

// --- Registro de Apps (cada sección es su propia app, con su agente) ---
const APPS = [
  { id: 'correo', nombre: 'Correo', icono: 'mail', agente: 'secretario', chatLabel: 'Agente Secretario', ayuda: 'Lee tu correo, resume lo importante y redacta respuestas — pero nunca envía nada sin que tú apruetes el borrador.' },
  { id: 'oportunidades', nombre: 'Oportunidades', icono: 'trophy', agente: 'investigador', chatLabel: 'Agente Investigador', ayuda: 'Busca fondos concursables y convocatorias relevantes para tu negocio.' },
  { id: 'ideas', nombre: 'Ideas', icono: 'bulb', agente: 'creativo', chatLabel: 'Agente Creativo', ayuda: 'Guarda y desarrolla tus ideas, como un Pinterest personal — de idea suelta a proyecto.' },
  { id: 'finanzas', nombre: 'Finanzas', icono: 'chart', agente: 'financiero', chatLabel: 'Asistente Financiero', ayuda: 'Lleva el control de tus gastos: los registra, los ordena por categoría y te da reportes.' },
  { id: 'crm', nombre: 'CRM', icono: 'users', agente: 'crm', chatLabel: 'Agente Comercial', ayuda: 'Gestiona clientes potenciales y te ayuda a redactar propuestas y cotizaciones.' },
  { id: 'seguridad', nombre: 'Seguridad', icono: 'shield', agente: 'guardia_seguridad', chatLabel: 'Guardia de Seguridad', ayuda: 'Vigila que los demás agentes no se atasquen ni gasten de más — funciona en silencio.' },
  { id: 'rrss', nombre: 'RRSS y Web', icono: 'globe', agente: 'rrss_web', chatLabel: 'Agente RRSS y Web', ayuda: 'Actualiza tu sitio web por GitHub y programa publicaciones en Instagram y Facebook.' },
  { id: 'compras', nombre: 'Compras', icono: 'cart', agente: 'compras', chatLabel: 'Agente de Compras', ayuda: 'Sigue el precio de productos en tiendas chilenas y te avisa por correo cuando encuentra ofertas.' },
  { id: 'agenda', nombre: 'Agenda', icono: 'calendar', agente: 'agenda', chatLabel: 'Agente de Agenda', ayuda: 'Agenda tus actividades y te dice qué tienes hoy, mañana o esta semana — puede avisarte por WhatsApp si se lo pides.' },
  { id: 'navegacion', nombre: 'Navegación', icono: 'search', agente: 'navegacion', chatLabel: 'Agente de Navegación', ayuda: 'Busca y lee contenido web, y te lo puede leer en voz alta mientras trabajas en otra parte del sistema.' },
  { id: 'codigo', nombre: 'Código', icono: 'terminal', agente: 'build', chatLabel: 'CTO Adjunto (Build)', ayuda: 'Entorno de desarrollo con permisos completos de OpenCode, comandos bash, edición directa y navegación por grafos AST.' },
  { id: 'reuniones', nombre: 'Reuniones', icono: 'mic', agente: 'reuniones', chatLabel: 'Agente de Reuniones', ayuda: 'Graba o sube audios de reuniones, genera minutas ejecutivas y crea mapas conceptuales en un canvas infinito interactivo.' },
  { id: 'ajustes', nombre: 'Ajustes', icono: 'gear', agente: null, ayuda: 'Configura WhatsApp, tu Perfil de Negocio y qué IA usan tus agentes.' },
  { id: 'modulos', nombre: 'Módulos', icono: 'modulos', agente: null, ayuda: 'Activa, desactiva o elimina agentes — protegido con contraseña.' },
];
const NAV_ITEMS = [{ id: 'inicio', nombre: 'Inicio', icono: 'home', ayuda: 'El punto de partida: un vistazo rápido a todo.' }, ...APPS];
function appPorId(id) { return APPS.find(a => a.id === id); }

function renderNavTabs() {
  document.getElementById('navTabs').innerHTML = NAV_ITEMS.map(a =>
    `<button class="nav-tab${a.id === 'inicio' ? ' active' : ''}" id="tab-${a.id}" onclick="abrirApp('${a.id}')" data-ayuda="${(a.ayuda || '').replace(/"/g,'&quot;')}"><svg class="icon"><use href="#icon-${a.icono}"/></svg>${a.nombre}</button>`
  ).join('');
}

// --- Chat genérico (reusado por el asistente principal y cada app-chat-panel) ---
const chatHistoriales = {};
const chatInicializados = new Set();
const chatOnSuccess = {};

function montarChatPanels() {
  document.querySelectorAll('.app-chat-panel[data-app]').forEach(panel => {
    const app = appPorId(panel.dataset.app);
    if (!app || !app.agente) return;
    const micBtn = app.id === 'navegacion'
      ? `<button id="micBtn_${app.id}" onclick="toggleGrabacionMic('${app.id}')" title="Grabar voz" data-ayuda="Graba tu voz y la transcribe para pedírselo al agente sin escribir."><svg class="icon"><use href="#icon-mic"/></svg></button>`
      : '';
    const audioPlayer = app.id === 'navegacion' ? `<div id="audioPlayer_${app.id}" style="margin-top:8px"></div>` : '';
    panel.innerHTML = `
      <span class="widget-title">${app.chatLabel}</span>
      <div class="chat-area">
        <div class="chat-msgs" id="chatMsgs_${app.id}"></div>
        <div class="chat-box">
          <input type="text" id="chatInp_${app.id}" placeholder="Escribe un mensaje..." autocomplete="off">
          ${micBtn}
          <button id="chatBtn_${app.id}">Enviar</button>
        </div>
        ${audioPlayer}
      </div>`;
  });
}

// --- Micrófono (módulo de Navegación): graba, transcribe con Whisper local y envía ---
let grabadorMicActivo = null;
let chunksGrabacionMic = [];

async function toggleGrabacionMic(appId) {
  const btn = document.getElementById('micBtn_' + appId);
  if (grabadorMicActivo && grabadorMicActivo.state === 'recording') {
    grabadorMicActivo.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    grabadorMicActivo = new MediaRecorder(stream);
    chunksGrabacionMic = [];
    grabadorMicActivo.ondataavailable = e => chunksGrabacionMic.push(e.data);
    grabadorMicActivo.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      btn.classList.remove('grabando');
      const blob = new Blob(chunksGrabacionMic, { type: 'audio/webm' });
      await transcribirYEnviarMic(appId, blob);
    };
    grabadorMicActivo.start();
    btn.classList.add('grabando');
  } catch (e) {
    mostrarToast('No se pudo acceder al micrófono: ' + e.message, 'error');
  }
}

async function transcribirYEnviarMic(appId, blob) {
  const inp = document.getElementById('chatInp_' + appId);
  const placeholderOriginal = inp.placeholder;
  inp.placeholder = 'Transcribiendo...';
  inp.disabled = true;
  try {
    const formData = new FormData();
    formData.append('archivo', blob, 'grabacion.webm');
    const r = await fetch('/api/navegacion/transcribir', { method: 'POST', body: formData });
    const d = await r.json();
    inp.disabled = false;
    if (d.ok && d.texto && d.texto.trim()) {
      inp.value = d.texto.trim();
      enviarChatGenerico(appId, 'navegacion');
    } else {
      mostrarToast('No se entendió el audio, intenta de nuevo', 'error');
    }
  } catch (e) {
    inp.disabled = false;
    mostrarToast('Error transcribiendo: ' + e.message, 'error');
  } finally {
    inp.placeholder = placeholderOriginal;
  }
}

async function revisarUltimoAudioNavegacion() {
  const el = document.getElementById('audioPlayer_navegacion');
  if (!el) return;
  try {
    const r = await fetch('/api/navegacion/ultimo-audio');
    const d = await r.json();
    if (!d.url || el.dataset.url === d.url) return;
    el.dataset.url = d.url;
    el.innerHTML = `<audio controls autoplay src="${d.url}" style="width:100%"></audio>`;
  } catch (e) { /* silencioso: no interrumpir el chat por esto */ }
}

function initChat(appId, agente, onSuccess) {
  if (onSuccess) chatOnSuccess[appId] = onSuccess;
  if (chatInicializados.has(appId)) return;
  chatInicializados.add(appId);
  const inp = document.getElementById('chatInp_' + appId);
  const btn = document.getElementById('chatBtn_' + appId);
  if (!inp || !btn) return;
  inp.addEventListener('keydown', e => { if (e.key === 'Enter') enviarChatGenerico(appId, agente); });
  btn.addEventListener('click', () => enviarChatGenerico(appId, agente));

  if (!chatHistoriales[appId] || chatHistoriales[appId].length === 0) {
    fetch('/api/chat/historial/' + agente)
      .then(r => r.json())
      .then(data => {
        if (data && data.mensajes && data.mensajes.length > 0) {
          chatHistoriales[appId] = data.mensajes.map(m => ({
            role: m.rol === 'user' ? 'user' : 'assistant',
            text: m.texto,
          }));
          renderChatGenerico(appId);
        }
      })
      .catch(() => {});
  }
}

function renderChatGenerico(appId) {
  const el = document.getElementById('chatMsgs_' + appId);
  if (!el) return;
  const hist = chatHistoriales[appId] || [];
  el.innerHTML = hist.map(m => m.role === 'thinking'
    ? '<div class="chat-msg thinking"><span class="dots"><span></span><span></span><span></span></span></div>'
    : `<div class="chat-msg ${m.role}">${m.text}</div>`).join('');
  el.scrollTop = el.scrollHeight;
}

async function enviarChatGenerico(appId, agente) {
  const inp = document.getElementById('chatInp_' + appId);
  const btn = document.getElementById('chatBtn_' + appId);
  const texto = inp.value.trim();
  if (!texto || btn.disabled) return;
  inp.value = '';
  const hist = chatHistoriales[appId] = chatHistoriales[appId] || [];
  hist.push({ role: 'user', text: texto });
  hist.push({ role: 'thinking', text: 'Pensando...' });
  renderChatGenerico(appId);
  btn.disabled = true;

  try {
    const r = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensaje: texto, agente }),
      signal: AbortSignal.timeout(window.IMRRYR_CONFIG.chatTimeoutMs),
    });

    if (!r.ok || !r.body) {
      throw new Error(`HTTP ${r.status}`);
    }

    const reader = r.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let streamText = '';
    const toolsUsadas = [];

    hist.pop();
    const assistantMsg = { role: 'assistant', text: '' };
    hist.push(assistantMsg);

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const dataStr = line.slice(6).trim();
        if (!dataStr) continue;
        try {
          const ev = JSON.parse(dataStr);
          if (ev.tipo === 'tool') {
            toolsUsadas.push(ev.tool);
            assistantMsg.text = `[🔧 Usando ${toolsUsadas.join(', ')}...]\n` + streamText;
            renderChatGenerico(appId);
          } else if (ev.tipo === 'token') {
            streamText += ev.texto;
            assistantMsg.text = (toolsUsadas.length > 0 ? `[🔧 Usé: ${toolsUsadas.join(', ')}]\n\n` : '') + streamText;
            renderChatGenerico(appId);
          } else if (ev.tipo === 'done') {
            assistantMsg.text = ev.respuesta;
            renderChatGenerico(appId);
            if (chatOnSuccess[appId]) chatOnSuccess[appId]();
          } else if (ev.tipo === 'error') {
            assistantMsg.role = 'error';
            assistantMsg.text = 'Error: ' + ev.error;
            renderChatGenerico(appId);
          }
        } catch {
          // chunk parcial
        }
      }
    }
  } catch (e) {
    hist.pop();
    hist.push({ role: 'error', text: 'Error de conexión: ' + e.message });
  }

  renderChatGenerico(appId);
  btn.disabled = false;
  inp.focus();
  if (hist.length > 40) chatHistoriales[appId] = hist.slice(-40);
}

// --- Navegación entre apps ---
const vistasInicializadas = new Set();

let vistaActivaActual = 'inicio';

let _acabaDeArrastrar = false;

function abrirApp(id) {
  if (_acabaDeArrastrar) return;
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.toggle('active', b.id === 'tab-' + id));
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + id));
  // Módulos vuelve a pedir la contraseña cada vez que se sale de la sección
  // — es una barrera de verdad, no un desbloqueo permanente de la pestaña.
  if (vistaActivaActual === 'modulos' && id !== 'modulos') {
    modulosDesbloqueado = false;
    modulosPasswordActual = null;
  }
  vistaActivaActual = id;
  if (!vistasInicializadas.has(id)) {
    inicializarVista(id);
    vistasInicializadas.add(id);
  }
  cargarVista(id);
}

function inicializarVista(id) {
  switch (id) {
    case 'inicio': initChat('inicio', 'asistente'); break;
    case 'ideas':
      initChat('ideas', 'creativo', cargarIdeasView);
      document.getElementById('ideasFiltroEstado').addEventListener('change', () => cargarIdeasView());
      break;
    case 'correo': initChat('correo', 'secretario'); break;
    case 'oportunidades': initChat('oportunidades', 'investigador', cargarOportunidadesView); break;
    case 'finanzas': initChat('finanzas', 'financiero'); break;
    case 'crm': initChat('crm', 'crm'); break;
    case 'seguridad': initChat('seguridad', 'guardia_seguridad'); break;
    case 'rrss': initChat('rrss', 'rrss_web', cargarRrssView); break;
    case 'compras': initChat('compras', 'compras', cargarComprasView); break;
    case 'agenda': initChat('agenda', 'agenda', cargarAgendaView); break;
    case 'navegacion': initChat('navegacion', 'navegacion', revisarUltimoAudioNavegacion); break;
    case 'codigo': initChat('codigo', 'build', cargarEstadoProyecto); break;
    case 'reuniones':
      initChat('reuniones', 'reuniones', cargarReunionesView);
      inicializarReunionesView();
      break;
  }
}

function cargarVista(id) {
  switch (id) {
    case 'inicio': cargarHome(); break;
    case 'ideas': cargarIdeasView(); break;
    case 'correo': cambiarSubtabCorreo(correoSubtabActual); break;
    case 'oportunidades': cargarOportunidadesView(); break;
    case 'finanzas': cargarFinanzasView(); break;
    case 'codigo': cargarEstadoProyecto(); break;
    case 'reuniones': cargarReunionesView(); break;
    case 'ajustes': cambiarSubtabAjustes(ajustesSubtabActual); break;
    case 'modulos': cargarModulosView(); break;
    case 'rrss': cargarRrssView(); break;
    case 'compras': cargarComprasView(); break;
    case 'agenda': cargarAgendaView(); break;
  }
}

// --- Home ---
// --- Inicio configurable: qué apps van de tarjeta grande (hero, máx 3) o
// chica (secundaria), guardado en localStorage (preferencia de este navegador,
// igual que el tema o el modo ayuda — no hace falta ida y vuelta al servidor). ---
const INICIO_PREFS_DEFAULT = {
  hero: ['correo', 'oportunidades', 'ideas'],
  secundaria: ['finanzas', 'crm', 'codigo', 'reuniones', 'ajustes', 'seguridad', 'modulos', 'rrss', 'compras', 'agenda', 'navegacion'],
};

function leerInicioPrefs() {
  try {
    const guardado = JSON.parse(localStorage.getItem('imrryr_inicio_prefs') || 'null');
    if (guardado && Array.isArray(guardado.hero) && Array.isArray(guardado.secundaria)) return guardado;
  } catch (e) { /* localStorage corrupto, usar default */ }
  return INICIO_PREFS_DEFAULT;
}

function guardarInicioPrefs(prefs) {
  localStorage.setItem('imrryr_inicio_prefs', JSON.stringify(prefs));
}

// Apps con un cargador de métrica en vivo hecho a medida — cualquier otra app
// elegida como tarjeta grande/chica usa el renderer genérico (ícono + título + Entrar).
const HERO_LOADERS = { correo: cargarHeroCorreoImpl, oportunidades: cargarHeroOportunidadesImpl, ideas: cargarHeroIdeasImpl };
const SECUNDARIA_SUB_ESTATICO = {
  crm: 'Clientes y propuestas', ajustes: 'WhatsApp y Perfil de Negocio', seguridad: 'Observabilidad del sistema',
  modulos: 'Gestiona tus agentes', rrss: 'GitHub + Instagram/Facebook', compras: 'Cotizador de productos',
  agenda: 'Tus actividades del día', navegacion: 'Busca y lee la web en voz alta',
  reuniones: 'Minutas, tareas y canvas conceptual',
};
const SECUNDARIA_LOADERS = { finanzas: cargarMiniFinanzasImpl };

function pintarHomeHeroEsqueleto(heroIds) {
  document.getElementById('homeHero').innerHTML = heroIds.map(id => {
    const app = appPorId(id);
    if (!app) return '';
    return `<div class="hero-card" id="hero-${id}" data-id="${id}" onclick="abrirApp('${id}')" data-ayuda="${app.ayuda || ''}"><div class="loading">Cargando</div></div>`;
  }).join('');
}

function cargarHeroGenerico(id) {
  const el = document.getElementById('hero-' + id);
  const app = appPorId(id);
  if (!el || !app) return;
  el.innerHTML = `<div class="hero-card-icon"><svg class="icon"><use href="#icon-${app.icono}"/></svg></div>
    <div class="hero-card-title">${app.nombre}</div>
    <div class="hero-card-sub">${app.ayuda || ''}</div>${CTA_HTML}`;
}

async function cargarHome() {
  const prefs = leerInicioPrefs();
  pintarHomeHeroEsqueleto(prefs.hero);
  prefs.hero.forEach(id => (HERO_LOADERS[id] || cargarHeroGenerico)(id));
  cargarHomeSecundaria(prefs.secundaria);
  setupHomeDragAndDrop();
}

const CTA_HTML = '<div class="hero-card-cta">Entrar <svg class="icon"><use href="#icon-arrow-right"/></svg></div>';

async function cargarHeroCorreoImpl() {
  const el = document.getElementById('hero-correo');
  try {
    const r = await fetch('/api/correo/borradores?estado=pendiente');
    const d = await r.json();
    const n = (d.borradores || []).length;
    el.innerHTML = `<div class="hero-card-icon"><svg class="icon"><use href="#icon-mail"/></svg></div>
      <div class="hero-card-title">Correo</div>
      <div class="hero-card-metric">${n}</div>
      <div class="hero-card-sub">${n === 1 ? 'borrador esperando tu revisión' : 'borradores esperando tu revisión'}</div>${CTA_HTML}`;
  } catch (e) {
    el.innerHTML = `<div class="hero-card-title">Correo</div><div class="hero-card-sub">Sin conexión</div>${CTA_HTML}`;
  }
}

async function cargarHeroOportunidadesImpl() {
  const el = document.getElementById('hero-oportunidades');
  try {
    const r = await fetch('/api/oportunidades?estado=nueva');
    const d = await r.json();
    const n = (d.oportunidades || []).length;
    el.innerHTML = `<div class="hero-card-icon"><svg class="icon"><use href="#icon-trophy"/></svg></div>
      <div class="hero-card-title">Oportunidades</div>
      <div class="hero-card-metric">${n}</div>
      <div class="hero-card-sub">${n === 1 ? 'fondo nuevo por revisar' : 'fondos nuevos por revisar'}</div>${CTA_HTML}`;
  } catch (e) {
    el.innerHTML = `<div class="hero-card-title">Oportunidades</div><div class="hero-card-sub">Sin conexión</div>${CTA_HTML}`;
  }
}

async function cargarHeroIdeasImpl() {
  const el = document.getElementById('hero-ideas');
  try {
    const r = await fetch('/api/semillas');
    const d = await r.json();
    const todas = d.semillas || [];
    const thumbs = todas.slice(0, 4).map(s => s.primer_adjunto
      ? `<img class="hero-preview-thumb" src="${s.primer_adjunto}">`
      : `<div class="hero-preview-thumb" style="display:flex;align-items:center;justify-content:center">&#128161;</div>`
    ).join('');
    el.innerHTML = `<div class="hero-card-icon"><svg class="icon"><use href="#icon-bulb"/></svg></div>
      <div class="hero-card-title">Ideas</div>
      <div class="hero-card-metric">${todas.length}</div>
      <div class="hero-card-sub">ideas guardadas</div>
      <div class="hero-preview-row">${thumbs}</div>${CTA_HTML}`;
  } catch (e) {
    el.innerHTML = `<div class="hero-card-title">Ideas</div><div class="hero-card-sub">Sin conexión</div>${CTA_HTML}`;
  }
}

async function cargarMiniFinanzasImpl() {
  const el = document.getElementById('mini-finanzas-sub');
  if (!el) return;
  try {
    const r = await fetch('/api/finanzas');
    const d = await r.json();
    el.textContent = `Total registrado: ${fmtCLP(d.total)}`;
  } catch {
    el.textContent = 'Sin datos';
  }
}

function cargarHomeSecundaria(secundariaIds) {
  document.getElementById('homeSecondary').innerHTML = secundariaIds.map(id => {
    const app = appPorId(id);
    if (!app) return '';
    const subInicial = SECUNDARIA_LOADERS[id] ? 'Cargando…' : (SECUNDARIA_SUB_ESTATICO[id] || '');
    return `<div class="mini-card" id="mini-${id}" data-id="${id}" onclick="abrirApp('${id}')" data-ayuda="${app.ayuda || ''}">
      <div class="mini-card-icon"><svg class="icon"><use href="#icon-${app.icono}"/></svg></div>
      <div class="mini-card-body"><div class="mini-card-title">${app.nombre}</div><div class="mini-card-sub" id="mini-${id}-sub">${subInicial}</div></div>
    </div>`;
  }).join('');
  secundariaIds.forEach(id => { if (SECUNDARIA_LOADERS[id]) SECUNDARIA_LOADERS[id](); });
}

function setupHomeDragAndDrop() {
  const heroEl = document.getElementById('homeHero');
  const secEl = document.getElementById('homeSecondary');
  if (!heroEl || !secEl) return;

  function bindCard(card, zone) {
    card.setAttribute('draggable', 'true');
    card.addEventListener('dragstart', (e) => {
      _acabaDeArrastrar = true;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', JSON.stringify({ id: card.dataset.id, zone }));
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      document.querySelectorAll('.hero-card, .mini-card').forEach(c => c.classList.remove('drag-over'));
      setTimeout(() => { _acabaDeArrastrar = false; }, 150);
    });
    card.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      card.classList.add('drag-over');
    });
    card.addEventListener('dragleave', () => {
      card.classList.remove('drag-over');
    });
    card.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      card.classList.remove('drag-over');
      try {
        const raw = e.dataTransfer.getData('text/plain');
        if (!raw) return;
        const src = JSON.parse(raw);
        const targetId = card.dataset.id;
        if (!src.id || src.id === targetId) return;
        reordenarCardsHome(src.id, src.zone, targetId, zone);
      } catch (err) {
        console.error('Error en drop de card:', err);
      }
    });
  }

  heroEl.querySelectorAll('.hero-card').forEach(c => bindCard(c, 'hero'));
  secEl.querySelectorAll('.mini-card').forEach(c => bindCard(c, 'secundaria'));

  [heroEl, secEl].forEach(container => {
    const zone = container === heroEl ? 'hero' : 'secundaria';
    container.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    });
    container.addEventListener('drop', (e) => {
      e.preventDefault();
      if (e.target.closest('.hero-card, .mini-card')) return;
      try {
        const raw = e.dataTransfer.getData('text/plain');
        if (!raw) return;
        const src = JSON.parse(raw);
        if (!src.id) return;
        reordenarCardsHome(src.id, src.zone, null, zone);
      } catch (err) {
        console.error('Error en drop de contenedor:', err);
      }
    });
  });
}

function reordenarCardsHome(srcId, srcZone, targetId, targetZone) {
  const prefs = leerInicioPrefs();
  if (srcZone === targetZone) {
    const list = targetZone === 'hero' ? prefs.hero : prefs.secundaria;
    const oldIdx = list.indexOf(srcId);
    if (oldIdx !== -1) list.splice(oldIdx, 1);
    const newIdx = targetId ? list.indexOf(targetId) : list.length;
    if (newIdx !== -1) {
      list.splice(newIdx, 0, srcId);
    } else {
      list.push(srcId);
    }
  } else if (srcZone === 'secundaria' && targetZone === 'hero') {
    if (prefs.hero.length >= 3 && targetId) {
      const hIdx = prefs.hero.indexOf(targetId);
      const sIdx = prefs.secundaria.indexOf(srcId);
      if (hIdx !== -1 && sIdx !== -1) {
        prefs.hero[hIdx] = srcId;
        prefs.secundaria[sIdx] = targetId;
      }
    } else {
      prefs.secundaria = prefs.secundaria.filter(x => x !== srcId);
      const newIdx = targetId ? prefs.hero.indexOf(targetId) : prefs.hero.length;
      if (prefs.hero.length >= 3) {
        const expulsado = prefs.hero.pop();
        prefs.secundaria.unshift(expulsado);
      }
      if (newIdx !== -1 && newIdx < prefs.hero.length) {
        prefs.hero.splice(newIdx, 0, srcId);
      } else {
        prefs.hero.push(srcId);
      }
    }
  } else if (srcZone === 'hero' && targetZone === 'secundaria') {
    if (prefs.hero.length <= 1) {
      mostrarToast('Debe haber al menos 1 tarjeta grande', 'info');
      return;
    }
    prefs.hero = prefs.hero.filter(x => x !== srcId);
    const newIdx = targetId ? prefs.secundaria.indexOf(targetId) : prefs.secundaria.length;
    if (newIdx !== -1) {
      prefs.secundaria.splice(newIdx, 0, srcId);
    } else {
      prefs.secundaria.push(srcId);
    }
  }
  guardarInicioPrefs(prefs);
  cargarHome();
  mostrarToast('Diseño de Inicio actualizado', 'success');
}

// Formato chileno de dinero: 29900 -> "$29.900" (punto de miles, sin decimales)
function fmtCLP(n) {
  return '$' + Math.round(n || 0).toLocaleString('es-CL');
}

// --- Helper de gráficos propio (sin dependencias externas) ---
function dibujarBarras(el, datos) {
  if (!datos.length) { el.innerHTML = '<div class="empty">Sin datos</div>'; return; }
  const max = Math.max(...datos.map(d => d.valor), 1);
  el.innerHTML = '<div style="display:flex;flex-direction:column;gap:7px">' + datos.map(d => {
    const pct = Math.max((d.valor / max) * 100, 2);
    return `<div style="display:flex;align-items:center;gap:8px">
      <div style="width:100px;font-size:11px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${d.etiqueta}</div>
      <div style="flex:1;background:var(--surface2);border-radius:4px;overflow:hidden;height:16px">
        <div style="width:${pct}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:4px"></div>
      </div>
      <div style="width:70px;text-align:right;font-size:11px">${fmtCLP(d.valor)}</div>
    </div>`;
  }).join('') + '</div>';
}

function dibujarLineas(el, datos) {
  if (!datos.length) { el.innerHTML = '<div class="empty">Sin datos</div>'; return; }
  const ancho = 600, alto = 150, pad = 30;
  const max = Math.max(...datos.map(d => d.valor), 1);
  const pasoX = datos.length > 1 ? (ancho - pad * 2) / (datos.length - 1) : 0;
  const puntos = datos.map((d, i) => [pad + i * pasoX, alto - pad - (d.valor / max) * (alto - pad * 2)]);
  const linea = puntos.map(([x, y]) => `${x},${y}`).join(' ');
  const area = `${pad},${alto - pad} ${linea} ${puntos[puntos.length - 1][0]},${alto - pad}`;
  const etiquetas = datos.map((d, i) => `<text x="${puntos[i][0]}" y="${alto - 8}" font-size="9" fill="var(--text-dim)" text-anchor="middle">${(d.etiqueta || '').slice(5)}</text>`).join('');
  const circulos = puntos.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="3" fill="var(--accent2)"/>`).join('');
  el.innerHTML = `<svg viewBox="0 0 ${ancho} ${alto}" style="width:100%;height:150px">
    <polygon points="${area}" fill="rgba(124,111,240,0.15)" stroke="none"/>
    <polyline points="${linea}" fill="none" stroke="var(--accent)" stroke-width="2"/>
    ${circulos}${etiquetas}
  </svg>`;
}

// --- Finanzas (app completa: sub-tabs Actual/Histórico, edición inline) ---
// El filtro de año elegido se guarda en localStorage: es la "vista guardada"
// (no una página congelada — siempre consulta SQLite en vivo, así que nunca
// queda desactualizada ni hay que recalcular nada con IA).
let finanzasSubtabActual = 'actual';
let finanzasFiltroAnio = localStorage.getItem('imrryr_finanzas_anio') || '';
let gastoEnEdicionId = null;

function cargarFinanzasView() {
  cambiarSubtabFinanzas(finanzasSubtabActual);
}

function cambiarSubtabFinanzas(sub) {
  finanzasSubtabActual = sub;
  document.getElementById('finSub-actual').classList.toggle('active', sub === 'actual');
  document.getElementById('finSub-historico').classList.toggle('active', sub === 'historico');
  gastoEnEdicionId = null;
  if (sub === 'actual') cargarFinanzasActual(); else cargarFinanzasHistorico();
}

async function cargarFinanzasActual() {
  const el = document.getElementById('finanzasSubcontent');
  if (!el) return;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const r = await fetch('/api/finanzas?limite=15');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const cats = Object.entries(d.por_categoria || {});
    let html = '<div id="finImportadorBox" style="margin-bottom:14px"></div>';
    html += `<div class="metric-row"><span class="metric-label">Total registrado</span><span class="metric-value" style="font-size:22px;font-family:var(--font-display)">${fmtCLP(d.total)}</span></div>`;
    html += cats.length ? '<div id="finCategoriasChart" style="margin:14px 0"></div>' : '<div class="empty">Sin gastos registrados</div>';
    html += tablaGastosHtml(d.gastos || []);
    el.innerHTML = html;
    if (cats.length) dibujarBarras(document.getElementById('finCategoriasChart'), cats.map(([cat, info]) => ({ etiqueta: cat, valor: info.subtotal })));
    cargarImportadorFinanzas();
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

// --- Importación histórica de correos bancarios (ver finanzas/importador_historico.py) ---
let finImportadorPollTimer = null;

async function cargarImportadorFinanzas() {
  const box = document.getElementById('finImportadorBox');
  if (!box) return;
  try {
    const r = await fetch('/api/finanzas/importar/estado');
    const d = await r.json();
    renderImportadorFinanzas(d.importacion);
  } catch (e) {
    box.innerHTML = '';
  }
}

function renderImportadorFinanzas(importacion) {
  const box = document.getElementById('finImportadorBox');
  if (!box) return;
  clearTimeout(finImportadorPollTimer);

  if (!importacion || importacion.estado === 'cancelada') {
    box.innerHTML = `
      <div class="seed-item" style="display:block">
        <div style="font-weight:600;margin-bottom:4px">¿Importar tu historial bancario?</div>
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">Podemos revisar tus correos bancarios y traer todos tus gastos pasados, no solo los nuevos. Primero calculamos cuántos correos hay antes de empezar — no se importa nada todavía.</div>
        <div id="finImportadorEstimadoBox"></div>
        <button class="gw-save-btn" onclick="estimarImportacionFinanzas()" data-ayuda="Calcula cuántos correos bancarios hay, sin traerlos todavía.">Calcular cuántos hay</button>
      </div>`;
    return;
  }

  if (importacion.estado === 'en_progreso' || importacion.estado === 'pendiente') {
    const pct = importacion.total_estimado ? Math.min(100, Math.round(importacion.procesados / importacion.total_estimado * 100)) : 0;
    box.innerHTML = `
      <div class="seed-item" style="display:block">
        <div style="font-weight:600;margin-bottom:6px">Importando tu historial bancario…</div>
        <div style="background:var(--surface2);border-radius:6px;overflow:hidden;height:10px;margin-bottom:6px">
          <div style="width:${pct}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2))"></div>
        </div>
        <div style="font-size:12px;color:var(--text-dim)">Procesados ${importacion.procesados} de ~${importacion.total_estimado} — ${importacion.agregados} gastos agregados</div>
        <button class="gw-modo-btn" style="margin-top:8px" onclick="cancelarImportacionFinanzas(${importacion.id})" data-ayuda="Detiene la importación. Lo que ya se agregó queda guardado.">Cancelar</button>
      </div>`;
    finImportadorPollTimer = setTimeout(cargarImportadorFinanzas, 4000);
    return;
  }

  if (importacion.estado === 'pausada_cuota') {
    box.innerHTML = `
      <div class="seed-item" style="display:block">
        <div style="font-weight:600;margin-bottom:6px;color:var(--yellow)">Pausado por el límite de tu proveedor de IA</div>
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">Llevamos ${importacion.procesados} de ~${importacion.total_estimado} correos (${importacion.agregados} gastos agregados). Va a seguir solo más tarde — o puedes activar temporalmente una cuenta de pago en <b>Ajustes → Cuentas de IA</b> para que termine altiro.</div>
        <button class="gw-save-btn" onclick="reintentarImportacionFinanzas()">Reintentar ahora</button>
      </div>`;
    finImportadorPollTimer = setTimeout(cargarImportadorFinanzas, 15000);
    return;
  }

  if (importacion.estado === 'completada') {
    cargarInformeImportacionFinanzas(importacion);
  }
}

async function cargarInformeImportacionFinanzas(importacion) {
  const box = document.getElementById('finImportadorBox');
  if (!box) return;
  try {
    const r = await fetch('/api/finanzas/importar/informe');
    const d = await r.json();
    const bancos = d.bancos || [];
    box.innerHTML = `
      <div class="seed-item" style="display:block">
        <div style="font-weight:600;margin-bottom:4px">Historial importado ✓</div>
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">${importacion.agregados} gastos agregados de ${importacion.procesados} correos revisados.</div>
        ${bancos.length ? bancos.map(b => `<div style="display:flex;justify-content:space-between;font-size:12px;padding:3px 0"><span>${b.banco}</span><span>${b.cantidad} · ${fmtCLP(b.total)}</span></div>`).join('') : ''}
        <button class="gw-modo-btn" style="margin-top:8px" onclick="iniciarImportacionFinanzas()" data-ayuda="Busca correos bancarios nuevos que hayan llegado después.">Buscar correos nuevos</button>
      </div>`;
  } catch (e) {
    box.innerHTML = '';
  }
}

async function estimarImportacionFinanzas() {
  const cont = document.getElementById('finImportadorEstimadoBox');
  if (cont) cont.innerHTML = '<div class="loading">Calculando</div>';
  try {
    const r = await fetch('/api/finanzas/importar/estimar', { method: 'POST' });
    const d = await r.json();
    if (!d.ok) {
      if (cont) cont.innerHTML = `<div class="empty">${d.error || 'No se pudo calcular'}</div>`;
      return;
    }
    const mensaje = d.estimado > 150
      ? `Encontramos ~${d.estimado} correos. Con el límite gratuito de IA esto puede tomar varios días — seguirá solo y avisamos el avance cada vez que entres. Si quieres que sea inmediato, activa una cuenta de pago en Ajustes → Cuentas de IA.`
      : `Encontramos ~${d.estimado} correos. Esto debería tardar solo unos minutos.`;
    if (cont) cont.innerHTML = `<div style="font-size:12px;margin:8px 0">${mensaje}</div><button class="gw-save-btn" onclick="iniciarImportacionFinanzas()">Importar ahora</button>`;
  } catch (e) {
    if (cont) cont.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

async function iniciarImportacionFinanzas() {
  try {
    await fetch('/api/finanzas/importar/iniciar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
    });
    mostrarToast('Importación iniciada', 'success');
    cargarImportadorFinanzas();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function reintentarImportacionFinanzas() {
  await iniciarImportacionFinanzas();
}

async function cancelarImportacionFinanzas(id) {
  try {
    await fetch('/api/finanzas/importar/cancelar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ importacion_id: id }),
    });
    mostrarToast('Importación cancelada', 'success');
    cargarImportadorFinanzas();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function cargarFinanzasHistorico() {
  const el = document.getElementById('finanzasSubcontent');
  if (!el) return;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const qs = (finanzasFiltroAnio ? `desde=${finanzasFiltroAnio}-01-01&hasta=${finanzasFiltroAnio}-12-31&` : '') + 'limite=100000';
    const r = await fetch('/api/finanzas?' + qs);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const anios = d.anios_disponibles || [];
    const meses = Object.entries(d.por_mes || {});

    let html = '<div class="app-toolbar">';
    if (anios.length) {
      html += `<select id="finAnioSel" style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:5px 8px">
        <option value="">Todos los años</option>
        ${anios.map(a => `<option value="${a}" ${a === finanzasFiltroAnio ? 'selected' : ''}>${a}</option>`).join('')}
      </select>`;
    }
    html += `<button class="gw-save-btn" onclick="exportarFinanzasCsv()" data-ayuda="Descarga estos gastos en una planilla CSV."><svg class="icon"><use href="#icon-download"/></svg> Exportar CSV</button>`;
    html += `<button class="gw-save-btn" onclick="window.print()" data-ayuda="Abre el diálogo de impresión con un informe limpio — puedes guardarlo como PDF."><svg class="icon"><use href="#icon-print"/></svg> Imprimir informe</button>`;
    html += '</div>';
    html += `<div class="metric-row"><span class="metric-label">Total${finanzasFiltroAnio ? ' ' + finanzasFiltroAnio : ''}</span><span class="metric-value" style="font-size:22px;font-family:var(--font-display)">${fmtCLP(d.total)}</span></div>`;
    html += meses.length ? '<div id="finMensualChart" style="margin:14px 0"></div>' : '<div class="empty">Sin datos mensuales</div>';
    html += tablaGastosHtml(d.gastos || []);
    el.innerHTML = html;

    if (meses.length) dibujarLineas(document.getElementById('finMensualChart'), meses.map(([mes, valor]) => ({ etiqueta: mes, valor })));

    const sel = document.getElementById('finAnioSel');
    if (sel) sel.addEventListener('change', () => {
      finanzasFiltroAnio = sel.value;
      localStorage.setItem('imrryr_finanzas_anio', finanzasFiltroAnio);
      cargarFinanzasHistorico();
    });
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function exportarFinanzasCsv() {
  const qs = finanzasFiltroAnio ? `?desde=${finanzasFiltroAnio}-01-01&hasta=${finanzasFiltroAnio}-12-31` : '';
  window.location.href = '/api/finanzas/export' + qs;
}

function tablaGastosHtml(gastos) {
  if (!gastos.length) return '';
  return `<div style="margin-top:10px"><span class="widget-title">Gastos</span><div style="margin-top:6px">` +
    gastos.map(g => filaGastoHtml(g)).join('') + `</div></div>`;
}

function filaGastoHtml(g) {
  if (gastoEnEdicionId === g.id) {
    return `<div class="seed-item" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
      <input id="edComercio_${g.id}" value="${(g.comercio || '').replace(/"/g,'&quot;')}" style="width:130px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:4px 6px">
      <input id="edCategoria_${g.id}" value="${(g.categoria || '').replace(/"/g,'&quot;')}" style="width:110px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:4px 6px">
      <input id="edMonto_${g.id}" type="number" value="${g.monto}" style="width:90px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:4px 6px">
      <button class="gw-save-btn" onclick="guardarEdicionGasto(${g.id})">Guardar</button>
      <button class="gw-modo-btn" onclick="cancelarEdicionGasto()">Cancelar</button>
    </div>`;
  }
  return `<div class="seed-item" style="display:flex;justify-content:space-between;align-items:center;gap:6px">
    <div><b>${g.comercio}</b> — ${fmtCLP(g.monto)} <span style="color:var(--text-dim)">(${g.categoria}, ${g.fecha})</span></div>
    <div style="display:flex;gap:4px;flex-shrink:0">
      <button class="gw-modo-btn" onclick="editarGasto(${g.id})" data-ayuda="Corrige el nombre, la categoría o el monto de este gasto."><svg class="icon"><use href="#icon-edit"/></svg></button>
      <button class="gw-modo-btn" onclick="borrarGasto(${g.id})" data-ayuda="Elimina este gasto por completo."><svg class="icon"><use href="#icon-trash"/></svg></button>
    </div>
  </div>`;
}

function editarGasto(id) {
  gastoEnEdicionId = id;
  if (finanzasSubtabActual === 'actual') cargarFinanzasActual(); else cargarFinanzasHistorico();
}

function cancelarEdicionGasto() {
  gastoEnEdicionId = null;
  if (finanzasSubtabActual === 'actual') cargarFinanzasActual(); else cargarFinanzasHistorico();
}

async function guardarEdicionGasto(id) {
  const comercio = document.getElementById(`edComercio_${id}`).value.trim();
  const categoria = document.getElementById(`edCategoria_${id}`).value.trim();
  const monto = parseFloat(document.getElementById(`edMonto_${id}`).value);
  try {
    const r = await fetch(`/api/finanzas/gastos/${id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comercio, categoria, monto }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    gastoEnEdicionId = null;
    mostrarToast('Gasto actualizado', 'success');
    if (finanzasSubtabActual === 'actual') cargarFinanzasActual(); else cargarFinanzasHistorico();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function borrarGasto(id) {
  try {
    await fetch(`/api/finanzas/gastos/${id}`, { method: 'DELETE' });
    mostrarToast('Gasto eliminado', 'success');
    if (finanzasSubtabActual === 'actual') cargarFinanzasActual(); else cargarFinanzasHistorico();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Gateway WhatsApp (Local/QR o Cloud API) — vive dentro de Ajustes ---
const GATEWAY_URL = 'http://localhost:5050';
let gwConfigActual = null;
let gwRefreshTimer = null;

async function cargarGateway() {
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  try {
    const r = await fetch(GATEWAY_URL + '/api/gateway/config');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    gwConfigActual = await r.json();
    if (ajustesSubtabActual !== 'whatsapp') return; // el usuario ya cambió de sub-tab mientras esperábamos
    renderGateway();
  } catch (e) {
    if (ajustesSubtabActual !== 'whatsapp') return; // idem: no pisar otra sub-tab con un error atrasado
    el.innerHTML = `<div class="widget-error">Gateway no disponible: ${e.message}</div>`;
  }
}

function renderGateway() {
  if (ajustesSubtabActual !== 'whatsapp') return;
  const el = document.getElementById('ajustesSubcontent');
  if (!el || !gwConfigActual) return;
  const modo = gwConfigActual.modo;
  let html = `<div style="display:flex;gap:6px;margin-bottom:10px">
    <button class="gw-modo-btn ${modo === 'local' ? 'active' : ''}" onclick="cambiarModoGateway('local')">Local (QR)</button>
    <button class="gw-modo-btn ${modo === 'cloud' ? 'active' : ''}" onclick="cambiarModoGateway('cloud')">Cloud API</button>
  </div>`;

  if (modo === 'local') {
    const conectado = !!(gwConfigActual.local && gwConfigActual.local.conectado);
    html += `<div style="font-size:11px;margin-bottom:6px">Estado: <span style="color:${conectado ? 'var(--accent2)' : 'var(--yellow)'}">${conectado ? 'Conectado' : 'Esperando escaneo de QR'}</span></div>`;
    if (!conectado) {
      html += `<div class="gw-qr"><img id="gwQrImg" src="${GATEWAY_URL}/api/gateway/qr?_=${Date.now()}" onerror="this.style.display='none'; document.getElementById('gwQrMsg').style.display='block'"></div>
        <div class="empty" id="gwQrMsg" style="display:none">QR aún no disponible. Verifica que el sidecar (gateway/whatsapp_local) esté corriendo.</div>`;
    }
  } else {
    const cloud = gwConfigActual.cloud || {};
    html += `
      <div class="gw-field"><label>Phone Number ID</label><input id="gwPhoneId" value="${cloud.phone_number_id || ''}"></div>
      <div class="gw-field"><label>Access Token</label><input id="gwToken" type="password" placeholder="${cloud.access_token || 'sin configurar'}"></div>
      <div class="gw-field"><label>Verify Token</label><input id="gwVerify" value="${cloud.verify_token || ''}"></div>
      <button class="gw-save-btn" onclick="guardarGatewayCloud()">Guardar credenciales</button>
    `;
  }
  el.innerHTML = html;

  clearTimeout(gwRefreshTimer);
  const vistaActiva = document.getElementById('view-ajustes').classList.contains('active') && ajustesSubtabActual === 'whatsapp';
  if (vistaActiva && modo === 'local' && !(gwConfigActual.local && gwConfigActual.local.conectado)) {
    gwRefreshTimer = setTimeout(cargarGateway, 5000);
  }
}

async function cambiarModoGateway(modo) {
  try {
    const r = await fetch(GATEWAY_URL + '/api/gateway/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modo }),
    });
    gwConfigActual = await r.json();
    renderGateway();
    mostrarToast('Modo WhatsApp: ' + modo, 'success');
  } catch (e) {
    mostrarToast('Error cambiando modo: ' + e.message, 'error');
  }
}

async function guardarGatewayCloud() {
  const cloud = {
    phone_number_id: document.getElementById('gwPhoneId').value.trim(),
    verify_token: document.getElementById('gwVerify').value.trim(),
  };
  const token = document.getElementById('gwToken').value.trim();
  if (token) cloud.access_token = token;
  try {
    const r = await fetch(GATEWAY_URL + '/api/gateway/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cloud }),
    });
    gwConfigActual = await r.json();
    renderGateway();
    mostrarToast('Credenciales guardadas', 'success');
  } catch (e) {
    mostrarToast('Error guardando: ' + e.message, 'error');
  }
}

// --- Perfil de Negocio (usado por el Investigador para filtrar fondos relevantes) ---
let perfilNegocioActual = null;

async function cargarPerfilNegocio() {
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  try {
    const r = await fetch('/api/perfil-negocio');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    perfilNegocioActual = await r.json();
    if (ajustesSubtabActual !== 'perfil') return; // el usuario ya cambió de sub-tab mientras esperábamos
    renderPerfilNegocio();
  } catch (e) {
    if (ajustesSubtabActual !== 'perfil') return;
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function renderPerfilNegocio() {
  if (ajustesSubtabActual !== 'perfil') return;
  const el = document.getElementById('ajustesSubcontent');
  if (!el || !perfilNegocioActual) return;
  const p = perfilNegocioActual;
  const empresas = Array.isArray(p.empresas) ? p.empresas : [];
  const extras = Object.entries(p.caracteristicas_extra || {});

  let empresasHtml = empresas.map((emp, idx) => `
    <div style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:8px;margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
        <strong style="font-size:13px">${emp.nombre || 'Empresa #' + (idx+1)}</strong>
        <span style="cursor:pointer;color:var(--red);font-size:12px" onclick="quitarEmpresaPerfil(${idx})">✕ Eliminar</span>
      </div>
      <div style="font-size:12px;color:var(--text-dim)">${emp.descripcion || emp.giro || 'Sin descripción'}</div>
    </div>
  `).join('');

  let html = `
    <div class="gw-field">
      <label>Tu Nombre (cómo te llaman los agentes)</label>
      <input id="pnNombreUsuario" value="${(p.nombre_usuario || '').replace(/"/g, '&quot;')}" placeholder="ej. Carlos">
    </div>

    <div class="gw-field" style="margin-top:14px">
      <label>Tus Empresas o Proyectos Activos</label>
      <div id="listaEmpresasPerfil">${empresasHtml || '<div style="font-size:12px;color:var(--text-dim);margin-bottom:8px">No hay empresas registradas aún.</div>'}</div>
      <div style="display:flex;flex-direction:column;gap:6px;background:var(--surface1);padding:8px;border-radius:8px;border:1px dashed var(--border)">
        <input id="pnNuevaEmpresaNombre" placeholder="Nombre de la empresa (ej. Estudio Creativo SpA)" class="gw-inline-input">
        <input id="pnNuevaEmpresaDesc" placeholder="Qué hace (ej. Consultoría en museografía y software)" class="gw-inline-input">
        <button class="gw-save-btn" style="align-self:flex-start" onclick="agregarEmpresaPerfil()">+ Agregar Empresa</button>
      </div>
    </div>

    <div class="gw-field" style="margin-top:14px"><label>Giro General (separado por comas)</label><input id="pnGiro" value="${(p.giro || []).join(', ')}"></div>
    <div class="gw-field"><label>Región</label><input id="pnRegion" value="${(p.ubicacion && p.ubicacion.region) || ''}"></div>
    <div class="gw-field"><label>Comuna</label><input id="pnComuna" value="${(p.ubicacion && p.ubicacion.comuna) || ''}"></div>
    <div class="gw-field"><label>Tamaño de empresa</label><input id="pnTamano" value="${p.tamano_empresa || ''}" placeholder="micro, pequeña, mediana..."></div>
  `;
  if (extras.length) {
    html += '<div style="margin:8px 0;font-size:12px"><label>Reglas y Preferencias fijas:</label><div style="margin-top:4px">' + extras.map(([k, v]) =>
      `<span class="tag" style="margin:2px">${k}: ${v} <span style="cursor:pointer" onclick="quitarCaracteristica('${k.replace(/'/g, "\\'")}')">&times;</span></span>`
    ).join('') + '</div></div>';
  }
  html += `
    <div style="display:flex;gap:6px;margin-top:6px">
      <input id="pnNuevaClave" placeholder="regla o preferencia (ej. horario)" class="gw-inline-input">
      <input id="pnNuevoValor" placeholder="valor (ej. solo mañanas)" class="gw-inline-input">
      <button class="gw-save-btn" onclick="agregarCaracteristica()">+</button>
    </div>
    <button class="gw-save-btn" style="margin-top:12px" onclick="guardarPerfilNegocio()">Guardar perfil completo</button>
  `;
  el.innerHTML = html;
}

async function agregarEmpresaPerfil() {
  const nom = document.getElementById('pnNuevaEmpresaNombre').value.trim();
  const desc = document.getElementById('pnNuevaEmpresaDesc').value.trim();
  if (!nom) {
    mostrarToast('Ingresa el nombre de la empresa', 'error');
    return;
  }
  const empresas = Array.isArray(perfilNegocioActual.empresas) ? [...perfilNegocioActual.empresas] : [];
  empresas.push({ nombre: nom, descripcion: desc, giro: desc });
  try {
    const r = await fetch('/api/perfil-negocio', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ empresas }),
    });
    perfilNegocioActual = await r.json();
    renderPerfilNegocio();
    mostrarToast('Empresa agregada', 'success');
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function quitarEmpresaPerfil(idx) {
  const empresas = (perfilNegocioActual.empresas || []).filter((_, i) => i !== idx);
  try {
    const r = await fetch('/api/perfil-negocio', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ empresas }),
    });
    perfilNegocioActual = await r.json();
    renderPerfilNegocio();
    mostrarToast('Empresa eliminada', 'info');
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function guardarPerfilNegocio() {
  const datos = {
    nombre_usuario: document.getElementById('pnNombreUsuario') ? document.getElementById('pnNombreUsuario').value.trim() : '',
    giro: document.getElementById('pnGiro').value.split(',').map(s => s.trim()).filter(Boolean),
    ubicacion: {
      region: document.getElementById('pnRegion').value.trim(),
      comuna: document.getElementById('pnComuna').value.trim(),
    },
    tamano_empresa: document.getElementById('pnTamano').value.trim(),
  };
  try {
    const r = await fetch('/api/perfil-negocio', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    perfilNegocioActual = await r.json();
    renderPerfilNegocio();
    mostrarToast('Perfil guardado', 'success');
  } catch (e) {
    mostrarToast('Error guardando perfil: ' + e.message, 'error');
  }
}

async function agregarCaracteristica() {
  const clave = document.getElementById('pnNuevaClave').value.trim();
  const valor = document.getElementById('pnNuevoValor').value.trim();
  if (!clave) return;
  try {
    const r = await fetch('/api/perfil-negocio', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caracteristicas_extra: { [clave]: valor } }),
    });
    perfilNegocioActual = await r.json();
    renderPerfilNegocio();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function quitarCaracteristica(clave) {
  try {
    const r = await fetch('/api/perfil-negocio', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caracteristicas_extra: { [clave]: null } }),
    });
    perfilNegocioActual = await r.json();
    renderPerfilNegocio();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Cuentas de IA (qué proveedor/modelo usan todos los agentes) ---
let cuentasIaLista = [];
let cuentasIaProveedores = {};
let cuentasIaMostrarForm = false;
let cuentasGitLista = [];
let cuentasGitMostrarForm = false;
let cuentasSocialLista = [];
let cuentasSocialMostrarForm = false;

async function cargarCuentasIaView() {
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  try {
    const r = await fetch('/api/ajustes/cuentas-ia');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    cuentasIaLista = d.cuentas || [];
    cuentasIaProveedores = d.proveedores || {};
    if (ajustesSubtabActual !== 'ia') return; // el usuario ya cambió de sub-tab mientras esperábamos
    renderCuentasIaView();
  } catch (e) {
    if (ajustesSubtabActual !== 'ia') return;
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function renderCuentasIaView() {
  if (ajustesSubtabActual !== 'ia') return;
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  let html = '<p style="font-size:12px;color:var(--text-dim);margin-bottom:10px">Elige qué proveedor de IA usan todos tus agentes. Imrryr OS ya viene con <b>OpenCode Zen (gratis)</b> activo, que no necesita clave; si prefieres otro (OpenCode GO, Gemini, OpenAI, Claude, DeepSeek, un modelo local con Ollama, u otro), agrégalo y actívalo. Solo una cuenta puede estar activa a la vez.</p>';

  html += cuentasIaLista.length ? '<div style="margin-bottom:10px">' + cuentasIaLista.map(c => `
    <div class="seed-item" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
      <div>
        <b>${c.nombre}</b> <span class="tag">${(cuentasIaProveedores[c.proveedor] || {}).nombre || c.proveedor}</span>
        ${c.activa ? '<span class="estado-badge estado-proyecto" style="margin-left:6px">activa</span>' : ''}
      </div>
      <div style="display:flex;gap:6px">
        ${!c.activa ? `<button class="gw-save-btn" onclick="activarCuentaIa('${c.id}')" data-ayuda="Todos tus agentes empezarán a usar esta cuenta.">Usar esta</button>` : ''}
        <button class="gw-save-btn" onclick="eliminarCuentaIa('${c.id}')">Eliminar</button>
      </div>
    </div>`).join('') + '</div>' : '<div class="empty">Sin cuentas de IA configuradas todavía</div>';

  html += `<button class="gw-save-btn" onclick="toggleCuentaIaForm()">${cuentasIaMostrarForm ? 'Cancelar' : '+ Cuenta de IA'}</button>`;

  if (cuentasIaMostrarForm) {
    const opciones = Object.entries(cuentasIaProveedores).map(([id, p]) => `<option value="${id}">${p.nombre}</option>`).join('');
    html += `
      <div style="margin-top:10px">
        <div class="gw-field"><label>Nombre</label><input id="ciNombre" placeholder="ej. Mi cuenta de OpenAI"></div>
        <div class="gw-field"><label>Proveedor</label>
          <select id="ciProveedor" onchange="renderCuentaIaCampos()" style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:6px 8px;width:100%">
            ${opciones}
          </select>
        </div>
        <div id="ciCampos"></div>
        <button class="gw-save-btn" style="margin-top:6px" onclick="guardarCuentaIa()">Guardar cuenta</button>
      </div>`;
  }
  el.innerHTML = html;
  if (cuentasIaMostrarForm) renderCuentaIaCampos();
}

function renderCuentaIaCampos() {
  const proveedorId = document.getElementById('ciProveedor').value;
  const prov = cuentasIaProveedores[proveedorId] || {};
  const el = document.getElementById('ciCampos');
  let html = '';
  if (proveedorId === 'otro') {
    html += `<div class="gw-field"><label>Modelo LiteLLM (ej. mistral/mistral-large-latest)</label><input id="ciModelo" placeholder="proveedor/modelo"></div>`;
  }
  if (proveedorId === 'opencode_go') {
    // OpenCode GO no publica su catálogo en la web: lo entrega su propia API
    // según tu suscripción, así que se consulta en vivo con tu API key.
    html += `<div class="gw-field"><label>Modelo</label>
        <select id="ciModelo" style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:6px 8px;width:100%">
          <option value="">— pega tu API key y pulsa "Ver modelos" —</option>
        </select>
      </div>
      <div style="font-size:11px;color:var(--text-dim);margin:-2px 0 6px">Tus modelos los entrega OpenCode GO según tu suscripción. La dirección del servicio ya está configurada.</div>`;
  }
  if (proveedorId === 'opencode_zen') {
    // Capa gratuita de OpenCode Zen: sin clave ni suscripción. La respuesta
    // no sale por LiteLLM sino por el proveedor nativo de OpenCode (ver
    // config/cuentas_ia.py), y solo se listan los modelos gratuitos.
    html += `<div class="gw-field"><label>Modelo gratuito</label>
        <select id="ciModelo" style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:6px 8px;width:100%">
          <option value="${prov.modelo_base}">${prov.modelo_base} (recomendado)</option>
        </select>
      </div>
      <div style="font-size:11px;color:var(--text-dim);margin:-2px 0 6px">No necesita API key. Pulsa "Ver modelos disponibles" para ver los gratuitos de hoy; algunos pueden fallar en el servidor de OpenCode.</div>`;
  }
  if (proveedorId === 'ollama') {
    html += `<div class="gw-field"><label>Host (api_base)</label><input id="ciApiBase" value="http://localhost:11434"></div>`;
  }
  if (prov.requiere_key) {
    html += `<div class="gw-field"><label>API key</label><input id="ciApiKey" type="password"></div>`;
  }
  if (prov.api_base && proveedorId !== 'ollama') {
    html += `<button class="gw-modo-btn" style="flex:none;margin-bottom:6px" onclick="cargarModelosProveedor()">Ver modelos disponibles</button>`;
  }
  el.innerHTML = html;
}

// Pide al servidor local el catálogo real del proveedor. La API key se manda
// al backend propio (localhost), que es quien habla con el proveedor — nunca
// se expone el catálogo ni la clave a terceros.
async function cargarModelosProveedor() {
  const proveedor = document.getElementById('ciProveedor').value;
  const apiKeyEl = document.getElementById('ciApiKey');
  const sel = document.getElementById('ciModelo');
  if (cuentasIaProveedores[proveedor]?.requiere_key && (!apiKeyEl || !apiKeyEl.value.trim())) { mostrarToast('Primero pega tu API key', 'error'); return; }
  if (sel) sel.innerHTML = '<option value="">Consultando…</option>';
  try {
    const r = await fetch('/api/ajustes/cuentas-ia/modelos', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proveedor, api_key: apiKeyEl ? apiKeyEl.value.trim() : '' }),
    });
    const d = await r.json();
    if (!d.ok) throw new Error(d.error || 'no se pudo obtener la lista');
    if (sel) {
      sel.innerHTML = d.modelos.map(m => `<option value="${m.id}">${m.nombre}</option>`).join('')
        || '<option value="">(el proveedor no devolvió modelos)</option>';
    }
    mostrarToast(`${d.modelos.length} modelo(s) disponibles`);
  } catch (e) {
    if (sel) sel.innerHTML = '<option value="">— no se pudo cargar —</option>';
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function guardarCuentaIa() {
  const nombre = document.getElementById('ciNombre').value.trim();
  const proveedor = document.getElementById('ciProveedor').value;
  if (!nombre) { mostrarToast('Falta el nombre de la cuenta', 'error'); return; }
  const id = nombre.toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 40) + '_' + Date.now().toString(36);
  const datos = { id, nombre, proveedor };
  const modeloEl = document.getElementById('ciModelo');
  if (modeloEl) datos.modelo = modeloEl.value.trim();
  const apiBaseEl = document.getElementById('ciApiBase');
  if (apiBaseEl) datos.api_base = apiBaseEl.value.trim();
  const apiKeyEl = document.getElementById('ciApiKey');
  if (apiKeyEl && apiKeyEl.value.trim()) datos.api_key = apiKeyEl.value.trim();
  try {
    const r = await fetch('/api/ajustes/cuentas-ia', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    cuentasIaMostrarForm = false;
    mostrarToast('Cuenta de IA guardada', 'success');
    cargarCuentasIaView();
  } catch (e) {
    mostrarToast('Error guardando cuenta: ' + e.message, 'error');
  }
}

function toggleCuentaIaForm() {
  cuentasIaMostrarForm = !cuentasIaMostrarForm;
  renderCuentasIaView();
}

async function activarCuentaIa(id) {
  mostrarToast('Activando cuenta y reiniciando el motor de IA...', '');
  try {
    const r = await fetch(`/api/ajustes/cuentas-ia/${id}/activar`, { method: 'POST' });
    const d = await r.json();
    if (d.ok) mostrarToast(d.litellm_reiniciado ? 'Cuenta activada' : 'Cuenta activada, pero el motor de IA no respondió al reiniciar', d.litellm_reiniciado ? 'success' : 'error');
    else mostrarToast('Error: ' + (d.error || 'no se pudo activar'), 'error');
    cargarCuentasIaView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function eliminarCuentaIa(id) {
  try {
    await fetch(`/api/ajustes/cuentas-ia/${id}`, { method: 'DELETE' });
    mostrarToast('Cuenta eliminada', 'success');
    cargarCuentasIaView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Ajustes > GitHub (config/cuentas_git.py) ---
async function cargarCuentasGitView() {
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  try {
    const r = await fetch('/api/ajustes/cuentas-git');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    cuentasGitLista = d.cuentas || [];
    if (ajustesSubtabActual !== 'github') return;
    renderCuentasGitView();
  } catch (e) {
    if (ajustesSubtabActual !== 'github') return;
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function renderCuentasGitView() {
  if (ajustesSubtabActual !== 'github') return;
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  let html = '<p style="font-size:12px;color:var(--text-dim);margin-bottom:10px">Conecta el repositorio de GitHub de tu sitio web para que el Agente RRSS y Web pueda editarlo y hacer commit/push cuando se lo pidas.</p>';

  html += cuentasGitLista.length ? '<div style="margin-bottom:10px">' + cuentasGitLista.map(c => `
    <div class="seed-item" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
      <div><b>${c.nombre}</b> <span class="tag">${c.repo_url}</span>${c.activa ? '<span class="estado-badge estado-proyecto" style="margin-left:6px">activa</span>' : ''}</div>
      <div style="display:flex;gap:6px">
        ${!c.activa ? `<button class="gw-save-btn" onclick="activarCuentaGit('${c.id}')">Usar esta</button>` : ''}
        <button class="gw-save-btn" onclick="eliminarCuentaGit('${c.id}')">Eliminar</button>
      </div>
    </div>`).join('') + '</div>' : '<div class="empty">Sin repos de GitHub configurados todavía</div>';

  html += `<button class="gw-save-btn" onclick="toggleCuentaGitForm()">${cuentasGitMostrarForm ? 'Cancelar' : '+ Repo de GitHub'}</button>`;

  if (cuentasGitMostrarForm) {
    html += `
      <div style="margin-top:10px">
        <div class="gw-field"><label>Nombre</label><input id="cgNombre" placeholder="ej. Mi sitio web"></div>
        <div class="gw-field"><label>URL del repo</label><input id="cgRepoUrl" placeholder="https://github.com/usuario/repo.git"></div>
        <div class="gw-field"><label>Carpeta local (dónde clonarlo)</label><input id="cgRutaLocal" placeholder="C:\\ruta\\a\\mi-sitio"></div>
        <div class="gw-field"><label>Rama</label><input id="cgRama" value="main"></div>
        <div class="gw-field"><label>Token de acceso personal</label><input id="cgToken" type="password"></div>
        <button class="gw-save-btn" style="margin-top:6px" onclick="guardarCuentaGit()">Guardar repo</button>
      </div>`;
  }
  el.innerHTML = html;
}

function toggleCuentaGitForm() {
  cuentasGitMostrarForm = !cuentasGitMostrarForm;
  renderCuentasGitView();
}

async function guardarCuentaGit() {
  const nombre = document.getElementById('cgNombre').value.trim();
  const repo_url = document.getElementById('cgRepoUrl').value.trim();
  if (!nombre || !repo_url) { mostrarToast('Falta el nombre o la URL del repo', 'error'); return; }
  const id = nombre.toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 40) + '_' + Date.now().toString(36);
  const datos = {
    id, nombre, repo_url,
    ruta_local: document.getElementById('cgRutaLocal').value.trim(),
    rama: document.getElementById('cgRama').value.trim() || 'main',
  };
  const token = document.getElementById('cgToken').value.trim();
  if (token) datos.token = token;
  try {
    const r = await fetch('/api/ajustes/cuentas-git', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    cuentasGitMostrarForm = false;
    mostrarToast('Repo de GitHub guardado', 'success');
    cargarCuentasGitView();
  } catch (e) {
    mostrarToast('Error guardando repo: ' + e.message, 'error');
  }
}

async function activarCuentaGit(id) {
  try {
    const r = await fetch(`/api/ajustes/cuentas-git/${id}/activar`, { method: 'POST' });
    const d = await r.json();
    mostrarToast(d.ok ? 'Repo activado' : 'Error: ' + (d.error || ''), d.ok ? 'success' : 'error');
    cargarCuentasGitView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function eliminarCuentaGit(id) {
  try {
    await fetch(`/api/ajustes/cuentas-git/${id}`, { method: 'DELETE' });
    mostrarToast('Repo eliminado', 'success');
    cargarCuentasGitView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Ajustes > Redes sociales (config/cuentas_social.py) ---
async function cargarCuentasSocialView() {
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  try {
    const r = await fetch('/api/ajustes/cuentas-social');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    cuentasSocialLista = d.cuentas || [];
    if (ajustesSubtabActual !== 'social') return;
    renderCuentasSocialView();
  } catch (e) {
    if (ajustesSubtabActual !== 'social') return;
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function renderCuentasSocialView() {
  if (ajustesSubtabActual !== 'social') return;
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  let html = `<p style="font-size:12px;color:var(--text-dim);margin-bottom:10px">Conecta tu app de Meta for Developers (Página de Facebook +, opcional, cuenta de Instagram Business vinculada) para que el Agente RRSS y Web pueda publicar.
    <br><b>Importante:</b> publicar contra cuentas que no son admin/tester de tu app de Meta requiere que esa app pase App Review para los permisos pages_manage_posts / instagram_content_publish — es un trámite externo ante Meta, no algo que Imrryr pueda resolver por su cuenta.</p>`;

  html += cuentasSocialLista.length ? '<div style="margin-bottom:10px">' + cuentasSocialLista.map(c => `
    <div class="seed-item" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
      <div><b>${c.nombre}</b> <span class="tag">page_id: ${c.page_id}</span>${c.ig_business_id ? `<span class="tag">IG: ${c.ig_business_id}</span>` : ''}${c.activa ? '<span class="estado-badge estado-proyecto" style="margin-left:6px">activa</span>' : ''}</div>
      <div style="display:flex;gap:6px">
        ${!c.activa ? `<button class="gw-save-btn" onclick="activarCuentaSocial('${c.id}')">Usar esta</button>` : ''}
        <button class="gw-save-btn" onclick="eliminarCuentaSocial('${c.id}')">Eliminar</button>
      </div>
    </div>`).join('') + '</div>' : '<div class="empty">Sin cuentas sociales configuradas todavía</div>';

  html += `<button class="gw-save-btn" onclick="toggleCuentaSocialForm()">${cuentasSocialMostrarForm ? 'Cancelar' : '+ Cuenta social'}</button>`;

  if (cuentasSocialMostrarForm) {
    html += `
      <div style="margin-top:10px">
        <div class="gw-field"><label>Nombre</label><input id="csNombre" placeholder="ej. Página de mi negocio"></div>
        <div class="gw-field"><label>Facebook Page ID</label><input id="csPageId"></div>
        <div class="gw-field"><label>Instagram Business Account ID (opcional)</label><input id="csIgId"></div>
        <div class="gw-field"><label>Access token de Meta Graph API</label><input id="csToken" type="password"></div>
        <button class="gw-save-btn" style="margin-top:6px" onclick="guardarCuentaSocial()">Guardar cuenta</button>
      </div>`;
  }
  el.innerHTML = html;
}

function toggleCuentaSocialForm() {
  cuentasSocialMostrarForm = !cuentasSocialMostrarForm;
  renderCuentasSocialView();
}

async function guardarCuentaSocial() {
  const nombre = document.getElementById('csNombre').value.trim();
  const page_id = document.getElementById('csPageId').value.trim();
  if (!nombre || !page_id) { mostrarToast('Falta el nombre o el Page ID', 'error'); return; }
  const id = nombre.toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 40) + '_' + Date.now().toString(36);
  const datos = { id, nombre, page_id, ig_business_id: document.getElementById('csIgId').value.trim() };
  const token = document.getElementById('csToken').value.trim();
  if (token) datos.access_token = token;
  try {
    const r = await fetch('/api/ajustes/cuentas-social', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    cuentasSocialMostrarForm = false;
    mostrarToast('Cuenta social guardada', 'success');
    cargarCuentasSocialView();
  } catch (e) {
    mostrarToast('Error guardando cuenta: ' + e.message, 'error');
  }
}

async function activarCuentaSocial(id) {
  try {
    const r = await fetch(`/api/ajustes/cuentas-social/${id}/activar`, { method: 'POST' });
    const d = await r.json();
    mostrarToast(d.ok ? 'Cuenta activada' : 'Error: ' + (d.error || ''), d.ok ? 'success' : 'error');
    cargarCuentasSocialView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function eliminarCuentaSocial(id) {
  try {
    await fetch(`/api/ajustes/cuentas-social/${id}`, { method: 'DELETE' });
    mostrarToast('Cuenta eliminada', 'success');
    cargarCuentasSocialView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- App RRSS y Web (tabla posts_programados) ---
async function cargarRrssView() {
  const el = document.getElementById('rrssContent');
  if (!el) return;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const r = await fetch('/api/rrss/posts');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const lista = d.posts || [];
    if (!lista.length) {
      el.innerHTML = '<div class="empty">Sin posts programados todavía. Usa "Programar post" o pídeselo al Agente RRSS y Web.</div>';
      return;
    }
    el.innerHTML = `<div class="oport-board">${lista.map(p => `
      <div class="oport-card">
        <div class="oport-card-fuente">${p.plataformas}</div>
        <div class="oport-card-titulo">${p.contenido}</div>
        <div class="oport-card-meta">Programado: ${p.programado_at}</div>
        <span class="estado-badge estado-${p.estado === 'publicado' ? 'proyecto' : p.estado === 'fallido' ? 'archivada' : 'idea'}">${p.estado}</span>
        ${p.error_detalle ? `<div class="oport-card-nota">${p.error_detalle}</div>` : ''}
      </div>`).join('')}</div>`;
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function abrirFormularioPost() {
  const el = document.getElementById('rrssFormulario');
  const abierto = el.style.display !== 'none';
  if (abierto) { el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.innerHTML = `
    <div class="gw-field"><label>Contenido</label><input id="rrssContenido" placeholder="Texto del post"></div>
    <div class="gw-field"><label>Imagen (ruta local o URL pública — obligatoria para Instagram)</label><input id="rrssMedia" placeholder="https://... o ruta local"></div>
    <div class="gw-field"><label>Plataformas</label>
      <label style="font-size:12px;margin-right:10px"><input type="checkbox" id="rrssFb" checked> Facebook</label>
      <label style="font-size:12px"><input type="checkbox" id="rrssIg" checked> Instagram</label>
    </div>
    <div class="gw-field"><label>Fecha y hora</label><input id="rrssFecha" type="datetime-local"></div>
    <button class="gw-save-btn" style="margin-top:6px" onclick="guardarPostProgramado()">Programar</button>`;
}

async function guardarPostProgramado() {
  const contenido = document.getElementById('rrssContenido').value.trim();
  const fecha = document.getElementById('rrssFecha').value;
  if (!contenido || !fecha) { mostrarToast('Falta el contenido o la fecha', 'error'); return; }
  const plataformas = [
    document.getElementById('rrssFb').checked ? 'facebook' : null,
    document.getElementById('rrssIg').checked ? 'instagram' : null,
  ].filter(Boolean).join(',');
  const datos = {
    contenido, plataformas, programado_at: fecha.replace('T', ' '),
    media_ruta: document.getElementById('rrssMedia').value.trim(),
  };
  try {
    const r = await fetch('/api/rrss/posts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    document.getElementById('rrssFormulario').style.display = 'none';
    mostrarToast('Post programado', 'success');
    cargarRrssView();
  } catch (e) {
    mostrarToast('Error programando post: ' + e.message, 'error');
  }
}

// --- App Compras (tabla productos_seguimiento) ---
async function cargarComprasView() {
  cargarComprasCorreoSelector();
  const el = document.getElementById('comprasContent');
  if (!el) return;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const r = await fetch('/api/compras/seguimientos');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const lista = d.seguimientos || [];
    if (!lista.length) {
      el.innerHTML = '<div class="empty">Sin productos en seguimiento todavía. Usa "Seguir producto" o pídeselo al Agente de Compras.</div>';
      return;
    }
    el.innerHTML = `<div class="oport-board">${lista.map(s => `
      <div class="oport-card">
        <div class="oport-card-fuente">${s.tiendas}</div>
        <div class="oport-card-titulo">${s.producto}</div>
        <div class="oport-card-meta">${s.precio_min ? 'Desde ' + fmtCLP(s.precio_min) : ''}${s.precio_max ? ' hasta ' + fmtCLP(s.precio_max) : ''}</div>
        <div class="oport-card-nota">Último chequeo: ${s.ultimo_chequeo || 'todavía no'}</div>
        <span class="estado-badge estado-${s.activo ? 'proyecto' : 'archivada'}">${s.activo ? 'activo' : 'inactivo'}</span>
        <div class="oport-card-actions" style="margin-top:8px">
          <button onclick="eliminarSeguimientoCompras(${s.id})">Eliminar</button>
        </div>
      </div>`).join('')}</div>`;
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function abrirFormularioSeguimiento() {
  const el = document.getElementById('comprasFormulario');
  const abierto = el.style.display !== 'none';
  if (abierto) { el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.innerHTML = `
    <div class="gw-field"><label>Producto</label><input id="csProducto" placeholder="ej. audífonos sony wh-1000xm5"></div>
    <div class="gw-field"><label>Precio mínimo (opcional)</label><input id="csPrecioMin" type="number"></div>
    <div class="gw-field"><label>Precio máximo (opcional)</label><input id="csPrecioMax" type="number"></div>
    <div class="gw-field"><label>Tiendas</label>
      <label style="font-size:12px;margin-right:10px"><input type="checkbox" id="csFalabella" checked> Falabella</label>
      <label style="font-size:12px;margin-right:10px"><input type="checkbox" id="csMeli" checked> MercadoLibre</label>
      <label style="font-size:12px;margin-right:10px"><input type="checkbox" id="csParis" checked> Paris</label>
      <label style="font-size:12px"><input type="checkbox" id="csRipley" checked> Ripley</label>
    </div>
    <button class="gw-save-btn" style="margin-top:6px" onclick="guardarSeguimientoCompras()">Seguir producto</button>`;
}

async function guardarSeguimientoCompras() {
  const producto = document.getElementById('csProducto').value.trim();
  if (!producto) { mostrarToast('Falta el nombre del producto', 'error'); return; }
  const tiendas = [
    document.getElementById('csFalabella').checked ? 'falabella' : null,
    document.getElementById('csMeli').checked ? 'mercadolibre' : null,
    document.getElementById('csParis').checked ? 'paris' : null,
    document.getElementById('csRipley').checked ? 'ripley' : null,
  ].filter(Boolean).join(',');
  const datos = {
    producto, tiendas,
    precio_min: parseFloat(document.getElementById('csPrecioMin').value) || null,
    precio_max: parseFloat(document.getElementById('csPrecioMax').value) || null,
  };
  try {
    const r = await fetch('/api/compras/seguimientos', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    document.getElementById('comprasFormulario').style.display = 'none';
    mostrarToast('Producto en seguimiento', 'success');
    cargarComprasView();
  } catch (e) {
    mostrarToast('Error guardando seguimiento: ' + e.message, 'error');
  }
}

async function eliminarSeguimientoCompras(id) {
  try {
    await fetch(`/api/compras/seguimientos/${id}`, { method: 'DELETE' });
    mostrarToast('Seguimiento eliminado', 'success');
    cargarComprasView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function cargarComprasCorreoSelector() {
  const el = document.getElementById('comprasCorreoSelector');
  if (!el) return;
  try {
    const [rCuentas, rPrefs] = await Promise.all([fetch('/api/correo/cuentas'), fetch('/api/compras/prefs')]);
    const cuentas = (await rCuentas.json()).cuentas || [];
    const prefs = await rPrefs.json();
    const opciones = cuentas.map(c => `<option value="${c.id}" ${c.id === prefs.cuenta_correo_id ? 'selected' : ''}>${c.nombre}</option>`).join('');
    el.innerHTML = `
      <div class="gw-field"><label>Cuenta de correo</label>
        <select id="comprasCuentaCorreo" style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:6px 8px;width:100%">
          <option value="">Sin elegir</option>${opciones}
        </select>
      </div>
      <div class="gw-field"><label>Enviar a</label><input id="comprasDestinatario" value="${prefs.destinatario || ''}" placeholder="tu@correo.com"></div>
      <button class="gw-save-btn" onclick="guardarComprasPrefs()">Guardar</button>`;
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

async function guardarComprasPrefs() {
  const datos = {
    cuenta_correo_id: document.getElementById('comprasCuentaCorreo').value,
    destinatario: document.getElementById('comprasDestinatario').value.trim(),
  };
  try {
    await fetch('/api/compras/prefs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    mostrarToast('Preferencias guardadas', 'success');
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- App Agenda: grilla de mes (tabla eventos + avisos_evento) ---
const MESES_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const DIAS_ES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
let agendaAnio = new Date().getFullYear();
let agendaMes = new Date().getMonth() + 1; // 1-12
let agendaDiaSeleccionado = null; // 'YYYY-MM-DD'
let agendaEventosDelMes = [];

async function cargarAgendaView() {
  document.getElementById('agendaMesLabel').textContent = `${MESES_ES[agendaMes - 1]} ${agendaAnio}`;
  try {
    const r = await fetch(`/api/agenda/eventos?rango=mes&anio=${agendaAnio}&mes=${agendaMes}`);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    agendaEventosDelMes = d.eventos || [];
    renderAgendaGrid();
    if (agendaDiaSeleccionado) renderAgendaDiaDetalle();
  } catch (e) {
    document.getElementById('agendaGrid').innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
  cargarPendientes();
}

function cambiarMesAgenda(delta) {
  agendaMes += delta;
  if (agendaMes > 12) { agendaMes = 1; agendaAnio++; }
  if (agendaMes < 1) { agendaMes = 12; agendaAnio--; }
  agendaDiaSeleccionado = null;
  document.getElementById('agendaDiaDetalle').innerHTML = '';
  cargarAgendaView();
}

function renderAgendaGrid() {
  const el = document.getElementById('agendaGrid');
  const hoyISO = new Date().toISOString().slice(0, 10);
  const primerDia = new Date(agendaAnio, agendaMes - 1, 1);
  const diasEnMes = new Date(agendaAnio, agendaMes, 0).getDate();
  // getDay(): 0=domingo..6=sábado -> convertir a 0=lunes..6=domingo
  const offset = (primerDia.getDay() + 6) % 7;

  const eventosPorDia = {};
  agendaEventosDelMes.forEach(ev => { (eventosPorDia[ev.fecha] = eventosPorDia[ev.fecha] || []).push(ev); });

  let celdas = DIAS_ES.map(d => `<div class="agenda-dia-header">${d}</div>`).join('');
  for (let i = 0; i < offset; i++) celdas += '<div class="agenda-dia vacio"></div>';
  for (let dia = 1; dia <= diasEnMes; dia++) {
    const fechaISO = `${agendaAnio}-${String(agendaMes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
    const eventos = eventosPorDia[fechaISO] || [];
    const clases = ['agenda-dia'];
    if (fechaISO === hoyISO) clases.push('hoy');
    if (fechaISO === agendaDiaSeleccionado) clases.push('seleccionado');
    celdas += `<div class="${clases.join(' ')}" onclick="seleccionarDiaAgenda('${fechaISO}')">
      <div class="agenda-dia-num">${dia}</div>
      <div class="agenda-dia-eventos">${eventos.slice(0, 6).map(() => '<span class="agenda-dot"></span>').join('')}</div>
    </div>`;
  }
  el.innerHTML = celdas;
}

function seleccionarDiaAgenda(fechaISO) {
  agendaDiaSeleccionado = fechaISO;
  renderAgendaGrid();
  renderAgendaDiaDetalle();
}

function renderAgendaDiaDetalle() {
  const el = document.getElementById('agendaDiaDetalle');
  const eventos = agendaEventosDelMes.filter(ev => ev.fecha === agendaDiaSeleccionado);
  const encabezado = `<div class="widget-title" style="margin-bottom:8px">${agendaDiaSeleccionado}</div>`;
  if (!eventos.length) {
    el.innerHTML = encabezado + '<div class="empty">Sin eventos este día.</div>';
    return;
  }
  el.innerHTML = encabezado + eventos.map(ev => `
    <div class="seed-item" style="display:block">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <b>${ev.hora} — ${ev.titulo}</b>
        <button onclick="cancelarEventoAgenda(${ev.id})">Cancelar</button>
      </div>
      ${ev.descripcion ? `<div style="font-size:12px;color:var(--text-dim);margin-top:4px">${ev.descripcion}</div>` : ''}
      ${ev.avisos && ev.avisos.length ? `<div style="font-size:11px;color:var(--text-dim);margin-top:4px">Avisos: ${ev.avisos.map(a => a.hora_aviso).join(', ')}</div>` : ''}
    </div>`).join('');
}

function abrirFormularioEvento() {
  const el = document.getElementById('agendaFormulario');
  const abierto = el.style.display !== 'none';
  if (abierto) { el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.innerHTML = `
    <div class="gw-field"><label>Título</label><input id="agTitulo" placeholder="ej. Reunión con proveedor"></div>
    <div class="gw-field"><label>Fecha</label><input id="agFecha" type="date" value="${agendaDiaSeleccionado || ''}"></div>
    <div class="gw-field"><label>Hora</label><input id="agHora" type="time" value="09:00"></div>
    <div class="gw-field"><label>Descripción (opcional)</label><input id="agDescripcion"></div>
    <div class="gw-field"><label>Avisarme por WhatsApp a estas horas (opcional, separadas por coma)</label><input id="agAvisos" placeholder="ej. 08:00,17:00"></div>
    <button class="gw-save-btn" style="margin-top:6px" onclick="guardarEventoAgenda()">Agendar</button>`;
}

async function guardarEventoAgenda() {
  const titulo = document.getElementById('agTitulo').value.trim();
  const fecha = document.getElementById('agFecha').value;
  if (!titulo || !fecha) { mostrarToast('Falta el título o la fecha', 'error'); return; }
  const datos = {
    titulo, fecha,
    hora: document.getElementById('agHora').value || '09:00',
    descripcion: document.getElementById('agDescripcion').value.trim(),
    avisos: document.getElementById('agAvisos').value.trim(),
  };
  try {
    const r = await fetch('/api/agenda/eventos', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    document.getElementById('agendaFormulario').style.display = 'none';
    mostrarToast('Evento agendado', 'success');
    agendaDiaSeleccionado = fecha;
    cargarAgendaView();
  } catch (e) {
    mostrarToast('Error agendando: ' + e.message, 'error');
  }
}

async function cancelarEventoAgenda(id) {
  try {
    await fetch(`/api/agenda/eventos/${id}/cancelar`, { method: 'POST' });
    mostrarToast('Evento cancelado', 'success');
    cargarAgendaView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Pendientes (lista de tareas sin fecha fija, panel al costado de Agenda) ---
async function cargarPendientes() {
  const el = document.getElementById('pendientesLista');
  if (!el) return;
  try {
    const r = await fetch('/api/pendientes');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const lista = d.pendientes || [];
    if (!lista.length) { el.innerHTML = '<div class="empty" style="padding:10px 0">Sin pendientes</div>'; return; }
    el.innerHTML = lista.map(p => `
      <div class="pendiente-item ${p.hecho ? 'hecho' : ''}">
        <input type="checkbox" ${p.hecho ? 'checked' : ''} onchange="marcarPendiente(${p.id}, this.checked)">
        <span class="pendiente-texto" style="flex:1">${p.texto}</span>
        <button onclick="eliminarPendiente(${p.id})" style="background:none;border:none;color:var(--text-dim);cursor:pointer">✕</button>
      </div>`).join('');
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

async function crearPendiente() {
  const inp = document.getElementById('pendienteNuevoInput');
  const texto = inp.value.trim();
  if (!texto) return;
  inp.value = '';
  try {
    await fetch('/api/pendientes', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto }),
    });
    cargarPendientes();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function marcarPendiente(id, hecho) {
  try {
    await fetch(`/api/pendientes/${id}/hecho`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ hecho }),
    });
    cargarPendientes();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function eliminarPendiente(id) {
  try {
    await fetch(`/api/pendientes/${id}`, { method: 'DELETE' });
    cargarPendientes();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Módulos (gestión de agentes, protegido por contraseña) ---
let modulosPasswordActual = null; // solo en memoria, nunca en localStorage
let modulosDesbloqueado = false;
let ultimosModulosCargados = [];

async function cargarModulosView() {
  if (modulosDesbloqueado) { cargarModulosLista(); return; }
  const el = document.getElementById('modulosContent');
  if (!el) return;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const r = await fetch('/api/modulos/password-estado');
    const d = await r.json();
    renderModulosGate(d.configurada);
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function renderModulosGate(configurada) {
  const el = document.getElementById('modulosContent');
  if (!el) return;
  if (!configurada) {
    el.innerHTML = `
      <div class="seed-item" style="display:block;max-width:420px">
        <div style="font-weight:600;margin-bottom:6px"><svg class="icon"><use href="#icon-lock"/></svg> Crea la contraseña de administrador</div>
        <p style="font-size:12px;color:var(--text-dim);margin-bottom:10px">Es una sola contraseña compartida — una barrera para que nadie borre un agente por accidente, no un sistema de permisos por usuario. Guárdala en un lugar seguro.</p>
        <div class="gw-field"><label>Nueva contraseña</label><input type="password" id="modulosNuevaPass"></div>
        <button class="gw-save-btn" onclick="crearPasswordModulos()">Crear contraseña</button>
      </div>`;
    return;
  }
  el.innerHTML = `
    <div class="seed-item" style="display:block;max-width:420px">
      <div style="font-weight:600;margin-bottom:6px"><svg class="icon"><use href="#icon-lock"/></svg> Ingresa la contraseña de administrador</div>
      <div class="gw-field"><label>Contraseña</label><input type="password" id="modulosPassInput"></div>
      <button class="gw-save-btn" onclick="desbloquearModulos()">Entrar</button>
    </div>`;
  const input = document.getElementById('modulosPassInput');
  if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') desbloquearModulos(); });
}

async function crearPasswordModulos() {
  const val = document.getElementById('modulosNuevaPass').value;
  try {
    const r = await fetch('/api/modulos/configurar-password', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: val }),
    });
    const d = await r.json();
    if (!d.ok) { mostrarToast(d.error || 'No se pudo crear', 'error'); return; }
    modulosPasswordActual = val;
    modulosDesbloqueado = true;
    mostrarToast('Contraseña creada', 'success');
    cargarModulosLista();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function desbloquearModulos() {
  const val = document.getElementById('modulosPassInput').value;
  try {
    const r = await fetch('/api/modulos/verificar-password', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: val }),
    });
    const d = await r.json();
    if (!d.ok) { mostrarToast('Contraseña incorrecta', 'error'); return; }
    modulosPasswordActual = val;
    modulosDesbloqueado = true;
    cargarModulosLista();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function cargarModulosLista() {
  const el = document.getElementById('modulosContent');
  if (!el) return;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const r = await fetch('/api/modulos');
    const d = await r.json();
    ultimosModulosCargados = d.modulos || [];
    renderModulosLista(ultimosModulosCargados, d.eliminados || []);
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function tarjetaModuloHtml(m) {
  return `<div class="mini-card" style="align-items:flex-start;cursor:default;flex-direction:column;gap:8px;padding:16px">
    <div style="display:flex;align-items:center;gap:10px;width:100%">
      <div class="mini-card-icon"><svg class="icon"><use href="#icon-${m.icono}"/></svg></div>
      <div style="flex:1">
        <div class="mini-card-title">${m.nombre}</div>
        <span class="estado-badge ${m.activo ? 'estado-proyecto' : 'estado-archivada'}">${m.activo ? 'activo' : 'inactivo'}</span>
      </div>
    </div>
    <div style="font-size:11px;color:var(--text-dim)">${(m.descripcion || '').slice(0, 160)}</div>
    <div>${(m.herramientas || []).map(t => `<span class="tag">${t}</span>`).join('')}</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      ${m.activo
        ? `<button class="gw-modo-btn" onclick="desactivarModulo('${m.id}')" data-ayuda="Lo apaga sin borrar nada. Puedes reactivarlo cuando quieras.">Desactivar</button>`
        : `<button class="gw-save-btn" onclick="activarModulo('${m.id}')">Activar</button>`}
      <button class="gw-modo-btn" style="color:var(--red)" onclick="mostrarConfirmarEliminarModulo('${m.id}')" data-ayuda="Lo saca de la lista de agentes. Se puede recuperar después.">Eliminar</button>
    </div>
    <div id="confirmarEliminar_${m.id}" style="width:100%"></div>
  </div>`;
}

function renderModulosLista(modulos, eliminados) {
  const el = document.getElementById('modulosContent');
  if (!el) return;
  let html = '<div class="home-secondary" style="padding:0;margin-bottom:20px">' + modulos.map(tarjetaModuloHtml).join('') + '</div>';

  html += '<div class="app-title-row" style="margin:0 0 14px 0"><svg class="icon-lg" style="color:var(--text-dim)"><use href="#icon-trash"/></svg><h2 style="font-size:18px">Desactivados / eliminados</h2></div>';
  if (!eliminados.length) {
    html += '<div class="empty">No hay módulos eliminados. Por ahora, esta sección solo muestra los que tú mismo desactives o elimines — todavía no hay un catálogo externo de agentes nuevos para descargar.</div>';
  } else {
    html += '<div class="home-secondary" style="padding:0">' + eliminados.map(m => `
      <div class="mini-card" style="cursor:default">
        <div class="mini-card-icon"><svg class="icon"><use href="#icon-${m.icono}"/></svg></div>
        <div class="mini-card-body" style="flex:1"><div class="mini-card-title">${m.nombre}</div><div class="mini-card-sub">Eliminado</div></div>
        <button class="gw-save-btn" onclick="restaurarModulo('${m.id}')">Restaurar</button>
      </div>`).join('') + '</div>';
  }
  el.innerHTML = html;
}

function mostrarConfirmarEliminarModulo(id) {
  const box = document.getElementById('confirmarEliminar_' + id);
  const modulo = ultimosModulosCargados.find(m => m.id === id);
  const datos = modulo && modulo.datos_asociados ? modulo.datos_asociados : 'Este módulo no tiene datos propios guardados.';
  box.innerHTML = `
    <div style="margin-top:8px;padding:10px;background:var(--surface2);border-radius:8px;width:100%">
      <div style="font-size:11px;color:var(--text-dim);margin-bottom:6px">Al eliminar, se saca de la lista de agentes (recuperable con "Restaurar"). Si además marcas la casilla, esto también se borra: <b>${datos}</b></div>
      <label style="display:flex;align-items:center;gap:6px;font-size:11px;margin-bottom:8px">
        <input type="checkbox" id="borrarDatos_${id}"> También borrar los datos guardados
      </label>
      <div style="display:flex;gap:6px">
        <button class="gw-save-btn" style="background:var(--red)" onclick="confirmarEliminarModulo('${id}')">Confirmar eliminación</button>
        <button class="gw-modo-btn" onclick="document.getElementById('confirmarEliminar_${id}').innerHTML=''">Cancelar</button>
      </div>
    </div>`;
}

async function confirmarEliminarModulo(id) {
  const borrarDatos = document.getElementById('borrarDatos_' + id).checked;
  try {
    const r = await fetch(`/api/modulos/${id}/eliminar`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: modulosPasswordActual, borrar_datos: borrarDatos }),
    });
    const d = await r.json();
    if (!d.ok) { mostrarToast(d.error || 'No se pudo eliminar', 'error'); return; }
    mostrarToast('Módulo eliminado', 'success');
    cargarModulosLista();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function activarModulo(id) {
  try {
    await fetch(`/api/modulos/${id}/activar`, { method: 'POST' });
    mostrarToast('Módulo activado', 'success');
    cargarModulosLista();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function desactivarModulo(id) {
  try {
    await fetch(`/api/modulos/${id}/desactivar`, { method: 'POST' });
    mostrarToast('Módulo desactivado', 'success');
    cargarModulosLista();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function restaurarModulo(id) {
  try {
    await fetch(`/api/modulos/${id}/restaurar`, { method: 'POST' });
    mostrarToast('Módulo restaurado', 'success');
    cargarModulosLista();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Correo (app completa: sub-tabs Bandeja / Borradores) ---
let correoCuentas = [];
let correoCuentaSel = localStorage.getItem('imrryr_correo_cuenta') || '';
let correoMostrarForm = false;
let correoSubtabActual = 'bandeja';

function cambiarSubtabCorreo(sub) {
  correoSubtabActual = sub;
  document.getElementById('correoSub-bandeja').classList.toggle('active', sub === 'bandeja');
  document.getElementById('correoSub-borradores').classList.toggle('active', sub === 'borradores');
  if (sub === 'bandeja') cargarBandejaSubtab(); else cargarBorradoresSubtab();
}

async function cargarBandejaSubtab() {
  const el = document.getElementById('correoSubcontent');
  if (!el) return;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const r = await fetch('/api/correo/cuentas');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    correoCuentas = d.cuentas || [];
    renderBandejaSubtab();
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function renderBandejaSubtab() {
  const el = document.getElementById('correoSubcontent');
  if (!el) return;
  let html = '<div style="display:flex;gap:6px;align-items:center;margin-bottom:10px">';
  html += `<select id="correoCuentaSel" style="flex:1;background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:5px 8px">
    <option value="">Selecciona una cuenta...</option>
    ${correoCuentas.map(c => `<option value="${c.id}" ${c.id === correoCuentaSel ? 'selected' : ''}>${c.id} (${c.proveedor})</option>`).join('')}
  </select>`;
  html += `<button class="gw-save-btn" onclick="toggleCorreoForm()">${correoMostrarForm ? 'Cancelar' : '+ Cuenta'}</button>`;
  if (correoCuentaSel) html += `<button class="gw-save-btn" onclick="eliminarCuentaCorreo()">Eliminar</button>`;
  html += '</div>';

  if (correoMostrarForm) {
    html += `
      <div class="gw-field"><label>ID de la cuenta</label><input id="ccId" placeholder="ej. gmail_principal, hosting_web"></div>
      <div class="gw-field"><label>Proveedor</label>
        <select id="ccProveedor" onchange="renderCorreoFormCampos()" style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:5px 8px;width:100%">
          <option value="gmail">Gmail (OAuth)</option>
          <option value="imap">IMAP genérico (hosting, Outlook, etc.)</option>
        </select>
      </div>
      <div class="gw-field"><label>Email</label><input id="ccEmail" placeholder="cuenta@dominio.com"></div>
      <div id="ccCamposImap"></div>
      <button class="gw-save-btn" style="margin-top:6px" onclick="guardarCuentaCorreo()">Guardar cuenta</button>
    `;
  }

  html += '<div id="correoBandejaLista" style="margin-top:10px">' +
    (correoCuentaSel ? '<div class="loading">Cargando bandeja</div>' : '<div class="empty">Elige una cuenta para ver su bandeja</div>') +
    '</div>';

  el.innerHTML = html;
  document.getElementById('correoCuentaSel').addEventListener('change', (e) => {
    correoCuentaSel = e.target.value;
    localStorage.setItem('imrryr_correo_cuenta', correoCuentaSel);
    cargarBandejaMensajes();
  });
  if (correoMostrarForm) renderCorreoFormCampos();
  if (correoCuentaSel) cargarBandejaMensajes();
}

async function cargarBorradoresSubtab() {
  const el = document.getElementById('correoSubcontent');
  if (!el) return;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const r = await fetch('/api/correo/borradores?estado=pendiente');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const borradores = d.borradores || [];
    if (!borradores.length) { el.innerHTML = '<div class="empty">Sin borradores pendientes</div>'; return; }
    el.innerHTML = borradores.map(b => `
      <div class="seed-item" style="display:block">
        <div><b>Para:</b> ${b.destinatario} — <b>Asunto:</b> ${b.asunto || '(sin asunto)'}</div>
        <div style="font-size:11px;color:var(--text-dim);margin:4px 0">${(b.cuerpo || '').slice(0, 200)}</div>
        <div style="display:flex;gap:6px">
          <button class="gw-save-btn" onclick="enviarBorradorCorreo(${b.id})" data-ayuda="Envía este correo tal cual. El Secretario nunca lo hace solo — el envío final siempre es tu decisión.">Enviar</button>
          <button class="gw-save-btn" onclick="descartarBorradorCorreo(${b.id})" data-ayuda="Descarta este borrador sin enviarlo.">Descartar</button>
        </div>
      </div>`).join('');
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

function renderCorreoFormCampos() {
  const proveedor = document.getElementById('ccProveedor').value;
  const el = document.getElementById('ccCamposImap');
  if (proveedor === 'imap') {
    el.innerHTML = `
      <div class="gw-field"><label>Servidor IMAP</label><input id="ccImapHost" placeholder="mail.midominio.com"></div>
      <div class="gw-field"><label>Servidor SMTP</label><input id="ccSmtpHost" placeholder="mail.midominio.com"></div>
      <div class="gw-field"><label>Usuario</label><input id="ccUsuario" placeholder="usuario de acceso"></div>
      <div class="gw-field"><label>Contraseña</label><input id="ccPassword" type="password"></div>
    `;
  } else {
    el.innerHTML = '<div class="empty" style="margin:4px 0">Gmail usa OAuth (config/gmail_secretario_credentials.json). Guarda la cuenta y sigue las instrucciones de autorización.</div>';
  }
}

function toggleCorreoForm() {
  correoMostrarForm = !correoMostrarForm;
  cargarBandejaSubtab();
}

async function guardarCuentaCorreo() {
  const id = document.getElementById('ccId').value.trim();
  const proveedor = document.getElementById('ccProveedor').value;
  const email = document.getElementById('ccEmail').value.trim();
  if (!id) { mostrarToast('Falta el ID de la cuenta', 'error'); return; }
  const datos = { id, proveedor, email };
  if (proveedor === 'imap') {
    datos.imap_host = document.getElementById('ccImapHost').value.trim();
    datos.smtp_host = document.getElementById('ccSmtpHost').value.trim();
    datos.usuario = document.getElementById('ccUsuario').value.trim();
    const pass = document.getElementById('ccPassword').value.trim();
    if (pass) datos.password = pass;
  }
  try {
    const r = await fetch('/api/correo/cuentas', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    correoMostrarForm = false;
    correoCuentaSel = id;
    localStorage.setItem('imrryr_correo_cuenta', id);
    mostrarToast('Cuenta de correo guardada', 'success');
    cargarBandejaSubtab();
  } catch (e) {
    mostrarToast('Error guardando cuenta: ' + e.message, 'error');
  }
}

async function eliminarCuentaCorreo() {
  if (!correoCuentaSel) return;
  try {
    const r = await fetch('/api/correo/cuentas/' + encodeURIComponent(correoCuentaSel), { method: 'DELETE' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    correoCuentaSel = '';
    localStorage.removeItem('imrryr_correo_cuenta');
    mostrarToast('Cuenta eliminada', 'success');
    cargarBandejaSubtab();
  } catch (e) {
    mostrarToast('Error eliminando cuenta: ' + e.message, 'error');
  }
}

async function cargarBandejaMensajes() {
  const el = document.getElementById('correoBandejaLista');
  if (!el) return;
  if (!correoCuentaSel) { el.innerHTML = '<div class="empty">Elige una cuenta para ver su bandeja</div>'; return; }
  el.innerHTML = '<div class="loading">Cargando bandeja</div>';
  try {
    const r = await fetch(`/api/correo/bandeja?cuenta_id=${encodeURIComponent(correoCuentaSel)}&max_resultados=10`);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const correos = d.correos || [];
    if (!correos.length) {
      el.innerHTML = '<div class="empty">Sin correos recientes (o cuenta sin credenciales configuradas)</div>';
      return;
    }
    el.innerHTML = correos.map(c => `
      <div class="seed-item" style="display:block">
        <div><b>${(c.remitente || '').replace(/</g,'&lt;')}</b></div>
        <div style="font-size:11px">${c.asunto || '(sin asunto)'}</div>
      </div>`).join('');
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

async function enviarBorradorCorreo(id) {
  try {
    const r = await fetch(`/api/correo/borradores/${id}/enviar`, { method: 'POST' });
    const d = await r.json();
    if (d.ok) { mostrarToast('Correo enviado', 'success'); } else { mostrarToast('Error: ' + (d.error || 'no se pudo enviar'), 'error'); }
    cargarBorradoresSubtab();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function descartarBorradorCorreo(id) {
  try {
    await fetch(`/api/correo/borradores/${id}/descartar`, { method: 'POST' });
    mostrarToast('Borrador descartado', 'success');
    cargarBorradoresSubtab();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Ajustes (WhatsApp, Perfil de Negocio, Cuentas de IA, Ayuda: sub-tabs) ---
let ajustesSubtabActual = 'whatsapp';
function cambiarSubtabAjustes(sub) {
  ajustesSubtabActual = sub;
  ['whatsapp', 'perfil', 'ia', 'ayuda', 'apariencia', 'github', 'social', 'respaldos'].forEach(s =>
    document.getElementById('ajustesSub-' + s).classList.toggle('active', sub === s));
  document.getElementById('ajustesSubcontent').innerHTML = '<div class="loading">Cargando</div>';
  if (sub === 'whatsapp') cargarGateway();
  else if (sub === 'perfil') cargarPerfilNegocio();
  else if (sub === 'ia') cargarCuentasIaView();
  else if (sub === 'apariencia') renderApariencia();
  else if (sub === 'github') cargarCuentasGitView();
  else if (sub === 'social') cargarCuentasSocialView();
  else if (sub === 'respaldos') cargarRespaldosView();
  else renderAyudaSettings();
}

// --- Respaldos locales de la base de datos (Tanda X) ---
async function cargarRespaldosView() {
  const el = document.getElementById('ajustesSubcontent');
  try {
    const r = await fetch('/api/respaldos');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const filas = (d.respaldos || []).map(b => `
      <div style="display:flex;justify-content:space-between;padding:7px 10px;border-bottom:1px solid var(--border);font-size:12px">
        <span>${b.archivo}</span><span style="color:var(--text-dim)">${b.tamano_kb} KB</span>
      </div>`).join('');
    el.innerHTML = `
      <p style="font-size:12px;color:var(--text-dim);margin-bottom:10px;max-width:560px">
        Todos tus datos (gastos, agenda, seguimientos, mensajes) viven en una base de datos local.
        Cada día que abres Imrryr OS se guarda automáticamente una copia en
        <code>vault/backups/</code> (se conservan las últimas 14). Para restaurar una,
        cierra los servicios y copia el archivo sobre <code>vault/sqlite/imrryr.db</code>.
      </p>
      <button class="gw-save-btn" onclick="crearRespaldoAhora()">Respaldar ahora</button>
      ${filas
        ? `<div style="margin-top:12px;max-width:560px;border:1px solid var(--border);border-radius:8px;overflow:hidden">${filas}</div>`
        : '<div class="empty" style="margin-top:12px">Todavía no hay respaldos — el primero se crea solo hoy, o puedes crearlo ahora.</div>'}`;
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

async function crearRespaldoAhora() {
  try {
    const r = await fetch('/api/respaldos', { method: 'POST' });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    mostrarToast(`Respaldo creado: ${d.archivo} (${d.tamano_kb} KB)`);
    cargarRespaldosView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Modo Ayuda (tooltips contextuales, ver atributos data-ayuda) ---
function aplicarModoAyuda(valor) {
  document.body.classList.toggle('ayuda-on', valor);
  localStorage.setItem('imrryr_ayuda_on', valor ? '1' : '0');
}

// El tooltip es CSS puro (::after con attr(data-ayuda)), pero su posición
// horizontal se corrige aquí para que nunca se salga de la pantalla en los
// elementos cerca de los bordes, y se muestra debajo en vez de arriba para
// los elementos pegados al techo (ej. la barra de navegación).
function inicializarPosicionAyuda() {
  document.addEventListener('mouseover', (e) => {
    const el = e.target.closest('[data-ayuda]');
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const anchoTip = Math.min(260, window.innerWidth * 0.78);
    const margen = 14;
    const centroX = rect.left + rect.width / 2;
    const desbordeDerecha = (centroX + anchoTip / 2) - (window.innerWidth - margen);
    const desbordeIzquierda = margen - (centroX - anchoTip / 2);
    let corrimiento = 0;
    if (desbordeDerecha > 0) corrimiento = -desbordeDerecha;
    else if (desbordeIzquierda > 0) corrimiento = desbordeIzquierda;
    el.style.setProperty('--tip-shift', corrimiento + 'px');
    el.classList.toggle('ayuda-below', rect.top < 70);
  }, true);
}

function renderAyudaSettings() {
  const activo = localStorage.getItem('imrryr_ayuda_on') === '1';
  document.getElementById('ajustesSubcontent').innerHTML = `
    <p style="font-size:12px;color:var(--text-dim);margin-bottom:10px">Cuando está activo, al pasar el mouse por botones y secciones aparece una explicación simple de para qué sirven — pensado para quien no usa este tipo de sistemas todos los días.</p>
    <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
      <span class="ayuda-switch ${activo ? 'on' : ''}" id="ayudaSwitch" onclick="toggleAyudaSwitch()"><span class="ayuda-switch-knob"></span></span>
      <span style="font-size:13px">Explicar secciones al pasar el mouse</span>
    </label>`;
}

function toggleAyudaSwitch() {
  const nuevo = localStorage.getItem('imrryr_ayuda_on') !== '1';
  aplicarModoAyuda(nuevo);
  renderAyudaSettings();
}

// --- Apariencia: tema Creativo/Minimalista + fondo personalizado ---
function aplicarTema(tema) {
  document.documentElement.setAttribute('data-tema', tema);
  localStorage.setItem('imrryr_tema', tema);
}

function seleccionarTema(tema) {
  aplicarTema(tema);
  renderApariencia();
  mostrarToast('Tema aplicado: ' + (tema === 'creativo' ? 'Creativo' : 'Minimalista'), 'success');
}

function renderApariencia() {
  const el = document.getElementById('ajustesSubcontent');
  if (!el) return;
  const actual = localStorage.getItem('imrryr_tema') || 'minimalista';
  el.innerHTML = `
    <p style="font-size:12px;color:var(--text-dim);margin-bottom:12px">Elige cómo se ve Imrryr OS. El cambio es inmediato.</p>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px">
      <div class="tema-opcion ${actual === 'creativo' ? 'activo' : ''}" onclick="seleccionarTema('creativo')" data-ayuda="Fondo con imagen, logo grande, más decorativo — pensado para artistas y diseñadores.">
        <svg class="icon-lg" style="color:var(--accent);margin-bottom:6px"><use href="#icon-bulb"/></svg>
        <div style="font-family:var(--font-display);font-size:16px;margin-bottom:4px">Creativo</div>
        <div style="font-size:11px;color:var(--text-dim)">Fondo con imagen, logo grande, más visual.</div>
      </div>
      <div class="tema-opcion ${actual === 'minimalista' ? 'activo' : ''}" onclick="seleccionarTema('minimalista')" data-ayuda="Sobrio y profesional, sin decoraciones de fondo.">
        <svg class="icon-lg" style="color:var(--accent);margin-bottom:6px"><use href="#icon-briefcase"/></svg>
        <div style="font-family:var(--font-display);font-size:16px;margin-bottom:4px">Minimalista</div>
        <div style="font-size:11px;color:var(--text-dim)">Sobrio y profesional, sin decoraciones.</div>
      </div>
    </div>
    <div class="gw-field" style="margin-bottom:16px">
      <label>Qué aparece en Inicio (máx. 3 tarjetas grandes)</label>
      <div id="inicioPrefsList"></div>
    </div>
    <div id="fondoPersonalizadoBox"></div>`;
  renderInicioPrefs();
  cargarFondoPersonalizado();
}

function renderInicioPrefs() {
  const el = document.getElementById('inicioPrefsList');
  if (!el) return;
  const prefs = leerInicioPrefs();
  el.innerHTML = APPS.map(app => {
    const tier = prefs.hero.includes(app.id) ? 'hero' : prefs.secundaria.includes(app.id) ? 'secundaria' : 'oculta';
    return `<div class="seed-item" style="display:flex;justify-content:space-between;align-items:center;gap:8px">
      <span><svg class="icon"><use href="#icon-${app.icono}"/></svg> ${app.nombre}</span>
      <select onchange="cambiarTierInicio('${app.id}', this.value)" style="background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:11px;padding:4px 6px">
        <option value="hero" ${tier === 'hero' ? 'selected' : ''}>Grande</option>
        <option value="secundaria" ${tier === 'secundaria' ? 'selected' : ''}>Chica</option>
        <option value="oculta" ${tier === 'oculta' ? 'selected' : ''}>Oculta</option>
      </select>
    </div>`;
  }).join('');
}

function cambiarTierInicio(id, tier) {
  const prefs = leerInicioPrefs();
  prefs.hero = prefs.hero.filter(x => x !== id);
  prefs.secundaria = prefs.secundaria.filter(x => x !== id);
  if (tier === 'hero') {
    if (prefs.hero.length >= 3) {
      mostrarToast('Máximo 3 tarjetas grandes — quita una primero', 'error');
      renderInicioPrefs();
      return;
    }
    prefs.hero.push(id);
  } else if (tier === 'secundaria') {
    prefs.secundaria.push(id);
  }
  guardarInicioPrefs(prefs);
  mostrarToast('Guardado', 'success');
}

async function cargarFondoPersonalizado() {
  const box = document.getElementById('fondoPersonalizadoBox');
  if (!box) return;
  const tema = localStorage.getItem('imrryr_tema') || 'minimalista';
  if (tema !== 'creativo') { box.innerHTML = '<p style="font-size:11px;color:var(--text-dim)">El fondo personalizado solo aplica en modo Creativo.</p>'; return; }
  try {
    const r = await fetch('/api/ajustes/fondo');
    const d = await r.json();
    box.innerHTML = `
      <div class="seed-item" style="display:block">
        <div style="font-weight:600;margin-bottom:6px">Fondo personalizado</div>
        ${d.url ? `<img src="${d.url}?t=${Date.now()}" style="max-width:220px;border-radius:10px;margin-bottom:8px;display:block">` : '<div class="empty" style="padding:6px 0">Usando el fondo por defecto (tu logo, difuminado)</div>'}
        <input type="file" id="fondoInput" accept="image/*" style="margin-bottom:8px;font-size:12px">
        <div style="display:flex;gap:6px">
          <button class="gw-save-btn" onclick="subirFondoPersonalizado()" data-ayuda="Usa tu propia imagen (mood board, arte, foto) como fondo del sistema.">Subir imagen</button>
          ${d.url ? '<button class="gw-modo-btn" onclick="quitarFondoPersonalizado()">Quitar</button>' : ''}
        </div>
      </div>`;
  } catch (e) {
    box.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

async function subirFondoPersonalizado() {
  const input = document.getElementById('fondoInput');
  if (!input || !input.files[0]) { mostrarToast('Elige una imagen primero', 'error'); return; }
  const formData = new FormData();
  formData.append('archivo', input.files[0]);
  try {
    const r = await fetch('/api/ajustes/fondo', { method: 'POST', body: formData });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    mostrarToast('Fondo actualizado', 'success');
    aplicarFondoPersonalizado();
    cargarFondoPersonalizado();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function quitarFondoPersonalizado() {
  try {
    await fetch('/api/ajustes/fondo', { method: 'DELETE' });
    mostrarToast('Fondo quitado', 'success');
    aplicarFondoPersonalizado();
    cargarFondoPersonalizado();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

async function aplicarFondoPersonalizado() {
  try {
    const r = await fetch('/api/ajustes/fondo');
    const d = await r.json();
    if (d.url) {
      document.body.style.setProperty('--fondo-personalizado', `url('${d.url}?t=${Date.now()}')`);
      document.body.classList.add('tiene-fondo-personalizado');
    } else {
      document.body.classList.remove('tiene-fondo-personalizado');
    }
  } catch (e) { /* silencioso: el fondo es cosmético, no crítico */ }
}

// --- Status dots ---
async function actualizarStatus() {
  const bar = document.getElementById('statusBar');
  try {
    const [r, rUso, rHitl] = await Promise.all([
      fetch('/api/status'),
      fetch('/api/uso-ia'),
      fetch('/api/hitl/pendientes').catch(() => ({ ok: false }))
    ]);
    if (!r.ok) throw new Error('');
    const d = await r.json();
    const svc = d.servicios || {};
    // opencode/litellm son el motor (sin ellos nada funciona); gateway solo
    // afecta WhatsApp — por eso su ausencia es "warn", no "off".
    const critico = svc.litellm && svc.opencode;
    const clase = critico ? (svc.gateway ? 'on' : 'warn') : 'off';
    const detalle = `Motor de IA (LiteLLM): ${svc.litellm ? 'activo' : 'apagado'}. Agentes (OpenCode): ${svc.opencode ? 'activo' : 'apagado'}. WhatsApp (Gateway): ${svc.gateway ? 'activo' : 'apagado'}.`;
    let usoHtml = '';
    if (rUso.ok) {
      const uso = await rUso.json();
      // El conteo es por turnos de conversación: un turno con herramientas
      // puede costar varias llamadas API reales, así que es piso, no exacto.
      const claseUso = uso.hoy >= uso.limite ? 'off' : (uso.hoy >= uso.limite * 0.75 ? 'warn' : 'on');
      const provInfo = uso.proveedor ? ` (${uso.proveedor})` : '';
      const detalleUso = `Proveedor: ${uso.proveedor || 'Gemini'} (${uso.modelo || 'flash'}). Consultas hoy: ${uso.hoy}/${uso.limite}. Clic para telemetría y presupuesto.`;
      usoHtml = `<div class="status-item" style="cursor:pointer" onclick="abrirModalObservabilidadIA()" data-ayuda="${detalleUso}"><span class="status-dot ${claseUso}"></span>IA hoy: ${uso.hoy}/${uso.limite}${provInfo}</div>`;
    }
    let hitlHtml = '';
    if (rHitl && rHitl.ok) {
      try {
        const dHitl = await rHitl.json();
        const pendientes = dHitl.solicitudes || [];
        if (pendientes.length > 0) {
          hitlHtml = `<div class="status-item" style="color:var(--color-accent);font-weight:600;cursor:pointer" onclick="abrirModalHitl()" data-ayuda="Hay acciones de agentes esperando tu autorización expresa."><span class="status-dot warn"></span>${pendientes.length} HITL pendiente(s)</div>`;
        }
      } catch {}
    }
    bar.innerHTML = `<div class="status-item" data-ayuda="${detalle.replace(/"/g,'&quot;')}"><span class="status-dot ${clase}"></span>Sistema</div>${usoHtml}${hitlHtml}`;
  } catch {
    bar.innerHTML = '<div class="status-item" style="color:var(--red)">sin conexión</div>';
  }
}

async function abrirModalObservabilidadIA() {
  const anterior = document.getElementById('obsIAOverlay');
  if (anterior) anterior.remove();

  try {
    const r = await fetch('/api/uso-ia');
    const d = await r.json();

    const overlay = document.createElement('div');
    overlay.className = 'detalle-overlay';
    overlay.id = 'obsIAOverlay';
    overlay.onclick = (e) => { if (e.target === overlay) cerrarModalObservabilidadIA(); };

    const pct = d.consumo_pct || 0;
    const colorBarra = pct >= 100 ? 'var(--red)' : pct >= 75 ? 'var(--color-accent)' : 'var(--color-accent2)';

    // Desglose por agente
    const agEntries = Object.entries(d.por_agente || {});
    const agHtml = agEntries.length ? agEntries.map(([ag, cnt]) => `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px">
        <span>Agente <strong>${ag}</strong></span>
        <span class="tag">${cnt} turnos</span>
      </div>
    `).join('') : '<div style="font-size:12px;color:var(--text-dim)">Sin actividad registrada hoy</div>';

    // Desglose por canal
    const chEntries = Object.entries(d.por_canal || {});
    const chHtml = chEntries.map(([ch, cnt]) => `
      <span class="tag" style="font-size:11px">${ch}: ${cnt}</span>
    `).join(' ') || 'Sin datos';

    overlay.innerHTML = `
      <div class="detalle-panel" style="max-width:540px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <span class="widget-title">Telemetría & Presupuesto IA (Kernel)</span>
          <button class="gw-modo-btn" style="padding:2px 8px;font-size:11px" onclick="cerrarModalObservabilidadIA()">✕</button>
        </div>

        <div style="background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span style="font-size:12px;color:var(--text-dim)">Cuota diaria consumida</span>
            <strong style="font-size:13px">${d.hoy} / ${d.limite} turnos (${pct}%)</strong>
          </div>
          <div style="background:var(--surface1);height:10px;border-radius:5px;overflow:hidden;border:1px solid var(--border)">
            <div style="width:${Math.min(pct, 100)}%;background:${colorBarra};height:100%;transition:width .3s"></div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px">
          <div style="background:var(--surface2);padding:10px;border-radius:8px;border:1px solid var(--border);font-size:12px">
            <div style="color:var(--text-dim);margin-bottom:2px">Proveedor Activo</div>
            <strong style="color:var(--color-accent)">${d.proveedor || 'Google Gemini'}</strong>
            <div style="font-size:10px;color:var(--text-dim);margin-top:2px">${d.modelo || 'gemini-2.5-flash'}</div>
          </div>
          <div style="background:var(--surface2);padding:10px;border-radius:8px;border:1px solid var(--border);font-size:12px">
            <div style="color:var(--text-dim);margin-bottom:2px">Canales Activos</div>
            <div>${chHtml}</div>
            <div style="font-size:10px;color:var(--text-dim);margin-top:2px">Latencia prom: ${d.latencia_promedio_ms || 0} ms</div>
          </div>
        </div>

        <div class="gw-field" style="margin-bottom:14px">
          <label style="font-size:11px;font-weight:600;margin-bottom:6px;display:block">Consumo por Agente Hoy</label>
          <div style="max-height:130px;overflow-y:auto;background:var(--surface1);padding:8px;border-radius:8px;border:1px solid var(--border)">
            ${agHtml}
          </div>
        </div>

        <div class="gw-field" style="border-top:1px solid var(--border);padding-top:12px">
          <label style="font-size:11px;font-weight:600;margin-bottom:4px;display:block">Ajustar Presupuesto / Límite Diario</label>
          <div style="display:flex;gap:6px">
            <input type="number" id="inpLimiteDiario" value="${d.limite}" min="5" max="10000" class="gw-inline-input" style="width:110px">
            <button class="gw-save-btn" onclick="guardarPresupuestoDiario()">Guardar límite</button>
          </div>
          <div style="font-size:10px;color:var(--text-dim);margin-top:4px">Define el tope diario de consultas para controlar cuota o consumo.</div>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
  } catch (e) {
    mostrarToast('Error cargando observabilidad: ' + e.message, 'error');
  }
}

function cerrarModalObservabilidadIA() {
  const el = document.getElementById('obsIAOverlay');
  if (el) el.remove();
}

async function guardarPresupuestoDiario() {
  const inp = document.getElementById('inpLimiteDiario');
  if (!inp) return;
  const nuevo = parseInt(inp.value, 10);
  if (isNaN(nuevo) || nuevo <= 0) {
    mostrarToast('Ingresa un número válido mayor a 0', 'error');
    return;
  }
  try {
    const r = await fetch('/api/uso-ia/presupuesto', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limite_diario: nuevo }),
    });
    const d = await r.json();
    if (d.ok) {
      mostrarToast(`Límite diario actualizado a ${nuevo} consultas`, 'success');
      cerrarModalObservabilidadIA();
      actualizarStatus();
    } else {
      mostrarToast('Error: ' + (d.error || 'falló'), 'error');
    }
  } catch (e) {
    mostrarToast('Error de red: ' + e.message, 'error');
  }
}

async function abrirModalHitl() {
  const anterior = document.getElementById('hitlOverlay');
  if (anterior) anterior.remove();

  try {
    const r = await fetch('/api/hitl/pendientes');
    const d = await r.json();
    const pendientes = d.solicitudes || [];
    if (!pendientes.length) {
      mostrarToast('No hay autorizaciones pendientes', 'info');
      actualizarStatus();
      return;
    }

    const overlay = document.createElement('div');
    overlay.className = 'detalle-overlay';
    overlay.id = 'hitlOverlay';
    overlay.onclick = (e) => { if (e.target === overlay) cerrarModalHitl(); };

    const itemsHtml = pendientes.map(s => `
      <div style="background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:12px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <strong style="color:var(--color-accent)">Agente: ${s.agente}</strong>
          <span style="font-size:11px;color:var(--text-dim)">#${s.id} · ${s.creado_at || ''}</span>
        </div>
        <div style="font-size:13px;margin-bottom:8px;font-weight:500">${s.resumen_humano}</div>
        <div style="font-size:11px;color:var(--text-dim);background:var(--surface1);padding:6px;border-radius:6px;margin-bottom:10px;font-family:var(--font-mono)">
          Acción: ${s.accion} | Params: ${JSON.stringify(s.parametros || {})}
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="gw-modo-btn" style="color:var(--red);border-color:var(--red)" onclick="resolverAccionHitl(${s.id}, 'rechazado')">Rechazar</button>
          <button class="gw-save-btn" onclick="resolverAccionHitl(${s.id}, 'aprobado')">Aprobar Acción</button>
        </div>
      </div>
    `).join('');

    overlay.innerHTML = `
      <div class="detalle-panel" style="max-width:550px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <span class="widget-title">Human-In-The-Loop: Autorizaciones</span>
          <button class="gw-modo-btn" style="padding:2px 8px;font-size:11px" onclick="cerrarModalHitl()">✕</button>
        </div>
        <p style="font-size:12px;color:var(--text-dim);margin-bottom:14px">
          Los siguientes agentes solicitaron permiso para ejecutar acciones sensibles en tu sistema:
        </p>
        <div style="max-height:400px;overflow-y:auto">
          ${itemsHtml}
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
  } catch (e) {
    mostrarToast('Error cargando solicitudes HITL: ' + e, 'error');
  }
}

function cerrarModalHitl() {
  const el = document.getElementById('hitlOverlay');
  if (el) el.remove();
}

async function resolverAccionHitl(id, decision) {
  try {
    const r = await fetch(`/api/hitl/${id}/resolver`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision })
    });
    const d = await r.json();
    if (d.ok) {
      mostrarToast(`Solicitud #${id} ${decision}`, 'success');
      cerrarModalHitl();
      actualizarStatus();
    } else {
      mostrarToast('Error: ' + (d.error || 'no resuelto'), 'error');
    }
  } catch (e) {
    mostrarToast('Error de red: ' + e, 'error');
  }
}

// --- Vista Ideas/Proyectos ("Pinterest de ideas") ---
let ideaDetalleActualId = null; // null = creando una idea nueva

async function cargarIdeasView() {
  const grid = document.getElementById('ideaGrid');
  const estado = document.getElementById('ideasFiltroEstado').value;
  try {
    const r = await fetch('/api/semillas' + (estado ? '?estado=' + estado : ''));
    const d = await r.json();
    renderIdeaGrid(d.semillas || []);
  } catch (e) {
    grid.innerHTML = `<div class="widget-error">Error cargando ideas: ${e.message}</div>`;
  }
}

function renderIdeaGrid(lista) {
  const grid = document.getElementById('ideaGrid');
  if (!lista.length) {
    grid.innerHTML = '<div class="empty">Sin ideas todavía. Usa "+ Nueva idea" o cuéntale una al Agente Creativo.</div>';
    return;
  }
  grid.innerHTML = lista.map(idea => {
    const img = (idea.primer_adjunto)
      ? `<img class="idea-card-img" src="${idea.primer_adjunto}">`
      : '<div class="idea-card-noimg">&#128161;</div>';
    const snippet = (idea.descripcion || '').slice(0, 90);
    const tags = (idea.etiquetas || []).map(t => `<span class="tag">${t}</span>`).join('');
    return `<div class="idea-card" onclick="abrirDetalleIdea(${idea.id})">
      ${img}
      <div class="idea-card-body">
        <span class="estado-badge estado-${idea.estado}">${idea.estado}</span>
        <div class="idea-card-title">${idea.titulo}</div>
        <div class="idea-card-snippet">${snippet}</div>
        <div>${tags}</div>
      </div>
    </div>`;
  }).join('');
}

async function abrirDetalleIdea(id) {
  ideaDetalleActualId = id;
  let idea = { titulo: '', descripcion: '', etiquetas: [], estado: 'idea', adjuntos: [] };
  if (id) {
    try {
      const r = await fetch(`/api/semillas/${id}`);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      idea = await r.json();
    } catch (e) {
      mostrarToast('Error cargando la idea: ' + e.message, 'error');
      return;
    }
  }

  const overlay = document.createElement('div');
  overlay.className = 'detalle-overlay';
  overlay.id = 'detalleOverlay';
  overlay.onclick = (e) => { if (e.target === overlay) cerrarDetalleIdea(); };

  const adjuntosHtml = (idea.adjuntos || []).map(a => `<img src="${a.ruta_archivo}">`).join('');
  const estados = ['idea', 'desarrollada', 'proyecto', 'archivada'];
  const opcionesEstado = estados.map(e => `<option value="${e}" ${e === idea.estado ? 'selected' : ''}>${e}</option>`).join('');

  overlay.innerHTML = `
    <div class="detalle-panel">
      <span class="widget-title">${id ? 'Editar idea #' + id : 'Nueva idea'}</span>
      <div style="margin-top:10px">
        <label style="font-size:10px;color:var(--text-dim)">TÍTULO</label>
        <input id="detTitulo" value="${(idea.titulo || '').replace(/"/g, '&quot;')}">
        <label style="font-size:10px;color:var(--text-dim)">CONTENIDO</label>
        <textarea id="detContenido" rows="6">${idea.descripcion || ''}</textarea>
        <label style="font-size:10px;color:var(--text-dim)">ETIQUETAS (separadas por coma)</label>
        <input id="detEtiquetas" value="${(idea.etiquetas || []).join(', ')}">
        ${id ? `<label style="font-size:10px;color:var(--text-dim)">ESTADO</label>
        <select id="detEstado">${opcionesEstado}</select>` : ''}
        <div class="detalle-adjuntos" id="detAdjuntos">${adjuntosHtml}</div>
        ${id ? `<input type="file" id="detArchivo" accept="image/*" style="margin-bottom:10px">` : ''}
        <div style="display:flex;gap:8px;margin-top:6px">
          <button class="gw-save-btn" onclick="guardarDetalleIdea()">Guardar</button>
          <button class="gw-modo-btn" onclick="cerrarDetalleIdea()">Cancelar</button>
        </div>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  if (id) {
    document.getElementById('detArchivo').addEventListener('change', (e) => subirAdjuntoIdea(id, e.target.files[0]));
  }
}

function cerrarDetalleIdea() {
  const overlay = document.getElementById('detalleOverlay');
  if (overlay) overlay.remove();
  ideaDetalleActualId = null;
}

async function guardarDetalleIdea() {
  const titulo = document.getElementById('detTitulo').value.trim();
  const contenido = document.getElementById('detContenido').value.trim();
  const etiquetas = document.getElementById('detEtiquetas').value.split(',').map(s => s.trim()).filter(Boolean);
  const estadoEl = document.getElementById('detEstado');

  try {
    if (ideaDetalleActualId) {
      await fetch(`/api/semillas/${ideaDetalleActualId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titulo, contenido, etiquetas }),
      });
      if (estadoEl) {
        await fetch(`/api/semillas/${ideaDetalleActualId}/estado`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ estado: estadoEl.value }),
        });
      }
    } else {
      if (!titulo || !contenido) {
        mostrarToast('Falta título o contenido', 'error');
        return;
      }
      await fetch('/api/semillas', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titulo, contenido, etiquetas }),
      });
    }
    mostrarToast('Idea guardada', 'success');
    cerrarDetalleIdea();
    cargarIdeasView();
  } catch (e) {
    mostrarToast('Error guardando: ' + e.message, 'error');
  }
}

async function subirAdjuntoIdea(id, archivo) {
  if (!archivo) return;
  const formData = new FormData();
  formData.append('archivo', archivo);
  try {
    const r = await fetch(`/api/semillas/${id}/adjunto`, { method: 'POST', body: formData });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    mostrarToast('Adjunto subido', 'success');
    cerrarDetalleIdea();
    abrirDetalleIdea(id);
  } catch (e) {
    mostrarToast('Error subiendo adjunto: ' + e.message, 'error');
  }
}

// --- Oportunidades / Concursos ---
async function cargarOportunidadesView() {
  const el = document.getElementById('oportContent');
  if (!el) return;
  const estado = document.getElementById('oportFiltroEstado').value;
  el.innerHTML = '<div class="loading">Cargando</div>';
  try {
    const r = await fetch('/api/oportunidades' + (estado ? '?estado=' + estado : ''));
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    const lista = d.oportunidades || [];
    if (!lista.length) {
      el.innerHTML = '<div class="empty">Sin oportunidades registradas todavía. Pídele al Agente Investigador que busque fondos.</div>';
      return;
    }
    const badgeDe = (estado) => ({ nueva: 'idea', revisada: 'desarrollada', postulada: 'proyecto', descartada: 'archivada' }[estado] || 'idea');
    el.innerHTML = `<div class="oport-board">${lista.map(o => `
      <div class="oport-card">
        <div class="oport-card-fuente">${o.fuente}</div>
        <div class="oport-card-titulo">${o.hallazgo}</div>
        <div class="oport-card-meta">${o.monto_estimado ? 'Monto: ' + o.monto_estimado + ' — ' : ''}${o.fecha_cierre ? 'Cierra: ' + o.fecha_cierre : ''}</div>
        ${o.relevancia_nota ? `<div class="oport-card-nota">${o.relevancia_nota}</div>` : ''}
        <span class="estado-badge estado-${badgeDe(o.estado)}">${o.estado}</span>
        <div class="oport-card-actions" style="margin-top:8px">
          ${o.estado !== 'revisada' ? `<button onclick="cambiarEstadoOportunidad(${o.id},'revisada')" data-ayuda="Marca que ya revisaste este fondo.">Marcar revisada</button>` : ''}
          ${o.estado !== 'postulada' ? `<button onclick="cambiarEstadoOportunidad(${o.id},'postulada')" data-ayuda="Marca que ya postulaste a este fondo.">Postulada</button>` : ''}
          ${o.estado !== 'descartada' ? `<button onclick="cambiarEstadoOportunidad(${o.id},'descartada')" data-ayuda="Descarta este fondo, no te interesa.">Descartar</button>` : ''}
        </div>
      </div>`).join('')}</div>`;
  } catch (e) {
    el.innerHTML = `<div class="widget-error">Error: ${e.message}</div>`;
  }
}

async function cambiarEstadoOportunidad(id, estado) {
  try {
    await fetch(`/api/oportunidades/${id}/estado`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ estado }),
    });
    mostrarToast('Oportunidad actualizada', 'success');
    cargarOportunidadesView();
  } catch (e) {
    mostrarToast('Error: ' + e.message, 'error');
  }
}

// --- Vista de Código y Desarrollo (Agente Build) ---
async function cargarEstadoProyecto() {
  const cont = document.getElementById('codigoEstadoContenido');
  const badge = document.getElementById('codigoRutaBadge');
  if (!cont) return;
  cont.textContent = 'Consultando estado del repositorio y proyecto...';
  try {
    const r = await fetch('/api/codigo/estado');
    const data = await r.json();
    if (data.ok) {
      if (badge) {
        const repoNombre = (data.ruta || '').split(/\\|\//).filter(Boolean).pop() || 'imrryr-os';
        badge.textContent = `${data.branch} @ ${repoNombre}`;
      }
      cont.textContent = data.estado || 'Sin estado registrado.';
    } else {
      cont.textContent = 'No se pudo cargar el estado: ' + (data.error || 'error desconocido');
    }
  } catch (err) {
    cont.textContent = 'Error conectando con la API de código: ' + err.message;
  }
}

function ejecutarAccionCodigo(accion) {
  const inp = document.getElementById('chatInp_codigo');
  const btn = document.getElementById('chatBtn_codigo');
  if (!inp || !btn) return;
  let prompt = '';
  switch (accion) {
    case 'pytest':
      prompt = 'Ejecuta los tests del proyecto con pytest (.venv\\Scripts\\pytest -q) e infórmame los resultados detallados.';
      break;
    case 'ruff':
      prompt = 'Ejecuta el linter (.venv\\Scripts\\ruff check .) para verificar sintaxis, imports y calidad de código.';
      break;
    case 'git_status':
      prompt = 'Ejecuta git status y git log -n 5 para revisar los cambios recientes y archivos pendientes.';
      break;
    case 'ast_graph':
      prompt = 'Usa el servidor MCP codebase-memory para inspeccionar la arquitectura del proyecto, listar componentes clave y resumir dependencias.';
      break;
    default:
      prompt = accion;
  }
  inp.value = prompt;
  btn.click();
}

// ============================================
// REUNIONES & CANVAS CONCEPTUAL INFINITO
// ============================================
let reunionesLista = [];
let reunionActiva = null;
let reunionSubtabActual = 'canvas';
let grabadorReunion = null;
let chunksGrabacionReunion = [];
let grabacionReunionInterval = null;
let segundosGrabacionReunion = 0;
let canvasInicializado = false;

const canvasState = {
  panX: 40,
  panY: 30,
  scale: 1.0,
  isPanning: false,
  startX: 0,
  startY: 0,
  activeTool: 'select',
  selectedElement: null,
  connectingSourceId: null,
  draggedNode: null,
  dragOffsetX: 0,
  dragOffsetY: 0,
  resizingNode: null,
  resizeStartX: 0,
  resizeStartY: 0,
  initialWidth: 0,
  initialHeight: 0,
  theme: 'black',
  mapa: { nodos: [], conexiones: [] },
};

function inicializarReunionesView() {
  if (!canvasInicializado) {
    initConceptMapCanvas();
    canvasInicializado = true;
  }
}

async function cargarReunionesView() {
  inicializarReunionesView();
  try {
    const r = await fetch('/api/reuniones');
    const data = await r.json();
    if (data && data.ok) {
      reunionesLista = data.reuniones || [];
      poblarSelectorReuniones();
      if (reunionesLista.length > 0) {
        const idASeleccionar = reunionActiva ? reunionActiva.id : reunionesLista[0].id;
        await seleccionarReunion(idASeleccionar);
      } else {
        limpiarDetalleReunion();
      }
    }
  } catch (err) {
    mostrarToast('Error cargando reuniones: ' + err.message, 'error');
  }
}

function poblarSelectorReuniones() {
  const sel = document.getElementById('reunionesSelector');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- Seleccionar reunión --</option>' +
    reunionesLista.map(reu => {
      const f = reu.fecha ? ` (${reu.fecha})` : '';
      return `<option value="${reu.id}">${(reu.titulo || 'Sin título') + f}</option>`;
    }).join('');
  if (reunionActiva) {
    sel.value = String(reunionActiva.id);
  }
}

async function seleccionarReunion(reunionId) {
  if (!reunionId) return;
  try {
    const r = await fetch(`/api/reuniones/${reunionId}`);
    const data = await r.json();
    if (data && data.ok && data.reunion) {
      reunionActiva = data.reunion;
      const sel = document.getElementById('reunionesSelector');
      if (sel) sel.value = String(reunionId);
      mostrarDetalleReunion(reunionActiva);
    }
  } catch (err) {
    mostrarToast('Error obteniendo reunión: ' + err.message, 'error');
  }
}

function limpiarDetalleReunion() {
  reunionActiva = null;
  document.getElementById('reunionAudioBanner').style.display = 'none';
  document.getElementById('reunionResumenTexto').textContent = 'No hay reuniones registradas todavía. Graba o sube una reunión.';
  document.getElementById('reunionConclusionesTexto').textContent = 'No hay acuerdos registrados.';
  document.getElementById('reunionTareasLista').innerHTML = '<div style="color:var(--text-dim);font-size:12px">No hay tareas pendientes.</div>';
  document.getElementById('reunionTranscripcionTexto').value = '';
  canvasState.mapa = { nodos: [], conexiones: [] };
  renderConceptMapCanvas(canvasState.mapa);
}

function mostrarDetalleReunion(reunion) {
  // 1. Audio Banner
  const banner = document.getElementById('reunionAudioBanner');
  const player = document.getElementById('reunionAudioPlayer');
  const titAudio = document.getElementById('reunionAudioTitulo');
  if (reunion.audio_ruta) {
    const filename = reunion.audio_ruta.split(/[/\\]/).pop();
    player.src = `/reuniones_audio/${filename}`;
    titAudio.textContent = `Audio: ${reunion.titulo || filename}`;
    banner.style.display = 'flex';
  } else {
    banner.style.display = 'none';
    player.src = '';
  }

  // 2. Minuta Resumen y Conclusiones
  document.getElementById('reunionResumenTexto').textContent = reunion.resumen_ejecutivo || 'Aún no hay resumen generado. Haz clic en "Procesar Minuta y Grafo".';
  document.getElementById('reunionConclusionesTexto').textContent = reunion.conclusiones || 'Aún no hay acuerdos registrados.';

  // 3. Tareas y Compromisos agrupadas por responsable
  const contenedorTareas = document.getElementById('reunionTareasLista');
  const tareas = reunion.acuerdos_tareas || [];
  if (tareas.length === 0) {
    contenedorTareas.innerHTML = '<div style="color:var(--text-dim);font-size:12px;padding:8px 0">No hay tareas detectadas todavía. Procesa la minuta para extraerlas.</div>';
  } else {
    const agrupadas = {};
    tareas.forEach((t, idx) => {
      const resp = (t.responsable || '').trim() || 'General / Sin asignar';
      if (!agrupadas[resp]) agrupadas[resp] = [];
      agrupadas[resp].push({ ...t, origIdx: idx });
    });

    contenedorTareas.innerHTML = Object.entries(agrupadas).map(([resp, items]) => {
      const itemsHtml = items.map(t => {
        const fecha = t.fecha_limite ? `<span style="font-size:11px;color:var(--text-dim);margin-left:6px">📅 ${t.fecha_limite}</span>` : '';
        const agendada = t.agendada ? '<span style="font-size:10px;color:#10b981;margin-left:auto;font-weight:600">✓ En Agenda</span>' : '';
        return `
          <label style="display:flex;align-items:center;gap:10px;background:var(--surface2);padding:9px 12px;border-radius:6px;border:1px solid var(--border);cursor:pointer;margin-bottom:6px">
            <input type="checkbox" class="chk-tarea-reunion" data-index="${t.origIdx}" ${t.agendada ? 'disabled' : 'checked'}>
            <span style="font-size:13px;color:var(--text);flex:1">${t.tarea || 'Tarea sin descripción'} ${fecha}</span>
            ${agendada}
          </label>
        `;
      }).join('');

      return `
        <div style="margin-bottom:14px">
          <div style="font-size:12px;font-weight:600;color:var(--color-accent);margin-bottom:6px;display:flex;align-items:center;gap:6px">
            <svg class="icon" style="width:14px;height:14px"><use href="#icon-users"/></svg>
            <span>${resp}</span>
            <span style="font-size:10px;color:var(--text-dim);font-weight:normal">(${items.length} ${items.length === 1 ? 'compromiso' : 'compromisos'})</span>
          </div>
          <div>${itemsHtml}</div>
        </div>
      `;
    }).join('');
  }

  // 4. Transcripción Cruda
  document.getElementById('reunionTranscripcionTexto').value = reunion.transcripcion_cruda || '';

  // 5. Canvas Mapa Conceptual
  canvasState.mapa = reunion.mapa_conceptual_json && reunion.mapa_conceptual_json.nodos ? reunion.mapa_conceptual_json : { nodos: [], conexiones: [] };
  renderConceptMapCanvas(canvasState.mapa);
}

function cambiarSubtabReunion(subtab) {
  reunionSubtabActual = subtab;
  document.querySelectorAll('#reunionSub-canvas, #reunionSub-minuta, #reunionSub-transcripcion').forEach(b => {
    b.classList.toggle('active', b.id === 'reunionSub-' + subtab);
  });
  document.getElementById('reunionCanvasContainer').style.display = subtab === 'canvas' ? 'block' : 'none';
  document.getElementById('reunionMinutaContainer').style.display = subtab === 'minuta' ? 'block' : 'none';
  document.getElementById('reunionTranscripcionContainer').style.display = subtab === 'transcripcion' ? 'block' : 'none';
  if (subtab === 'canvas') {
    updateCanvasTransform();
  }
}

// --- Grabación en Vivo con Micrófono ---
async function toggleGrabacionReunion() {
  const btn = document.getElementById('btnGrabarReunion');
  const lbl = document.getElementById('lblGrabarReunion');
  const badge = document.getElementById('reunionTimerBadge');

  if (grabadorReunion && grabadorReunion.state === 'recording') {
    grabadorReunion.stop();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    grabadorReunion = new MediaRecorder(stream);
    chunksGrabacionReunion = [];
    segundosGrabacionReunion = 0;

    grabadorReunion.ondataavailable = e => chunksGrabacionReunion.push(e.data);
    grabadorReunion.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      clearInterval(grabacionReunionInterval);
      btn.classList.remove('btn-grabando-reunion');
      lbl.textContent = 'Procesando Grabación...';
      btn.disabled = true;

      const blob = new Blob(chunksGrabacionReunion, { type: 'audio/webm' });
      await enviarAudioReunion(blob, 'grabacion_reunion.webm');

      lbl.textContent = 'Grabar Reunión';
      btn.disabled = false;
      badge.style.display = 'none';
    };

    grabadorReunion.start();
    btn.classList.add('btn-grabando-reunion');
    lbl.textContent = 'Detener Grabación';
    badge.textContent = '00:00';
    badge.style.display = 'inline-block';

    grabacionReunionInterval = setInterval(() => {
      segundosGrabacionReunion++;
      const m = String(Math.floor(segundosGrabacionReunion / 60)).padStart(2, '0');
      const s = String(segundosGrabacionReunion % 60).padStart(2, '0');
      badge.textContent = `${m}:${s}`;
    }, 1000);

    mostrarToast('Grabación de reunión iniciada', 'success');
  } catch (err) {
    mostrarToast('No se pudo acceder al micrófono: ' + err.message, 'error');
  }
}

// --- Subida de Archivo de Audio ---
function abrirModalSubirAudio() {
  document.getElementById('reunionesDropzoneArea').style.display = 'block';
}

function cerrarModalSubirAudio() {
  document.getElementById('reunionesDropzoneArea').style.display = 'none';
  document.getElementById('audioSubirTitulo').value = '';
  document.getElementById('audioSubirParticipantes').value = '';
}

async function archivoAudioSeleccionado(input) {
  const file = input.files && input.files[0];
  if (!file) return;
  const titulo = document.getElementById('audioSubirTitulo').value.trim();
  const participantes = document.getElementById('audioSubirParticipantes').value.trim();
  cerrarModalSubirAudio();
  await enviarAudioReunion(file, file.name, titulo, participantes);
  input.value = '';
}

async function enviarAudioReunion(blobOrFile, nombreArchivo, titulo, participantes) {
  mostrarToast('Subiendo y transcribiendo audio con Whisper...', 'info');
  try {
    const formData = new FormData();
    formData.append('archivo', blobOrFile, nombreArchivo);
    if (titulo) formData.append('titulo', titulo);
    if (participantes) formData.append('participantes', participantes);

    const r = await fetch('/api/reuniones/upload', {
      method: 'POST',
      body: formData,
    });
    const data = await r.json();
    if (data && data.ok) {
      mostrarToast('Transcripción completada con éxito', 'success');
      await cargarReunionesView();
      if (data.reunion_id) {
        await seleccionarReunion(data.reunion_id);
      }
    } else {
      mostrarToast('Error transcribiendo: ' + (data.error || 'Fallo desconocido'), 'error');
    }
  } catch (err) {
    mostrarToast('Error subiendo audio: ' + err.message, 'error');
  }
}

// --- Procesar Minuta y Grafo ---
async function procesarReunionActual() {
  if (!reunionActiva) {
    mostrarToast('Selecciona o sube primero una reunión para procesar', 'error');
    return;
  }
  const btn = document.getElementById('btnProcesarReunion');
  btn.disabled = true;
  mostrarToast('Agente analizando reunión y generando mapa conceptual...', 'info');
  try {
    const r = await fetch(`/api/reuniones/${reunionActiva.id}/procesar`, { method: 'POST' });
    const data = await r.json();
    if (data && data.ok && data.reunion) {
      reunionActiva = data.reunion;
      mostrarDetalleReunion(reunionActiva);
      mostrarToast('¡Minuta y mapa conceptual generados!', 'success');
    } else {
      mostrarToast('Error procesando: ' + (data.error || 'Respuesta inválida'), 'error');
    }
  } catch (err) {
    mostrarToast('Error procesando minuta: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

// --- Volcar Tareas a Agenda y Pendientes ---
async function volcarTareasSeleccionadas() {
  if (!reunionActiva) return;
  const checkboxes = document.querySelectorAll('.chk-tarea-reunion:checked');
  const indices = Array.from(checkboxes).map(cb => parseInt(cb.dataset.index, 10));
  if (indices.length === 0) {
    mostrarToast('Selecciona al menos una tarea para agendar', 'info');
    return;
  }

  try {
    const r = await fetch(`/api/reuniones/${reunionActiva.id}/agendar-tareas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        indices: indices,
        agendar_en_eventos: true,
        agendar_en_pendientes: true,
      }),
    });
    const data = await r.json();
    if (data && data.ok) {
      mostrarToast(`${data.total_procesadas} compromisos volcados a Agenda y Pendientes`, 'success');
      await seleccionarReunion(reunionActiva.id);
    } else {
      mostrarToast('Error volcando tareas: ' + (data.error || 'Error desconocido'), 'error');
    }
  } catch (err) {
    mostrarToast('Error al agendar tareas: ' + err.message, 'error');
  }
}

function copiarTranscripcionReunion() {
  const txt = document.getElementById('reunionTranscripcionTexto').value;
  if (!txt) return;
  navigator.clipboard.writeText(txt)
    .then(() => mostrarToast('Transcripción copiada al portapapeles', 'success'))
    .catch(() => mostrarToast('No se pudo copiar el texto', 'error'));
}

async function guardarTranscripcionReunion() {
  if (!reunionActiva) {
    mostrarToast('Selecciona o crea primero una reunión antes de guardar la transcripción', 'info');
    return;
  }
  const txt = document.getElementById('reunionTranscripcionTexto').value;
  try {
    const r = await fetch(`/api/reuniones/${reunionActiva.id}/transcripcion`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcripcion: txt }),
    });
    const data = await r.json();
    if (data && data.ok) {
      reunionActiva.transcripcion_cruda = txt;
      mostrarToast('Transcripción guardada. Ya puedes hacer clic en "Procesar Minuta y Grafo"', 'success');
    } else {
      mostrarToast('Error guardando transcripción: ' + (data.error || 'Error desconocido'), 'error');
    }
  } catch (err) {
    mostrarToast('Error guardando texto: ' + err.message, 'error');
  }
}

async function crearNuevaReunionModal() {
  const titulo = prompt('Ingresa el título para la nueva reunión:', 'Reunión de Equipo');
  if (!titulo || !titulo.trim()) return;

  const participantes = prompt('Participantes (separados por coma, opcional):', '');

  try {
    const r = await fetch('/api/reuniones', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        titulo: titulo.trim(),
        participantes: participantes ? participantes.trim() : '',
        transcripcion_cruda: '',
      }),
    });
    const data = await r.json();
    if (data && data.ok && data.id) {
      await cargarReunionesView();
      await seleccionarReunion(data.id);
      cambiarSubtabReunion('transcripcion');
      mostrarToast('Reunión creada. Pega el texto en la pestaña Transcripción o sube un audio.', 'success');
    } else {
      mostrarToast('No se pudo crear la reunión: ' + (data.error || 'Error desconocido'), 'error');
    }
  } catch (err) {
    mostrarToast('Error creando reunión: ' + err.message, 'error');
  }
}

// ============================================
// MOTOR DE CANVAS CONCEPTUAL INFINITO
// ============================================
function initConceptMapCanvas() {
  const svg = document.getElementById('conceptMapSvg');
  if (!svg) return;

  // Zoom con rueda de mouse
  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    canvasZoom(factor);
  }, { passive: false });

  // Panning y Creación
  svg.addEventListener('mousedown', e => {
    if (e.target.closest('.canvas-node-g') || e.target.closest('.canvas-resize-handle')) return;

    if (canvasState.activeTool === 'select' || canvasState.activeTool === 'conector') {
      canvasState.isPanning = true;
      canvasState.startX = e.clientX - canvasState.panX;
      canvasState.startY = e.clientY - canvasState.panY;
      svg.style.cursor = 'grabbing';
      if (canvasState.selectedElement) {
        canvasState.selectedElement = null;
        actualizarSeleccionCanvas();
      }
    } else if (['idea', 'tarea', 'decision'].includes(canvasState.activeTool)) {
      const rect = svg.getBoundingClientRect();
      const clickX = (e.clientX - rect.left - canvasState.panX) / canvasState.scale;
      const clickY = (e.clientY - rect.top - canvasState.panY) / canvasState.scale;
      crearNodoEnCanvas(canvasState.activeTool, clickX, clickY);
      setCanvasTool('select');
    }
  });

  window.addEventListener('mousemove', e => {
    if (canvasState.isPanning) {
      canvasState.panX = e.clientX - canvasState.startX;
      canvasState.panY = e.clientY - canvasState.startY;
      updateCanvasTransform();
    } else if (canvasState.resizingNode) {
      const deltaX = (e.clientX - canvasState.resizeStartX) / canvasState.scale;
      const deltaY = (e.clientY - canvasState.resizeStartY) / canvasState.scale;
      canvasState.resizingNode.ancho = Math.max(90, Math.round(canvasState.initialWidth + deltaX));
      canvasState.resizingNode.alto = Math.max(45, Math.round(canvasState.initialHeight + deltaY));
      renderConceptMapCanvas(canvasState.mapa);
    } else if (canvasState.draggedNode) {
      const svgRect = svg.getBoundingClientRect();
      const nx = (e.clientX - svgRect.left - canvasState.panX) / canvasState.scale - canvasState.dragOffsetX;
      const ny = (e.clientY - svgRect.top - canvasState.panY) / canvasState.scale - canvasState.dragOffsetY;
      canvasState.draggedNode.x = Math.round(nx);
      canvasState.draggedNode.y = Math.round(ny);
      renderConceptMapCanvas(canvasState.mapa);
    }
  });

  window.addEventListener('mouseup', () => {
    if (canvasState.isPanning) {
      canvasState.isPanning = false;
      svg.style.cursor = canvasState.activeTool === 'select' ? 'grab' : (canvasState.activeTool === 'conector' ? 'crosshair' : 'copy');
    }
    if (canvasState.resizingNode) {
      canvasState.resizingNode = null;
    }
    if (canvasState.draggedNode) {
      canvasState.draggedNode = null;
    }
  });

  updateCanvasTransform();
}

function updateCanvasTransform() {
  const layer = document.getElementById('canvasTransformLayer');
  const label = document.getElementById('canvasZoomLabel');
  if (layer) {
    layer.setAttribute('transform', `translate(${canvasState.panX}, ${canvasState.panY}) scale(${canvasState.scale})`);
  }
  if (label) {
    label.textContent = Math.round(canvasState.scale * 100) + '%';
  }
}

function canvasZoom(factor) {
  const nuevoScale = Math.max(0.2, Math.min(3.0, canvasState.scale * factor));
  const svg = document.getElementById('conceptMapSvg');
  if (svg) {
    const rect = svg.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    canvasState.panX = cx - (cx - canvasState.panX) * (nuevoScale / canvasState.scale);
    canvasState.panY = cy - (cy - canvasState.panY) * (nuevoScale / canvasState.scale);
  }
  canvasState.scale = nuevoScale;
  updateCanvasTransform();
}

function canvasResetView() {
  canvasState.scale = 1.0;
  canvasState.panX = 60;
  canvasState.panY = 40;
  updateCanvasTransform();
}

function setCanvasTool(tool) {
  canvasState.activeTool = tool;
  canvasState.connectingSourceId = null;
  document.querySelectorAll('.canvas-tool-btn').forEach(btn => {
    btn.classList.toggle('active', btn.id === 'tool-' + tool);
  });
  const svg = document.getElementById('conceptMapSvg');
  if (!svg) return;
  if (tool === 'select') {
    svg.style.cursor = 'grab';
  } else if (tool === 'conector') {
    svg.style.cursor = 'crosshair';
  } else {
    svg.style.cursor = 'copy';
  }
}

function toggleCanvasTheme() {
  const container = document.getElementById('reunionCanvasContainer');
  if (!container) return;
  canvasState.theme = canvasState.theme === 'black' ? 'white' : 'black';
  container.classList.toggle('theme-white', canvasState.theme === 'white');
  const bgRect = document.getElementById('canvasBgRect');
  if (bgRect) {
    bgRect.setAttribute('fill', canvasState.theme === 'white' ? '#f8fafc' : 'url(#canvasGridPattern)');
  }
  const marker = document.getElementById('arrowMarkerPath');
  if (marker) {
    marker.setAttribute('fill', canvasState.theme === 'white' ? '#475569' : '#C09135');
  }
  renderConceptMapCanvas(canvasState.mapa);
}

function abrirSubirImagenCanvas() {
  if (!reunionActiva) {
    mostrarToast('Selecciona o sube primero una reunión para adjuntar imágenes en el canvas', 'info');
    return;
  }
  const inp = document.getElementById('canvasImageFileInput');
  if (inp) inp.click();
}

async function imagenCanvasSeleccionada(input) {
  const file = input.files && input.files[0];
  if (!file || !reunionActiva) return;

  mostrarToast('Subiendo imagen al canvas...', 'info');
  try {
    const formData = new FormData();
    formData.append('archivo', file);

    const r = await fetch(`/api/reuniones/${reunionActiva.id}/imagen`, {
      method: 'POST',
      body: formData,
    });
    const data = await r.json();
    if (data && data.ok) {
      const mapa = canvasState.mapa;
      if (!mapa.nodos) mapa.nodos = [];

      const svg = document.getElementById('conceptMapSvg');
      const rect = svg ? svg.getBoundingClientRect() : { width: 800, height: 600 };
      const cx = (rect.width / 2 - canvasState.panX) / canvasState.scale;
      const cy = (rect.height / 2 - canvasState.panY) / canvasState.scale;

      const imgNode = {
        id: `node-img-${Date.now()}`,
        tipo: 'imagen',
        texto: data.nombre || 'Imagen Adjunta',
        url: data.url,
        x: Math.round(cx - 110),
        y: Math.round(cy - 90),
        ancho: 220,
        alto: 170,
        color: '#8b5cf6',
      };
      mapa.nodos.push(imgNode);
      renderConceptMapCanvas(mapa);
      mostrarToast('Imagen insertada en el canvas. Puedes moverla o redimensionarla arrastrando.', 'success');
    } else {
      mostrarToast('Error subiendo imagen: ' + (data.error || 'Error desconocido'), 'error');
    }
  } catch (err) {
    mostrarToast('Error en carga de imagen: ' + err.message, 'error');
  } finally {
    input.value = '';
  }
}

function crearNodoEnCanvas(tipo, x, y) {
  const mapa = canvasState.mapa;
  if (!mapa.nodos) mapa.nodos = [];
  const nid = `node-${tipo}-${Date.now()}`;
  let texto = 'Nueva Idea';
  let color = '#3b82f6';
  if (tipo === 'tarea') {
    texto = 'Nueva Tarea (Responsable)';
    color = '#f59e0b';
  } else if (tipo === 'decision') {
    texto = 'Nuevo Acuerdo Clave';
    color = '#10b981';
  }
  mapa.nodos.push({
    id: nid,
    tipo: tipo,
    texto: texto,
    x: Math.round(x - 85),
    y: Math.round(y - 32),
    ancho: 170,
    alto: 65,
    color: color,
  });
  renderConceptMapCanvas(mapa);
  mostrarToast('Nodo agregado. Haz doble clic para editar o arrastra desde la esquina para redimensionar.', 'info');
}

function renderConceptMapCanvas(mapa) {
  const edgesLayer = document.getElementById('canvasEdgesLayer');
  const nodesLayer = document.getElementById('canvasNodesLayer');
  if (!edgesLayer || !nodesLayer) return;

  edgesLayer.innerHTML = '';
  nodesLayer.innerHTML = '';

  const nodos = mapa.nodos || [];
  const conexiones = mapa.conexiones || [];
  const nodoMap = new Map();
  nodos.forEach(n => nodoMap.set(n.id, n));

  // 1. Render Conexiones con Curvas Bézier Suaves
  conexiones.forEach(c => {
    const from = nodoMap.get(c.desde);
    const to = nodoMap.get(c.hacia);
    if (!from || !to) return;

    const fromW = from.ancho || 160;
    const fromH = from.alto || 60;
    const toW = to.ancho || 160;
    const toH = to.alto || 60;

    const x1 = from.x + fromW / 2;
    const y1 = from.y + fromH / 2;
    const x2 = to.x + toW / 2;
    const y2 = to.y + toH / 2;

    const dx = x2 - x1;
    const dy = y2 - y1;

    // Cálculo de puntos de control cúbicos Bézier
    let cx1, cy1, cx2, cy2;
    if (Math.abs(dx) >= Math.abs(dy)) {
      const offset = dx * 0.5;
      cx1 = x1 + offset;
      cy1 = y1;
      cx2 = x2 - offset;
      cy2 = y2;
    } else {
      const offset = dy * 0.5;
      cx1 = x1;
      cy1 = y1 + offset;
      cx2 = x2;
      cy2 = y2 - offset;
    }

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.dataset.id = c.id;

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`);
    path.setAttribute('marker-end', 'url(#arrowMarker)');
    path.setAttribute('class', 'canvas-edge-path' + (canvasState.selectedElement && canvasState.selectedElement.id === c.id ? ' selected' : ''));
    if (canvasState.theme === 'white') {
      path.setAttribute('stroke', '#64748b');
    }

    path.addEventListener('click', e => {
      e.stopPropagation();
      canvasState.selectedElement = { type: 'edge', id: c.id };
      actualizarSeleccionCanvas();
    });

    g.appendChild(path);

    if (c.etiqueta) {
      // Punto medio exacto de la curva Bézier en t=0.5
      const mx = 0.125 * x1 + 0.375 * cx1 + 0.375 * cx2 + 0.125 * x2;
      const my = 0.125 * y1 + 0.375 * cy1 + 0.375 * cy2 + 0.125 * y2;
      const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      txt.setAttribute('x', mx);
      txt.setAttribute('y', my - 6);
      txt.setAttribute('text-anchor', 'middle');
      txt.setAttribute('fill', canvasState.theme === 'white' ? '#475569' : '#9a9ab2');
      txt.setAttribute('font-size', '11');
      txt.setAttribute('font-family', 'sans-serif');
      txt.textContent = c.etiqueta;
      g.appendChild(txt);
    }

    edgesLayer.appendChild(g);
  });

  // 2. Render Nodos (Texto o Imagen con redimensionamiento y edición)
  nodos.forEach(n => {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', 'canvas-node-g' + (n.tipo === 'imagen' ? ' canvas-image-node' : '') + (canvasState.selectedElement && canvasState.selectedElement.id === n.id ? ' selected' : ''));
    g.setAttribute('transform', `translate(${n.x}, ${n.y})`);
    g.dataset.id = n.id;

    const w = n.ancho || 160;
    const h = n.alto || 60;
    const bgFill = canvasState.theme === 'white' ? '#ffffff' : '#18181f';
    const textColor = canvasState.theme === 'white' ? '#0f172a' : '#dedee6';

    if (n.tipo === 'imagen') {
      // Tarjeta de Imagen
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('width', w);
      rect.setAttribute('height', h);
      rect.setAttribute('rx', '8');
      rect.setAttribute('fill', bgFill);
      rect.setAttribute('stroke', n.color || '#8b5cf6');
      rect.setAttribute('stroke-width', '2');
      g.appendChild(rect);

      const img = document.createElementNS('http://www.w3.org/2000/svg', 'image');
      img.setAttribute('href', n.url);
      img.setAttribute('x', 6);
      img.setAttribute('y', 6);
      img.setAttribute('width', Math.max(10, w - 12));
      img.setAttribute('height', Math.max(10, h - (n.texto ? 30 : 12)));
      img.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      g.appendChild(img);

      if (n.texto) {
        const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        txt.setAttribute('x', w / 2);
        txt.setAttribute('y', h - 10);
        txt.setAttribute('text-anchor', 'middle');
        txt.setAttribute('fill', textColor);
        txt.setAttribute('font-size', '11');
        txt.setAttribute('font-weight', '500');
        txt.setAttribute('font-family', 'Inter, sans-serif');
        txt.textContent = n.texto.length > 25 ? n.texto.substring(0, 22) + '...' : n.texto;
        g.appendChild(txt);
      }
    } else {
      // Nodo de Texto Estándar
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('width', w);
      rect.setAttribute('height', h);
      rect.setAttribute('rx', n.tipo === 'central' ? '12' : (n.tipo === 'persona' ? '10' : '8'));
      rect.setAttribute('fill', bgFill);
      rect.setAttribute('stroke', n.color || '#6366f1');
      rect.setAttribute('stroke-width', n.tipo === 'central' ? '3' : '2');
      g.appendChild(rect);

      // Barra superior de categoría
      const topBar = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      topBar.setAttribute('x', '0');
      topBar.setAttribute('y', '0');
      topBar.setAttribute('width', w);
      topBar.setAttribute('height', '5');
      topBar.setAttribute('rx', '3');
      topBar.setAttribute('fill', n.color || '#6366f1');
      g.appendChild(topBar);

      // Texto multilinea autoajustado
      const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      txt.setAttribute('x', w / 2);
      txt.setAttribute('text-anchor', 'middle');
      txt.setAttribute('fill', textColor);
      txt.setAttribute('font-size', n.tipo === 'central' ? '13' : '12');
      txt.setAttribute('font-weight', n.tipo === 'central' ? '600' : '500');
      txt.setAttribute('font-family', 'Inter, sans-serif');

      const maxChars = Math.max(12, Math.floor(w / 8.5));
      const lineas = ajustarTextoNodo(n.texto || '', maxChars);
      if (lineas.length === 1) {
        txt.setAttribute('y', h / 2 + 4);
        txt.textContent = lineas[0];
      } else {
        const startY = h / 2 - ((lineas.length - 1) * 7.5) + 3;
        txt.setAttribute('y', startY);
        lineas.forEach((lin, idx) => {
          const tspan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
          tspan.setAttribute('x', w / 2);
          tspan.setAttribute('dy', idx === 0 ? '0' : '15');
          tspan.textContent = lin;
          txt.appendChild(tspan);
        });
      }
      g.appendChild(txt);
    }

    // Tirador de Redimensionamiento (Resize Handle)
    const handleSize = 10;
    const resizeHandle = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    resizeHandle.setAttribute('class', 'canvas-resize-handle');
    resizeHandle.setAttribute('x', w - handleSize);
    resizeHandle.setAttribute('y', h - handleSize);
    resizeHandle.setAttribute('width', handleSize);
    resizeHandle.setAttribute('height', handleSize);
    resizeHandle.setAttribute('rx', '2');
    resizeHandle.setAttribute('title', 'Arrastra para cambiar el tamaño');

    resizeHandle.addEventListener('mousedown', e => {
      e.stopPropagation();
      canvasState.resizingNode = n;
      canvasState.resizeStartX = e.clientX;
      canvasState.resizeStartY = e.clientY;
      canvasState.initialWidth = n.ancho || 160;
      canvasState.initialHeight = n.alto || 60;
    });
    g.appendChild(resizeHandle);

    // Eventos del Nodo
    g.addEventListener('mousedown', e => {
      e.stopPropagation();
      if (canvasState.activeTool === 'conector') {
        if (!canvasState.connectingSourceId) {
          canvasState.connectingSourceId = n.id;
          mostrarToast(`Conectando desde "${(n.texto || '').substring(0, 20)}...". Haz clic en el nodo de destino.`, 'info');
          g.classList.add('selected');
        } else if (canvasState.connectingSourceId !== n.id) {
          conectarNodosCanvas(canvasState.connectingSourceId, n.id);
          canvasState.connectingSourceId = null;
          setCanvasTool('select');
        }
      } else {
        canvasState.selectedElement = { type: 'node', id: n.id };
        actualizarSeleccionCanvas();

        const svg = document.getElementById('conceptMapSvg');
        const svgRect = svg.getBoundingClientRect();
        canvasState.draggedNode = n;
        canvasState.dragOffsetX = (e.clientX - svgRect.left - canvasState.panX) / canvasState.scale - n.x;
        canvasState.dragOffsetY = (e.clientY - svgRect.top - canvasState.panY) / canvasState.scale - n.y;
      }
    });

    g.addEventListener('dblclick', e => {
      e.stopPropagation();
      editarTextoNodo(n);
    });

    nodesLayer.appendChild(g);
  });
}

function ajustarTextoNodo(str, maxChars) {
  if (!str) return [];
  const lineasRaw = str.split('\n');
  const lineas = [];
  for (const parrafo of lineasRaw) {
    const palabras = parrafo.split(' ');
    let actual = '';
    for (const p of palabras) {
      if ((actual + ' ' + p).trim().length > maxChars) {
        if (actual) lineas.push(actual);
        actual = p;
        if (lineas.length >= 4) {
          lineas.push(actual + '...');
          return lineas;
        }
      } else {
        actual = (actual + ' ' + p).trim();
      }
    }
    if (actual) lineas.push(actual);
  }
  return lineas.slice(0, 4);
}

function editarTextoNodo(nodo) {
  const promptMsg = nodo.tipo === 'imagen'
    ? 'Modificar descripción o etiqueta de la imagen:'
    : 'Modificar texto del elemento:\n(Puedes incluir saltos de línea para estructurarlo)';
  const nuevoTexto = prompt(promptMsg, nodo.texto);
  if (nuevoTexto !== null && nuevoTexto.trim() !== '') {
    nodo.texto = nuevoTexto.trim();
    renderConceptMapCanvas(canvasState.mapa);
  }
}

function conectarNodosCanvas(sourceId, targetId) {
  const mapa = canvasState.mapa;
  if (!mapa.conexiones) mapa.conexiones = [];
  const existe = mapa.conexiones.some(c => c.desde === sourceId && c.hacia === targetId);
  if (!existe) {
    mapa.conexiones.push({
      id: `edge-${Date.now()}`,
      desde: sourceId,
      hacia: targetId,
      etiqueta: '',
      curva: 'bezier',
    });
    renderConceptMapCanvas(mapa);
    mostrarToast('Relación conectada con curva Bézier', 'success');
  }
}

function actualizarSeleccionCanvas() {
  document.querySelectorAll('.canvas-node-g').forEach(g => {
    const isSel = canvasState.selectedElement && canvasState.selectedElement.type === 'node' && canvasState.selectedElement.id === g.dataset.id;
    g.classList.toggle('selected', isSel);
  });
  document.querySelectorAll('.canvas-edge-path, .canvas-edge-line').forEach(l => {
    const p = l.parentElement;
    const isSel = canvasState.selectedElement && canvasState.selectedElement.type === 'edge' && canvasState.selectedElement.id === p.dataset.id;
    l.classList.toggle('selected', isSel);
  });
}

function eliminarElementoSeleccionadoCanvas() {
  if (!canvasState.selectedElement) {
    mostrarToast('Selecciona un nodo o flecha para eliminar', 'info');
    return;
  }
  const mapa = canvasState.mapa;
  if (canvasState.selectedElement.type === 'node') {
    const nid = canvasState.selectedElement.id;
    mapa.nodos = (mapa.nodos || []).filter(n => n.id !== nid);
    mapa.conexiones = (mapa.conexiones || []).filter(c => c.desde !== nid && c.hacia !== nid);
    mostrarToast('Nodo eliminado', 'info');
  } else if (canvasState.selectedElement.type === 'edge') {
    const eid = canvasState.selectedElement.id;
    mapa.conexiones = (mapa.conexiones || []).filter(c => c.id !== eid);
    mostrarToast('Conexión eliminada', 'info');
  }
  canvasState.selectedElement = null;
  renderConceptMapCanvas(mapa);
}

async function guardarMapaCanvasActual() {
  if (!reunionActiva) {
    mostrarToast('No hay una reunión activa seleccionada', 'error');
    return;
  }
  try {
    const r = await fetch(`/api/reuniones/${reunionActiva.id}/mapa`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mapa: canvasState.mapa }),
    });
    const data = await r.json();
    if (data && data.ok) {
      mostrarToast('Mapa conceptual guardado con éxito', 'success');
    } else {
      mostrarToast('Error guardando mapa: ' + (data.error || 'Error desconocido'), 'error');
    }
  } catch (err) {
    mostrarToast('Error guardando mapa: ' + err.message, 'error');
  }
}



// Cada perfil empaqueta solo parte de los agentes: se quitan las pestañas de los que no
// existen (o están desactivados) en esta instalación, en vez de dejar pestañas que fallan.
async function filtrarAppsPorAgentesDisponibles() {
  try {
    const r = await fetch('/api/agentes-disponibles');
    if (!r.ok) return;
    const disponibles = new Set((await r.json()).agentes || []);
    for (let i = APPS.length - 1; i >= 0; i--) {
      if (APPS[i].agente && !disponibles.has(APPS[i].agente)) APPS.splice(i, 1);
    }
    NAV_ITEMS.length = 1;
    NAV_ITEMS.push(...APPS);
  } catch (e) { /* sin la lista se muestran todas, como antes */ }
}

// --- Init ---
aplicarModoAyuda(localStorage.getItem('imrryr_ayuda_on') === '1');
aplicarTema(localStorage.getItem('imrryr_tema') || 'minimalista');
aplicarFondoPersonalizado();
inicializarPosicionAyuda();
filtrarAppsPorAgentesDisponibles().then(() => {
  renderNavTabs();
  montarChatPanels();
  abrirApp('inicio');
  actualizarStatus();
  setInterval(actualizarStatus, 15000);
});
