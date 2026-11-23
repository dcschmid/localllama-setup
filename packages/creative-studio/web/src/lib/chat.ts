import { api, chat, esc, type Alias, type Session } from './core';

const ALIASES: Array<{ id: Alias; label: string; hint: string }> = [
  { id: 'research', label: 'Research · Gemma 26B', hint: 'Recherche, Fakten, Chat' },
  { id: 'creative-writing', label: 'Creative Writing · Gemma 12B', hint: 'Story, Dialog, Devlog' },
];

export async function renderChat(main: HTMLElement, sidebar: HTMLElement, inspector: HTMLElement) {
  let sessionId: string | null = null;
  let model: Alias = 'research';
  let controller: AbortController | null = null;
  const history: Array<{ role: string; content: string }> = [];

  main.innerHTML = `
    <div class="chat">
      <div class="row" role="group" aria-label="Schreibprofil">
        ${ALIASES.map((a, i) => `
          <label style="flex:0 1 auto"><input type="radio" name="alias" value="${a.id}" ${i === 0 ? 'checked' : ''}/> ${a.label}</label>`).join('')}
      </div>
      <div class="chat-log" id="log" aria-live="polite"></div>
      <form class="composer" id="composer">
        <label for="prompt" class="muted small">Auftrag — Streaming über llama.cpp-Router</label>
        <textarea id="prompt" required rows="3" placeholder="Schreibe … (Strg+Enter sendet)"></textarea>
        <button class="btn primary" type="submit">${'Senden'}</button>
        <button class="btn" type="button" id="stop" disabled>Stopp</button>
      </form>
    </div>`;
  const log = main.querySelector('#log')!;
  const form = main.querySelector('#composer') as HTMLFormElement;
  const prompt = main.querySelector('#prompt') as HTMLTextAreaElement;
  const stopBtn = main.querySelector('#stop') as HTMLButtonElement;
  const submitBtn = form.querySelector('button[type=submit]') as HTMLButtonElement;

  const bubbles = (m: Array<{ role: string; content: string }>) =>
    m.map((x) => `<article class="msg"><div class="role">${x.role === 'user' ? 'Du' : 'Studio'}</div>
      <div class="prose">${esc(x.content)}</div></article>`).join('');

  async function mountSidebar() {
    sidebar.innerHTML = `<h2>Chats</h2><button class="btn" id="new-chat">Neuer Chat</button>
      <ul class="list" id="sessions"></ul>`;
    const list = sidebar.querySelector('#sessions')!;
    const sessions: Session[] = await api.sessions().catch(() => []);
    list.innerHTML = sessions.slice(0, 30).map((s) =>
      `<li><button data-sid="${s.id}">${esc(s.title || 'Unbenannt')}</button></li>`).join('')
      || '<li class="muted small">Keine Chats.</li>';
    list.querySelectorAll('button[data-sid]').forEach((b) =>
      b.addEventListener('click', async () => {
        sessionId = (b as HTMLElement).dataset.sid!;
        history.length = 0;
        history.push(...await api.messages(sessionId).catch(() => []));
        log.innerHTML = bubbles(history);
      }));
    sidebar.querySelector('#new-chat')!.addEventListener('click', () => {
      sessionId = null; history.length = 0; log.innerHTML = ''; prompt.focus();
    });
  }
  await mountSidebar();

  main.querySelector('input[name=alias]')!.closest('div')!
    .addEventListener('change', (e) => { model = (e.target as HTMLInputElement).value as Alias; });

  prompt.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') form.requestSubmit();
  });

  stopBtn.addEventListener('click', () => controller?.abort());

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = prompt.value.trim();
    if (!text) return;
    submitBtn.disabled = true;
    history.push({ role: 'user', content: text });
    prompt.value = '';
    if (!sessionId) sessionId = (await api.createSession({ title: text.slice(0, 40) })).id;
    log.innerHTML = bubbles(history) + '<article class="msg"><div class="role">Studio</div><div class="prose" id="stream"></div></article>';
    const target = main.querySelector('#stream')!;
    controller = new AbortController();
    stopBtn.disabled = false;
    let acc = '';
    try {
      acc = await chat({
        model, messages: history.map((m) => ({ role: m.role, content: m.content })),
        sessionId: sessionId ?? undefined,
        signal: controller.signal,
        onToken: (tk) => { acc += tk; target.textContent = acc; },
      });
    } catch (err) {
      if (!acc) target.innerHTML = `<span class="badge err">Fehler: ${esc(String(err).slice(0, 160))}</span>`;
    } finally {
      stopBtn.disabled = true; submitBtn.disabled = false;
      if (acc) history.push({ role: 'assistant', content: acc });
      await mountSidebar();
    }
  });

  // Inspector: alias explanation (right pane)
  inspector.innerHTML = `<h2>Profile</h2>
    <ul class="list">${ALIASES.map((a) =>
      `<li><button><strong>${a.label}</strong><div class="muted small">${a.hint}</div></button></li>`).join('')}</ul>
    <p class="muted small">Schreibprofile sind die vorhandenen llama.cpp-Aliase;
      Human-Writing-Skill liegt als Template an (<code>creative-writing</code>).
      Coding-Profile bleiben reserviert.</p>`;
}
