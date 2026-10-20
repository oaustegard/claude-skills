/* page-scrawl overlay: draw on a web page, note each mark, hand the marks to an agent.
   Paste the whole file into Claude in Chrome's javascript_tool (or run it as a bookmarklet).
   Re-running it is safe: it shows the existing overlay and returns its status.
   Only block comments in this file, so it survives being turned into a bookmarklet. */
(function pageScrawl() {
  const VERSION = '0.2.0';
  if (window.__scrawl && window.__scrawl.version) { window.__scrawl.show(); return window.__scrawl.status(); }

  const RED = '#e5484d';
  const KEY = 'page-scrawl:' + location.origin + location.pathname;
  const state = { marks: [], drawing: true, done: false, chrome: true, ink: true, errors: [], started: Date.now() };
  let current = null, editing = null, nextId = 1;

  /* ---------- DOM: one fixed host, everything inside a shadow root ---------- */
  const host = document.createElement('div');
  host.id = '__scrawl-host';
  host.style.cssText = 'all:initial;position:fixed;inset:0;z-index:2147483647;pointer-events:none;';
  const root = host.attachShadow({ mode: 'open' });
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(`
    canvas{position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;cursor:crosshair;touch-action:none}
    canvas.on{pointer-events:auto}
    .bar{position:fixed;right:16px;bottom:16px;display:flex;gap:2px;align-items:center;padding:5px;background:#1c1c1e;color:#f5f5f7;border-radius:10px;font:12px/1.2 -apple-system,system-ui,sans-serif;box-shadow:0 4px 18px rgba(0,0,0,.28);pointer-events:auto;user-select:none}
    .bar button{all:unset;padding:5px 9px;border-radius:6px;cursor:pointer}
    .bar button:hover{background:#3a3a3c}
    .bar button.on{background:${RED}}
    .bar .count{padding:0 6px;opacity:.65;min-width:44px;text-align:center}
    .bar .ready{padding:0 6px;color:#7ee2a8}
    .note{position:fixed;display:none;width:260px;pointer-events:auto;background:#fff;border:2px solid ${RED};border-radius:8px;padding:6px 8px;box-shadow:0 4px 18px rgba(0,0,0,.22)}
    .note.open{display:block}
    .note b{font:600 11px system-ui,sans-serif;color:${RED}}
    .note textarea{all:unset;display:block;box-sizing:border-box;width:100%;min-height:42px;margin-top:3px;font:13px/1.4 system-ui,sans-serif;color:#111;white-space:pre-wrap}
    .note small{display:block;font:11px system-ui,sans-serif;color:#777;margin-top:3px}
    .hidden{display:none!important}
  `);
  root.adoptedStyleSheets = [sheet];

  const canvas = document.createElement('canvas');
  canvas.className = 'on';
  const ctx = canvas.getContext('2d');
  const bar = document.createElement('div');
  bar.className = 'bar';
  const mk = (label, title, fn) => { const b = document.createElement('button'); b.textContent = label; b.title = title; b.addEventListener('click', fn); bar.appendChild(b); return b; };
  const drawBtn = mk('✎ Draw', 'Toggle drawing (⌥⇧S)', () => setDrawing(!state.drawing));
  const count = document.createElement('span'); count.className = 'count'; bar.appendChild(count);
  mk('Undo', 'Remove the last mark', () => undo());
  mk('Clear', 'Remove all marks', () => clear());
  const copyBtn = mk('Copy', 'Copy the marks as text, to paste into any chat', () => copyMarks());
  const saveBtn = mk('Save', 'Download the marks as a .scrawl.json file', () => saveMarks());
  const doneBtn = mk('Done', 'Finish and hand the marks to Claude', () => finish());
  const ready = document.createElement('span'); ready.className = 'ready hidden'; ready.textContent = 'Ready';
  ready.title = 'Tell Claude to look at your marks, or Copy / Save them'; bar.appendChild(ready);
  mk('✕', 'Close the overlay (marks are kept until reload)', () => hide());

  const note = document.createElement('div');
  note.className = 'note';
  const noteTitle = document.createElement('b');
  const noteText = document.createElement('textarea');
  noteText.placeholder = "What's wrong here?";
  const noteHint = document.createElement('small');
  noteHint.textContent = 'Enter to save · Shift+Enter new line · Esc to skip';
  note.append(noteTitle, noteText, noteHint);
  root.append(canvas, note, bar);
  document.documentElement.appendChild(host);

  /* Keep our pointer and key events away from the page's own handlers. */
  for (const t of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu', 'keydown', 'keyup', 'keypress', 'input'])
    host.addEventListener(t, e => e.stopPropagation());

  /* ---------- canvas sizing and rendering ---------- */
  function resize() {
    const dpr = devicePixelRatio || 1;
    canvas.width = Math.round(innerWidth * dpr);
    canvas.height = Math.round(innerHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    render();
  }
  let queued = false;
  const render = () => {
    if (queued) return; queued = true;
    requestAnimationFrame(() => { queued = false; paint(); });
  };
  function paint() {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    if (!state.ink) return;
    const all = current ? state.marks.concat([current]) : state.marks;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    for (const m of all) {
      ctx.strokeStyle = RED; ctx.lineWidth = 3;
      for (const s of m.strokes) {
        ctx.beginPath();
        s.forEach(([x, y], i) => { const vx = x - scrollX, vy = y - scrollY; i ? ctx.lineTo(vx, vy) : ctx.moveTo(vx, vy); });
        if (s.length === 1) { ctx.arc(s[0][0] - scrollX, s[0][1] - scrollY, 4, 0, 7); ctx.fillStyle = RED; ctx.fill(); }
        ctx.stroke();
      }
      if (m.n) {
        /* badge at the start of the first stroke, nudged away from what the mark points at */
        const [sx, sy] = m.strokes[0][0], under = m.kind === 'underline';
        const bx = sx - scrollX - (under ? 16 : 12), by = sy - scrollY + (under ? 0 : -10);
        ctx.beginPath(); ctx.arc(bx, by, 10, 0, 7); ctx.fillStyle = RED; ctx.fill();
        ctx.fillStyle = '#fff'; ctx.font = '600 11px system-ui,sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(String(m.n), bx, by + 0.5);
      }
    }
  }

  /* ---------- drawing ---------- */
  canvas.addEventListener('pointerdown', e => {
    if (!state.drawing || e.button !== 0) return;
    e.preventDefault();
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* synthetic events have no live pointer */ }
    current = { strokes: [[[e.clientX + scrollX, e.clientY + scrollY]]] };
    render();
  });
  canvas.addEventListener('pointermove', e => {
    if (!current) return;
    const s = current.strokes[0], [lx, ly] = s[s.length - 1];
    const x = e.clientX + scrollX, y = e.clientY + scrollY;
    if (Math.hypot(x - lx, y - ly) >= 2) { s.push([x, y]); render(); }
  });
  const endStroke = () => {
    if (!current) return;
    const stroke = current.strokes[0];
    current = null;
    const prev = state.marks[state.marks.length - 1];
    if (prev && isArrowHead(stroke, prev)) {
      prev.strokes.push(stroke); prev.kind = 'arrow'; prev.bbox = bboxOf(prev.strokes.flat());
      persist(); render();
      if (editing === prev) { noteTitle.textContent = noteTitle.textContent.replace(' line', ' arrow'); noteText.focus(); }
      return;
    }
    if (editing) saveNote();
    addMark(stroke);
  };
  canvas.addEventListener('pointerup', endStroke);
  canvas.addEventListener('pointercancel', endStroke);

  /* A short stroke drawn right after a line, near its end, is that line's arrowhead. */
  function isArrowHead(stroke, prev) {
    if (Date.now() - prev.at > 2500 || prev.strokes.length > 2) return false;
    if (prev.kind !== 'line' && prev.kind !== 'arrow') return false;
    const b = bboxOf(stroke);
    const tip = prev.tip;
    const near = p => Math.hypot(p[0] - tip[0], p[1] - tip[1]) < 30;
    return Math.hypot(b.w, b.h) < 60 && (near(stroke[0]) || near(stroke[stroke.length - 1]));
  }

  function addMark(stroke) {
    const kind = classify(stroke);
    const mark = { id: nextId++, n: 0, kind, strokes: [stroke], bbox: bboxOf(stroke), at: Date.now(), note: '' };
    if (kind === 'line') { mark.tip = stroke[stroke.length - 1]; mark.tail = stroke[0]; }
    Object.assign(mark, target(mark));
    state.marks.push(mark);
    renumber(); persist(); render();
    openNote(mark);
  }

  /* ---------- shape heuristics ---------- */
  function bboxOf(pts) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
  }
  function classify(pts) {
    const b = bboxOf(pts), diag = Math.hypot(b.w, b.h);
    if (pts.length < 3 || diag < 10) return 'point';
    let len = 0;
    for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    const gap = Math.hypot(pts[0][0] - pts[pts.length - 1][0], pts[0][1] - pts[pts.length - 1][1]);
    if (gap < 0.35 * Math.max(b.w, b.h) && len > 1.7 * diag) return 'circle';
    if (gap / len > 0.85) return b.h < 0.3 * b.w && b.h < 30 ? 'underline' : 'line';
    return 'scribble';
  }

  /* ---------- what is under a mark ---------- */
  const ours = el => el === host || host.contains(el);
  function hits(x, y) {
    if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) return [];
    return document.elementsFromPoint(x, y).filter(el => !ours(el) && el !== document.documentElement && el !== document.body);
  }
  const top = (x, y) => hits(x, y)[0] || null;
  function commonAncestor(els) {
    if (!els.length) return null;
    let a = els[0];
    while (a && !els.every(e => a.contains(e))) a = a.parentElement;
    return a;
  }
  function textBetween(x0, x1, y) {
    if (!document.caretRangeFromPoint) return '';
    const a = document.caretRangeFromPoint(x0, y), b = document.caretRangeFromPoint(x1, y);
    if (!a || !b) return '';
    const r = document.createRange();
    try { r.setStart(a.startContainer, a.startOffset); r.setEnd(b.startContainer, b.startOffset); } catch (e) { return ''; }
    return clip(r.toString(), 200);
  }

  function target(mark) {
    canvas.classList.remove('on'); /* hit-test the page, not the canvas */
    try {
      const b = { x: mark.bbox.x - scrollX, y: mark.bbox.y - scrollY, w: mark.bbox.w, h: mark.bbox.h };
      let primary = null, others = [], quote = '';
      if (mark.kind === 'point') {
        primary = top(b.x, b.y);
      } else if (mark.kind === 'line') {
        /* a pointer line often stops just short of (or past) its target: probe around the tip, keep the smallest element */
        const tx = mark.tip[0] - scrollX, ty = mark.tip[1] - scrollY;
        const len = Math.hypot(tx - (mark.tail[0] - scrollX), ty - (mark.tail[1] - scrollY)) || 1;
        const ux = (tx - mark.tail[0] + scrollX) / len, uy = (ty - mark.tail[1] + scrollY) / len;
        let area = Infinity;
        for (const d of [0, 6, 12, 18, 24, -6, -12]) {
          const el = top(tx + ux * d, ty + uy * d);
          if (!el) continue;
          const r = el.getBoundingClientRect();
          if (r.width * r.height < area) { area = r.width * r.height; primary = el; }
        }
        const from = top(mark.tail[0] - scrollX, mark.tail[1] - scrollY);
        if (from && from !== primary) others = [from];
      } else if (mark.kind === 'underline') {
        const ys = [b.y - 9, b.y - 4, b.y + b.h / 2];
        for (const y of ys) {
          const xs = [0.1, 0.3, 0.5, 0.7, 0.9].map(f => b.x + f * b.w);
          const found = xs.map(x => top(x, y)).filter(Boolean);
          if (found.length) { primary = commonAncestor(found); quote = textBetween(b.x - 4, b.x + b.w + 4, y); break; }
        }
      } else {
        /* circle or scribble: the largest elements fully inside the shape, else what is at its centre */
        const pad = 0.15, B = { l: b.x - b.w * pad, r: b.x + b.w * (1 + pad), t: b.y - b.h * pad, b: b.y + b.h * (1 + pad) };
        const inside = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.left >= B.l && r.right <= B.r && r.top >= B.t && r.bottom <= B.b; };
        const found = new Set();
        for (let i = 1; i < 6; i++) for (let j = 1; j < 6; j++) {
          let el = top(b.x + b.w * i / 6, b.y + b.h * j / 6);
          if (!el || !inside(el)) continue;
          while (el.parentElement && el.parentElement !== document.body && inside(el.parentElement)) el = el.parentElement;
          found.add(el);
        }
        const enclosed = [...found];
        if (enclosed.length === 1) primary = enclosed[0];
        else if (enclosed.length > 1) {
          const ca = commonAncestor(enclosed), r = ca && ca.getBoundingClientRect();
          primary = r && r.width * r.height < 2.5 * Math.max(1, b.w * b.h) ? ca : enclosed[0];
          others = enclosed.filter(e => e !== primary).slice(0, 4);
        } else primary = top(b.x + b.w / 2, b.y + b.h / 2);
        quote = textBetween(b.x + 2, b.x + b.w - 2, b.y + b.h / 2);
      }
      return { target: primary ? describe(primary) : null, others: others.map(describe), quote };
    } finally { if (state.drawing) canvas.classList.add('on'); }
  }

  /* ---------- describing an element ---------- */
  const clip = (s, n) => { s = (s || '').replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
  function selectorFor(el) {
    const esc = CSS.escape, unique = sel => { try { return document.querySelectorAll(sel).length === 1; } catch (e) { return false; } };
    if (el.id && unique('#' + esc(el.id))) return '#' + esc(el.id);
    for (const a of ['data-testid', 'data-test', 'data-cy', 'name', 'aria-label']) {
      const v = el.getAttribute(a);
      if (v && v.length < 60) { const s = `${el.tagName.toLowerCase()}[${a}="${v.replace(/"/g, '\\"')}"]`; if (unique(s)) return s; }
    }
    const parts = [];
    for (let e = el; e && e.nodeType === 1 && e !== document.documentElement && parts.length < 5; e = e.parentElement) {
      let p = e.tagName.toLowerCase();
      if (e.id && unique('#' + esc(e.id))) { parts.unshift('#' + esc(e.id)); break; }
      const cls = [...e.classList].filter(c => /^[a-zA-Z][\w-]{1,40}$/.test(c) && !/[0-9a-f]{5,}/i.test(c)).slice(0, 2);
      if (cls.length) p += '.' + cls.map(esc).join('.');
      const sib = e.parentElement ? [...e.parentElement.children].filter(c => c.tagName === e.tagName) : [];
      if (sib.length > 1) p += `:nth-of-type(${sib.indexOf(e) + 1})`;
      parts.unshift(p);
      if (unique(parts.join(' > '))) break;
    }
    return parts.join(' > ');
  }
  function styleOf(el) {
    const cs = getComputedStyle(el), s = {};
    s.font = `${cs.fontSize}/${cs.lineHeight} ${cs.fontWeight} ${cs.fontFamily.split(',')[0].replace(/["']/g, '')}`;
    s.color = cs.color;
    if (cs.backgroundColor !== 'rgba(0, 0, 0, 0)') s.background = cs.backgroundColor;
    s.display = cs.display;
    if (cs.position !== 'static') s.position = cs.position;
    if (cs.margin !== '0px') s.margin = cs.margin;
    if (cs.padding !== '0px') s.padding = cs.padding;
    if (cs.gap && cs.gap !== 'normal') s.gap = cs.gap;
    if (cs.borderRadius !== '0px') s.radius = cs.borderRadius;
    if (cs.borderWidth && cs.borderStyle !== 'none' && cs.borderWidth !== '0px') s.border = `${cs.borderWidth} ${cs.borderStyle} ${cs.borderColor}`;
    if (cs.textAlign !== 'start') s.textAlign = cs.textAlign;
    if (cs.opacity !== '1') s.opacity = cs.opacity;
    if (cs.overflow !== 'visible') s.overflow = cs.overflow;
    if (cs.zIndex !== 'auto') s.zIndex = cs.zIndex;
    return s;
  }
  /* Source locations from dev builds: React fibers, Vue and Svelte dev metadata, inspector-plugin attributes. */
  function stackFrame(stack) {
    for (const line of String(stack || '').split('\n')) {
      if (/node_modules|react-dom|react\.development|jsx-dev-runtime|react-jsx|chunk-/.test(line)) continue;
      const m = line.match(/(https?:\/\/[^\s)]+?):(\d+):(\d+)/);
      if (m) return new URL(m[1]).pathname.replace(/^\//, '') + ':' + m[2] + ' (from a stack trace, line may be off)';
    }
    return undefined;
  }
  function componentOf(el) {
    const fk = Object.keys(el).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
    if (fk) {
      const f = el[fk], chain = [];
      let source;
      if (f._debugSource) source = `${f._debugSource.fileName}:${f._debugSource.lineNumber}`;
      else if (f._debugStack) source = stackFrame(f._debugStack.stack);
      for (let n = f; n && chain.length < 4; n = n.return) {
        const t = n.type;
        if (!t || typeof t === 'string') continue;
        const name = t.displayName || t.name || (t.render && (t.render.displayName || t.render.name)) || (t.type && (t.type.displayName || t.type.name));
        if (name && chain[chain.length - 1] !== name) chain.push(name);
        if (!source && n._debugSource) source = `${n._debugSource.fileName}:${n._debugSource.lineNumber}`;
      }
      return { framework: 'react', chain, source };
    }
    let v = el;
    while (v && !v.__vueParentComponent) v = v.parentElement;
    if (v) {
      const chain = [];
      let c = v.__vueParentComponent;
      const source = c.type && c.type.__file;
      for (; c && chain.length < 4; c = c.parent) { const nm = c.type && (c.type.name || c.type.__name); if (nm) chain.push(nm); }
      return { framework: 'vue', chain, source };
    }
    for (let s = el, i = 0; s && i < 4; s = s.parentElement, i++)
      if (s.__svelte_meta && s.__svelte_meta.loc) { const l = s.__svelte_meta.loc; return { framework: 'svelte', source: `${l.file}:${l.line}:${l.column}` }; }
    return undefined;
  }
  function sourceAttr(el) {
    for (let e = el, i = 0; e && e.nodeType === 1 && i < 4; e = e.parentElement, i++)
      for (const a of e.attributes)
        if (a.name.startsWith('data-') && /\.(tsx?|jsx?|vue|svelte|astro|html?|erb|php|py)(:\d+)?/.test(a.value)) return `${a.name}="${a.value}"`;
    return undefined;
  }
  function describe(el) {
    const r = el.getBoundingClientRect();
    const text = el.matches('input,textarea,select') ? (el.value || el.placeholder || '') : el.innerText;
    const d = {
      selector: selectorFor(el),
      tag: el.tagName.toLowerCase(),
      text: clip(text, 120),
      rect: { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) },
      style: styleOf(el),
    };
    const role = el.getAttribute('role'), label = el.getAttribute('aria-label') || el.getAttribute('alt') || el.getAttribute('title');
    if (role) d.role = role;
    if (label) d.label = clip(label, 80);
    if (el.getAttribute('href')) d.href = el.getAttribute('href');
    const comp = componentOf(el); if (comp) d.component = comp;
    const src = sourceAttr(el); if (src) d.sourceAttr = src;
    return d;
  }

  /* ---------- notes ---------- */
  function openNote(mark) {
    editing = mark;
    noteTitle.textContent = `#${mark.n} ${mark.kind}${mark.target ? ' · ' + mark.target.tag + (mark.target.text ? ' “' + clip(mark.target.text, 30) + '”' : '') : ''}`;
    noteText.value = mark.note || '';
    note.classList.add('open');
    const b = mark.bbox, vx = b.x - scrollX, vy = b.y + b.h - scrollY;
    const left = Math.min(Math.max(8, vx), innerWidth - 280), below = vy + 12;
    note.style.left = left + 'px';
    note.style.top = (below + 110 < innerHeight ? below : Math.max(8, b.y - scrollY - 120)) + 'px';
    noteText.focus({ preventScroll: true });
  }
  function saveNote() {
    if (!editing) return;
    editing.note = noteText.value.trim();
    editing = null;
    note.classList.remove('open');
    persist();
  }
  noteText.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveNote(); }
    else if (e.key === 'Escape') { e.preventDefault(); noteText.value = editing ? editing.note : ''; saveNote(); }
  });

  /* ---------- page context: errors from now on, failed requests since load ---------- */
  const origError = console.error;
  console.error = function (...a) {
    state.errors.push({ t: Date.now(), msg: clip(a.map(x => x instanceof Error ? x.stack || x.message : typeof x === 'object' ? safeJson(x) : String(x)).join(' '), 400) });
    if (state.errors.length > 30) state.errors.shift();
    return origError.apply(this, a);
  };
  const onErr = e => state.errors.push({ t: Date.now(), msg: clip(e.reason ? String(e.reason && e.reason.stack || e.reason) : `${e.message} @ ${e.filename}:${e.lineno}`, 400) });
  addEventListener('error', onErr);
  addEventListener('unhandledrejection', onErr);
  function safeJson(x) { try { return JSON.stringify(x); } catch (e) { return String(x); } }
  function failedRequests() {
    return performance.getEntriesByType('resource')
      .filter(r => r.responseStatus >= 400 && !/\/favicon\.ico$/.test(r.name))
      .slice(-20)
      .map(r => ({ status: r.responseStatus, type: r.initiatorType, url: r.name }));
  }

  /* ---------- state changes ---------- */
  function renumber() { state.marks.forEach((m, i) => { m.n = i + 1; }); count.textContent = state.marks.length === 1 ? '1 mark' : state.marks.length + ' marks'; }
  function persist() {
    try { sessionStorage.setItem(KEY, JSON.stringify({ saved: Date.now(), marks: state.marks })); } catch (e) { /* storage may be blocked */ }
  }
  function setDrawing(on) {
    state.drawing = on;
    canvas.classList.toggle('on', on);
    drawBtn.classList.toggle('on', on);
    if (on && state.done) { state.done = false; ready.classList.add('hidden'); doneBtn.classList.remove('hidden'); }
  }
  function undo() { if (editing) saveNote(); state.marks.pop(); renumber(); persist(); render(); }
  function clear() { if (editing) saveNote(); state.marks = []; renumber(); persist(); render(); }
  function finish() {
    if (editing) saveNote();
    setDrawing(false);
    state.done = true;
    doneBtn.classList.add('hidden'); ready.classList.remove('hidden');
  }
  function hide() { if (editing) saveNote(); setDrawing(false); host.style.display = 'none'; }
  function show() { host.style.display = ''; if (!state.done) setDrawing(true); }

  addEventListener('keydown', e => {
    if (e.altKey && e.shiftKey && e.code === 'KeyS') { e.preventDefault(); host.style.display === 'none' ? show() : setDrawing(!state.drawing); }
    else if (state.drawing && !editing && (e.metaKey || e.ctrlKey) && e.key === 'z') { e.preventDefault(); undo(); }
  }, true);
  addEventListener('scroll', render, { passive: true, capture: true });
  addEventListener('resize', resize);

  /* ---------- the agent's side ---------- */
  function exportMark(m, withPoints) {
    const o = { n: m.n, kind: m.kind, note: m.note, bbox: { x: Math.round(m.bbox.x), y: Math.round(m.bbox.y), w: Math.round(m.bbox.w), h: Math.round(m.bbox.h) }, target: m.target, others: m.others };
    if (m.quote) o.quote = m.quote;
    if (m.restored) o.restored = true;
    if (withPoints) o.strokes = m.strokes;
    return o;
  }
  function exportData(opts) {
    const withPoints = !!(opts && opts.points);
    return {
      tool: 'page-scrawl', version: VERSION,
      url: location.href, title: document.title,
      viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio, scrollX: Math.round(scrollX), scrollY: Math.round(scrollY) },
      done: state.done,
      marks: state.marks.map(m => exportMark(m, withPoints)),
      consoleErrors: state.errors,
      failedRequests: failedRequests(),
    };
  }
  function line(d) {
    if (!d) return '(nothing found under the mark)';
    let s = '`' + d.selector + '`';
    if (d.text) s += ` “${clip(d.text, 60)}”`;
    if (d.component) {
      if (d.component.chain && d.component.chain.length) s += ` ‹${d.component.chain.join(' › ')}›`;
      if (d.component.source) s += ` ${d.component.source}`;
    }
    if (d.sourceAttr) s += ` [${d.sourceAttr}]`;
    return s;
  }
  function summary() {
    const v = exportData();
    const out = [`[page-scrawl · ${v.marks.length} mark${v.marks.length === 1 ? '' : 's'} · “${v.title}” · ${v.url} · ${v.viewport.w}×${v.viewport.h} @${v.viewport.dpr}x${v.done ? '' : ' · not marked Done yet'}]`];
    for (const m of v.marks) {
      out.push(`- #${m.n} ${m.kind}${m.quote ? ` over “${clip(m.quote, 80)}”` : ''} → ${line(m.target)}${m.note ? ` — “${m.note}”` : ''}`);
      if (m.target) out.push('  style: ' + Object.entries(m.target.style).map(([k, x]) => `${k} ${x}`).join(' · ')); /* not '; ': Claude in Chrome's output filter reads that as a cookie header */
      for (const o of m.others || []) out.push('  also: ' + line(o));
    }
    if (v.consoleErrors.length) { out.push('Console errors since the overlay opened:'); v.consoleErrors.slice(-8).forEach(e => out.push('  · ' + clip(e.msg, 200))); }
    if (v.failedRequests.length) { out.push('Failed requests since page load:'); v.failedRequests.slice(-8).forEach(r => out.push(`  · ${r.status} ${r.type} ${r.url}`)); }
    return out.join('\n');
  }
  /* Standalone export, for when no agent is attached to the tab (bookmarklet use). */
  function flash(btn, text) {
    const was = btn.dataset.label || (btn.dataset.label = btn.textContent);
    btn.textContent = text;
    clearTimeout(btn._t); btn._t = setTimeout(() => { btn.textContent = was; }, 1600);
  }
  function fileData() {
    if (editing) saveNote();
    return Object.assign(exportData({ points: true }), { saved: new Date().toISOString(), summary: summary() });
  }
  function fileName() {
    const d = new Date(), z = n => String(n).padStart(2, '0');
    const site = (location.hostname || 'page').replace(/[^a-z0-9.-]+/gi, '_');
    return `${site}-${d.getFullYear()}${z(d.getMonth() + 1)}${z(d.getDate())}-${z(d.getHours())}${z(d.getMinutes())}.scrawl.json`;
  }
  function saveMarks() {
    if (!state.marks.length) return flash(saveBtn, 'No marks'), null;
    const name = fileName();
    const url = URL.createObjectURL(new Blob([JSON.stringify(fileData(), null, 2)], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url; a.download = name; a.style.display = 'none';
    root.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    flash(saveBtn, 'Saved ✓');
    return name;
  }
  function copyFallback(text) {
    const t = document.createElement('textarea');
    t.value = text; t.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    root.appendChild(t); t.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { /* unsupported */ }
    t.remove();
    return ok;
  }
  async function copyMarks() {
    if (!state.marks.length) return flash(copyBtn, 'No marks'), false;
    if (editing) saveNote();
    const text = summary();
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch (e) { ok = copyFallback(text); }
    flash(copyBtn, ok ? 'Copied ✓' : 'Copy failed');
    return ok;
  }

  /* Scroll a mark into the middle of the viewport; returns its viewport box for a zoomed screenshot. */
  function focus(n) {
    const m = state.marks.find(x => x.n === n);
    if (!m) return null;
    scrollTo({ left: Math.max(0, m.bbox.x + m.bbox.w / 2 - innerWidth / 2), top: Math.max(0, m.bbox.y + m.bbox.h / 2 - innerHeight / 2), behavior: 'instant' });
    paint();
    const p = 40;
    return { x0: Math.max(0, Math.round(m.bbox.x - scrollX - p)), y0: Math.max(0, Math.round(m.bbox.y - scrollY - p)), x1: Math.min(innerWidth, Math.round(m.bbox.x + m.bbox.w - scrollX + p)), y1: Math.min(innerHeight, Math.round(m.bbox.y + m.bbox.h - scrollY + p)) };
  }
  function restore() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (!saved || !saved.marks) return 0;
      state.marks = saved.marks.map(m => Object.assign(m, { restored: true }));
      nextId = state.marks.reduce((a, m) => Math.max(a, m.id || 0), 0) + 1;
      renumber(); render();
      return state.marks.length;
    } catch (e) { return 0; }
  }
  function destroy(forget) {
    console.error = origError;
    removeEventListener('error', onErr); removeEventListener('unhandledrejection', onErr);
    removeEventListener('resize', resize);
    removeEventListener('scroll', render, { capture: true });
    host.remove();
    delete window.__scrawl;
    if (forget) try { localStorage.removeItem('page-scrawl:src'); sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ }
  }

  window.__scrawl = {
    version: VERSION,
    status: () => ({ version: VERSION, marks: state.marks.length, done: state.done, drawing: state.drawing, editingNote: !!editing }),
    export: exportData,
    summary,
    save: saveMarks,
    copy: copyMarks,
    focus,
    restore,
    show,
    hide,
    clear,
    undo,
    destroy,
    draw: setDrawing,
    /* Hide the toolbar and note box (ink stays) for a clean screenshot; pass true to bring them back. */
    chrome: on => { state.chrome = on !== false; bar.classList.toggle('hidden', !state.chrome); note.classList.toggle('hidden', !state.chrome); },
    /* Hide or show the ink itself, for a before/after screenshot of the bare page. */
    ink: on => { state.ink = on !== false; paint(); },
  };

  /* Cache this script per origin, so after a reload the agent can re-inject it with a one-line loader. */
  try { localStorage.setItem('page-scrawl:src', JSON.stringify({ version: VERSION, src: '(' + pageScrawl + ')()' })); } catch (e) { /* storage may be blocked */ }

  resize();
  renumber();
  setDrawing(true);
  return window.__scrawl.status();
})();
