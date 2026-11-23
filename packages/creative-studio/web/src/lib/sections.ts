import { api, chat, esc } from './core';

// Deep Research — autonomous loop over the sandboxed websearch MCP (:8642).
// Zero-cost: DuckDuckGo via the existing llama-cpp research sandbox only.

export async function renderResearch(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  let rid: string | null = null;
  let timer: number | null = null;

  main.innerHTML = `<h1>Deep Research</h1>
    <p class="muted">Autonome Recherche: Planung → Quellen → Extraktion → Prüfung →
    Lücken → Follow-up. Kostenfrei über den sandboxten websearch-mcp (DuckDuckGo),
    Synthese über den llama.cpp-Router. Kein Cloud-Dienst.</p>
    <form id="rq" class="row">
      <div style="flex:4 1 20rem"><label for="q">Rechercheauftrag</label>
        <input id="q" required placeholder="Welche Leuchttürme der Ostsee stammen aus dem 19. Jh. …"/></div>
      <div style="flex:0 1 9rem"><label for="mode">Modus</label>
        <select id="mode"><option value="quick">Quick</option>
        <option value="deep" selected>Deep</option><option value="extended">Extended</option></select></div>
      <button class="btn primary" type="submit" style="flex:0 0 auto">Starten</button>
      <button class="btn" id="pause" type="button" disabled>Pause</button>
    </form>
    <p class="status" id="state" role="status">Ohne Auftrag keine Recherche.</p>
    <div id="log" class="small"></div>
    <div id="dossier" class="prose" style="font-family:var(--font-read)"></div>`;
  const state = main.querySelector('#state')!;
  const log = main.querySelector('#log')!;
  const dossier = main.querySelector('#dossier')!;
  const pauseBtn = main.querySelector('#pause') as HTMLButtonElement;

  async function poll() {
    if (!rid) return;
    try {
      const d = await fetch(`/api/research/${rid}`).then((r) => r.json());
      const cp = d.checkpoint ?? {};
      const facts: Array<{ fact: string; url: string }> = cp.facts ?? [];
      state.textContent = `${d.status} · Runde ${cp.done_rounds ?? 0}/${cp.rounds ?? '?'}` +
        ` · Fakten ${facts.length} · Quellen ${(cp.sources ?? []).length}` +
        ` · offen ${(cp.open ?? []).length}${cp.paused ? ' (pausiert)' : ''}`;
      log.innerHTML = `<ul class="list">${facts.slice(-12).map((f) =>
        `<li>• ${esc(f.fact.slice(0, 220))} <span class="muted small">${esc(f.url.slice(0, 70))}</span></li>`).join('')}</ul>`
        + ((cp.contradictions ?? []).length
          ? `<p class="muted">Widersprüche: ${(cp.contradictions as string[]).map(esc).join(' · ')}</p>` : '');
      if (d.status === 'completed') {
        stop();
        pauseBtn.disabled = true;
        const docId = (d.result as Record<string, string>)?.document_id;
        if (docId) {
          const doc = await api.document(docId);
          dossier.textContent = doc.body;
          state.textContent = 'Dossier fertig — als Dokument gespeichert (' + docId.slice(0, 8) + ')';
        }
      }
    } catch { state.textContent = 'Studio-Backend kurz nicht erreichbar – Retry'; }
  }
  function stop() { if (timer !== null) { clearInterval(timer); timer = null; } }

  (main.querySelector('#rq') as HTMLFormElement).addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = (main.querySelector('#q') as HTMLInputElement).value.trim();
    if (!question) return;
    const r = await api.research({ question, mode: (main.querySelector('#mode') as HTMLSelectElement).value });
    rid = r.id; pauseBtn.disabled = false;
    state.textContent = 'Recherche läuft (Runden dauern wegen 26B-Synthese …)';
    stop(); timer = setInterval(poll, 5000) as unknown as number; poll();
  });
  pauseBtn.addEventListener('click', async () => {
    if (!rid) return;
    const paused = /pausiert/.test(state.textContent ?? '');
    await fetch(`/api/research/${rid}/${paused ? 'resume' : 'pause'}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    poll();
  });
  await poll();

  sidebar.innerHTML = `<h2>Modi</h2><p class="small muted">Quick 1 Runde · Deep 3 ·
    Extended bis 10 mit Fortsetzung. Budget: 30 min (extended 60).</p>
    <h2>Frühere Dossiers</h2><div id="old" class="small muted">–</div>`;
  const projects = await api.projects().catch(() => []);
  void projects;
  sidebar.querySelector('#old')!.textContent = 'Dossiers liegen in der Projektbibliothek (kind: dossier).';
  inspector.innerHTML = `<h2>Nullkosten</h2><p class="small muted">Nur erlaubte freie
    Zugänge: DuckDuckGo über :8642-Sandbox (robots.txt/nft-Filter), lokale Modelle.
    Keine Paywalls, keine Cloud.</p>`;
}

// Articles & Devlogs — research dossier → draft → human writing → export.
export async function renderArticles(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  const projects = (await api.projects().catch(() => []))
    .filter((p: { kind: string }) => ['article', 'devlog', 'custom'].includes(p.kind));
  sidebar.innerHTML = `<h2>Redaktion</h2>
    <form id="na"><label for="n">Neuer Artikel</label><input id="n" required placeholder="Titel"/>
    <button class="btn primary" type="submit">+</button></form>
    <ul class="list" id="l">${projects.map((p: { id: string; name: string }) =>
      `<li><button data-id="${p.id}">${esc(p.name)}</button></li>`).join('') || '<li class="muted small">keine</li>'}</ul>`;
  (sidebar.querySelector('#na') as HTMLFormElement).addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = (sidebar.querySelector('#n') as HTMLInputElement).value.trim();
    if (name) { await api.createProject({ name, kind: 'article', lang: 'de' }); renderArticles(main, sidebar, inspector); }
  });
  sidebar.querySelectorAll('[data-id]').forEach((b) => b.addEventListener('click', () =>
    openProject(projects.find((x: { id: string }) => x.id === (b as HTMLElement).dataset.id)!)));
  main.innerHTML = `<h1>Articles &amp; Devlogs</h1><p class="muted">
    Dossier aus Deep Research → Gliederung → Entwurf (creative-writing) → Human-Writing-Audit →
    Illustration → Astro-Export. Projekte links.</p>`;

  async function openProject(p: { id: string; name: string }) {
    const full = await api.project(p.id);
    main.innerHTML = `<h1>${esc(p.name)}</h1><p class="muted small">Dokumente:</p>`;
    for (const d of (full.documents ?? []).slice(0, 6)) {
      const el = document.createElement('article');
      el.className = 'msg';
      el.innerHTML = `<div class="role">${esc(d.title || 'Entwurf')} · v${d.version}</div>
        <div class="prose">${esc((d.body || '').slice(0, 400))}</div>
        <button class="btn" data-save="${d.id}" data-before="">Übernehmen aus Chat →</button>`;
      el.querySelector('button')!.addEventListener('click', async () => {
        const out = el.querySelector('[data-save]') as HTMLElement;
        out.textContent = '…';
        const t = await streamText('creative-writing',
          `[de][generate] Schreibe einen Artikel-Entwurf für "${p.name}". Kontext: ${(d.body || '').slice(0, 4000)}`);
        await api.editDocument(d.id, { body: t, note: 'artikel-entwurf' });
        out.textContent = 'übernommen (neue Version)';
      });
      main.append(el);
    }
    inspector.innerHTML = `<h2>Export</h2><p class="small muted">Fertigen Text im
      Schreib-Editor öffnen und „Astro-Export" nutzen (Publishing).</p>`;
  }
}

async function streamText(model: 'creative-writing', content: string): Promise<string> {
  let acc = '';
  await chat({ model, messages: [{ role: 'user', content }], onToken: (t) => { acc += t; } });
  return acc;
}

// Game Idea Lab — dialogischer Designpartner mit Decision Log.
export async function renderGame(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  const MODES: Record<string, string> = {
    partner: 'Creative Partner: Brainstorming, Mechanik-Alternativen, Genremix.',
    critical: 'Critical Game Designer: Spielspaß, Umfang, Originalität, Risiken, Kosten.',
    planner: 'Production Planner: Prototyp, Arbeitspakete, Sprint, Engine-Entscheid (Godot 4.7.2 / Defold 1.14.1).',
  };
  const projects = (await api.projects().catch(() => [])).filter((p: { kind: string }) => p.kind === 'game');
  let pid: string | null = null;
  let mode = 'partner';
  main.innerHTML = `<h1>Game Idea Lab</h1>
    <p class="muted">Dialogischer Sparringspartner — nichts ist festgelegt, bevor du
    entscheidest. Entscheidungen landen im Decision Log und bleiben änderbar.</p>
    <div class="row" role="group" aria-label="Rolle">
      ${Object.entries(MODES).map(([m, hint], i) =>
        `<label style="flex:0 1 auto"><input type="radio" name="gm" value="${m}" ${i === 0 ? 'checked' : ''} title="${esc(hint)}"/> ${m}</label>`).join('')}
    </div>
    <form id="ask" class="composer"><label for="gq">Designfrage an ${'den Partner'}</label>
      <textarea id="gq" rows="3" required placeholder="2D-Metroidvania mit Drift-Rennen … was sind 3 Alternativen zur Progression?"></textarea>
      <button class="btn primary" type="submit">Diskutieren</button></form>
    <pre id="answer" class="diff" style="white-space:pre-wrap"></pre>
    <h2>Decision Log</h2><div id="log" class="small">–</div>`;
  const answer = main.querySelector('#answer')!;
  const logEl = main.querySelector('#log')!;
  main.querySelector('[name=gm]')!.closest('div')!.addEventListener('change', (e) => {
    mode = (e.target as HTMLInputElement).value;
  });
  async function loadLog() {
    if (!pid) return;
    const ds = await fetch(`/api/projects/${pid}/decisions`).then((r) => r.json());
    logEl.innerHTML = (ds as Array<{ key: string; title?: string; status: string; rationale?: string }>)
      .map((d) => `<div><strong>${esc(d.title ?? d.key)}</strong> · ${esc(d.status)}` +
        (d.rationale ? ` <span class="muted">${esc(d.rationale.slice(0, 120))}</span>` : '') + '</div>').join('')
      || 'leer';
  }
  (main.querySelector('#ask') as HTMLFormElement).addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = (main.querySelector('#gq') as HTMLTextAreaElement).value.trim();
    if (!q) return;
    if (!pid) { pid = (await api.createProject({ name: q.slice(0, 30), kind: 'game', lang: 'de' })).id; }
    answer.textContent = '';
    const roleHint = mode === 'critical'
      ? 'Du bist Critical Game Designer: nenne Risiken, fehlende Lustfaktoren, Umfangsprobleme.'
      : mode === 'planner'
        ? 'Du bist Production Planner: breche in Prototyp + Pakete herunter (Godot/Defold stabil).'
        : 'Du bist Creative Partner: 3 Alternativen, Trade-offs, keine Festlegung.';
    await chat({ model: 'research', messages: [{ role: 'user', content: `[de] ${roleHint}\n${q}` }],
      onToken: (t) => { answer.textContent += t; } });
    loadLog();
  });
  sidebar.innerHTML = `<h2>Projekte</h2><div id="pl" class="small muted">${projects.length
    ? (projects as Array<{ name: string }>).map((p) => esc(p.name)).join('<br>')
    : 'beim ersten Brainstorm angelegt'}</div>
    <h2>Regeln</h2><p class="small muted">Status: idee→diskussion→vorgeschlagen→beschlossen→
    verworfen|spaeter. Alles änderbar; Engine-Beratung nutzt Godot-4.7.2-/Defold-1.14.1-Skills.</p>`;
  inspector.innerHTML = `<h2>Entscheidung</h2>
    <form id="dec"><label for="dt">Titel</label><input id="dt" required placeholder="Engine"/>
    <label for="ds">Status</label><select id="ds"><option>idee</option><option selected>diskussion</option>
    <option>vorgeschlagen</option><option>beschlossen</option><option>verworfen</option><option>spaeter</option></select>
    <label for="dr">Begründung</label><textarea id="dr" rows="2"></textarea>
    <button class="btn primary" type="submit">Ins Log</button>
    <button class="btn" id="gdd" type="button">GDD exportieren</button></form><div id="gddOut" class="small"></div>`;
  (main.parentElement!.querySelector('#dec') as HTMLFormElement)!.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!pid) return;
    await fetch('/api/decisions', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: pid,
        key: (document.querySelector('#dt') as HTMLInputElement).value.toLowerCase().replace(/\s+/g, '-'),
        title: (document.querySelector('#dt') as HTMLInputElement).value,
        status: (document.querySelector('#ds') as HTMLSelectElement).value,
        rationale: (document.querySelector('#dr') as HTMLTextAreaElement).value }) });
    loadLog();
  });
  (main.parentElement!.querySelector('#gdd') as HTMLButtonElement)!.addEventListener('click', async () => {
    if (!pid) return;
    const g = await fetch('/api/gdd', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: pid }) }).then((r) => r.json());
    const blob = new Blob([g.gdd], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'gdd.md'; a.click();
  });
  void loadLog;
}
