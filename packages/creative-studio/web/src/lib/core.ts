// Local Creative Studio core. Talks only to the local backend on the same
// origin (127.0.0.1). No cloud endpoints exist anywhere in this app.

export type Project = { id: string; name: string; kind: string; lang: string;
  description: string; tags: string[]; meta: Record<string, unknown>; updated?: number;
  latest_document?: string; document_count?: number; folder_id?: string | null; archived_at?: number };
export type Document = { id: string; project_id: string; title: string; kind: string;
  body: string; lang: string | null; status: string; version: number; updated: number;
  version_origin?: string; version_note?: string; folder_id?: string | null; story_number?: number | null };
export type DocVersion = { id: string; version: number; note: string; origin: string; created: number; title?: string | null };
export type Session = { id: string; project_id: string | null; title: string; model: string | null;
  folder_id?: string | null; archived_at?: number; updated?: number; contexts?: Array<{id: string; name: string; kind: string}> };
export type Msg = { id: string; role: 'user' | 'assistant'; content: string; meta?: Record<string, unknown> };
export type Alias = 'research' | 'deep-research' | 'creative-writing' | 'human-writing'
  | 'human-rewrite' | 'human-audit';

export const SECTIONS = ['chat', 'stories', 'articles', 'research', 'images',
  'game', 'library', 'publish', 'settings'] as const;
export type Section = typeof SECTIONS[number];
const SECTION_LABEL: Record<Section, string> = {
  chat: 'Chat', stories: 'Stories & Novels', articles: 'Articles & Devlogs',
  research: 'Deep Research', images: 'Image Studio', game: 'Game Idea Lab',
  library: 'Project Library', publish: 'Publishing', settings: 'Settings',
};
export const sectionLabel = (s: Section) => SECTION_LABEL[s];

// ---------- aliases per task (existing router profiles, never coding-*) -----
export const ALIAS_FOR: Record<string, Alias> = {
  chat: 'research', ideas: 'research', discuss: 'research',
  story: 'creative-writing', article: 'creative-writing', devlog: 'creative-writing',
  game: 'research',
};

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string) { super(code); }
}

export async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.error ?? 'request_failed');
  }
  return res.status === 204 ? ({} as T) : res.json();
}

export const post = <T>(path: string, body: object = {}) =>
  json<T>(path, { method: 'POST', body: JSON.stringify(body) });

export const api = {
  status: () => fetch('/api/status').then((r) => r.json()),
  projects: (): Promise<Project[]> => json('/api/projects'),
  createProject: (body: Record<string, unknown>) =>
    json<{ id: string }>('/api/projects', { method: 'POST', body: JSON.stringify(body) }),
  project: (id: string) => json<Project & { documents: Document[] }>(`/api/projects/${id}`),
  documents: (body: Record<string, unknown>) =>
    json<{ id: string }>('/api/documents', { method: 'POST', body: JSON.stringify(body) }),
  document: (id: string) => json<Document>(`/api/documents/${id}`),
  editDocument: (id: string, body: Record<string, unknown>) =>
    json<{ id: string; version: number; status?: string }>(`/api/documents/${id}`,
      { method: 'POST', body: JSON.stringify(body) }),
  versions: (id: string) => json<DocVersion[]>(`/api/documents/${id}/versions`),
  sessions: (): Promise<Session[]> => json('/api/sessions'),
  session: (id: string) => json<Session>(`/api/sessions/${id}`),
  createSession: (body: Record<string, unknown>) =>
    json<{ id: string }>('/api/sessions', { method: 'POST', body: JSON.stringify(body) }),
  messages: (sid: string): Promise<Msg[]> => json(`/api/sessions/${sid}/messages`),
  search: (q: string) =>
    json<Array<{ document_id: string; title: string; kind: string; hit: string }>>(
      `/api/search?q=${encodeURIComponent(q)}`),
  imageJobs: () => json<unknown[]>('/api/images/jobs'),
  imageJob: (id: string) => json<Record<string, unknown>>(`/api/images/jobs/${id}`),
  gallery: () => fetch('/api/images/gallery').then((r) => r.json()),
  generate: (body: Record<string, unknown>) =>
    json<{ job?: { id: string; status: string } }>('/api/images/generate',
      { method: 'POST', body: JSON.stringify(body) }),
  catalog: () => fetch('/api/catalog').then((r) => r.json()),
  research: (body: Record<string, unknown>) =>
    json<{ id: string; status: string }>('/api/research', { method: 'POST', body: JSON.stringify(body) }),
};

// ---------- SSE chat with stop/resume ---------------------------------------
export async function chat(opts: {
  model: Alias; messages: Array<{ role: string; content: string }>;
  sessionId?: string; userContent?: string; kwargs?: Record<string, unknown>;
  onToken: (t: string) => void; signal?: AbortSignal;
}): Promise<string> {
  return stream('/api/chat', { model: opts.model, messages: opts.messages,
    session_id: opts.sessionId, user_content: opts.userContent, chat_template_kwargs: opts.kwargs },
    opts.onToken, opts.signal);
}

export async function stream(path: string, body: object, onToken: (text: string) => void,
  signal?: AbortSignal): Promise<string> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  });
  if (!res.ok || !res.body) {
    const error = await res.json().catch(() => null);
    throw new ApiError(res.status, error?.error ?? 'stream_unavailable');
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '', full = '', complete = false;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl: number;
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1);
      if (line === 'data: [DONE]') { complete = true; continue; }
      if (!line.startsWith('data: ')) continue;
      const frame = JSON.parse(line.slice(6));
      if (frame.error) throw new ApiError(502, 'stream_unavailable');
      for (const ch of frame.choices ?? []) {
        const t = ch?.delta?.content;
        if (typeof t === 'string' && t) { full += t; onToken(t); }
        if (ch.finish_reason) complete = true;
      }
    }
  }
  if (!complete || !full.trim()) throw new ApiError(502, 'stream_incomplete');
  return full;
}

// ---------- image job polling (client timeout never loses the job) ----------
export async function pollJob(id: string, onProgress: (s: string) => void,
  deadlineMs = 420_000): Promise<Record<string, unknown>> {
  const stop = Date.now() + deadlineMs;
  for (;;) {
    const job = await api.imageJob(id);
    onProgress(String(job.status ?? job.state ?? 'queued'));
    if (['completed', 'failed', 'cancelled'].includes(String(job.status))) return job;
    if (Date.now() > stop) throw new Error('deadline');
    const { promise, resolve } = Promise.withResolvers<void>();
    setTimeout(resolve, 1000);
    await promise;
  }
}

// ---------- i18n (de default, en) -------------------------------------------
const STRINGS: Record<string, [string, string]> = {
  new_project: ['Neues Projekt', 'New project'], new_chat: ['Neuer Chat', 'New chat'],
  send: ['Senden', 'Send'], stop: ['Stopp', 'Stop'], save: ['Speichern', 'Save'],
  back: ['Zurück', 'Back'], title: ['Titel', 'Title'],
  writing_alias: ['Schreibprofil', 'Writing profile'],
};
export type Lang = 'de' | 'en';
export const t = (key: string, lang: Lang) =>
  (STRINGS[key] ? lang === 'de' ? STRINGS[key][0] : STRINGS[key][1] : key);

// ---------- prefs (localStorage, per browser only) ---------------------------
export const prefs = {
  get theme(): 'light' | 'dark' {
    const stored = localStorage.getItem('cs-theme');
    if (stored === 'light' || stored === 'dark') return stored;
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  },
  set theme(v: 'light' | 'dark') { localStorage.setItem('cs-theme', v); },
  get lang(): Lang { return localStorage.getItem('cs-lang') === 'en' ? 'en' : 'de'; },
  set lang(v: Lang) { localStorage.setItem('cs-lang', v); },
};

// ---------- view helpers ------------------------------------------------------
export const esc = (s: string) => s.replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

export function diffLines(a: string, b: string): string {
  const al = a.split('\n'), bl = b.split('\n'), out: string[] = [];
  let i = 0, j = 0;
  while (i < al.length || j < bl.length) {
    if (al[i] === bl[j]) { out.push(` ${al[i]}`); i += 1; j += 1; continue; }
    if (bl.indexOf(al[i]!, j) < 0) out.push(`-${al[i++]}`);
    else { while (bl[j] !== al[i]) out.push(`+${bl[j++]}`); }
  }
  return out.join('\n');
}
