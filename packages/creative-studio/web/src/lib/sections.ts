import { api, chat, esc } from './core';

// Deep Research — autonomous loop over the sandboxed websearch MCP (:8642).
// Zero-cost: DuckDuckGo via the existing llama-cpp research sandbox only.

export async function renderResearch(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  let rid: string | null = null;
  let timer: number | null = null;

  main.innerHTML = `<h1>Deep Research</h1>
    <p class="muted">Frage eintippen, auf <strong>Starten</strong> drücken, warten. Die Recherche
    läuft von allein in Runden und endet als Dossier.</p>
    <form id="rq" class="row">
      <div style="flex:4 1 20rem"><label for="q">Rechercheauftrag</label>
        <input id="q" required placeholder="Welche Leuchttürme der Ostsee stammen aus dem 19. Jh. …"/></div>
      <div style="flex:0 1 9rem"><label for="mode">Tiefe</label>
        <select id="mode"><option value="quick">Schnell</option>
        <option value="deep" selected>Normal</option><option value="extended">Gründlich</option></select></div>
      <button class="btn primary" type="submit" style="flex:0 0 auto">Starten</button>
      <button class="btn" id="pause" type="button" disabled>Pause</button>
    </form>
    <p class="status" id="state" role="status">Noch keine Recherche gestartet.</p>
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
      state.textContent = `Runde ${cp.done_rounds ?? 0}/${cp.rounds ?? '?'} · Fakten ${facts.length}`
        + ` · Quellen ${(cp.sources ?? []).length} · offen ${(cp.open ?? []).length}`
        + (cp.paused ? ' (pausiert)' : '');
      log.innerHTML = `<ul class="list">${facts.slice(-12).map((f) =>
        `<li>• ${esc(f.fact.slice(0, 220))} <span class="muted small">${esc(f.url.slice(0, 70))}</span></li>`).join('')}</ul>`
        + ((cp.contradictions ?? []).length
          ? `<p class="muted">Widersprüche: ${(cp.contradictions as string[]).map(esc).join(' · ')}</p>` : '');
      if (d.status === 'completed') {
        stop();
        pauseBtn.disabled = true;
        state.textContent = 'Fertig. Dossier:';
        const docId = (d.result as Record<string, string>)?.document_id;
        if (docId) {
          const doc = await api.document(docId);
          dossier.textContent = doc.body;
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
    rid = r.id; pauseBtn.disabled = false; pauseBtn.textContent = 'Pause';
    state.textContent = 'Recherche läuft …';
    stop(); timer = setInterval(poll, 5000) as unknown as number; poll();
  });
  pauseBtn.addEventListener('click', async () => {
    if (!rid) return;
    const paused = pauseBtn.textContent === 'Pause';
    await fetch(`/api/research/${rid}/${paused ? 'pause' : 'resume'}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    pauseBtn.textContent = paused ? 'Weiter' : 'Pause';
    poll();
  });

  sidebar.innerHTML = `<h2>So funktioniert's</h2>
    <p class="small muted">1. Frage oben eingeben → Starten.<br>
    2. Das Studio sucht, prüft und fragt Lücken nach — ohne weitere Klicks.<br>
    3. Fertige Dossiers: Bereich <strong>Bibliothek</strong> → Projekt „Recherche“.</p>
    <h2>Tiefen</h2><p class="small muted">Schnell 1 Runde · Normal 3 · Gründlich bis 10
    (Budget 30/60&nbsp;min). Pause und Weiter sind jederzeit möglich.</p>`;
  inspector.innerHTML = `<h2>Kostenlos</h2><p class="small muted">Nur freie Zugänge:
    DuckDuckGo durch die sandboxte Recherche (:8642), Synthese über den lokalen
    llama.cpp-Router. Keine Cloud, keine Paywalls.</p>`;
}

// Articles & Devlogs — research dossier → draft → human writing → export.
export async function renderArticles(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  const projects = (await api.projects().catch(() => []))
    .filter((p: { kind: string }) => ['article', 'devlog', 'custom'].includes(p.kind));

  const createForm = `<form id="na2" class="row" style="max-width:28rem">
    <div><label for="n2">Titel des Artikels</label>
    <input id="n2" required placeholder="z. B. Devlog: Studio-Woche 48"/></div>
    <button class="btn primary" type="submit" style="flex:0 0 auto">Projekt anlegen</button></form>`;
  const projectList = projects.length
    ? `<h2>Projekte</h2><div class="row">${projects.map((p: { id: string; name: string }) =>
        `<button class="btn" data-open="${p.id}" style="flex:0 1 auto">${esc(p.name)}</button>`).join('')}</div>`
    : '';

  main.innerHTML = `<h1>Artikel &amp; Devlogs</h1>
    <p class="muted"><strong>1.</strong> Projekt anlegen &nbsp;→&nbsp;
    <strong>2.</strong> Dokument öffnen &nbsp;→&nbsp; <strong>3.</strong> Text
    generieren/bearbeiten &nbsp;→&nbsp; <strong>4.</strong> Export unter Publishing.</p>
    ${createForm}${projectList}
    <div id="stage"></div>`;
  const stage = main.querySelector('#stage') as HTMLElement;
  const wire = () => {
    (main.querySelector('#na2') as HTMLFormElement).addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = (main.querySelector('#n2') as HTMLInputElement).value.trim();
      if (!name) return;
      await api.createProject({ name, kind: 'article', lang: 'de' });
      renderArticles(main, sidebar, inspector);
    });
    main.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => {
      const p = projects.find((x: { id: string }) => x.id === (b as HTMLElement).dataset.open);
      if (p) openProject(p, stage, () => renderArticles(main, sidebar, inspector));
    }));
  };
  wire();

  sidebar.innerHTML = `<h2>Redaktion</h2>
    <p class="small muted">Artikel entstehen aus Recherche-Dossiers oder frei.
    Jede Bearbeitung erzeugt eine neue Version — nichts geht verloren.</p>
    <h2>Weiter</h2><p class="small muted">Fertiger Text → Bereich
    <strong>Publishing</strong> → Astro md/mdx als Download.</p>`;
  inspector.innerHTML = `<h2>Quality-Gate</h2><p class="small muted">
    Vor dem Export im Editor <em>Text-Audit</em> laufen lassen (human-writing-Linter,
    zählt Befunde statt Scores).</p>`;

  async function openProject(p: { id: string; name: string }, host: HTMLElement, reload: () => void) {
    const full = await api.project(p.id);
    const dossiers = await dossierList();
    host.innerHTML = `<h2>${esc(p.name)}</h2>
      <p class="status">Dokument wählen und neu anlegen — beides öffnet den Editor.</p>
      <div class="row" style="max-width:30rem">
      <div><label for="dp">Aus Recherche-Dossier starten</label>
        <select id="dp"><option value="">— kein Dossier —</option>
        ${dossiers.map((d) => `<option value="${d.id}">${esc(d.title.slice(0, 60))}</option>`).join('')}</select></div>
      <button class="btn" id="import" style="flex:0 0 auto">Importieren</button>
      <button class="btn primary" id="blank" style="flex:0 0 auto">+ Leeres Dokument</button></div>
      <ul class="list" id="docs">${((full.documents ?? []) as Array<{ id: string; title: string; version: number }>)
        .map((d) => `<li><button data-doc="${d.id}">${esc(d.title || '—')}
        <span class="badge">v${d.version}</span></button></li>`).join('')
        || '<li class="muted small">Noch keine Dokumente.</li>'}</ul>`;
    host.querySelectorAll('[data-doc]').forEach((b) => b.addEventListener('click', async () => {
      await editDocument((b as HTMLElement).dataset.doc!, host);
    }));
    (host.querySelector('#blank') as HTMLButtonElement).addEventListener('click', async () => {
      const { id } = await api.documents({ project_id: p.id, title: 'Entwurf', kind: 'article', body: '' });
      await editDocument(id, host);
    });
    (host.querySelector('#import') as HTMLButtonElement).addEventListener('click', async () => {
      const did = (host.querySelector('#dp') as HTMLSelectElement).value;
      if (!did) return;
      const src = await api.document(did);
      const { id } = await api.documents({ project_id: p.id, title: `Entwurf: ${src.title}`,
        kind: 'article', body: src.body });
      await editDocument(id, host);
      void reload;
    });
  }

  async function dossierList(): Promise<Array<{ id: string; title: string }>> {
    const recherche = (await api.projects().catch(() => []))
      .find((p: { name: string }) => p.name === 'Recherche');
    if (!recherche) return [];
    const full = await api.project(recherche.id);
    return ((full.documents ?? []) as Array<{ id: string; title: string; kind: string }>)
      .filter((d) => d.kind === 'dossier');
  }

  async function editDocument(docId: string, host: HTMLElement) {
    const d = await api.document(docId);
    host.innerHTML = `<h2>${esc(d.title || 'Entwurf')} <span class="badge">v${d.version}</span></h2>
      <textarea id="body" rows="14" aria-label="Artikeltext">${esc(d.body)}</textarea>
      <div class="row" style="margin-top:var(--sp-3)">
        <button class="btn primary" id="save">Speichern (neue Version)</button>
        <button class="btn" id="gen">Text generieren (creative-writing)</button>
        <button class="btn" id="lint">Text-Audit</button>
      </div><p class="status" id="st">bereit</p><pre class="diff" id="out" hidden></pre>`;
    const st = host.querySelector('#st')!;
    const out = host.querySelector('#out') as HTMLElement;
    const body = host.querySelector('#body') as HTMLTextAreaElement;
    (host.querySelector('#save') as HTMLButtonElement).addEventListener('click', async () => {
      st.textContent = '…';
      await api.editDocument(d.id, { body: body.value, title: d.title, note: 'editor' });
      st.textContent = 'gespeichert';
    });
    (host.querySelector('#gen') as HTMLButtonElement).addEventListener('click', async () => {
      st.textContent = 'generiert …'; out.hidden = false; out.textContent = '';
      let acc = '';
      await chat({ model: 'creative-writing',
        messages: [{ role: 'user', content: `[de][generate] Schreibe einen Artikel-Entwurf für "${d.title}". GLIEDERUNG + PROSA. Stand: ${body.value.slice(0, 3000)}` }] ,
        onToken: (t) => { acc += t; out.textContent = acc; } });
      body.value = acc; st.textContent = 'übernommen — Speichern nicht vergessen';
    });
    (host.querySelector('#lint') as HTMLButtonElement).addEventListener('click', async () => {
      st.textContent = 'Audit …'; out.hidden = false;
      const r = await fetch('/api/lint', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: body.value.slice(0, 100_000), lang: 'de' }) }).then((x) => x.json());
      out.textContent = (r.findings ?? []).map((f: { severity: string; rule: string; excerpt: string; why: string; fix: string }) =>
        `[${f.severity}] ${f.rule}: ${f.excerpt} — ${f.why} → ${f.fix}`).join('\n') || 'keine Befunde';
      st.textContent = `${(r.findings ?? []).length} Befunde`;
    });
  }
}

// Game Idea Lab — dialogischer Designpartner mit Decision Log.
export async function renderGame(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  const MODES: Record<string, string> = {
    partner: 'Brainstorming, Mechanik-Alternativen, Genremix — nichts festgelegt.',
    critical: 'Spielspaß, Umfang, Originalität, Risiken, Kosten kritisch prüfen.',
    planner: 'Prototyp, Arbeitspakete, Sprint, Engine-Wahl (Godot 4.7.2 / Defold 1.14.1).',
  };
  const projects = (await api.projects().catch(() => []))
    .filter((p: { kind: string }) => p.kind === 'game');
  let pid: string | null = null;
  let mode = 'partner';

  main.innerHTML = `<h1>Game Idea Lab</h1>
    <p class="muted"><strong>1.</strong> Rolle wählen &nbsp;→&nbsp; <strong>2.</strong> Frage
    stellen &nbsp;→&nbsp; <strong>3.</strong> Antwort lesen &nbsp;→&nbsp;
    <strong>4.</strong> Entscheidung unten festhalten &nbsp;→&nbsp; <strong>5.</strong> GDD exportieren.</p>
    <div class="row" role="group" aria-label="Rolle">
      ${Object.entries(MODES).map(([m, hint], i) =>
        `<label style="flex:0 1 auto"><input type="radio" name="gm" value="${m}" ${i === 0 ? 'checked' : ''}/> ${{ partner: 'Partner', critical: 'Kritiker', planner: 'Planer' }[m]}</label>`).join('')}
    </div>
    <form id="ask" class="composer" style="margin-top:var(--sp-4)"><label for="gq">Designfrage</label>
      <textarea id="gq" rows="3" required placeholder="2D-Metroidvania mit Drift-Rennen — 3 Alternativen zur Progression?"></textarea>
      <button class="btn primary" type="submit">Diskutieren</button></form>
    <pre id="answer" class="diff" style="white-space:pre-wrap" hidden></pre>
    <h2>Decision Log</h2><div id="log" class="small">Noch keine Entscheidungen.</div>
    <form id="dec" class="row" style="max-width:44rem">
      <div style="flex:2 1 10rem"><label for="dt">Entscheidung</label>
        <input id="dt" required placeholder="Engine: Godot"/></div>
      <div style="flex:1 1 7rem"><label for="ds">Status</label>
        <select id="ds"><option value="idee">Idee</option><option value="diskussion" selected>Diskussion</option>
        <option value="vorgeschlagen">Vorgeschlagen</option><option value="beschlossen">Beschlossen</option>
        <option value="verworfen">Verworfen</option><option value="spaeter">Später</option></select></div>
      <div style="flex:3 1 12rem"><label for="dr">Warum</label><input id="dr" placeholder="2D stark, klein team"/></div>
      <button class="btn primary" type="submit" style="flex:0 0 auto">Ins Log</button>
    </form>
    <p class="status" id="gdst"></p>
    <button class="btn" id="gdd">GDD (Markdown) herunterladen</button>`;
  const answer = main.querySelector('#answer') as HTMLElement;
  const logEl = main.querySelector('#log')!;
  const gdst = main.querySelector('#gdst')!;
  main.querySelector('[name=gm]')!.closest('div')!
    .addEventListener('change', (e) => { mode = (e.target as HTMLInputElement).value; });

  async function loadLog() {
    if (!pid) return;
    const ds = await fetch(`/api/projects/${pid}/decisions`).then((r) => r.json());
    logEl.innerHTML = (ds as Array<{ key: string; title?: string; status: string; rationale?: string }>)
      .map((d) => `<div><strong>${esc(d.title ?? d.key)}</strong> · ${{
        idee: 'Idee', diskussion: 'Diskussion', vorgeschlagen: 'Vorgeschlagen',
        beschlossen: 'Beschlossen', verworfen: 'Verworfen', spaeter: 'Später',
      }[d.status] ?? esc(d.status)}${d.rationale ? ` <span class="muted">${esc(d.rationale.slice(0, 120))}</span>` : ''}</div>`).join('')
      || 'Noch keine Entscheidungen.';
  }
  async function ensurePid(q: string) {
    if (!pid) pid = (await api.createProject({ name: q.slice(0, 30), kind: 'game', lang: 'de' })).id;
    return pid;
  }
  (main.querySelector('#ask') as HTMLFormElement).addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = (main.querySelector('#gq') as HTMLTextAreaElement).value.trim();
    if (!q) return;
    await ensurePid(q);
    answer.hidden = false; answer.textContent = '';
    const roleHint = mode === 'critical'
      ? 'Du bist Critical Game Designer: nenne Risiken, fehlende Lustfaktoren, Umfangsprobleme.'
      : mode === 'planner'
        ? 'Du bist Production Planner: breche in Prototyp + Pakete herunter (Godot/Defold stabil).'
        : 'Du bist Creative Partner: 3 Alternativen, Trade-offs, keine Festlegung.';
    await chat({ model: 'research', messages: [{ role: 'user', content: `[de] ${roleHint}\n${q}` }],
      onToken: (t) => { answer.textContent += t; } });
    loadLog();
  });
  (main.querySelector('#dec') as HTMLFormElement).addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = (main.querySelector('#gq') as HTMLTextAreaElement).value.trim() || 'game';
    const id = await ensurePid(q);
    await fetch('/api/decisions', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: id,
        key: (main.querySelector('#dt') as HTMLInputElement).value.toLowerCase().replace(/\s+/g, '-'),
        title: (main.querySelector('#dt') as HTMLInputElement).value,
        status: (main.querySelector('#ds') as HTMLSelectElement).value,
        rationale: (main.querySelector('#dr') as HTMLInputElement).value }) });
    (main.querySelector('#dt') as HTMLInputElement).value = '';
    (main.querySelector('#dr') as HTMLInputElement).value = '';
    loadLog();
  });
  (main.querySelector('#gdd') as HTMLButtonElement).addEventListener('click', async () => {
    const q = (main.querySelector('#gq') as HTMLTextAreaElement).value.trim() || 'game';
    const id = await ensurePid(q);
    gdst.textContent = 'GDD wird geschrieben …';
    const g = await fetch('/api/gdd', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: id }) }).then((r) => r.json());
    const blob = new Blob([g.gdd], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'gdd.md'; a.click();
    URL.revokeObjectURL(a.href);
    gdst.textContent = 'gdd.md heruntergeladen';
  });
  if (projects.length) { pid = projects[0].id; loadLog(); }

  sidebar.innerHTML = `<h2>Regeln</h2><p class="small muted">Idee → Diskussion →
    Vorschlag → Beschluss; alles bleibt änderbar. Engine-Beratung nutzt die
    Godot-4.7.2-/Defold-1.14.1-Skills.</p>
    <h2>Projekte</h2><p class="small muted">${projects.length
      ? (projects as Array<{ name: string }>).map((p) => esc(p.name)).join('<br>')
      : 'Das erste Brainstorm legt das Projekt automatisch an.'}</p>`;
  inspector.innerHTML = `<h2>Rollen</h2><ul class="list">${Object.entries(MODES).map(([m, h]) =>
    `<li><button><strong>${{ partner: 'Partner', critical: 'Kritiker', planner: 'Planer' }[m]}</strong>
    <div class="muted small">${esc(h)}</div></button></li>`).join('')}</ul>`;
}
