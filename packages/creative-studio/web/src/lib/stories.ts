import { api, chat, esc, type Document, type Project } from './core';

export async function renderStories(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  let project: Project | null = null;

  async function streamInto(target: HTMLElement, model: 'creative-writing', content: string) {
    target.textContent = '';
    let acc = '';
    const write = (tk: string) => { acc += tk; target.textContent = acc; };
    try {
      acc = await chat({ model, messages: [{ role: 'user', content }], onToken: write });
      target.textContent = acc || '(leer)';
    } catch (err) { target.innerHTML = `<span class="badge err">${esc(String(err).slice(0, 160))}</span>`; }
    return acc;
  }

  async function openDoc(d: Document) {
    main.innerHTML = `<h1>${esc(d.title)}</h1>
      <p class="status">Version ${d.version} · Kapitel von ${esc(project?.name ?? '')}</p>
      <textarea id="body" aria-label="Kapiteltext">${esc(d.body)}</textarea>
      <div class="row" style="margin-top:var(--sp-3)">
        <button class="btn primary" id="save">Speichern (neue Version)</button>
        <button class="btn" id="next">Kapitel generieren (Human Writing Template)</button>
        <button class="btn" id="audit">Bibel-Prüfung</button>
        <button class="btn" id="lint">Text-Audit (Skill-Linter)</button>
      </div>
      <p class="status" id="state" role="status"></p>
      <h3>Ergebnis</h3><pre class="diff" id="out" hidden></pre>`;
    const state = main.querySelector('#state')!;
    const out = main.querySelector('#out') as HTMLElement;
    const bodyEl = main.querySelector('#body') as HTMLTextAreaElement;
    (main.querySelector('#save') as HTMLButtonElement).addEventListener('click', async () => {
      state.textContent = '…';
      const res = await api.editDocument(d.id, { body: bodyEl.value, title: d.title, note: 'editor' });
      state.textContent = `gespeichert als v${res.version} (alt: v${d.version} unter Versionen)`;
    });
    (main.querySelector('#next') as HTMLButtonElement).addEventListener('click', async () => {
      state.textContent = 'Schreibe Kapitel …';
      out.hidden = false;
      const t = await streamInto(out, 'creative-writing',
        `[de][generate] Schreibe das nächste Kapitel von ${project?.name}. Bisheriges Ende: ${bodyEl.value.slice(-400)}`);
      state.textContent = `Kapiteltext ${t.length} Zeichen — Speichern übernimmt ihn`;
      bodyEl.value += `\n\n${t}`;
    });
    (main.querySelector('#audit') as HTMLButtonElement).addEventListener('click', async () => {
      state.textContent = 'Bibel-Prüfung läuft …';
      out.hidden = false;
      await streamInto(out, 'creative-writing',
        `[de][audit] Vergleiche den Text mit der Story-Bibel; nenne nur Abweichungen. Story-Bibel: ${await bibleText()}\n\nText: ${bodyEl.value.slice(0, 12000)}`);
      state.textContent = 'fertig';
    });
    (main.querySelector('#lint') as HTMLButtonElement).addEventListener('click', async () => {
      state.textContent = 'Skill-Linter läuft …'; out.hidden = false;
      const r = await call('/api/lint', { text: bodyEl.value.slice(0, 100_000), lang: 'de' });
      out.textContent = `human-writing v${r.skill_version} · scores ` +
        JSON.stringify(r.scores) + '\n' +
        (r.findings ?? []).map((f: { rule: string; severity: string; excerpt: string; why: string; fix: string }) =>
          `[${f.severity}] ${f.rule}: ${f.excerpt} — ${f.why} → ${f.fix}`).join('\n') || 'keine Befunde';
      state.textContent = `${(r.findings ?? []).length} Befunde (zählen Findings, keine Autorenschaft)`;
    });
    inspector.innerHTML = `<h2>Versionen</h2><div id="hist" class="small muted">–</div>`;
    const vs = await api.versions(d.id);
    inspector.querySelector('#hist')!.innerHTML =
      vs.map((v) => `<div>v${v.version} · ${new Date(v.created * 1000).toLocaleString()} ${esc(v.note)}</div>`).join('');
  }

  async function bibleText(): Promise<string> {
    if (!project) return '';
    const mem = await fetch(`/api/projects/${project.id}/memories`).then((r) => r.json());
    return (mem as Array<{ kind: string; key: string; body: string }>)
      .map((m) => `${m.kind}:${m.key}: ${m.body}`).join(' | ').slice(0, 4000);
  }

  async function openProject(p: Project) {
    project = p;
    const full = await api.project(p.id);
    sidebar.innerHTML = `<button class="btn" id="back">← Bereich</button>
      <h2>${esc(p.name)}</h2><button class="btn" id="nc">+ Kapitel</button>
      <ul class="list" id="ch">${(full.documents ?? []).map((d) =>
        `<li><button data-id="${d.id}">${esc(d.title)} <span class="badge">v${d.version}</span></button></li>`).join('')}</ul>
      <h2>Story-Bibel</h2><div id="bible" class="small muted">…</div>
      <form id="mem"><label for="mk">Merksatz (Art:Schlüssel)</label>
        <input id="mk" placeholder="character:Nerida" required/><label for="mv">Wert</label>
        <textarea id="mv" rows="2" required placeholder="17, blauer Wollpullover…"></textarea>
        <button class="btn primary" type="submit">Merken</button></form>`;
    sidebar.querySelector('#back')!.addEventListener('click', () => mount());
    (sidebar.querySelector('#mem') as HTMLFormElement).addEventListener('submit', async (e) => {
      e.preventDefault();
      const k = (sidebar.querySelector('#mk') as HTMLInputElement).value;
      const v = (sidebar.querySelector('#mv') as HTMLTextAreaElement).value;
      const [kind, key] = k.includes(':') ? k.split(':') : ['bible', k];
      await fetch('/api/memories', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: p.id, kind, key, body: v }) });
      openProject(p);
    });
    sidebar.querySelector('#nc')!.addEventListener('click', async () => {
      const count = (full.documents ?? []).length + 1;
      const { id } = await api.documents({ project_id: p.id, title: `Kapitel ${count}`,
        kind: 'chapter', body: '' });
      openDoc(await api.document(id));
    });
    sidebar.querySelectorAll('[data-id]').forEach((b) => b.addEventListener('click', async () => {
      openDoc(await api.document((b as HTMLElement).dataset.id!));
    }));
    sidebar.querySelector('#bible')!.textContent = await bibleText() || 'leer — unten Merksätze anlegen';
    main.innerHTML = `<h1>${esc(p.name)}</h1><p class="muted">Kapitel links öffnen.</p>`;
  }

  async function mount() {
    inspector.innerHTML = '';
    const projects = (await api.projects().catch(() => [])).filter((p: Project) =>
      ['story', 'novel', 'custom'].includes(p.kind));
    sidebar.innerHTML = `<h2>Story Projects</h2>
      <form id="ns"><label for="n">Projektname</label><input id="n" required placeholder="z. B. Tochter des Meeres"/>
      <button class="btn primary" type="submit">Anlegen</button></form>
      <ul class="list" id="l">${projects.map((p: Project) =>
        `<li><button data-id="${p.id}">${esc(p.name)}</button></li>`).join('') || '<li class="muted small">keine</li>'}</ul>`;
    (sidebar.querySelector('#ns') as HTMLFormElement).addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = (sidebar.querySelector('#n') as HTMLInputElement).value.trim();
      if (name) { await api.createProject({ name, kind: 'story', lang: 'de' }); mount(); }
    });
    sidebar.querySelectorAll('[data-id]').forEach((b) => b.addEventListener('click', () => {
      openProject(projects.find((x: Project) => x.id === (b as HTMLElement).dataset.id)!);
    }));
    main.innerHTML = `<h1>Stories &amp; Romane</h1>
      <p class="muted">Projekte links. Kapitel entstehen über das Human-Writing-Template
      (<code>creative-writing</code>), Bibel-Prüfung und Skill-Lint melden Abweichungen,
      jede Bearbeitung behält die Vorversion.</p>`;
  }
  await mount();
}

async function call(path: string, body: unknown) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body) });
  return r.json();
}
