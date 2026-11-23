import { api, diffLines, esc, type Document, type Project } from './core';

export async function renderLibrary(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  async function showDoc(d: Document) {
    main.innerHTML = `<h1>${esc(d.title || 'Ohne Titel')}</h1>
      <div class="field"><label for="dtitle">Titel</label>
        <input id="dtitle" value="${esc(d.title)}" /></div>
      <div class="editor-body"><label for="dbody">Text</label>
        <textarea id="dbody">${esc(d.body)}</textarea></div>
      <p><button class="btn primary" id="save">Speichern
        <span class="status" id="state"></span></button>
      <span class="status">Version ${d.version} — Speichern erzeugt eine neue Version;
      die vorherige bleibt unter Versionen erhalten.</span></p>
      <pre class="diff" id="diff" hidden></pre>`;
    const save = main.querySelector('#save') as HTMLButtonElement;
    const state = main.querySelector('#state')!;
    const diffEl = main.querySelector('#diff') as HTMLElement;
    save.addEventListener('click', async () => {
      const body = (main.querySelector('#dbody') as HTMLTextAreaElement).value;
      const title = (main.querySelector('#dtitle') as HTMLInputElement).value;
      save.disabled = true; state.textContent = '…';
      try {
        const res = await api.editDocument(d.id, { body, title, note: 'editor' });
        d = { ...d, ...res, title, body };
        state.textContent = `gespeichert (v${res.version})`;
        diffEl.hidden = false;
        diffEl.textContent = diffLines(d.body, body);
      } catch (err) { state.textContent = `Fehler ${String(err).slice(0, 120)}`; } finally {
        save.disabled = false;
        setTimeout(() => { state.textContent = ''; }, 3000);
      }
    });
    inspector.innerHTML = `<h2>${esc(d.title || 'Dokument')}</h2>
      <p class="muted small">Version ${d.version} · ${d.kind}</p>
      <button class="btn" id="hist">Versionen</button>
      <div id="histlist" class="small muted"></div>`;
    inspector.querySelector('#hist')!.addEventListener('click', async () => {
      const vs = await api.versions(d.id);
      inspector.querySelector('#histlist')!.innerHTML =
        vs.map((v) => `<div>v${v.version} · ${new Date(v.created * 1000).toLocaleString()}
          <em>${esc(v.note || '')}</em></div>`).join('') || '—';
    });
  }

  async function pickProject(p: Project) {
    const full = await api.project(p.id);
    sidebar.innerHTML = `<button class="btn" id="back">← Bibliothek</button>
      <h2>${esc(p.name)}</h2>
      <button class="btn" id="nd">Neues Dokument</button>
      <ul class="list">${(full.documents || []).map((d: Document) =>
        `<li><button data-doc="${d.id}">${esc(d.title || '—')} <span class="badge">v${d.version}</span></button></li>`).join('')}</ul>`;
    sidebar.querySelector('#back')!.addEventListener('click', mount);
    sidebar.querySelector('#nd')!.addEventListener('click', async () => {
      const { id } = await api.documents({ project_id: p.id, title: 'Kapitel', kind: 'chapter', body: '' });
      showDoc(await api.document(id));
    });
    sidebar.querySelectorAll('[data-doc]').forEach((b) => b.addEventListener('click', async () => {
      showDoc(await api.document((b as HTMLElement).dataset.doc!));
    }));
    main.innerHTML = `<h1>${esc(p.name)}</h1><p class="muted">${esc(p.kind)} ·
      Dokument links wählen oder oben anlegen.</p>`;
  }

  async function mount() {
    inspector.innerHTML = '';
    const projects: Project[] = await api.projects().catch(() => []);
    sidebar.innerHTML = `<h2>Bibliothek</h2>
      <form id="np"><label for="pname">Neues Projekt</label>
        <div class="row"><input id="pname" required placeholder="Name"/>
        <select id="pkind" aria-label="Art"><option value="story">story</option>
        <option value="novel">novel</option><option value="article">article</option>
        <option value="devlog">devlog</option><option value="research">research</option>
        <option value="game">game</option><option value="custom">custom</option></select>
        <button class="btn primary" type="submit">+</button></div></form>
      <ul class="list" id="projects"></ul>
      <h2>Volltextsuche</h2>
      <form id="sf"><label for="sq">Suche</label><input id="sq" placeholder="Begriff…"/></form>
      <div id="hits" class="small"></div>`;
    (sidebar.querySelector('#np') as HTMLFormElement).addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = (sidebar.querySelector('#pname') as HTMLInputElement).value.trim();
      const kind = (sidebar.querySelector('#pkind') as HTMLSelectElement).value;
      if (name) { await api.createProject({ name, kind }); mount(); }
    });
    const list = sidebar.querySelector('#projects')!;
    list.innerHTML = projects.map((p) =>
      `<li><button data-pid="${p.id}">${esc(p.name)} <span class="muted small">${esc(p.kind)}</span></button></li>`).join('')
      || '<li class="muted small">Noch keine Projekte.</li>';
    list.querySelectorAll('[data-pid]').forEach((b) => b.addEventListener('click', () => {
      const p = projects.find((x) => x.id === (b as HTMLElement).dataset.pid)!;
      pickProject(p);
    }));
    (sidebar.querySelector('#sf') as HTMLFormElement).addEventListener('submit', async (e) => {
      e.preventDefault();
      const q = (sidebar.querySelector('#sq') as HTMLInputElement).value.trim();
      const hits = q ? await api.search(q).catch(() => []) : [];
      sidebar.querySelector('#hits')!.innerHTML = hits.map((h) =>
        `<div>${h.hit ?? ''} <span class="badge">${esc(h.kind)}</span></div>`).join('') || 'keine Treffer';
    });
    main.innerHTML = `<h1>Projektbibliothek</h1>
      <p class="muted">Links Projekte wählen oder anlegen. Alle Daten bleiben lokal
      unter <code>~/.local/share/creative-studio</code>.</p>`;
  }
  await mount();
}
