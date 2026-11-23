import { api, esc, pollJob } from './core';

export async function renderImages(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  main.innerHTML = `<h1>Image Studio</h1>
    <p class="muted">Erzeugt über den lokalen local-image-ai-service (:7861), Proxy über
    8700. Modellwechsel nur explizit — der Service ist ein geteilter GPU-Slot.</p>
    <form id="gen" class="row">
      <div style="flex:3 1 16rem"><label for="prompt">Motiv (Text-to-Image)</label>
        <input id="prompt" required placeholder="atmospheric lighthouse in fog, dark comic style"/></div>
      <div style="flex:0 1 10rem"><label for="preset">Preset-Stil (optional)</label>
        <select id="preset"><option value="">— ohne —</option></select></div>
      <div style="flex:0 1 8rem"><label for="size">Format</label>
        <select id="size"><option>1024x1024</option><option>1024x576</option>
        <option>576x1024</option><option>512x512</option></select></div>
      <button class="btn primary" type="submit" style="flex:0 0 auto">Erzeugen</button>
    </form>
    <p class="status" id="state" role="status"></p>
    <figure id="result" hidden><img class="art" alt="" id="result-img"/>
      <figcaption class="muted small" id="result-cap"></figcaption></figure>
    <h2>Galerie</h2><div id="gallery" class="small muted">…</div>`;
  const state = main.querySelector('#state')!;
  const result = main.querySelector('#result') as HTMLElement;
  const img = main.querySelector('#result-img') as HTMLImageElement;
  const cap = main.querySelector('#result-cap')!;
  const gallery = main.querySelector('#gallery')!;

  async function loadGallery() {
    const g = await api.gallery().catch(() => ({ images: [] }));
    const items = (g.images ?? []).slice(0, 18);
    gallery.innerHTML = items.length ? `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(9rem,1fr));gap:var(--sp-3)">` +
      items.map((im: { id: string; request?: { prompt?: string }; license?: string }) =>
        `<figure style="margin:0"><img class="art" loading="lazy" alt="${esc((im.request?.prompt ?? 'Bild').slice(0, 90))}"
          src="/api/images/files/${im.id}" data-id="${im.id}" style="cursor:pointer"/>
        <figcaption class="muted small">${esc(im.license ?? '')}</figcaption></figure>`).join('') + '</div>'
      : 'leer';
    gallery.querySelectorAll('img[data-id]').forEach((el) => el.addEventListener('click', async () => {
      const id = (el as HTMLElement).dataset.id!;
      const meta = await fetch(`/api/images/gallery/${id}`).then((r) => r.json()).catch(() => ({}));
      show(id, meta?.request?.prompt ?? id);
      (el as HTMLImageElement).scrollIntoView({ block: 'center' });
    }));
  }
  function show(id: string, prompt: string) {
    result.hidden = false;
    img.src = `/api/images/files/${id}`;
    img.alt = prompt.slice(0, 160);
    cap.textContent = `image ${id.slice(0, 12)} · ${prompt.slice(0, 120)}`;
  }

  (main.querySelector('#gen') as HTMLFormElement).addEventListener('submit', async (e) => {
    e.preventDefault();
    const prompt = (main.querySelector('#prompt') as HTMLInputElement).value.trim();
    const size = (main.querySelector('#size') as HTMLSelectElement).value;
    const preset = (main.querySelector('#preset') as HTMLSelectElement).value;
    if (!prompt) return;
    state.textContent = 'Job wird eingereiht (Coordinator wartet auf GPU-Slot) …';
    const { job } = await api.generate({ prompt, size, ...(preset ? { preset } : {}),
      wait_gpu_seconds: 300 });
    if (!job?.id) { state.textContent = `Fehler: ${JSON.stringify(job).slice(0, 160)}`; return; }
    try {
      const done = await pollJob(job.id, (s) => { state.textContent = `Job ${s} …`; });
      const imageId = String(done.image_id ?? '');
      if (!imageId) { state.textContent = `Job ${done.status} ohne Bild (${String(done.error).slice(0, 80)})`; return; }
      show(imageId, prompt);
      const req = done.request as Record<string, unknown> | undefined;
      state.textContent = `fertig in ${Math.round(Number(done.seconds ?? 0))}s — seed ` +
        `${req?.seed ?? '?'} (Regen speichert Parameter)`;
      loadGallery();
    } catch (err) { state.textContent = `Fehler: ${String(err).slice(0, 140)}`; }
  });

  sidebar.innerHTML = `<h2>Studio-Jobs</h2><div id="jobs" class="small muted">lädt …</div>
    <button class="btn" id="rj">Neu laden</button>`;
  async function jobs() {
    const rows = await api.imageJobs().catch(() => []);
    sidebar.querySelector('#jobs')!.innerHTML = (rows as Array<{ id: string; state: string; payload?: { request?: { prompt?: string } } }>)
      .slice(0, 25).map((j) => `<div>${j.state} · ${esc((j.payload?.request?.prompt ?? j.id).slice(0, 60))}</div>`).join('')
      || 'keine Jobs';
  }
  sidebar.querySelector('#rj')!.addEventListener('click', jobs);
  jobs();
  loadGallery();
  const cat = await api.catalog().catch(() => null);
  inspector.innerHTML = `<h2>Katalog</h2>
    <p class="small muted">Modelle: ${(cat?.models ?? []).map((m: { id: string }) => m.id).join(', ') || '?'}</p>
    <p class="small muted">Recipes: ${(cat?.recipes ?? []).map((r: { id: string }) => r.id).join(', ') || '?'}</p>
    <p class="small muted">Lizenzen je Modell im Katalog (z. B. moss Apache-2.0);
    kommerzielle Nutzung: Lizenz des erzeugten Modells beachten.</p>`;
  const sel = main.querySelector('#preset') as HTMLSelectElement;
  for (const p of (cat?.presets ?? []) as Array<{ id: string; name?: string }>) {
    const o = document.createElement('option');
    o.value = p.id; o.textContent = p.name ?? p.id; sel.append(o);
  }
}
