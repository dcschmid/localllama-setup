import { api, esc } from './core';

// Publishing & Export — Astro md/mdx payloads leave as downloads; nothing is
// written into any repository automatically.
export async function renderPublish(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  main.innerHTML = `<h1>Publishing &amp; Export</h1>
    <p class="muted">Dokument wählen → Astro-Format → Dateien als Download.
    Kein automatisches Schreiben, keine Git-Commits — Zielpfad entscheidet der Nutzer.</p>
    <form id="ex" class="row">
      <div style="flex:3 1 16rem"><label for="doc">Dokument</label><select id="doc"></select></div>
      <div style="flex:0 1 8rem"><label for="fmt">Format</label>
        <select id="fmt"><option value="md">Markdown</option><option value="mdx">MDX</option></select></div>
      <div style="flex:0 1 10rem"><label for="coll">Content Collection (optional)</label>
        <input id="coll" placeholder="devlog"/></div>
      <button class="btn primary" type="submit" style="flex:0 0 auto">Exportieren</button>
    </form>
    <p class="status" id="state" role="status"></p>
    <pre id="preview" class="diff" style="white-space:pre-wrap"></pre>`;
  const state = main.querySelector('#state')!;
  const preview = main.querySelector('#preview')!;
  const sel = main.querySelector('#doc') as HTMLSelectElement;
  const projects = await api.projects().catch(() => []);
  const opts: string[] = [];
  for (const p of projects) {
    const full = await api.project(p.id).catch(() => ({ documents: [] }));
    for (const d of (full.documents ?? []).filter((x: { body: string }) => (x.body || '').length > 40)) {
      opts.push(`<option value="${d.id}">${esc(`${p.name} / ${d.title || 'Dokument'}`)}</option>`);
    }
  }
  sel.innerHTML = opts.join('') || '<option value="">— keine Dokumente —</option>';
  (main.querySelector('#ex') as HTMLFormElement).addEventListener('submit', async (e) => {
    e.preventDefault();
    const docId = sel.value;
    if (!docId) { state.textContent = 'kein Dokument gewählt'; return; }
    state.textContent = 'exportiere …';
    const d = await fetch('/api/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id: docId,
        format: (main.querySelector('#fmt') as HTMLSelectElement).value,
        collection: (main.querySelector('#coll') as HTMLInputElement).value.trim() || undefined }),
    }).then((r) => r.json());
    if (d.error) { state.textContent = `Fehler: ${d.detail ?? d.error}`; return; }
    preview.textContent = d.files[0].content.slice(0, 2000);
    state.textContent = `${d.files.length} Datei(en): ${d.files.map((f: { path: string }) => f.path).join(', ')}`;
    for (const f of d.files) {
      const body = f.base64 ? atob(f.base64) : f.content;
      const blob = new Blob([body as BlobPart], { type: f.content_type ?? 'text/markdown' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = f.path.split('/').pop()!;
      a.click(); URL.revokeObjectURL(a.href);
    }
  });
  sidebar.innerHTML = `<h2>Zielsystem</h2><p class="small muted">Astro Content Collections
    (Schema frei wählbar, kein festes Projekt). Bilder relativ, Alt-Texte aus Metadaten.</p>`;
  inspector.innerHTML = `<h2>Prüfung</h2><p class="small muted">Frontmatter-Felder:
    title/description/date/lang/tags/hero/seo_*. Bildpfade relativ; PNGs als Binärdateien.
    MDX: reines Markdown ohne JSX-Extras — kompatibel mit Standard-Astro-Setup.</p>`;
}

export async function renderSettings(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  const st = await fetch('/api/status').then((r) => r.json()).catch(() => null);
  main.innerHTML = `<h1>Einstellungen</h1>
    <p class="muted">Alles lokal; Sprache und Theme im Browser gespeichert.</p>
    <div class="row" style="max-width:32rem">
      <div><label for="lang">Sprache</label><select id="lang">
        <option value="de">Deutsch</option><option value="en">English</option></select></div>
    </div>
    <h2>Dienste</h2>
    <table><thead><tr><th>Dienst</th><th>Status</th></tr></thead><tbody>
      ${(st?.upstream ?? []).map((u: { service: string; ok: boolean; error?: string }) =>
        `<tr><td>${esc(u.service)}</td><td><span class="badge ${u.ok ? 'ok' : 'err'}">
          ${u.ok ? 'bereit' : esc((u.error ?? 'fehlt').slice(0, 60))}</span></td></tr>`).join('')}
    </tbody></table>
    <p class="muted small">Daten: ${esc(st?.data_dir ?? '~/.local/share/creative-studio')} ·
    Schreibprofile: ${(st?.aliases ?? []).join(', ')}</p>`;
  const lang = main.querySelector('#lang') as HTMLSelectElement;
  lang.value = localStorage.getItem('cs-lang') === 'en' ? 'en' : 'de';
  lang.addEventListener('change', () => {
    localStorage.setItem('cs-lang', lang.value);
    document.documentElement.lang = lang.value;
  });
  sidebar.innerHTML = `<h2>Profil</h2><p class="small muted">Sprachprofile bleiben die
    llama.cpp-Aliase; Coding-Profile (Cyber-Tiel) sind reserviert und hier wählbar
    nur lesend gelistet.</p>`;
  inspector.innerHTML = `<h2>Coordinator</h2><p class="small muted">Eine GPU-Schlange:
    Bildjobs warten auf echte Slots (nvidia-smi), LLM-Jobs serialisieren über den
    Router; Coding-Sessions werden nie unterbrochen.</p>`;
}
