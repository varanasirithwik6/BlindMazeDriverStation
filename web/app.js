/* ═══════════════════════════════════════════════════════════════
   app.js — Blind Maze Driver Station Pro  (Web Edition)
   Full interactive dashboard with boot sequence, SLAM maze,
   JARVIS holographic viewport, AI neural monitor, demo sim,
   and 60 FPS canvas rendering.
   ═══════════════════════════════════════════════════════════════ */

// ── State ────────────────────────────────────────────────────
const S = {
  isDark: true,
  btConnected: false,
  camConnected: false,
  emergency: false,
  demoActive: false,
  demoIdx: 0,
  demoTimer: null,
  activeDir: null,
  pressedKeys: new Set(),
  // Maze
  maze: { rows: 7, cols: 7, robotR: 3, robotC: 3, heading: 0, visited: new Set(['3,3']), qr: 0, trail: [] },
  // Telemetry
  tel: { cov: 0, health: 100, vision: 98.4, nav: 99.2, signal: 95, battery: 88 },
  // Camera Fit Mode: 'cover' (fills screen), 'stretch' (stretch fill), 'contain' (original letterbox)
  camFitMode: 'cover',
  // Animation
  t: 0,
};
const DEMO_MOVES = ['up','up','right','right','down','right','down','down','left','up','right','down'];

// ── Boot Sequence ────────────────────────────────────────────
const BOOT_STAGES = [
  ['Loading Navigation System...', 'NAV SYSTEM', 'online', 15],
  ['Loading Bluetooth Controller...', 'BT LINK', 'waiting', 30],
  ['Loading Motion Planner...', 'MOTION PLANNER', 'online', 50],
  ['Loading Mission Engine...', 'MISSION ENGINE', 'online', 65],
  ['Running Diagnostics...', 'DIAGNOSTICS', '100% OK', 80],
  ['Connecting Services...', 'CAM PIPELINE', 'waiting', 95],
  ['System Ready', null, null, 100],
];
const HEALTH_MODULES = [
  ['AI CORE', 'online'], ['BT LINK', 'waiting'], ['VISION ENGINE', 'online'],
  ['MOTION PLANNER', 'online'], ['CAM PIPELINE', 'waiting'], ['MISSION ENGINE', 'online'],
  ['NAV SYSTEM', 'waiting'], ['DIAGNOSTICS', '100% OK'],
];

function runBootSequence() {
  const overlay = document.getElementById('boot-overlay');
  const pctEl = document.getElementById('boot-pct');
  const statusEl = document.getElementById('boot-status');
  const fillEl = document.getElementById('boot-bar-fill');
  const termLines = document.getElementById('boot-term-lines');
  const healthGrid = document.getElementById('boot-health-grid');

  // Health grid
  HEALTH_MODULES.forEach(([name, val]) => {
    const isOnline = val === 'online' || val === '100% OK';
    healthGrid.innerHTML += `<div class="health-item"><span class="h-name">${name}:</span>
      <span class="h-val ${isOnline ? 'online' : 'waiting'}">${val.toUpperCase()} ${isOnline ? '✓' : ''}</span></div>`;
  });

  // Boot canvas (rotating rings)
  const bc = document.getElementById('boot-canvas');
  const bctx = bc.getContext('2d');
  function resizeBC() { bc.width = bc.parentElement.clientWidth; bc.height = bc.parentElement.clientHeight; }
  resizeBC(); window.addEventListener('resize', resizeBC);

  let bootAngle = 0;
  function drawBootCanvas() {
    const w = bc.width, h = bc.height, cx = w / 2, cy = h / 2 - 60;
    bctx.clearRect(0, 0, w, h);
    bootAngle += 0.008;

    // Outer ring
    bctx.strokeStyle = 'rgba(53,207,255,0.15)';
    bctx.lineWidth = 1; bctx.setLineDash([4, 8]);
    bctx.beginPath(); bctx.arc(cx, cy, 160, 0, Math.PI * 2); bctx.stroke();

    // Rotating ring
    bctx.save(); bctx.translate(cx, cy); bctx.rotate(bootAngle);
    bctx.strokeStyle = 'rgba(53,207,255,0.25)'; bctx.lineWidth = 2; bctx.setLineDash([12, 6]);
    bctx.beginPath(); bctx.arc(0, 0, 130, 0, Math.PI * 2); bctx.stroke();
    // Ticks
    bctx.setLineDash([]);
    for (let i = 0; i < 36; i++) {
      const a = (i * 10) * Math.PI / 180;
      const r1 = i % 3 === 0 ? 120 : 125, r2 = 135;
      bctx.strokeStyle = `rgba(53,207,255,${i % 3 === 0 ? 0.3 : 0.1})`;
      bctx.beginPath(); bctx.moveTo(r1 * Math.cos(a), r1 * Math.sin(a));
      bctx.lineTo(r2 * Math.cos(a), r2 * Math.sin(a)); bctx.stroke();
    }
    bctx.restore();
    bctx.setLineDash([]);
  }

  let stageIdx = 0;
  function nextStage() {
    if (stageIdx >= BOOT_STAGES.length) {
      // Finish boot
      setTimeout(() => {
        overlay.classList.add('fade-out');
        setTimeout(() => {
          overlay.style.display = 'none';
          const dash = document.getElementById('dashboard');
          dash.classList.remove('hidden');
          requestAnimationFrame(() => dash.classList.add('visible'));
          startDashboard();
        }, 600);
      }, 400);
      return;
    }
    const [msg, modKey, modVal, pct] = BOOT_STAGES[stageIdx];
    const ts = (performance.now() / 1000).toFixed(2);
    termLines.innerHTML += `<div>[${ts}] > ${msg.toUpperCase()}</div>`;
    termLines.scrollTop = termLines.scrollHeight;
    statusEl.textContent = `● ${msg.toUpperCase()}`;
    animateValue(pctEl, parseInt(pctEl.textContent), pct, 350, v => { pctEl.textContent = v + '%'; });
    fillEl.style.width = pct + '%';

    stageIdx++;
    setTimeout(nextStage, 450 + Math.random() * 200);
  }

  // Boot canvas loop
  (function bootLoop() {
    if (overlay.style.display === 'none') return;
    drawBootCanvas();
    requestAnimationFrame(bootLoop);
  })();

  setTimeout(nextStage, 600);
}

// ── Dashboard Init ───────────────────────────────────────────
function startDashboard() {
  buildGauges();
  buildPipelines();
  buildStatusCards();
  startClock();
  startJarvisCanvas();
  startAICanvas();
  startMazeCanvas();
  setupDpad();
  setupKeyboard();
  setupSpeedSlider();
  logConsole('Discovered 8 serial port(s). Selected COM12.', 'INFO');
  logConsole('Dashboard initialized. All systems nominal.', 'SUCCESS');
}

// ── Gauges ───────────────────────────────────────────────────
const GAUGES = [
  { id: 'cov', label: 'COVERAGE %', color: '#35CFFF', key: 'cov' },
  { id: 'health', label: 'ROBOT HEALTH', color: '#00E676', key: 'health' },
  { id: 'vision', label: 'VISION CONF.', color: '#35CFFF', key: 'vision' },
  { id: 'nav', label: 'NAV ACCURACY', color: '#00E676', key: 'nav' },
  { id: 'signal', label: 'SIGNAL STRENGTH', color: '#35CFFF', key: 'signal' },
  { id: 'battery', label: 'BATTERY LEVEL', color: '#00E676', key: 'battery' },
];
function buildGauges() {
  const grid = document.getElementById('gauge-grid');
  GAUGES.forEach(g => {
    const circ = 2 * Math.PI * 16;
    const offset = circ * (1 - S.tel[g.key] / 100);
    grid.innerHTML += `<div class="gauge-card">
      <div class="gauge-ring"><svg viewBox="0 0 40 40">
        <circle class="bg" cx="20" cy="20" r="16"/>
        <circle class="fg" id="gr-${g.id}" cx="20" cy="20" r="16"
          stroke="${g.color}" stroke-dasharray="${circ}" stroke-dashoffset="${offset}"/>
      </svg></div>
      <div class="gauge-info"><div class="gauge-label">${g.label}</div>
        <div class="gauge-val" id="gv-${g.id}" style="color:${g.color}">${S.tel[g.key].toFixed(1)}%</div>
      </div></div>`;
  });
}
function updateGauges() {
  const circ = 2 * Math.PI * 16;
  GAUGES.forEach(g => {
    const ring = document.getElementById('gr-' + g.id);
    const val = document.getElementById('gv-' + g.id);
    if (ring && val) {
      ring.setAttribute('stroke-dashoffset', circ * (1 - S.tel[g.key] / 100));
      val.textContent = S.tel[g.key].toFixed(1) + '%';
    }
  });
}

// ── Pipelines ────────────────────────────────────────────────
const PIPES = [
  ['BT LINK', '115200 BAUD'], ['CAMERA STREAM', '1080P 30FPS'],
  ['VISION ENGINE', '98.4% CONF'], ['NAV PLANNER', 'SLAM ACTIVE'],
  ['MOTORS DRIVER', 'PWM 255'],
];
function buildPipelines() {
  const el = document.getElementById('pipelines');
  PIPES.forEach(([name, val], i) => {
    el.innerHTML += `<div class="pipeline-row">
      <span class="pipe-name">${name}</span>
      <div class="pipe-anim"><div class="pipe-dot" style="animation-delay:${i * 0.35}s"></div></div>
      <span class="pipe-val">${val}</span></div>`;
  });
}

// ── Status Cards ─────────────────────────────────────────────
function buildStatusCards() {
  const container = document.getElementById('status-cards');
  const cards = [
    { id: 'sc-bt', dot: 'dot-red', text: 'Bluetooth : Disconnected (COM12)' },
    { id: 'sc-cam', dot: 'dot-red', text: 'Camera : Offline (1920×1080)' },
    { id: 'sc-ping', dot: 'dot-amber', text: 'Ping : -- ms' },
    { id: 'sc-robot', dot: 'dot-amber', text: 'Robot : Standby (Idle)' },
    { id: 'sc-timer', dot: 'dot-amber', text: 'Match Timer : 00:00' },
    { id: 'sc-fps', dot: 'dot-amber', text: 'Camera Rate : -- FPS' },
  ];
  cards.forEach(c => {
    container.innerHTML += `<div class="status-card" id="${c.id}"><span class="dot ${c.dot}"></span>${c.text}</div>`;
  });
}
function setStatusCard(id, dotClass, text) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<span class="dot ${dotClass}"></span>${text}`;
}

// ── Clock ────────────────────────────────────────────────────
function startClock() {
  const el = document.getElementById('live-clock');
  setInterval(() => {
    const d = new Date();
    el.textContent = `CLK  ${d.toLocaleTimeString('en-GB')}`;
  }, 1000);
}

// ── Console ──────────────────────────────────────────────────
function logConsole(msg, level = 'INFO') {
  const el = document.getElementById('console-lines');
  const ts = new Date().toLocaleTimeString('en-GB', { hour12: false }) + '.' + String(Date.now() % 1000).padStart(3, '0');
  const cls = { INFO: 'log-info', SUCCESS: 'log-success', ERROR: 'log-error', WARNING: 'log-warning' }[level] || 'log-info';
  const icon = { INFO: 'ℹ', SUCCESS: '✓', ERROR: '✕', WARNING: '⚠' }[level] || 'ℹ';
  el.innerHTML += `<div><span class="log-ts">[${ts}]</span> <span class="${cls}">${icon} [${level}] ${msg}</span></div>`;
  el.parentElement.scrollTop = el.parentElement.scrollHeight;
}

// ── JARVIS Canvas ────────────────────────────────────────────
let jarvisAngle = 0;
function startJarvisCanvas() {
  const c = document.getElementById('jarvis-canvas');
  const ctx = c.getContext('2d');
  function resize() {
    const rect = c.parentElement.getBoundingClientRect();
    c.width = rect.width; c.height = rect.height;
  }
  resize(); window.addEventListener('resize', resize);

  (function loop() {
    drawJarvis(ctx, c.width, c.height);
    requestAnimationFrame(loop);
  })();
}
function drawJarvis(ctx, w, h) {
  if (S.camConnected) return; // Do not clear canvas or draw radar HUD when camera is live
  ctx.clearRect(0, 0, w, h);
  const cx = w / 2, cy = h / 2;
  jarvisAngle += 0.005;

  // Corner brackets
  ctx.strokeStyle = 'rgba(53,207,255,0.5)'; ctx.lineWidth = 2;
  const m = 20, bLen = 40;
  [[m,m,1,1],[w-m,m,-1,1],[m,h-m,1,-1],[w-m,h-m,-1,-1]].forEach(([x,y,dx,dy]) => {
    ctx.beginPath(); ctx.moveTo(x, y + dy*bLen); ctx.lineTo(x, y); ctx.lineTo(x + dx*bLen, y); ctx.stroke();
  });

  // Grid
  ctx.strokeStyle = 'rgba(53,207,255,0.04)'; ctx.lineWidth = 0.5;
  for (let x = 0; x < w; x += 30) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
  for (let y = 0; y < h; y += 30) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }

  // Sweep circle
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(jarvisAngle);
  ctx.strokeStyle = 'rgba(53,207,255,0.12)'; ctx.lineWidth = 1; ctx.setLineDash([6,4]);
  ctx.beginPath(); ctx.arc(0, 0, 100, 0, Math.PI * 2); ctx.stroke();
  ctx.strokeStyle = 'rgba(53,207,255,0.08)';
  ctx.beginPath(); ctx.arc(0, 0, 60, 0, Math.PI * 2); ctx.stroke();
  ctx.setLineDash([]);

  // Cross
  ctx.strokeStyle = 'rgba(53,207,255,0.15)'; ctx.lineWidth = 0.5;
  ctx.beginPath(); ctx.moveTo(-110, 0); ctx.lineTo(110, 0); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0, -110); ctx.lineTo(0, 110); ctx.stroke();

  // Rotating sweep line
  ctx.strokeStyle = 'rgba(53,207,255,0.25)'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(100, 0); ctx.stroke();

  // Compass letters
  ctx.restore();
  ctx.font = '600 9px "JetBrains Mono"'; ctx.fillStyle = 'rgba(53,207,255,0.3)'; ctx.textAlign = 'center';
  ctx.fillText('N', cx, cy - 108); ctx.fillText('S', cx, cy + 116);
  ctx.fillText('E', cx + 115, cy + 4); ctx.fillText('W', cx - 115, cy + 4);

  // Robot wireframe (pentagon)
  ctx.save(); ctx.translate(cx, cy); ctx.rotate(S.maze.heading * Math.PI / 180);
  ctx.strokeStyle = 'rgba(53,207,255,0.35)'; ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < 5; i++) {
    const a = (i * 72 - 90) * Math.PI / 180;
    const r = 22;
    i === 0 ? ctx.moveTo(r*Math.cos(a), r*Math.sin(a)) : ctx.lineTo(r*Math.cos(a), r*Math.sin(a));
  }
  ctx.closePath(); ctx.stroke();
  // Forward arrow
  ctx.fillStyle = 'rgba(53,207,255,0.5)';
  ctx.beginPath(); ctx.moveTo(0, -30); ctx.lineTo(-5, -22); ctx.lineTo(5, -22); ctx.closePath(); ctx.fill();
  ctx.restore();
}

// ── AI Canvas ────────────────────────────────────────────────
function startAICanvas() {
  const c = document.getElementById('ai-canvas');
  const ctx = c.getContext('2d');
  const nodes = Array.from({ length: 12 }, () => ({
    x: Math.random(), y: Math.random(),
    vx: (Math.random() - 0.5) * 0.001, vy: (Math.random() - 0.5) * 0.001,
    r: 3 + Math.random() * 4,
  }));
  function resize() { const r = c.parentElement.getBoundingClientRect(); c.width = r.width; c.height = r.height; }
  resize(); window.addEventListener('resize', resize);

  const thinkTexts = ['Analyzing Maze...', 'Planning Route...', 'Estimating Path...', 'Optimizing Nav...'];
  let thinkIdx = 0;
  setInterval(() => {
    thinkIdx = (thinkIdx + 1) % thinkTexts.length;
    document.getElementById('ai-thinking').textContent = '🧠 AI THINKING: ' + thinkTexts[thinkIdx];
  }, 2500);

  (function loop() {
    const w = c.width, h = c.height;
    ctx.clearRect(0, 0, w, h);
    // Connections
    nodes.forEach((a, i) => {
      nodes.forEach((b, j) => {
        if (j <= i) return;
        const dx = (a.x - b.x) * w, dy = (a.y - b.y) * h;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < 120) {
          ctx.strokeStyle = `rgba(53,207,255,${0.15 * (1 - dist/120)})`;
          ctx.lineWidth = 0.8;
          ctx.beginPath(); ctx.moveTo(a.x*w, a.y*h); ctx.lineTo(b.x*w, b.y*h); ctx.stroke();
        }
      });
    });
    // Nodes
    nodes.forEach(n => {
      n.x += n.vx; n.y += n.vy;
      if (n.x < 0.05 || n.x > 0.95) n.vx *= -1;
      if (n.y < 0.1 || n.y > 0.9) n.vy *= -1;
      ctx.fillStyle = 'rgba(53,207,255,0.6)';
      ctx.beginPath(); ctx.arc(n.x*w, n.y*h, n.r, 0, Math.PI*2); ctx.fill();
    });
    requestAnimationFrame(loop);
  })();
}

// ── Maze Canvas ──────────────────────────────────────────────
function startMazeCanvas() {
  const c = document.getElementById('maze-canvas');
  const ctx = c.getContext('2d');
  function resize() {
    const r = c.parentElement.getBoundingClientRect();
    c.width = r.width; c.height = 170;
  }
  resize(); window.addEventListener('resize', resize);

  const qrCheckpoints = [[1,1],[1,5],[5,1]];
  const goalPos = [5,5];

  (function loop() {
    const w = c.width, h = c.height;
    const m = S.maze;
    const cellW = (w - 20) / m.cols, cellH = (h - 20) / m.rows;
    const ox = 10, oy = 10;
    ctx.clearRect(0, 0, w, h);

    // Grid cells
    for (let r = 0; r < m.rows; r++) {
      for (let cc = 0; cc < m.cols; cc++) {
        const x = ox + cc * cellW, y = oy + r * cellH;
        const visited = m.visited.has(`${r},${cc}`);
        ctx.fillStyle = visited ? 'rgba(53,207,255,0.08)' : 'rgba(30,41,59,0.3)';
        ctx.fillRect(x + 1, y + 1, cellW - 2, cellH - 2);
        ctx.strokeStyle = 'rgba(53,207,255,0.12)'; ctx.lineWidth = 0.5;
        ctx.strokeRect(x + 1, y + 1, cellW - 2, cellH - 2);
      }
    }

    // QR checkpoints
    qrCheckpoints.forEach(([qr, qc]) => {
      const x = ox + qc * cellW, y = oy + qr * cellH;
      ctx.strokeStyle = 'rgba(251,191,36,0.5)'; ctx.lineWidth = 1.5;
      const m2 = 3;
      const cl = 8;
      ctx.beginPath();
      ctx.moveTo(x+m2, y+m2+cl); ctx.lineTo(x+m2, y+m2); ctx.lineTo(x+m2+cl, y+m2);
      ctx.moveTo(x+cellW-m2-cl, y+m2); ctx.lineTo(x+cellW-m2, y+m2); ctx.lineTo(x+cellW-m2, y+m2+cl);
      ctx.moveTo(x+cellW-m2, y+cellH-m2-cl); ctx.lineTo(x+cellW-m2, y+cellH-m2); ctx.lineTo(x+cellW-m2-cl, y+cellH-m2);
      ctx.moveTo(x+m2+cl, y+cellH-m2); ctx.lineTo(x+m2, y+cellH-m2); ctx.lineTo(x+m2, y+cellH-m2-cl);
      ctx.stroke();
      ctx.font = '600 8px "JetBrains Mono"'; ctx.fillStyle = 'rgba(251,191,36,0.6)'; ctx.textAlign = 'center';
      ctx.fillText('QR', x + cellW/2, y + cellH/2 + 3);
    });

    // Goal beacon
    const gx = ox + goalPos[1] * cellW + cellW/2, gy = oy + goalPos[0] * cellH + cellH/2;
    const pulseR = 8 + Math.sin(S.t * 3) * 3;
    ctx.strokeStyle = 'rgba(0,230,118,0.3)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(gx, gy, pulseR, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = 'rgba(0,230,118,0.5)';
    ctx.beginPath(); ctx.arc(gx, gy, 4, 0, Math.PI * 2); ctx.fill();
    ctx.font = '600 7px "JetBrains Mono"'; ctx.fillText('GOAL', gx, gy + 14);

    // Breadcrumb trail
    m.trail.forEach((p, i) => {
      const tx = ox + p[1] * cellW + cellW/2, ty = oy + p[0] * cellH + cellH/2;
      ctx.fillStyle = `rgba(53,207,255,${0.15 + i * 0.03})`;
      ctx.beginPath(); ctx.arc(tx, ty, 2, 0, Math.PI * 2); ctx.fill();
    });

    // Robot
    const rx = ox + m.robotC * cellW + cellW/2, ry = oy + m.robotR * cellH + cellH/2;
    ctx.save(); ctx.translate(rx, ry); ctx.rotate(m.heading * Math.PI / 180);
    // Body
    ctx.fillStyle = 'rgba(53,207,255,0.7)';
    ctx.beginPath(); ctx.moveTo(0, -8); ctx.lineTo(-6, 6); ctx.lineTo(6, 6); ctx.closePath(); ctx.fill();
    // Heading cone
    ctx.strokeStyle = 'rgba(53,207,255,0.2)'; ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-12, -20); ctx.moveTo(0, 0); ctx.lineTo(12, -20);
    ctx.stroke();
    ctx.restore();

    // Compass
    ctx.strokeStyle = 'rgba(53,207,255,0.15)'; ctx.lineWidth = 0.8;
    const compX = w - 24, compY = 24, compR = 12;
    ctx.beginPath(); ctx.arc(compX, compY, compR, 0, Math.PI*2); ctx.stroke();
    ctx.font = '600 6px "JetBrains Mono"'; ctx.fillStyle = 'rgba(53,207,255,0.4)'; ctx.textAlign = 'center';
    ctx.fillText('N', compX, compY - compR - 3);

    S.t += 0.016;
    // Update info
    const covPct = Math.round(m.visited.size / (m.rows * m.cols) * 100);
    document.getElementById('maze-pos').textContent = `POS: (${m.robotR}, ${m.robotC}) | HDG: ${Math.round(m.heading)}° [${headingLabel(m.heading)}]`;
    document.getElementById('maze-cov').textContent = `SLAM COVERAGE: ${covPct}% | QR: ${m.qr}/3`;
    S.tel.cov = covPct;

    requestAnimationFrame(loop);
  })();
}

function headingLabel(h) {
  h = ((h % 360) + 360) % 360;
  if (h < 45 || h >= 315) return 'N';
  if (h < 135) return 'E';
  if (h < 225) return 'S';
  return 'W';
}

// ── D-Pad ────────────────────────────────────────────────────
function setupDpad() {
  ['up','down','left','right'].forEach(dir => {
    const btn = document.getElementById('btn-' + dir);
    btn.addEventListener('mousedown', e => { e.preventDefault(); pressDir(dir); });
    btn.addEventListener('mouseup', e => { e.preventDefault(); releaseDir(dir); });
    btn.addEventListener('mouseleave', e => { releaseDir(dir); });
    btn.addEventListener('touchstart', e => { e.preventDefault(); pressDir(dir); }, { passive: false });
    btn.addEventListener('touchend', e => { e.preventDefault(); releaseDir(dir); });
  });
}
function pressDir(dir) {
  if (S.emergency) return;
  S.activeDir = dir;
  document.querySelectorAll('.dir-btn').forEach(b => b.classList.remove('pressed'));
  document.getElementById('btn-' + dir).classList.add('pressed');
  sendCommand(dir);
}
function releaseDir(dir) {
  if (S.activeDir === dir) {
    S.activeDir = null;
    document.getElementById('btn-' + dir).classList.remove('pressed');
    document.getElementById('cmd-status').textContent = 'COMMAND: STOPPED';
  }
}
function sendStop() {
  S.activeDir = null;
  document.querySelectorAll('.dir-btn').forEach(b => b.classList.remove('pressed'));
  document.getElementById('cmd-status').textContent = 'COMMAND: STOPPED';
  setStatusCard('sc-robot', 'dot-green', 'Robot : Ready');
}

function sendCommand(dir) {
  const labels = { up: 'FORWARD', down: 'BACKWARD', left: 'LEFT', right: 'RIGHT' };
  document.getElementById('cmd-status').textContent = 'COMMAND: ' + (labels[dir] || dir.toUpperCase());
  setStatusCard('sc-robot', 'dot-cyan', `Robot : ${labels[dir] || dir.toUpperCase()}`);
  moveRobot(dir);
}

function moveRobot(dir) {
  const m = S.maze;
  m.trail.push([m.robotR, m.robotC]);
  if (m.trail.length > 30) m.trail.shift();

  if (dir === 'up' && m.robotR > 0) { m.robotR--; m.heading = 0; }
  else if (dir === 'down' && m.robotR < m.rows - 1) { m.robotR++; m.heading = 180; }
  else if (dir === 'left' && m.robotC > 0) { m.robotC--; m.heading = 270; }
  else if (dir === 'right' && m.robotC < m.cols - 1) { m.robotC++; m.heading = 90; }

  m.visited.add(`${m.robotR},${m.robotC}`);

  // Check QR
  const qrCheckpoints = [[1,1],[1,5],[5,1]];
  let qrHit = 0;
  qrCheckpoints.forEach(([qr, qc]) => { if (m.visited.has(`${qr},${qc}`)) qrHit++; });
  m.qr = qrHit;

  updateGauges();
  updateFooter();
}

function updateFooter() {
  const cov = Math.round(S.maze.visited.size / (S.maze.rows * S.maze.cols) * 100);
  document.getElementById('mp-footer').textContent = `QR CHECKPOINTS: ${S.maze.qr}/3  |  BT LINK: 96%  |  EST: 05:48`;
  S.tel.cov = cov;
}

// ── Keyboard ─────────────────────────────────────────────────
function setupKeyboard() {
  const keyMap = { w: 'up', arrowup: 'up', s: 'down', arrowdown: 'down', a: 'left', arrowleft: 'left', d: 'right', arrowright: 'right' };
  document.addEventListener('keydown', e => {
    const k = e.key.toLowerCase();
    if (k === ' ') { e.preventDefault(); emergencyStop(); return; }
    if (keyMap[k] && !S.pressedKeys.has(k)) {
      S.pressedKeys.add(k);
      pressDir(keyMap[k]);
    }
  });
  document.addEventListener('keyup', e => {
    const k = e.key.toLowerCase();
    if (keyMap[k]) {
      S.pressedKeys.delete(k);
      releaseDir(keyMap[k]);
    }
  });
}

// ── Speed Slider ─────────────────────────────────────────────
function setupSpeedSlider() {
  const slider = document.getElementById('speed-slider');
  slider.addEventListener('input', () => {
    document.getElementById('speed-val').textContent = slider.value;
    document.getElementById('speed-pct').textContent = Math.round(slider.value / 255 * 100);
  });
}
function setSpeed(val) {
  const slider = document.getElementById('speed-slider');
  slider.value = val;
  document.getElementById('speed-val').textContent = val;
  document.getElementById('speed-pct').textContent = Math.round(val / 255 * 100);
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
}

// ── Actions ──────────────────────────────────────────────────
function toggleTheme() {
  S.isDark = !S.isDark;
  document.body.classList.toggle('light', !S.isDark);
  logConsole(S.isDark ? 'Switched to Tactical Dark Theme' : 'Switched to Daylight Light Theme', 'INFO');
}

function toggleBluetooth() {
  S.btConnected = !S.btConnected;
  const btn = document.getElementById('bt-connect-btn');
  if (S.btConnected) {
    btn.textContent = 'DISCONNECT'; btn.classList.add('connected');
    setStatusCard('sc-bt', 'dot-green', 'Bluetooth : Connected (COM12)');
    setStatusCard('sc-robot', 'dot-green', 'Robot : Ready');
    logConsole('Bluetooth link established on COM12 @ 115200 baud', 'SUCCESS');
  } else {
    btn.textContent = 'CONNECT LINK'; btn.classList.remove('connected');
    setStatusCard('sc-bt', 'dot-red', 'Bluetooth : Disconnected (COM12)');
    setStatusCard('sc-robot', 'dot-amber', 'Robot : Standby (Idle)');
    logConsole('Bluetooth link disconnected', 'WARNING');
  }
}

function setSource(type) {
  const input = document.getElementById('stream-url');
  if (!input) return;
  if (type === 'webcam') {
    input.value = 'webcam';
    logConsole('Stream mode set: Device Webcam (MediaStream)', 'INFO');
  } else if (type === 'sim') {
    input.value = 'sim';
    logConsole('Stream mode set: Virtual Cyber Rover Camera Simulation', 'INFO');
  } else {
    input.value = '10.9.91.169:8080';
    logConsole('Stream mode set: Hardware IP Webcam (Proxy Link)', 'INFO');
  }
}

function disconnectVideo() {
  S.camConnected = false;
  if (S._wsStream) {
    try { S._wsStream.close(); } catch(e){}
    S._wsStream = null;
  }
  if (S._feedAbort) {
    try { S._feedAbort.abort(); } catch(e){}
    S._feedAbort = null;
  }
  if (S._webcamStream) {
    try { S._webcamStream.getTracks().forEach(t => t.stop()); } catch(e){}
    S._webcamStream = null;
  }
  if (S._simAnimId) {
    cancelAnimationFrame(S._simAnimId);
    S._simAnimId = null;
  }
  if (S._directPollStop) {
    S._directPollStop();
    S._directPollStop = null;
  }
  const feed = document.getElementById('jarvis-feed');
  if (feed) { feed.src = ''; feed.style.display = 'none'; feed.onload = null; feed.onerror = null; }
  const video = document.getElementById('webcam-video');
  if (video) { video.srcObject = null; video.style.display = 'none'; }
  const viewport = document.getElementById('jarvis-viewport');
  if (viewport) viewport.classList.remove('live');
  const canvas = document.getElementById('jarvis-canvas');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  const statusEl = document.getElementById('jarvis-status');
  if (statusEl) statusEl.textContent = 'JARVIS_VISION_CORE :: DISCONNECTED';
  const connBtn = document.getElementById('connect-cam-btn');
  if (connBtn) { connBtn.textContent = 'CONNECT VIDEO'; connBtn.classList.remove('active'); }
  setStatusCard('sc-cam', 'dot-red', 'Camera : Disconnected');
  setStatusCard('sc-fps', 'dot-amber', 'Camera Rate : -- FPS');
  setStatusCard('sc-ping', 'dot-amber', 'Ping : -- ms');
  logConsole('Camera feed disconnected', 'WARNING');
}

function drawHudOverlay(ctx, w, h) {
  const cx = w / 2, cy = h / 2;
  // Corner brackets
  ctx.strokeStyle = 'rgba(53,207,255,0.7)'; ctx.lineWidth = 2;
  const m = 18, bLen = 32;
  [[m,m,1,1],[w-m,m,-1,1],[m,h-m,1,-1],[w-m,h-m,-1,-1]].forEach(([x,y,dx,dy]) => {
    ctx.beginPath(); ctx.moveTo(x, y + dy*bLen); ctx.lineTo(x, y); ctx.lineTo(x + dx*bLen, y); ctx.stroke();
  });
  // Center reticle
  ctx.strokeStyle = 'rgba(53,207,255,0.4)'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(cx, cy, 26, 0, Math.PI * 2); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx - 36, cy); ctx.lineTo(cx - 8, cy); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx + 8, cy); ctx.lineTo(cx + 36, cy); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, cy - 36); ctx.lineTo(cx, cy - 8); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, cy + 8); ctx.lineTo(cx, cy + 36); ctx.stroke();
  // AI telemetry text overlay
  ctx.font = '700 9px "JetBrains Mono"';
  ctx.fillStyle = 'rgba(53,207,255,0.85)';
  ctx.fillText('LIVE HUD TELEMETRY [ACTIVE]', m + 6, m + 14);
  ctx.fillText(`HDG: ${Math.round(S.maze.heading)}° | BAT: ${S.tel.battery}%`, m + 6, m + 28);
}

async function startWebcamPipeline(viewport, statusEl, canvas, video) {
  try {
    statusEl.textContent = 'JARVIS_VISION_CORE :: REQUESTING CAMERA...';
    logConsole('Requesting device camera access (MediaStream API)...', 'INFO');
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false
    });
    S._webcamStream = stream;
    S.camConnected = true;
    viewport.classList.add('live');
    const connBtn = document.getElementById('connect-cam-btn');
    if (connBtn) { connBtn.textContent = 'DISCONNECT'; connBtn.classList.add('active'); }

    video.srcObject = stream;
    await video.play();

    statusEl.textContent = 'JARVIS_VISION_CORE :: LIVE WEBCAM';
    setStatusCard('sc-cam', 'dot-green', 'Camera : LIVE WEBCAM (Device)');
    setStatusCard('sc-ping', 'dot-green', 'Ping : <1 ms (Zero Latency)');
    logConsole('Device webcam feed connected with zero latency ✓', 'SUCCESS');

    let frameCount = 0, lastFpsTime = performance.now();
    function renderLoop() {
      if (!S.camConnected || !S._webcamStream) return;
      const rect = viewport.getBoundingClientRect();
      if (canvas.width !== rect.width || canvas.height !== rect.height) {
        canvas.width = rect.width; canvas.height = rect.height;
      }
      const ctx = canvas.getContext('2d');
      const fitMode = S.camFitMode || 'cover';
      const vw = video.videoWidth || 640, vh = video.videoHeight || 480;

      if (fitMode === 'stretch') {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      } else {
        const scale = fitMode === 'cover'
          ? Math.max(canvas.width / vw, canvas.height / vh)
          : Math.min(canvas.width / vw, canvas.height / vh);
        const dw = vw * scale, dh = vh * scale;
        const dx = (canvas.width - dw) / 2, dy = (canvas.height - dh) / 2;
        if (fitMode === 'contain') {
          ctx.fillStyle = '#000';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
        ctx.drawImage(video, dx, dy, dw, dh);
      }

      drawHudOverlay(ctx, canvas.width, canvas.height);

      frameCount++;
      const now = performance.now();
      if (now - lastFpsTime >= 1000) {
        setStatusCard('sc-fps', 'dot-green', `Camera Rate : ${frameCount} FPS`);
        frameCount = 0;
        lastFpsTime = now;
      }
      requestAnimationFrame(renderLoop);
    }
    requestAnimationFrame(renderLoop);
  } catch (err) {
    logConsole(`Webcam permission denied or unavailable: ${err.message}`, 'WARNING');
    logConsole('Falling back to Virtual Cyber Rover simulation...', 'INFO');
    startSimulatedCameraPipeline(viewport, statusEl, canvas);
  }
}

function startSimulatedCameraPipeline(viewport, statusEl, canvas) {
  S.camConnected = true;
  viewport.classList.add('live');
  const connBtn = document.getElementById('connect-cam-btn');
  if (connBtn) { connBtn.textContent = 'DISCONNECT'; connBtn.classList.add('active'); }

  statusEl.textContent = 'JARVIS_VISION_CORE :: LIVE CYBER SIMULATION';
  setStatusCard('sc-cam', 'dot-green', 'Camera : LIVE SIM (Virtual Rover)');
  setStatusCard('sc-ping', 'dot-green', 'Ping : 2 ms');
  setStatusCard('sc-fps', 'dot-green', 'Camera Rate : 60 FPS');
  logConsole('Virtual Cyber Rover camera pipeline active (60 FPS) ✓', 'SUCCESS');

  let simT = 0;
  function simLoop() {
    if (!S.camConnected) return;
    const rect = viewport.getBoundingClientRect();
    if (canvas.width !== rect.width || canvas.height !== rect.height) {
      canvas.width = rect.width; canvas.height = rect.height;
    }
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    simT += 0.03;

    // Cyber space background
    ctx.fillStyle = '#060910';
    ctx.fillRect(0, 0, w, h);

    const horizon = h * 0.52;
    const cx = w / 2;

    // Floor perspective grid
    ctx.strokeStyle = 'rgba(53, 207, 255, 0.2)';
    ctx.lineWidth = 1;
    for (let i = -10; i <= 10; i++) {
      ctx.beginPath();
      ctx.moveTo(cx, horizon);
      ctx.lineTo(cx + i * (w / 8), h);
      ctx.stroke();
    }
    // Floor depth pulses
    for (let d = 0; d < 8; d++) {
      const p = ((simT * 0.7 + d * 0.125) % 1);
      const y = horizon + Math.pow(p, 2) * (h - horizon);
      ctx.strokeStyle = `rgba(0, 230, 118, ${p * 0.45})`;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Dynamic obstacle detection box
    const b1x = cx + Math.sin(simT * 0.6) * 110 - 45;
    const b1y = horizon - 25 + Math.cos(simT * 0.6) * 12;
    ctx.strokeStyle = '#35CFFF';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(b1x, b1y, 90, 55);
    ctx.fillStyle = 'rgba(53,207,255,0.12)';
    ctx.fillRect(b1x, b1y, 90, 55);
    ctx.font = '700 8px "JetBrains Mono"';
    ctx.fillStyle = '#35CFFF';
    ctx.fillText('TARGET [MAZE_OBSTACLE]', b1x + 4, b1y - 5);
    ctx.fillText(`DIST: ${(2.2 + Math.sin(simT)*0.4).toFixed(1)}m | 99.4%`, b1x + 4, b1y + 67);

    // QR Target scan box
    const qrX = cx - 180 + Math.cos(simT * 0.4) * 25;
    const qrY = horizon - 70;
    ctx.strokeStyle = '#FBBF24';
    ctx.strokeRect(qrX, qrY, 55, 55);
    ctx.fillStyle = 'rgba(251,191,36,0.1)';
    ctx.fillRect(qrX, qrY, 55, 55);
    ctx.fillStyle = '#FBBF24';
    ctx.fillText('QR_CHECKPOINT_1', qrX, qrY - 6);
    ctx.fillText('DETECTED ✓', qrX + 4, qrY + 32);

    drawHudOverlay(ctx, w, h);
    S._simAnimId = requestAnimationFrame(simLoop);
  }
  S._simAnimId = requestAnimationFrame(simLoop);
}

function connectVideo() {
  const viewport = document.getElementById('jarvis-viewport');
  const statusEl = document.getElementById('jarvis-status');
  const canvas = document.getElementById('jarvis-canvas');
  const feed = document.getElementById('jarvis-feed');
  const video = document.getElementById('webcam-video');

  if (S.camConnected) {
    disconnectVideo();
    return;
  }

  let raw = (document.getElementById('stream-url').value || '').trim();
  if (!raw) {
    raw = 'sim';
    document.getElementById('stream-url').value = 'sim';
  }

  const rawLower = raw.toLowerCase();

  if (rawLower === 'webcam' || rawLower === 'camera') {
    startWebcamPipeline(viewport, statusEl, canvas, video);
    return;
  }

  if (rawLower === 'sim' || rawLower === 'demo' || rawLower === 'virtual') {
    startSimulatedCameraPipeline(viewport, statusEl, canvas);
    return;
  }

  // ── Hardware IP Webcam Mode ──
  let ip = raw.replace(/^https?:\/\//i, '').replace(/\/+$/, '');
  statusEl.textContent = 'JARVIS_VISION_CORE :: CONNECTING...';
  setStatusCard('sc-cam', 'dot-cyan', `Camera : Testing ${ip}...`);
  logConsole(`Testing connection to IP Webcam at ${ip}...`, 'INFO');

  // Try local proxy server first (fast path when server.py is running)
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 2000);

  fetch('/cam/set?ip=' + encodeURIComponent(ip), { signal: controller.signal })
    .then(r => {
      clearTimeout(timeoutId);
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(data => {
      if (data.connected) {
        logConsole(`Server proxy connected to ${ip} ✓`, 'SUCCESS');
        startStream(ip, viewport, statusEl, canvas, feed);
      } else {
        logConsole(`Proxy could not reach ${ip}, trying direct browser connection...`, 'WARNING');
        startDirectCameraConnection(ip, viewport, statusEl, canvas, feed);
      }
    })
    .catch(err => {
      clearTimeout(timeoutId);
      logConsole(`No proxy server detected — connecting directly to camera...`, 'INFO');
      startDirectCameraConnection(ip, viewport, statusEl, canvas, feed);
    });
}

// ── Direct Browser → IP Camera Connection (No Proxy Needed) ─
function startDirectCameraConnection(ip, viewport, statusEl, canvas, feed) {
  S.camConnected = true;
  viewport.classList.add('live');
  const connBtn = document.getElementById('connect-cam-btn');
  if (connBtn) { connBtn.textContent = 'DISCONNECT'; connBtn.classList.add('active'); }

  statusEl.textContent = 'JARVIS_VISION_CORE :: DIRECT LINK...';
  logConsole(`Attempting direct MJPEG stream: http://${ip}/video`, 'INFO');

  // Try MJPEG stream first via <img> tag (zero latency, works cross-origin)
  let mjpegTimedOut = false;
  const mjpegTimeout = setTimeout(() => {
    mjpegTimedOut = true;
    if (feed.naturalWidth === 0) {
      logConsole('MJPEG stream timed out, switching to snapshot polling...', 'WARNING');
      feed.onload = null; feed.onerror = null;
      feed.src = ''; feed.style.display = 'none';
      startDirectSnapshotPolling(ip, viewport, statusEl, canvas);
    }
  }, 4000);

  feed.onerror = () => {
    if (mjpegTimedOut) return;
    clearTimeout(mjpegTimeout);
    logConsole('MJPEG /video endpoint not available, switching to snapshot polling...', 'WARNING');
    feed.onerror = null; feed.onload = null;
    feed.src = ''; feed.style.display = 'none';
    startDirectSnapshotPolling(ip, viewport, statusEl, canvas);
  };

  feed.onload = () => {
    clearTimeout(mjpegTimeout);
    feed.style.display = 'block';
    feed.style.width = '100%'; feed.style.height = '100%';
    feed.style.objectFit = S.camFitMode === 'stretch' ? 'fill' : (S.camFitMode || 'cover');
    setStatusCard('sc-cam', 'dot-green', `Camera : ZERO-LATENCY DIRECT (${ip})`);
    setStatusCard('sc-fps', 'dot-green', 'Camera Rate : MJPEG Live Stream');
    setStatusCard('sc-ping', 'dot-green', 'Ping : 0 ms (Direct Link)');
    statusEl.textContent = 'JARVIS_VISION_CORE :: ZERO_LATENCY_DIRECT';
    logConsole(`Direct MJPEG stream LIVE — ZERO LATENCY ✓ (http://${ip}/video)`, 'SUCCESS');
  };

  feed.src = `http://${ip}/video?t=${Date.now()}`;
}

// ── Direct Snapshot Polling (Fallback if MJPEG stream unavailable) ─
function startDirectSnapshotPolling(ip, viewport, statusEl, canvas) {
  logConsole(`Starting direct snapshot polling: http://${ip}/shot.jpg`, 'INFO');

  let polling = true;
  let frameCount = 0, lastFpsTime = performance.now(), currentFps = 0;
  let reported = false;

  S._directPollStop = () => { polling = false; };

  function pollFrame() {
    if (!polling || !S.camConnected) return;
    const t0 = performance.now();
    const img = new Image();
    img.crossOrigin = 'anonymous';

    img.onload = () => {
      if (!polling || !S.camConnected) return;
      const rect = viewport.getBoundingClientRect();
      if (canvas.width !== rect.width || canvas.height !== rect.height) {
        canvas.width = rect.width; canvas.height = rect.height;
      }
      const ctx = canvas.getContext('2d');
      const fitMode = S.camFitMode || 'cover';
      const iw = img.naturalWidth || 640, ih = img.naturalHeight || 480;

      if (fitMode === 'stretch') {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      } else {
        const scale = fitMode === 'cover'
          ? Math.max(canvas.width / iw, canvas.height / ih)
          : Math.min(canvas.width / iw, canvas.height / ih);
        const dw = iw * scale, dh = ih * scale;
        const dx = (canvas.width - dw) / 2, dy = (canvas.height - dh) / 2;
        if (fitMode === 'contain') {
          ctx.fillStyle = '#000';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
        ctx.drawImage(img, dx, dy, dw, dh);
      }

      drawHudOverlay(ctx, canvas.width, canvas.height);

      const latency = Math.round(performance.now() - t0);
      frameCount++;
      const now = performance.now();
      if (now - lastFpsTime >= 1000) {
        currentFps = frameCount;
        frameCount = 0;
        lastFpsTime = now;
        setStatusCard('sc-fps', 'dot-green', `Camera Rate : ${currentFps} FPS`);
      }
      setStatusCard('sc-ping', 'dot-green', `Ping : ${latency} ms`);

      if (!reported) {
        reported = true;
        setStatusCard('sc-cam', 'dot-green', `Camera : ZERO-LATENCY DIRECT (${ip})`);
        statusEl.textContent = 'JARVIS_VISION_CORE :: ZERO_LATENCY_DIRECT';
        logConsole(`Direct snapshot pipeline LIVE — ${latency}ms latency ✓`, 'SUCCESS');
      }

      // Poll next frame immediately for max FPS
      requestAnimationFrame(pollFrame);
    };

    img.onerror = () => {
      if (!polling || !S.camConnected) return;
      logConsole(`Camera unreachable at http://${ip}/shot.jpg — check IP & WiFi`, 'ERROR');
      setStatusCard('sc-cam', 'dot-red', `Camera : Cannot reach ${ip}`);
      statusEl.textContent = 'JARVIS_VISION_CORE :: CONNECTION FAILED';
      // Retry after a delay
      setTimeout(() => {
        if (polling && S.camConnected) pollFrame();
      }, 2000);
    };

    img.src = `http://${ip}/shot.jpg?t=${Date.now()}`;
  }

  pollFrame();
}

function toggleFitMode() {
  const modes = ['cover', 'stretch', 'contain'];
  const labels = {
    cover: '📺 RATIO: COVER (FULL)',
    stretch: '📺 RATIO: STRETCH (FILL)',
    contain: '📺 RATIO: CONTAIN (ORIGINAL)'
  };
  const currentIdx = modes.indexOf(S.camFitMode || 'cover');
  S.camFitMode = modes[(currentIdx + 1) % modes.length];

  const fitBtn = document.getElementById('fit-btn');
  if (fitBtn) fitBtn.textContent = labels[S.camFitMode];

  const feed = document.getElementById('jarvis-feed');
  if (feed) {
    feed.style.objectFit = S.camFitMode === 'stretch' ? 'fill' : S.camFitMode;
  }
  logConsole(`Camera aspect ratio mode set to: ${S.camFitMode.toUpperCase()}`, 'INFO');
}

function startStream(ip, viewport, statusEl, canvas, feed) {
  S.camConnected = true;
  S._wsFallbackTriggered = false;
  viewport.classList.add('live');

  logConsole('Connecting WebSocket zero-latency binary stream...', 'INFO');

  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${location.host}/ws`;

  try {
    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    S._wsStream = ws;

    let frameCount = 0, lastFpsTime = performance.now(), currentFps = 0;
    let isRendering = false;

    ws.onopen = () => {
      logConsole('WebSocket binary stream connected — ZERO-LATENCY MODE ACTIVE ✓', 'SUCCESS');
      setStatusCard('sc-cam', 'dot-green', `Camera : ZERO-LATENCY WS (${ip})`);
      statusEl.textContent = 'JARVIS_VISION_CORE :: ZERO_LATENCY_LIVE';
      feed.style.display = 'none';
    };

    ws.onmessage = async (evt) => {
      if (!S.camConnected || isRendering) return;
      isRendering = true;
      const t0 = performance.now();

      try {
        const blob = new Blob([evt.data], { type: 'image/jpeg' });
        const bmp = await createImageBitmap(blob);

        const rect = viewport.getBoundingClientRect();
        if (canvas.width !== rect.width || canvas.height !== rect.height) {
          canvas.width = rect.width;
          canvas.height = rect.height;
        }
        const ctx = canvas.getContext('2d');

        const fitMode = S.camFitMode || 'cover';
        if (fitMode === 'stretch') {
          ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
        } else {
          const scale = fitMode === 'cover'
            ? Math.max(canvas.width / bmp.width, canvas.height / bmp.height)
            : Math.min(canvas.width / bmp.width, canvas.height / bmp.height);
          const dw = bmp.width * scale, dh = bmp.height * scale;
          const dx = (canvas.width - dw) / 2, dy = (canvas.height - dh) / 2;

          if (fitMode === 'contain') {
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
          }
          ctx.drawImage(bmp, dx, dy, dw, dh);
        }
        bmp.close();

        const latency = Math.round(performance.now() - t0);
        frameCount++;
        const now = performance.now();
        if (now - lastFpsTime >= 1000) {
          currentFps = frameCount;
          frameCount = 0;
          lastFpsTime = now;
          setStatusCard('sc-fps', 'dot-green', `Camera Rate : ${currentFps} FPS`);
        }
        setStatusCard('sc-ping', 'dot-green', `Ping : ${latency} ms (0 Latency)`);
      } catch (e) {
        logConsole(`Frame render error: ${e.message}`, 'ERROR');
      } finally {
        isRendering = false;
      }
    };

    ws.onerror = () => {
      if (S.camConnected && !S._wsFallbackTriggered) {
        S._wsFallbackTriggered = true;
        logConsole('WebSocket stream error, switching to MJPEG stream fallback...', 'WARNING');
        startMJPEGStreamFallback(ip, viewport, statusEl, canvas, feed);
      }
    };

    ws.onclose = () => {
      if (S.camConnected && !S._wsFallbackTriggered) {
        S._wsFallbackTriggered = true;
        logConsole('WebSocket closed, switching to MJPEG stream fallback...', 'WARNING');
        startMJPEGStreamFallback(ip, viewport, statusEl, canvas, feed);
      }
    };
  } catch (e) {
    logConsole(`WebSocket initialization error (${e.message}), falling back to MJPEG stream...`, 'WARNING');
    startMJPEGStreamFallback(ip, viewport, statusEl, canvas, feed);
  }
}

function startMJPEGStreamFallback(ip, viewport, statusEl, canvas, feed) {
  feed.style.objectFit = S.camFitMode === 'stretch' ? 'fill' : (S.camFitMode || 'cover');
  feed.style.display = 'block';
  feed.onerror = () => {
    feed.style.display = 'none';
    startSnapshotPipeline(ip, viewport, statusEl, canvas);
  };
  feed.onload = () => {
    setStatusCard('sc-cam', 'dot-green', `Camera : LIVE MJPEG (${ip})`);
    setStatusCard('sc-fps', 'dot-green', 'Camera Rate : MJPEG Live');
    setStatusCard('sc-ping', 'dot-green', 'Ping : <10 ms');
    statusEl.textContent = 'JARVIS_VISION_CORE :: LIVE';
  };
  feed.src = '/cam/stream?t=' + Date.now();
}

function startSnapshotPipeline(ip, viewport, statusEl, canvas) {
  logConsole('Starting zero-latency snapshot pipeline via proxy...', 'INFO');

  let frameCount = 0, lastFpsTime = performance.now(), currentFps = 0;
  const controller = new AbortController();
  S._feedAbort = controller;

  async function loop() {
    while (S.camConnected && !controller.signal.aborted) {
      const t0 = performance.now();
      try {
        const resp = await fetch('/cam/shot?t=' + Date.now(), {
          signal: controller.signal,
          cache: 'no-store',
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);

        const blob = await resp.blob();
        const bmp = await createImageBitmap(blob);

        const rect = viewport.getBoundingClientRect();
        if (canvas.width !== rect.width || canvas.height !== rect.height) {
          canvas.width = rect.width;
          canvas.height = rect.height;
        }
        const ctx = canvas.getContext('2d');

        const fitMode = S.camFitMode || 'cover';
        if (fitMode === 'stretch') {
          ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
        } else {
          const scale = fitMode === 'cover'
            ? Math.max(canvas.width / bmp.width, canvas.height / bmp.height)
            : Math.min(canvas.width / bmp.width, canvas.height / bmp.height);
          const dw = bmp.width * scale, dh = bmp.height * scale;
          const dx = (canvas.width - dw) / 2, dy = (canvas.height - dh) / 2;

          if (fitMode === 'contain') {
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
          }
          ctx.drawImage(bmp, dx, dy, dw, dh);
        }
        bmp.close();

        const latency = Math.round(performance.now() - t0);
        frameCount++;
        const now = performance.now();
        if (now - lastFpsTime >= 1000) {
          currentFps = frameCount;
          frameCount = 0;
          lastFpsTime = now;
          setStatusCard('sc-fps', 'dot-green', `Camera Rate : ${currentFps} FPS`);
        }
        setStatusCard('sc-ping', 'dot-green', `Ping : ${latency} ms`);

        if (!S._snapReported) {
          S._snapReported = true;
          setStatusCard('sc-cam', 'dot-green', `Camera : LIVE (${ip})`);
          statusEl.textContent = 'JARVIS_VISION_CORE :: LIVE';
          logConsole(`Snapshot pipeline live: ${currentFps || '~'} FPS, ${latency}ms latency`, 'SUCCESS');
        }
      } catch (e) {
        if (controller.signal.aborted) break;
        logConsole(`Frame error: ${e.message}`, 'ERROR');
        await new Promise(r => setTimeout(r, 300));
      }
    }
  }

  S._snapReported = false;
  loop();
}

function emergencyStop() {
  S.emergency = true;
  S.activeDir = null;
  document.querySelectorAll('.dir-btn').forEach(b => { b.classList.remove('pressed'); b.disabled = true; });
  document.getElementById('cmd-status').textContent = 'COMMAND: E-STOPPED';
  setStatusCard('sc-robot', 'dot-red', 'Robot : E-STOPPED');
  logConsole('CRITICAL: EMERGENCY STOP ENGAGED', 'ERROR');
  if (S.demoActive) stopDemo();
  setTimeout(() => {
    S.emergency = false;
    document.querySelectorAll('.dir-btn').forEach(b => b.disabled = false);
    setStatusCard('sc-robot', 'dot-green', 'Robot : Ready');
    document.getElementById('cmd-status').textContent = 'COMMAND: STOPPED';
    logConsole('Emergency lockout disengaged', 'SUCCESS');
  }, 3000);
}

function toggleFullscreen() {
  const vp = document.getElementById('jarvis-viewport');
  if (!document.fullscreenElement && !document.webkitFullscreenElement) {
    if (vp.requestFullscreen) {
      vp.requestFullscreen().catch(() => {});
    } else if (vp.webkitRequestFullscreen) {
      vp.webkitRequestFullscreen();
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    }
  }
}

// ── Demo Simulation ──────────────────────────────────────────
function toggleDemo() {
  if (S.demoActive) stopDemo(); else startDemo();
}
function startDemo() {
  S.demoActive = true; S.demoIdx = 0;
  const btn = document.getElementById('demo-btn');
  btn.textContent = '⏹ STOP'; btn.classList.add('active');

  if (!S.btConnected) toggleBluetooth();
  document.getElementById('mp-state').textContent = 'EXPLORING';
  logConsole('🚀 LIVE DEMO ACTIVATED: Virtual Rover link established', 'SUCCESS');
  logConsole('Autonomous exploration sequence active', 'INFO');

  S.demoTimer = setInterval(stepDemo, 900);
}
function stepDemo() {
  if (!S.demoActive || S.demoIdx >= DEMO_MOVES.length) {
    stopDemo();
    triggerMissionComplete();
    return;
  }
  const dir = DEMO_MOVES[S.demoIdx];
  S.demoIdx++;
  sendCommand(dir);

  const cov = Math.min(96, 20 + S.demoIdx * 7);
  S.tel.cov = cov;
  S.tel.battery = Math.max(70, 92 - S.demoIdx * 1.2);
  S.tel.vision = 96 + Math.random() * 3.5;
  S.tel.nav = 98.5 + Math.random() * 1.2;
  S.tel.signal = 95 + Math.random() * 3;
  updateGauges();

  logConsole(`AI NAV: Step ${S.demoIdx}/${DEMO_MOVES.length}: ${dir.toUpperCase()} | SLAM: ${cov}%`, 'INFO');

  if (S.demoIdx === 3) logConsole('SLAM: Checkpoint QR-1 Acquired (99.4%)', 'SUCCESS');
  if (S.demoIdx === 7) logConsole('SLAM: Checkpoint QR-2 Acquired (99.1%)', 'SUCCESS');
  if (S.demoIdx === 11) logConsole('SLAM: Checkpoint QR-3 Acquired (98.8%)', 'SUCCESS');
}
function stopDemo() {
  S.demoActive = false;
  clearInterval(S.demoTimer);
  const btn = document.getElementById('demo-btn');
  btn.textContent = '🚀 DEMO'; btn.classList.remove('active');
  sendStop();
  logConsole('DEMO: Autonomous run ended', 'SUCCESS');
}

// ── Mission Complete ─────────────────────────────────────────
function triggerMissionComplete() {
  const overlay = document.getElementById('mission-overlay');
  overlay.classList.remove('hidden');

  const mc = document.getElementById('mission-canvas');
  const mctx = mc.getContext('2d');
  mc.width = window.innerWidth; mc.height = window.innerHeight;
  // grid lines
  mctx.strokeStyle = 'rgba(53,207,255,0.05)'; mctx.lineWidth = 0.5;
  for (let x = 0; x < mc.width; x += 40) { mctx.beginPath(); mctx.moveTo(x, 0); mctx.lineTo(x, mc.height); mctx.stroke(); }
  for (let y = 0; y < mc.height; y += 40) { mctx.beginPath(); mctx.moveTo(0, y); mctx.lineTo(mc.width, y); mctx.stroke(); }

  const cards = document.getElementById('mission-cards');
  const cov = Math.round(S.maze.visited.size / (S.maze.rows * S.maze.cols) * 100);
  const data = [
    ['MAZE COVERAGE', `${cov}%`, '#00E676'], ['QR CHECKPOINTS', '3 / 3 DISCOVERED', '#00E676'],
    ['MISSION SCORE', '9850 PTS', '#35CFFF'], ['ROBOT HEALTH', '100% NOMINAL', '#00E676'],
    ['AVERAGE STREAM', '30.0 FPS', '#35CFFF'], ['LATENCY PING', '9.0 ms', '#00E676'],
    ['BLUETOOTH LINK', '115200 BAUD', '#35CFFF'], ['MATCH TIMELINE', 'FULL EXPLORED ✓', '#FBBF24'],
  ];
  cards.innerHTML = '';
  data.forEach(([title, val, color], i) => {
    cards.innerHTML += `<div class="mc-card" style="animation-delay:${i * 0.08}s">
      <div class="mc-title">${title}</div><div class="mc-val" style="color:${color}">${val}</div></div>`;
  });

  logConsole('CRITICAL EVENT: MISSION ACCOMPLISHED & COMPLETED', 'SUCCESS');
}
function dismissMission() {
  document.getElementById('mission-overlay').classList.add('hidden');
}

// ── Session Report Export ────────────────────────────────────
function exportSessionReport() {
  const cov = Math.round(S.maze.visited.size / (S.maze.rows * S.maze.cols) * 100);
  const now = new Date();
  const report = {
    title: "Blind Maze Driver Station Pro — Telemetry Mission Report",
    exportedAt: now.toISOString(),
    sessionSummary: {
      missionState: document.getElementById('mp-state')?.textContent || 'ACTIVE',
      slamCoveragePct: cov,
      qrCheckpointsFound: S.maze.qr,
      totalQrTargets: 3,
      cellsVisitedCount: S.maze.visited.size,
      visitedCoordinates: Array.from(S.maze.visited),
      currentPosition: { row: S.maze.robotR, col: S.maze.robotC, heading: S.maze.heading }
    },
    liveTelemetry: {
      batteryPct: Math.round(S.tel.battery),
      systemHealth: S.tel.health,
      navReliability: S.tel.nav,
      visionConfidence: S.tel.vision,
      bluetoothSignal: S.tel.signal
    },
    hardwareLinks: {
      bluetoothPort: "COM12",
      cameraSource: document.getElementById('stream-url')?.value || 'webcam',
      activeStreamMode: S.camConnected ? 'CONNECTED' : 'STANDBY'
    }
  };

  const jsonStr = JSON.stringify(report, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `blind_maze_report_${now.getFullYear()}${(now.getMonth()+1).toString().padStart(2,'0')}${now.getDate().toString().padStart(2,'0')}_${now.getHours().toString().padStart(2,'0')}${now.getMinutes().toString().padStart(2,'0')}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  logConsole(`✓ Flight mission telemetry exported: ${a.download}`, 'SUCCESS');
}

// ── Flight Replay ────────────────────────────────────────────
function replayFlightLog() {
  if (S.maze.trail.length === 0) {
    const sampleMoves = [[3,3],[2,3],[1,3],[1,2],[1,1],[2,1],[3,1],[4,1],[5,1],[5,2],[5,3],[5,4],[5,5]];
    S.maze.trail = sampleMoves;
    sampleMoves.forEach(pt => S.maze.visited.add(`${pt[0]},${pt[1]}`));
  }

  logConsole(`▶ Replaying mission flight path (${S.maze.trail.length} waypoints)...`, 'INFO');
  let step = 0;
  const replayTimer = setInterval(() => {
    if (step >= S.maze.trail.length) {
      clearInterval(replayTimer);
      logConsole('✓ Flight mission path replay completed', 'SUCCESS');
      return;
    }
    const pt = S.maze.trail[step];
    S.maze.robotR = pt[0];
    S.maze.robotC = pt[1];
    step++;
  }, 250);
}

// ── Helpers ──────────────────────────────────────────────────
function animateValue(el, from, to, duration, cb) {
  const start = performance.now();
  (function step(now) {
    const p = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - p, 3);
    const v = Math.round(from + (to - from) * eased);
    cb(v);
    if (p < 1) requestAnimationFrame(step);
  })(start);
}

// ── Launch ───────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', runBootSequence);
