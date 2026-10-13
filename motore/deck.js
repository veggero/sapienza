(() => {
  const root = document.documentElement, body = document.body;
  const deck = document.getElementById('deck');
  const bar = document.querySelector('#progress div');
  let slides = [], cur = 0, shown = 0;

  // --- tema salvato (T) ---
  try { const t = localStorage.getItem('slides-theme'); if (t) root.dataset.theme = t; } catch (e) {}

  // --- scala del palco 1920x1080 ---
  const scale = () => root.style.setProperty('--scale', Math.min(innerWidth / 1920, innerHeight / 1080));
  addEventListener('resize', scale); scale();

  // --- autofit: il testo più grande possibile che sta nella slide ---
  function fit(s) {
    const box = s.querySelector('.body'), inner = s.querySelector('.inner');
    if (!box || !inner) return;
    box.style.setProperty('--bh', box.clientHeight + 'px');
    const cs = getComputedStyle(s), v = n => parseFloat(cs.getPropertyValue(n));
    const kind = s.classList.contains('title') ? '--fit-max-title' : s.classList.contains('opener') ? '--fit-max-opener' : '--fit-max';
    const max = +(s.dataset.max || v(kind) || v('--fit-max') || 112);
    const txt = s.querySelector('.txt');
    const ok = () => inner.offsetHeight <= box.clientHeight && inner.scrollWidth <= inner.clientWidth + 1 && inner.offsetWidth <= box.clientWidth + 1 && (!txt || txt.scrollWidth <= txt.clientWidth + 1);
    let lo = v('--fit-min') || 24, hi = max;
    for (let i = 0; i < 14; i++) {
      const mid = (lo + hi) / 2;
      box.style.fontSize = mid + 'px';
      ok() ? lo = mid : hi = mid;
    }
    box.style.fontSize = Math.floor(lo) + 'px';
  }
  // le immagini cambiano l'impaginazione: rifai il fit quando arrivano
  const fitAll = () => slides.forEach(s => {
    fit(s);
    s.querySelectorAll('img').forEach(img => img.complete || img.addEventListener('load', () => fit(s), { once: true }));
  });

  // --- navigazione ---
  const steps = s => [...s.querySelectorAll('[data-step]')];
  const maxStep = s => +s.dataset.steps || 0;
  function render() {
    slides.forEach((s, i) => s.classList.toggle('active', i === cur));
    steps(slides[cur]).forEach(el => el.classList.toggle('hidden', +el.dataset.step > shown));
    bar.style.width = (slides.length > 1 ? cur / (slides.length - 1) * 100 : 100) + '%';
    history.replaceState(null, '', '#' + (cur + 1));
  }
  function go(i, step = 0) {
    cur = Math.max(0, Math.min(slides.length - 1, i));
    shown = step === 'all' ? maxStep(slides[cur]) : Math.min(step, maxStep(slides[cur]));
    render();
  }
  const next = () => shown < maxStep(slides[cur]) ? (shown++, render()) : cur < slides.length - 1 && go(cur + 1);
  const prev = () => shown > 0 ? (shown--, render()) : cur > 0 && go(cur - 1, 'all');

  function overview(on = !body.classList.contains('ov')) {
    body.classList.toggle('ov', on);
    if (on) slides[cur].scrollIntoView({ block: 'center' });
  }

  function bind() {
    slides = [...deck.querySelectorAll('.slide')];
    slides.forEach((s, i) => s.addEventListener('click', e => {
      if (body.classList.contains('ov')) { go(i, 'all'); overview(false); }
      else if (!e.target.closest('a')) e.clientX < innerWidth / 3 ? prev() : next();
    }));
  }

  addEventListener('keydown', e => {
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    const k = e.key;
    if (body.classList.contains('ov')) {
      if (k === 'Escape' || k === 'o' || k === 'Enter') overview(false);
      else if (k === 'ArrowRight') go(cur + 1, 'all');
      else if (k === 'ArrowLeft') go(cur - 1, 'all');
      else return;
    } else if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter', 'n'].includes(k)) next();
    else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace', 'p'].includes(k)) prev();
    else if (k === 'Home') go(0);
    else if (k === 'End') go(slides.length - 1, 'all');
    else if (k === 'f') document.fullscreenElement ? document.exitFullscreen() : root.requestFullscreen();
    else if (k === 'o' || k === 'Escape') overview(true);
    else if (k === 'b' || k === '.') body.classList.toggle('blank');
    else if (k === 'x') document.querySelectorAll('.notif').forEach(n => n.remove());
    else if (k === 't') {
      root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('slides-theme', root.dataset.theme); } catch (e) {}
      slides.forEach(fit);
    } else return;
    e.preventDefault();
  });

  // --- icone del task manager nel pannello ---
  const TASKS = [
    'img/pannelo/dolphin.svg',
    'img/pannello/konsle.svg',
    'img/pannello/browser.png',
  ];
  const overlay = document.createElement('div');
  overlay.id = 'overlay';
  overlay.innerHTML = '<div id="tasks">' + TASKS.map(src => `<span class="task"><img src="${src}" alt="${src.split('/').pop()}"></span>`).join('') +
    '</div><div id="board"></div><div id="notifs"></div>';
  body.appendChild(overlay);

  // --- avvio ---
  bind();
  document.fonts.ready.then(() => {
    fitAll();
    const n = parseInt(location.hash.slice(1)) - 1;
    go(isNaN(n) ? 0 : n, location.search.includes('print') ? 'all' : 0);
  });

  if (!location.protocol.startsWith('http')) return;

  // --- modalità live: se accanto c'è live.json (server del talk) ---
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let version = null, lastEvent = null, live = false;

  function drawBoard(live) {
    const medal = ['gold', 'silver', 'bronze'];
    const top = (live.top || []).slice(0, 3).map((u, i) =>
      `<span class="rank ${medal[i]}"><b>${i + 1}</b>@${esc(u.user)} <span class="pts">${u.points}</span></span>`).join('');
    document.getElementById('board').innerHTML =
      `<span class="repo">${esc(live.repo || '')}</span>` +
      (top || '<span class="rank empty">nessuno ancora: correggi tu il primo errore!</span>');
  }

  function notify(ev) {
    const n = document.createElement('div');
    n.className = 'notif';
    const pos = ev.rank ? ` · ${ev.rank}° posto` : '';
    n.innerHTML = `<div class="head"><span class="app">GitLab</span><span class="when">adesso</span><button aria-label="Chiudi">×</button></div>
      <div class="ntitle">@${esc(ev.user)} ha corretto ${ev.fixes.length === 1 ? 'un errore' : ev.fixes.length + ' errori'}</div>
      <ul>${ev.fixes.map(f => `<li>${esc(f)}</li>`).join('')}</ul>
      <div class="score">+${ev.points} punti → ${ev.total} in totale${pos}</div>`;
    n.querySelector('button').onclick = () => n.remove();
    const box = document.getElementById('notifs');
    box.prepend(n);
    while (box.children.length > 3) box.lastChild.remove();
    setTimeout(() => n.remove(), 45000);
  }

  async function swapDeck() {
    const html = await (await fetch(location.pathname + '?v=' + Date.now(), { cache: 'no-store' })).text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const fresh = doc.getElementById('deck');
    if (!fresh) return;
    deck.innerHTML = fresh.innerHTML;
    bind();
    fitAll();
    go(cur, shown);
  }

  async function poll() {
    try {
      const r = await fetch('live.json?t=' + Date.now(), { cache: 'no-store' });
      if (!r.ok) return false;
      const data = await r.json();
      live = true;
      drawBoard(data);
      if (version && data.version !== version) await swapDeck();
      version = data.version;
      const evs = data.events || [];
      if (lastEvent === null) lastEvent = evs.length ? Math.max(...evs.map(e => e.id)) : 0;
      evs.filter(e => e.id > lastEvent).sort((a, b) => a.id - b.id).forEach(notify);
      if (evs.length) lastEvent = Math.max(lastEvent, ...evs.map(e => e.id));
      return true;
    } catch (e) { return live; }
  }

  poll().then(isLive => {
    if (isLive) { setInterval(poll, 2000); return; }
    // anteprima di sviluppo (build.py --serve): ricarica quando l'html cambia
    let last = null;
    setInterval(async () => {
      try {
        const r = await fetch(location.pathname, { method: 'HEAD', cache: 'no-store' });
        const m = r.headers.get('last-modified');
        if (last && m !== last) location.reload();
        last = m;
      } catch (e) {}
    }, 800);
  });
})();
