import { ApiError, api, chat, esc, json, post, prefs, stream, type Document, type Msg, type Project, type Session } from './core';
import { Organizer, chatEntry, type Entry, type ManagedView } from './organizer';
import { chapterMenu, chapterPlanDialog, chapterTools, requestDialog, settingsDialog,
  storyInfo, storyJob, storyJobMarkup, storyMarkup, storyPost, type StoryInfo, type StoryJob, type StoryRequest } from './story';
import { Editor } from './editor';
import { artReviewDialog, editPlanDialog, exportManuscript, manuscript, manuscriptDialog, planDialog, productionAct, productionCard,
  productionInfo, productionJob, proposeDialog, type ProductionJob } from './production';
import { icon, type IconName } from './icons';
import { projectTitle, routeIntent, suggestions, tools, type Intent, type Mode, type Tool } from './intent';
import { $, announce, button, describe, details, dialogForm, download, formatDate, iconButton, imageUrl, main, mark, markdown, safeImageId, showDialog, sourceLink } from './studio-ui';

type DocSummary = Pick<Document, 'id' | 'title' | 'kind' | 'status' | 'updated' | 'version' | 'folder_id' | 'story_number'> & { project_id?: string };
type Attachment = { id: string; name: string; folder_id?: string; size: number };
type ProjectDetail = Project & { documents: DocSummary[]; attachments?: Attachment[]; chats?: Session[] };
type Memory = { kind: string; key: string; body: string };
type ImageItem = { id: string; name?: string; folder_id?: string | null; trashed?: boolean;
  request?: { prompt?: string }; created?: number };
type ImageJob = { id?: string; status: string; image_id?: string; progress?: number; error?: string;
  request?: { prompt?: string }; dimensions?: [number, number]; waiting_reason?: string };
type Task = { status: string; project_id?: string; document_id?: string; error?: string; image?: ImageJob;
  requirements: { language?: 'de' | 'en'; word_range?: [number, number]; image_size?: string };
  steps: Record<string, { status: string; name?: string; error?: string;
    diagnostics?: Array<{ validation: { words: number; language: string; issues: string[] } }> }> };
type ResearchJob = { status: string; result?: { document_id?: string }; checkpoint?: {
  stage?: string; paused?: boolean; done_rounds?: number; rounds?: number;
  sources?: Array<{ url: string; title: string }>; open?: string[];
} };
type Decision = { key: string; title: string; status: string; rationale?: string };
type View = 'home' | 'chat' | 'project' | 'library' | 'search' | 'settings' | ManagedView;
type Route = { view: View; id?: string; document?: string; tab?: string };

const navToggle = $<HTMLButtonElement>('#nav-toggle')!;
const navDialog = $<HTMLDialogElement>('#nav-dialog')!;
const mobile = matchMedia('(max-width: 60rem)');
const labels: Record<View, string> = {
  home: 'Neuer Chat', chat: 'Unterhaltung', project: 'Inhalte', library: 'Bibliothek', search: 'Suche', settings: 'Einstellungen',
  folder: 'Ordner', chats: 'Chats', archive: 'Archiv', trash: 'Papierkorb',
};
const kinds: Record<string, string> = {
  story: 'Geschichte', novel: 'Roman', chapter: 'Kapitel', article: 'Artikel', devlog: 'Devlog', research: 'Recherche',
  dossier: 'Dossier', game: 'Spielidee', image: 'Bilder', doc: 'Dokument', custom: 'Unterhaltung',
};
const roles = { partner: 'Creative Partner', critical: 'Critical Designer', planner: 'Production Planner' };
const stageLabels: Record<string, string> = {
  plan: 'Teilfragen planen', search: 'Quellen suchen', read: 'Quellen auswerten', verify: 'Fakten und offene Fragen prüfen', synthesize: 'Dossier schreiben',
};
const imageStates: Record<string, string> = {
  waiting_gpu: 'Wartet auf den Bilddienst', queued: 'In der Warteschlange', pending: 'In der Warteschlange',
  submitting: 'Wird an den Bilddienst übergeben',
  loading: 'Bilddienst wird vorbereitet', generating: 'Bild wird erstellt', running: 'Bild wird erstellt',
  completed: 'Bild fertig', cancelled: 'Bildauftrag abgebrochen', failed: 'Bild konnte nicht erstellt werden',
};
const ended = (status: string) => ['completed', 'partial', 'failed', 'cancelled'].includes(status);
const path = (value: string) => encodeURIComponent(value);
const validId = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{32}$/u.test(value);
const option = (value: string, label: string, selected = false) => `<option value="${esc(value)}"${selected ? ' selected' : ''}>${esc(label)}</option>`;

let route: Route = { view: 'home' };
let revision = 0;
let sessions: Session[] = [];
let project: ProjectDetail | undefined;
let story: StoryInfo | undefined;
let storyFor: string | undefined;
let session: Session | undefined;
let messages: Msg[] = [];
let images: ImageItem[] = [];
let imageOffset = 0;
let moreImages = true;
let loadingImages = false;
let collapsed = false;
let draft = '';
let mode: Mode = 'auto';
const chatModes = new Map<string, Mode>();
let gameRole: keyof typeof roles = 'partner';
let status = '';
let busy = false;
let controller: AbortController | undefined;
let chatDraftContext: Tool | undefined;
let clarify = '';
let options = { image: {} as Record<string, string | number>, research: { mode: 'deep', strategy: 'balanced' } as Record<string, string | number> };
const imageJobs = new Map<string, ImageJob>();
const researchJobs = new Map<string, ResearchJob>();
const dossiers = new Map<string, Document>();
const chatTasks = new Map<string, Task>();
const storyJobs = new Map<string, StoryJob>();
const productionJobs = new Map<string, ProductionJob>();
const productionDocuments = new Map<string, Document>();
const taskDocuments = new Map<string, Document>();
let pendingDispatch: { session: string; text: string; id: string } | undefined;
let pendingChoice: { text: string; kind: 'context' | 'document'; mode: Mode } | undefined;
const activities: Record<Mode, string> = {
  auto: 'Automatisch erkennen', story: 'Geschichte / Roman', research: 'Deep Research',
  image: 'Bilder erstellen', article: 'Artikel / Devlog', game: 'Spielideen', chat: 'Chat',
};
const polling = new Set<string>();
const pendingButtons = new WeakSet<HTMLButtonElement>();
let navigationLoad: Promise<void> | undefined;

const isManaged = (view: View): view is ManagedView => ['folder', 'chats', 'archive', 'trash'].includes(view);
const organizer = new Organizer({
  navigate: go,
  refresh: refreshOrganizer,
  previewImage: entry => previewImage(entry.id),
  status: setStatus,
});
const editor = new Editor(() => renderEditor(), () => projectOverview(), doc => {
  if (doc.story_number != null) void refreshStory(doc.project_id).catch(() => {});
});
const storyProject = (p?: Project) => p?.kind === 'story' || p?.kind === 'novel';
const kindLabel = (kind: string) => kinds[kind] ?? 'Inhalt';
const typeOf = (kind?: string): Tool | undefined =>
  kind === 'game' ? 'game' : kind === 'article' || kind === 'devlog' ? 'article' : kind === 'story' || kind === 'novel' ? 'story' : undefined;

function setStatus(text: string) {
  status = text;
  const target = $('#view-status');
  if (target) target.textContent = text;
}

function navItem(action: string, label: string, glyph: IconName, current: boolean) {
  return `<button class="nav-item${action === 'new' ? ' new-chat' : ''}" type="button" data-action="${action}"${current ? ' aria-current="page"' : ''}>${icon(glyph)}<span>${label}</span></button>`;
}

function navigation() {
  document.querySelectorAll('[data-navigation]').forEach(region => {
    const inDrawer = region.closest('dialog');
    const focused = region.contains(document.activeElement) ? document.activeElement as HTMLElement : undefined;
    const href = focused?.getAttribute('href');
    const action = focused?.dataset.action;
    const value = focused?.dataset.value;
    const folder = focused?.closest<HTMLDetailsElement>('details[data-studio-folder]')?.dataset.studioFolder;
    const scroll = $('.side-recents', region)?.scrollTop ?? 0;
    region.innerHTML = `<div class="side-content"><div class="side-brand">${mark()}<span>Creative Studio</span>
      ${inDrawer ? iconButton('close-nav', 'Seitenleiste schließen', 'x') : ''}</div>
      <nav aria-label="Chat starten"><div class="nav-stack">
        ${navItem('new', 'Neuer Chat', 'plus', route.view === 'home')}
      </div></nav>
      <div class="side-recents">${organizer.tree(route.id ?? session?.id)}</div>
      <nav class="side-secondary" aria-label="Studio"><div class="nav-stack">
        ${navItem('library', 'Bibliothek', 'library', route.view === 'library')}
        ${navItem('search', 'Suche', 'search', route.view === 'search')}
        ${navItem('archive', 'Archiv', 'archive', route.view === 'archive')}
        ${navItem('trash', 'Papierkorb', 'trash', route.view === 'trash')}
      </div></nav>
      <div class="side-footer">${navItem('settings', 'Einstellungen', 'settings', route.view === 'settings')}</div>
    </div>`;
    $('.side-recents', region)!.scrollTop = scroll;
    if (focused) {
      const next = Array.from(region.querySelectorAll<HTMLElement>('a, button, summary')).find(node =>
        href ? href === node.getAttribute('href') : action ? action === node.dataset.action && value === node.dataset.value :
          folder && node.tagName === 'SUMMARY' && node.parentElement?.dataset.studioFolder === folder);
      (next ?? $('[data-action="new"]', region))?.focus({ preventScroll: true });
    }
  });
}

function loadNavigation() {
  const request: Promise<void> = Promise.all([api.sessions(), organizer.fetchFolders()])
    .then(([nextSessions, folders]) => {
      if (request !== navigationLoad) return navigationLoad;
      sessions = nextSessions;
      organizer.remember(sessions, folders);
      navigation();
    });
  navigationLoad = request;
  return request;
}

async function refreshOrganizer(action: string, entries: Entry[]) {
  await loadNavigation();
  const current = route;
  if (action === 'duplicate' || action === 'create-chat') return;
  if (isManaged(current.view)) {
    if (current.view === 'folder' && action === 'trash' && !organizer.hasFolder(current.id)) go('#trash');
    else await organizer.list(current.view, current.id);
  } else if (current.view === 'chat') {
    const affectsSession = entries.some(entry => (entry.kind === 'chat' && entry.id === session?.id) ||
      (entry.kind === 'project' && entry.id === session?.project_id));
    if (action === 'archive' && affectsSession) { go('#archive'); return; }
    if (action === 'trash' && current.id && !await api.session(current.id).catch(() => null)) {
      go('#trash');
      return;
    }
    if (action === 'trash' && editor.doc && !await api.document(editor.doc.id).catch(() => null)) {
      closeEditor();
      return;
    }
    if (affectsSession && current.id) {
      session = await api.session(current.id);
      const pid = editor.doc?.project_id ?? session.project_id;
      project = pid ? await api.project(pid) : undefined;
      render();
    }
  } else if (current.view === 'search') {
    const query = $<HTMLInputElement>('#search-query')?.value;
    if (query) await search(query);
  } else if (current.view === 'library') {
    await loadRoute(true);
  }
}

function header() {
  $('#location-label')!.textContent = labels[route.view];
  const open = mobile.matches ? navDialog.open : !collapsed;
  navToggle.setAttribute('aria-controls', mobile.matches ? 'nav-dialog' : 'sidebar');
  navToggle.setAttribute('aria-expanded', String(open));
  navToggle.setAttribute('aria-label', open ? 'Seitenleiste schließen' : 'Seitenleiste öffnen');
  const dark = prefs.theme === 'dark';
  $('#header-actions')!.innerHTML = iconButton('theme', dark ? 'Helles Erscheinungsbild verwenden' : 'Dunkles Erscheinungsbild verwenden', dark ? 'sun' : 'moon');
}

function composer() {
  return `<form class="composer" id="composer"><label for="prompt" class="sr-only">Nachricht</label>
    <textarea id="prompt" name="prompt" required rows="2" maxlength="12000" placeholder="${route.view === 'home' ? 'Womit möchtest du anfangen?' : 'Nachricht schreiben …'}">${esc(draft)}</textarea>
    <div class="composer-actions"><div class="composer-tools"><label for="chat-activity" class="sr-only">Tätigkeit</label>
    <select id="chat-activity" class="field chat-activity">${Object.entries(activities).filter(([key]) => key !== 'chat')
      .map(([key, label]) => option(key, label, key === mode || (key === 'auto' && mode === 'chat'))).join('')}</select>
    ${iconButton('tools', 'Werkzeugoptionen', 'settings')}
    ${mode === 'story' && !storyProject(project) ? button('production-propose', 'Geschichte planen', 'book') : ''}
    ${project?.kind === 'game' ? button('game-role', roles[gameRole], 'game', 'button quiet tool-label') : ''}</div>
    ${busy ? iconButton('stop', 'Antwort stoppen', 'x') : `<button class="button primary send" type="submit" aria-label="Nachricht senden">${icon('up')}</button>`}
    </div></form>`;
}

function home() {
  return `<div class="home"><section class="welcome" aria-labelledby="welcome-title"><div class="welcome-inner">
    <h1 id="welcome-title" class="welcome-title">Was möchtest du <em>heute machen?</em></h1>
    <div class="suggestions" role="group" aria-label="Vorschläge">${suggestions.map(item =>
      `<button type="button" class="suggestion" data-action="suggestion" data-value="${item.id}">${icon(item.icon)}<span>${item.label}</span>${icon('turn')}</button>`).join('')}</div>
    ${composer()}<p id="view-status" class="feedback" role="status">${esc(status)}</p>
    </div></section></div>`;
}

function projectOverview(includeTools = true): string {
  if (!project) return '';
  const info = storyFor === project.id ? story : undefined;
  const chapter = info?.chapters.find(item => item.id === editor.doc?.id);
  const activeChapter = chapter && editor.doc ? { ...chapter, status: editor.doc.status } : chapter;
  return `${includeTools && activeChapter ? chapterTools(activeChapter) : ''}
    <details class="project-outline"${$('.project-outline')?.hasAttribute('open') ? ' open' : ''}><summary>${info ? 'Kapitelnavigation' : 'Dokumente'}</summary>
    ${info ? storyMarkup(info, true, editor.doc?.id) : ''}
    <ul class="plain-list">${project.documents.filter(d => d.story_number == null).map(d => `<li>${button('open-doc', d.title || 'Ohne Titel', 'text', 'button quiet', d.id)}</li>`).join('')}</ul>
    ${button('project-notes', 'Notizen', 'book')}
    </details>`;
}

function imageMedia(id: string, alt: string, actions = true) {
  return `<figure class="image-result"><button type="button" class="image-button" aria-label="Bild vergrößern" data-action="preview-image" data-value="${id}">
    <img src="${imageUrl(id)}" alt="${esc(alt.slice(0, 180))}" loading="${actions ? 'eager' : 'lazy'}"></button>
    ${actions ? `<figcaption class="editor-actions">${button('regen', 'Erneut generieren', undefined, 'button quiet', id)}
      ${button('variant', 'Variante erstellen', undefined, 'button quiet', id)}
      ${button('save-image', 'Zum Chat hinzufügen', undefined, 'button quiet', id)}
      ${button('insert-image', editor.doc ? 'In Dokument übernehmen' : 'In Dokument einfügen', undefined, 'button quiet', id)}</figcaption>` : ''}
    </figure>`;
}

const taskErrors: Record<string, string> = {
  writing_template_mismatch: 'Das Schreibprofil hat die erwarteten Human-Writing-Regeln nicht übernommen.',
  writing_service_unavailable: 'Das Schreibmodell oder der Human Writing Skill ist gerade nicht erreichbar.',
  writing_empty: 'Das Schreibmodell hat keinen Text geliefert.',
  lint_failed: 'Die Prüfung mit dem Human Writing Skill konnte nicht abgeschlossen werden.',
  writing_validation_failed: 'Der Entwurf erfüllte nach der Überarbeitung die Vorgaben für Sprache oder Wortzahl nicht.',
  project_name_ambiguous: 'Mehrere Geschichten haben diesen Namen. Wähle sie unter Inhalte.',
  image_archive_missing: 'Das Bild fehlt im Bildarchiv.',
  image_invalid_png: 'Die Antwort des Bilddienstes ist kein gültiges PNG.',
  image_dimensions_mismatch: 'Das gespeicherte Bild hat ein anderes Format als angefordert.',
  image_job_not_found: 'Der Bilddienst findet diesen Auftrag nicht mehr.',
  image_submission_uncertain: 'Der Bilddienst hat die Annahme nicht bestätigt. Prüfe die Galerie vor einem erneuten Versuch.',
  image_service_unreachable: 'Der Bilddienst ist gerade nicht erreichbar.',
  image_auth_required: 'Der Bilddienst hat den Zugriff verweigert. Prüfe die lokale Dienstkonfiguration.',
  variant_source_missing: 'In dieser Unterhaltung ist noch kein fertiges Bild für eine Variante verfügbar.',
  gpu_wait_timeout: 'Der Bilddienst blieb während der Wartezeit belegt.',
};
const taskFailure = (code?: string) => taskErrors[code ?? ''];

function taskContent(id: string) {
  const task = chatTasks.get(id);
  if (!task) return '<p>Auftrag wird geladen …</p>';
  const writing = task.steps.writing;
  const doc = task.document_id ? taskDocuments.get(task.document_id) : undefined;
  const image = task.image;
  const savedImage = image?.status === 'completed' && safeImageId(image.image_id);
  const requirements = task.requirements;
  const requested = [
    requirements.language === 'en' ? 'Englisch' : requirements.language === 'de' ? 'Deutsch' : '',
    requirements.word_range ? (requirements.word_range[0] === requirements.word_range[1]
      ? requirements.word_range[0] : requirements.word_range.join('–')) + ' Wörter' : '',
    requirements.image_size?.replace('x', ' × '),
  ].filter(Boolean).join(' · ');
  const writingStatus = writing?.status === 'generating' ? 'Text wird geschrieben' :
    writing?.status === 'validating' ? 'Sprache und Wortzahl werden geprüft' :
    writing?.status === 'revising' ? 'Text wird überarbeitet' : writing?.status === 'pending' ? 'Schreiben vorgesehen' : '';
  const error = taskFailure(task.error) || (task.error ? 'Der Auftrag konnte nicht vollständig ausgeführt werden.' : '');
  const imageError = task.steps.image?.error || image?.error;
  const imageStatus = image?.status ?? task.steps.image?.status;
  const progress = typeof image?.progress === 'number' && image.progress > 0 && image.progress <= 1
    ? Math.round(image.progress * 100) : undefined;
  return `<p class="job-title">${task.status === 'completed' ? 'Auftrag abgeschlossen' :
      task.status === 'partial' ? 'Auftrag teilweise abgeschlossen' : task.status === 'failed' ?
        'Auftrag fehlgeschlagen' : task.status === 'cancelled' ? 'Auftrag abgebrochen' : 'Auftrag läuft'}</p>
    ${requested ? `<p class="muted">${esc(requested)}</p>` : ''}
    ${error ? '<p>' + esc(error) + '</p>' : ''}
    ${writingStatus ? '<p>' + writingStatus + ' …</p>' : ''}
    ${writing?.status === 'failed' ? '<p>' + esc(taskFailure(writing.error) || 'Die Texterstellung ist fehlgeschlagen.') + '</p>' : ''}
    ${doc ? `<section class="task-result" aria-label="Gespeichertes Dokument"><h3>${esc(doc.title)}</h3>
      <p>Text gespeichert${writing?.diagnostics?.at(-1) ? ' · ' + writing.diagnostics.at(-1)!.validation.words + ' Wörter' : ''}</p>
      <div class="prose" lang="${doc.lang === 'en' ? 'en' : 'de'}">${markdown(doc.body)}</div>
      ${button('open-doc', 'Entwurf öffnen', 'text', 'button', doc.id)}</section>` : ''}
    ${savedImage && image?.image_id ? `<section class="task-result" aria-label="Gespeichertes Bild">
      <p>Bild erstellt${image.dimensions ? ' · ' + image.dimensions.join(' × ') : ''}</p>
      ${imageMedia(image.image_id, image.request?.prompt ?? 'Generiertes Bild')}</section>` : ''}
    ${!savedImage && imageStatus && imageStatus !== 'skipped' ? `<p class="job-title">${esc(imageStates[imageStatus] ??
      (imageStatus === 'pending' ? 'Bildauftrag vorgesehen' : 'Bildauftrag läuft'))}</p>
      ${imageStatus === 'failed' ? '<p>' + esc(taskFailure(imageError) || 'Der Bilddienst hat den Auftrag nicht abgeschlossen.') + '</p>' : ''}
      ${image?.waiting_reason === 'image_service_unreachable' ? '<p>Der Bilddienst ist gerade nicht erreichbar. Das Studio versucht es erneut.</p>' : ''}
      ${progress !== undefined ? `<label>Bildfortschritt · ${progress} %<progress value="${progress}" max="100"></progress></label>` : ''}
      ${image?.id && !ended(imageStatus) ? button('cancel-image', 'Bildauftrag abbrechen', undefined, 'button', image.id) : ''}` : ''}
    ${task.steps.image?.status === 'skipped' ? '<p>Der Bildauftrag konnte nicht gestartet werden.</p>' : ''}`;
}

function jobContent(kind: string, id: string) {
  if (kind === 'story-job') return storyJobMarkup(storyJobs.get(id));
  if (kind === 'production-job') return productionCard(productionJobs.get(id), productionDocuments, imageMedia);
  if (kind === 'chat-task') return taskContent(id);
  if (kind === 'image') {
    const job = imageJobs.get(id);
    if (!job) return '<p>Bildauftrag wird geladen …</p>';
    if (job.status === 'completed' && safeImageId(job.image_id)) return imageMedia(job.image_id, job.request?.prompt ?? 'Generiertes Bild');
    return `<p class="job-title">${esc(imageStates[job.status] ?? 'Bildauftrag läuft')}</p>
      ${job.status === 'failed' ? `<p>${job.error === 'gpu_wait_timeout' ? 'Der Bilddienst blieb belegt. Sende den Wunsch bei Bedarf erneut.' : 'Prüfe die Bildeinstellungen oder versuche es erneut.'}</p>` : ''}
      ${job.status === 'completed' ? '<p>Das Bild ist derzeit nicht verfügbar.</p>' : ''}
      ${!ended(job.status) ? button('cancel-image', 'Bildauftrag abbrechen', undefined, 'button', id) : ''}`;
  }
  const job = researchJobs.get(id);
  if (!job) return '<p>Recherche wird geladen …</p>';
  const cp = job.checkpoint ?? {};
  const title = job.status === 'completed' ? 'Dossier fertig' : job.status === 'failed' ? 'Recherche unterbrochen' : job.status === 'cancelled' ? 'Recherche abgebrochen' :
    cp.paused ? 'Recherche pausiert' : stageLabels[cp.stage ?? 'plan'] ?? 'Recherche läuft';
  const docId = job.result?.document_id;
  const dossier = docId ? dossiers.get(docId) : undefined;
  const sources = cp.sources ?? [];
  const open = cp.open ?? [];
  return `<p class="job-title">${title}</p>
    ${!ended(job.status) ? `<label>Rechercherunden · ${cp.done_rounds ?? 0} von ${cp.rounds ?? 3}
      <progress value="${cp.done_rounds ?? 0}" max="${cp.rounds ?? 3}"></progress></label>
      ${button(cp.paused ? 'resume-research' : 'pause-research', cp.paused ? 'Fortsetzen' : 'Pausieren', undefined, 'button', id)}
      ${button('cancel-research', 'Recherche abbrechen', undefined, 'button quiet', id)}` : ''}
    ${job.status === 'failed' ? '<p>Die Recherche konnte nicht abgeschlossen werden. Du kannst deine Frage erneut senden.</p>' : ''}
    ${sources.length ? `<details><summary>Quellen (${sources.length})</summary><ul>${sources.map(s => '<li>' + sourceLink(s.url, s.title) + '</li>').join('')}</ul></details>` : ''}
    ${open.length ? `<details><summary>Offene Fragen (${open.length})</summary><ul>${open.map(q => '<li>' + esc(q) + '</li>').join('')}</ul></details>` : ''}
    ${validId(docId) ? `<details open><summary>Dossier lesen</summary><div class="prose">${dossier ? markdown(dossier.body) : '<p>Dossier wird geladen …</p>'}</div></details>
      ${button('open-doc', 'Dossier öffnen', 'text', 'button', docId)}` : ''}`;
}

function transcript() {
  return messages.map(m => {
    const isUser = m.role === 'user';
    const meta = m.meta ?? {};
    const kind = meta.kind;
    const attachment = (kind === 'image' || kind === 'research' || kind === 'chat-task' || kind === 'story-job' || kind === 'production-job') && validId(meta.job_id)
      ? `<section class="research-card job-card" aria-label="${kind === 'image' ? 'Bildauftrag' : kind === 'chat-task' ? 'Kreativauftrag' : kind === 'production-job' ? 'Story-Produktion' : 'Rechercheauftrag'}" data-job="${meta.job_id}" data-kind="${kind}">${jobContent(kind, meta.job_id)}</section>`
      : (kind === 'document' && validId(meta.document_id) ? button('open-doc', 'Entwurf öffnen', 'text', 'button', meta.document_id) :
        (kind === 'draft-option' && validId(meta.document_id) ? button('replace-draft', 'Vorschlag übernehmen', 'text', 'button', m.id) :
          kind === 'editorial-run' && validId(meta.document_id) && validId(meta.run_id)
            ? button('open-editorial-run', meta.mode === 'rewrite' ? 'Vergleich öffnen' : 'Prüfbericht öffnen', 'text', 'button', m.id) :
              kind === 'chapter-unwritten' && Number.isInteger(meta.number) && Number(meta.number) > 0
                ? button('write-unwritten', 'Kapitel schreiben', 'text', 'button', String(meta.number)) : ''));
    return `<article class="message ${isUser ? 'user' : 'assistant'}">${isUser ? '' : mark()}<div class="message-content">
      <h2>${isUser ? 'Du' : 'Studio'}</h2>
      ${m.content && !['image', 'research', 'chat-task'].includes(String(kind)) ? `<div class="prose">${isUser ? '<p class="user-text">' + esc(m.content) + '</p>' : markdown(m.content)}</div>` : ''}
      ${attachment}</div></article>`;
  }).join('');
}

function chatView() {
  const title = session?.title || project?.name || 'Unterhaltung';
  return `<div class="conversation${editor.doc ? ' with-editor' : ''}">
    <section class="chat-column" aria-labelledby="chat-title">
      <header class="chat-heading"><div class="organizer-title-row"><h1 id="chat-title">${esc(title)}</h1>
        ${session ? organizer.menuButton(chatEntry(session)) : ''}</div><div class="project-context">
        ${project && project.kind !== 'custom' ? `<span class="chat-context">${storyProject(project) ? 'Geschichte' : esc(kindLabel(project.kind))}</span>` : ''}
        ${session ? button('contents', 'Inhalte', 'book') : ''}
        ${storyProject(project) ? button('production-plan', 'Story-Planung', 'book', 'button quiet', project?.id) : ''}
      </div></header>
      <div class="transcript" role="group" aria-label="Chatverlauf">${transcript()}
        ${busy ? `<article class="message assistant">${mark()}<div class="message-content"><h2>Studio</h2><div class="prose" id="streaming">Antwort wird vorbereitet …</div></div></article>` : ''}
        ${clarify ? `<article class="message assistant">${mark()}<div class="message-content"><h2>Studio</h2><p>Womit sollen wir anfangen?</p>
          <div class="editor-actions">${tools.map(t => button('clarify-tool', t.label, t.icon, 'button', t.id)).join('')}${button('clarify-tool', 'Darüber sprechen', 'chat', 'button', 'chat')}</div></div></article>` : ''}
      </div>
      <p id="view-status" class="feedback" role="status">${esc(status)}</p>${composer()}
    </section><div class="editor-host">${editor.html()}</div></div>`;
}

function docsList(docs: DocSummary[]) {
  return docs.length ? `<ul class="plain-list doc-list">${docs.map(d => `<li class="organizer-row">
    <div><div draggable="true" data-organizer-drag="document/${d.id}">${button('open-doc', d.title || 'Ohne Titel', 'text', 'button quiet', d.id)}</div>
    <small>${esc(kindLabel(d.kind))} · ${formatDate(d.updated)} · Version ${d.version}</small></div>
    ${organizer.menuButton({ ...d, kind: 'document', name: d.title || 'Ohne Titel' })}</li>`).join('')}</ul>` : '<p class="muted">Hier erscheinen die Dokumente aus dem Chat.</p>';
}

function attachmentList(attachments: Attachment[]) {
  return attachments.length ? `<ul class="plain-list organizer-list">${attachments.map(a => `<li class="organizer-row">
    <a class="organizer-link" href="/api/attachments/${path(a.id)}" draggable="true" data-organizer-drag="attachment/${a.id}">${icon('paperclip')}<span>${esc(a.name)}</span></a>
    ${organizer.menuButton({ ...a, kind: 'attachment' })}</li>`).join('')}</ul>` :
    '<p class="muted">Hier erscheinen die Anhänge aus deinen Chats.</p>';
}

function galleryTile(item: ImageItem) {
  const name = (item.name ?? item.request?.prompt ?? 'Generiertes Bild').slice(0, 180);
  const entry = { kind: 'image' as const, id: item.id, name, folder_id: item.folder_id };
  return `<div class="gallery-tile"><div draggable="true" data-organizer-drag="image/${item.id}">${imageMedia(item.id, name, false)}</div>
    <div class="organizer-row"><span>${esc(name)}</span>${organizer.menuButton(entry)}</div></div>`;
}

function libraryTabs() {
  return `<nav class="library-tabs" aria-label="Bibliotheksansichten">
    ${[['docs', 'Dokumente'], ['images', 'Bilder'], ['attachments', 'Anhänge']].map(([key, label]) =>
      `<a href="#library/${key}"${route.tab === key ? ' aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`;
}

function gallery() {
  const grid = images.length ? `<div class="gallery-grid">${images.map(galleryTile).join('')}</div>` : '';
  return grid + (moreImages ? button('more-images', 'Weitere Bilder laden', undefined, 'button') :
    grid ? '' : '<p>Hier erscheinen deine erzeugten Bilder. Du kannst im Chat mit einem Bildwunsch beginnen.</p>');
}

async function openContents() {
  const sid = session?.id;
  if (!sid) return;
  const epoch = revision;
  const current = await api.session(sid);
  if (epoch !== revision) return;
  const pid = current.project_id;
  const [p, memories]: [ProjectDetail | undefined, Memory[]] = pid
    ? await Promise.all([api.project(pid), getMemories(pid)]) : [undefined, []];
  const info = p && storyProject(p) ? await storyInfo(p.id) : undefined;
  if (epoch !== revision) return;
  session = current;
  if (p && p.id === project?.id) {
    project = p;
    if (info) { story = info; storyFor = p.id; }
  }
  const linkedImages = memories.filter(item => item.kind === 'image' && safeImageId(item.key));
  const contexts = current.contexts ?? [];
  const contextChoices = contexts.length > 1 ? `<div class="editor-actions" role="group" aria-label="Inhalte im Chat">
    ${contexts.map(item => button('switch-context', item.name, undefined, item.id === p?.id ? 'button primary' : 'button', item.id)).join('')}</div>` : '';
  showDialog('Inhalte', contextChoices + (info ? storyMarkup(info, true, editor.doc?.id) : '') +
    `<section><h3>Dokumente</h3>${docsList(p?.documents.filter(d => d.story_number == null) ?? [])}
      ${button('create-document', 'Neues Dokument', 'plus', 'button')}
      ${button('upload-attachment', 'Anhang hinzufügen', 'paperclip', 'button')}
      ${p?.kind === 'game' ? button('decisions', 'Decision Log', 'game', 'button') : ''}
      ${p ? button('project-notes', 'Notizen', undefined, 'button quiet') : ''}</section>` +
    (p?.attachments?.length ? '<section><h3>Anhänge</h3>' + attachmentList(p.attachments) + '</section>' : '') +
    (linkedImages.length ? '<section><h3>Bilder</h3><div class="gallery-grid dialog-gallery">' +
      linkedImages.map(item => galleryTile({ id: item.key, request: { prompt: item.body } })).join('') + '</div></section>' : ''), true);
}

function collection(content?: string) {
  const title = labels[route.view];
  const defaults: Partial<Record<View, string>> = {
    folder: '<h1 id="organizer-title">Ordner</h1>' + organizer.html('folder'),
    chats: '<h1>Chats</h1>' + organizer.html('chats'),
    archive: '<h1>Archiv</h1>' + organizer.html('archive'),
    trash: '<h1>Papierkorb</h1>' + organizer.html('trash'),
    project: '<h1>Inhalte</h1><p>Der Chat wird geöffnet …</p>',
    library: '<h1>Bibliothek</h1>' + libraryTabs() + (route.tab === 'images'
      ? '<div id="library-content">' + gallery() + '</div>' + button('job-history', 'Bildaufträge ansehen', undefined, 'button quiet')
      : '<div id="library-content"><p>Lädt …</p></div>'),
    search: '<h1>Suche</h1><form id="search-form" class="search-form"><label for="search-query">Chats und Dokumente</label><input id="search-query" class="field" name="q" type="search" maxlength="500" required><button class="button primary" type="submit">Suchen</button></form><div id="search-results"></div>',
    settings: `<h1>Einstellungen</h1><section class="collection-section"><h2>Erscheinungsbild</h2>
      ${button('theme', prefs.theme === 'dark' ? 'Helles Erscheinungsbild verwenden' : 'Dunkles Erscheinungsbild verwenden', prefs.theme === 'dark' ? 'sun' : 'moon', 'button')}</section>
      <section class="collection-section"><h2>Sprache für neue Texte</h2><label class="sr-only" for="response-lang">Sprache für neue Texte</label>
        <select id="response-lang" class="field">${option('de', 'Deutsch', prefs.lang === 'de')}${option('en', 'English', prefs.lang === 'en')}</select>
      </section><section class="collection-section"><details><summary>Dienste und Schreibprofile</summary>${button('services', 'Dienststatus anzeigen', 'settings', 'button')}</details></section>`,
  };
  return `<section class="collection">${content ?? defaults[route.view] ?? '<h1>' + title + '</h1>'}
    <p id="view-status" class="feedback" role="status">${esc(status)}</p></section>`;
}

function render(focus?: 'main' | 'prompt' | 'editor') {
  main.innerHTML = route.view === 'home' ? home() : route.view === 'chat' ? chatView() : collection();
  header();
  if (focus === 'main') main.focus();
  if (focus === 'prompt') $('#prompt')?.focus();
  if (focus === 'editor') focusEditor();
}

function focusEditor() { ($('#draft') ?? $('#doc-title'))?.focus(); }
function renderEditor() {
  const host = $('.editor-host');
  if (!host) return;
  host.innerHTML = editor.html();
  $('.conversation')?.classList.toggle('with-editor', Boolean(editor.doc));
  for (const card of main.querySelectorAll<HTMLElement>('[data-kind="image"][data-job]')) {
    const id = card.dataset.job!;
    if (imageJobs.get(id)?.status === 'completed') updateJobCard(id, 'image');
  }
}

function currentRoute(): Route {
  const [name, id, document] = location.hash.slice(1).split('/');
  if (name === 'chat' && validId(id)) return { view: 'chat', id, document: validId(document) ? document : undefined };
  if (name === 'project' && validId(id)) return { view: 'project', id };
  if (name === 'document' && validId(id)) return { view: 'chat', document: id };
  if (name === 'library' || name === 'publish' || name === 'images') return { view: 'library', tab: name === 'images' || id === 'images' ? 'images' : id === 'attachments' ? 'attachments' : 'docs' };
  if (name === 'stories' || name === 'articles') return { view: 'chats' };
  if (name === 'folder' && validId(id)) return { view: 'folder', id };
  if (name === 'projects') return { view: 'chats' };
  if (name === 'search' || name === 'settings' || name === 'chats' || name === 'archive' || name === 'trash') return { view: name };
  return { view: 'home' };
}

function go(hash: string) {
  closeNav();
  if (location.hash === hash) void loadRoute(true);
  else location.hash = hash;
}

function keepLocation(documentId?: string) {
  const id = session?.id;
  if (id) history.replaceState(null, '', '#chat/' + path(id) + (documentId ? '/' + path(documentId) : ''));
  else if (documentId) history.replaceState(null, '', '#document/' + path(documentId));
  else if (project) history.replaceState(null, '', '#chat');
  route = { view: 'chat', id, document: documentId };
}

async function loadRoute(focus = false) {
  controller?.abort();
  const epoch = ++revision;
  closeNav();
  route = currentRoute();
  organizer.reset(isManaged(route.view) ? route.view : undefined);
  status = ''; clarify = ''; draft = ''; busy = false; controller = undefined;
  mode = 'auto'; gameRole = 'partner'; chatDraftContext = undefined;
  project = undefined; session = undefined; messages = []; story = undefined; storyFor = undefined; editor.close();
  render(focus ? (route.view === 'home' ? 'prompt' : 'main') : undefined);
  navigation();
  try {
    if (route.view === 'chat') {
      const nextDocument = route.document ? await api.document(route.document) : undefined;
      if (epoch !== revision) return;
      const nextSession = route.id ? await api.session(route.id) : undefined;
      if (epoch !== revision) return;
      const pid = nextDocument?.project_id ?? nextSession?.project_id;
      const [nextProject, nextMessages] = await Promise.all([
        pid ? api.project(pid).catch(async error => {
          if (!nextDocument || nextSession?.project_id === pid) throw error;
          return nextSession?.project_id ? api.project(nextSession.project_id) : undefined;
        }) : undefined,
        nextSession ? api.messages(nextSession.id) : [],
      ]);
      if (epoch !== revision) return;
      session = nextSession;
      if (session) mode = chatModes.get(session.id) ?? 'auto';
      organizer.reveal(nextSession?.folder_id ?? nextDocument?.folder_id ?? undefined);
      project = nextProject;
      messages = nextMessages;
      if (nextDocument) editor.open(nextDocument);
      await loadStory(nextProject).catch(() => {});
      if (epoch !== revision) return;
      render(focus ? nextDocument ? 'editor' : 'main' : undefined);
      navigation();
      refreshJobs();
    }
    if (isManaged(route.view)) {
      if (route.view === 'folder') {
        await loadNavigation();
        if (epoch !== revision) return;
        organizer.reveal(route.id);
      }
      await organizer.list(route.view, route.id);
    }
    if (route.view === 'project' && route.id) {
      const linked = await json<{ id: string | null }>('/api/projects/' + route.id + '/chat');
      if (epoch !== revision) return;
      if (!linked.id) { go('#archive'); return; }
      history.replaceState(null, '', '#chat/' + linked.id);
      return loadRoute(focus);
    }
    if (route.view === 'library') {
      if (route.tab === 'images') {
        images = []; imageOffset = 0; moreImages = true; loadingImages = false;
        if ($('#library-content')) $('#library-content')!.innerHTML = gallery();
        await loadImages(epoch);
      } else if (route.tab === 'attachments') {
        const list = await api.projects();
        const full = await Promise.all(list.map(p => api.project(p.id) as Promise<ProjectDetail>));
        if (epoch === revision) $('#library-content')!.innerHTML = attachmentList(full.flatMap(p => p.attachments ?? []));
      } else {
        const docs = await allDocuments();
        if (epoch === revision) $('#library-content')!.innerHTML = docsList(docs);
      }
    }
    if (route.view === 'home' && ['#research', '#game'].includes(location.hash)) {
      selectTool(location.hash === '#game' ? 'game' : 'research', true);
    }
  } catch (error) {
    if (epoch === revision) {
      if (route.view !== 'home' && route.view !== 'chat') main.innerHTML = collection(`<h1>${labels[route.view]}</h1>${button('reload-view', 'Erneut versuchen', undefined, 'button')}`);
      setStatus(describe(error, 'Dieser Bereich konnte nicht geladen werden.'));
    }
  }
}

async function allDocuments() {
  const list = await api.projects();
  const full = await Promise.all(list.map(p => api.project(p.id)));
  return full.flatMap(p => p.documents.map(d => ({ ...d, project_id: p.id }))).sort((a, b) => b.updated - a.updated);
}

async function loadImages(epoch = revision) {
  if (loadingImages) return;
  loadingImages = true;
  try {
    const page = await json<{ images: ImageItem[]; next_offset: number | null }>(`/api/images/gallery?managed=1&offset=${imageOffset}`);
    if (epoch !== revision) return;
    const seen = new Set(images.map(i => i.id));
    images = [...images, ...page.images.filter(i => safeImageId(i.id) && !seen.has(i.id))];
    moreImages = page.next_offset !== null;
    imageOffset = page.next_offset ?? imageOffset;
    const region = $('#library-content');
    if (region) region.innerHTML = gallery();
  } catch (error) {
    if (epoch === revision) {
      $('#library-content')!.innerHTML = '<p>Bilder konnten nicht geladen werden.</p>' + button('more-images', 'Erneut versuchen', undefined, 'button');
      setStatus(describe(error, 'Die Galerie ist gerade nicht erreichbar.'));
    }
  } finally { if (epoch === revision) loadingImages = false; }
}

function galleryPage(offset = 0) {
  return json<ImageItem[] | { images: ImageItem[] }>(`/api/images/gallery?offset=${offset}`)
    .then(page => Array.isArray(page) ? page : page.images ?? []);
}

async function ensureSession(text: string) {
  if (session) return session;
  const epoch = revision;
  const title = projectTitle(text, 'Unterhaltung');
  const { id } = await api.createSession({ title, project_id: project?.id });
  if (epoch !== revision) throw new DOMException('Navigation', 'AbortError');
  session = { id, title, project_id: project?.id ?? null, model: null };
  if (route.view === 'home') route = { view: 'chat' };
  keepLocation(editor.doc?.id);
  return session;
}

async function record(role: Msg['role'], content: string, meta?: Msg['meta']) {
  const { id } = session!;
  const message = await post<Msg>(`/api/sessions/${id}/messages`, { role, content, meta });
  if (session?.id === id) messages.push(message);
}

async function ensureProject(kind: Tool | 'custom', text: string) {
  if (project) return project;
  const epoch = revision;
  const current = await ensureSession(text);
  const { project_id: id } = await post<{project_id: string}>(`/api/sessions/${current.id}/context`, { kind, lang: prefs.lang });
  const next = await api.project(id);
  if (epoch !== revision) throw new DOMException('Navigation', 'AbortError');
  session = await api.session(current.id);
  project = next;
  await loadStory(next).catch(() => {});
  return project;
}

function selectTool(choice: Mode, prefill: boolean) {
  mode = choice;
  if (session) chatModes.set(session.id, choice);
  const t = tools.find(item => item.id === choice);
  if (t && !draft.trim() && prefill) draft = t.prompt;
  render('prompt');
  const prompt = $<HTMLTextAreaElement>('#prompt');
  if (prompt) prompt.setSelectionRange(prompt.value.length, prompt.value.length);
}

function openTools() {
  showDialog('Werkzeugoptionen', `<div class="dialog-actions">
    ${button('image-options', 'Bildoptionen', 'picture', 'button')}
    ${button('research-options', 'Rechercheoptionen', 'research', 'button')}
    ${project?.kind === 'game' ? button('game-role', 'Rolle ändern', 'game', 'button') : ''}</div>`);
}

function toolsOptions(kind: 'image' | 'research') {
  if (kind === 'research') {
    dialogForm('Rechercheoptionen', `<label for="research-depth">Tiefe</label><select class="field" id="research-depth" name="mode">
      ${[['quick', 'Schnell'], ['deep', 'Ausführlich'], ['extended', 'Gründlich']].map(([k, label]) => option(k, label, options.research.mode === k)).join('')}</select>
      <label for="research-rounds">Maximale Runden (optional)</label><input class="field" id="research-rounds" name="rounds" type="number" min="1" max="10" value="${options.research.rounds ?? ''}">
      <label for="research-strategy">Quellenstrategie</label><select class="field" id="research-strategy" name="strategy">
      ${[['balanced', 'Ausgewogen'], ['primary', 'Primärquellen bevorzugen'], ['broad', 'Verschiedene Perspektiven']].map(([k, label]) => option(k, label, options.research.strategy === k)).join('')}</select>`, 'Übernehmen', async values => {
      options.research = { mode: String(values.get('mode')), strategy: String(values.get('strategy')) };
      if (values.get('rounds')) options.research.rounds = Number(values.get('rounds'));
    });
    return;
  }
  void api.catalog().then(catalog => {
    const models: Array<{ id: string; name?: string; installed?: boolean }> = catalog.models ?? [];
    const presets: Array<{ id: string; name?: string }> = catalog.presets ?? [];
    dialogForm('Bildoptionen', `<label for="image-model">Modell</label><select class="field" id="image-model" name="model">${option('', 'Automatisch')}
      ${models.filter(m => m.installed !== false).map(m => option(m.id, m.name ?? m.id, options.image.model === m.id)).join('')}</select>
      <label for="image-preset">Stilvorlage</label><select class="field" id="image-preset" name="preset">${option('', 'Keine')}
      ${presets.map(p => option(p.id, p.name ?? p.id, options.image.preset === p.id)).join('')}</select>
      <label for="image-size">Auflösung</label><select class="field" id="image-size" name="size">
      ${['1024x1024', '1024x576', '576x1024', '768x768', '512x512'].map(s => option(s, s.replace('x', ' × '), (options.image.size ?? '1024x1024') === s)).join('')}</select>
      <label for="image-seed">Seed (optional)</label><input class="field" id="image-seed" name="seed" type="number" min="0" max="2147483647" value="${options.image.seed ?? ''}">`, 'Übernehmen', async values => {
      options.image = { size: String(values.get('size')) };
      for (const name of ['model', 'preset']) if (values.get(name)) options.image[name] = String(values.get(name));
      if (values.get('seed')) options.image.seed = Number(values.get('seed'));
    });
  }).catch(error => {
    showDialog('Bildoptionen', '<p>' + esc(describe(error, 'Die Bildoptionen konnten nicht geladen werden.')) + '</p>');
  });
}

type EditorialChat = { mode: 'audit' | 'review' | 'rewrite' | 'both' | 'compare'; id: string; scoped: boolean };
type ChatDispatch = { handled: boolean; editorial?: EditorialChat; activity?: Mode; context_id?: string;
  choice?: 'context' | 'document'; choices?: {id: string; label: string}[] };

async function refreshChatContext(sid: string, epoch: number) {
  const updated = await api.session(sid);
  if (epoch !== revision || session?.id !== sid) return;
  session = updated;
  if (updated.project_id !== project?.id) {
    const next = updated.project_id ? await api.project(updated.project_id) : undefined;
    if (epoch !== revision || session?.id !== sid) return;
    project = next;
    story = undefined;
    storyFor = undefined;
    await loadStory(next).catch(() => {});
  }
}

async function editorialFromChat(input: EditorialChat, text: string, epoch: number) {
  const id = input.id;
  if (editor.doc?.id !== id) await openDocument(id);
  if (epoch !== revision || editor.doc?.id !== id) return;
  await record('user', text);
  const runs = await editor.fromChat(input.mode, text, input.scoped);
  if (epoch !== revision) return;
  if (input.mode === 'compare') await record('assistant', 'Der Versionsvergleich ist im Editor geöffnet.');
  for (const run of runs) {
    await record('assistant', run.mode === 'rewrite' ? 'Ein Überarbeitungsvorschlag liegt zur Freigabe vor.'
      : run.state === 'partial' ? 'Die lokalen Prüfbefunde sind verfügbar. Details zur Modellprüfung stehen im Bericht.'
        : 'Der Human Writing Audit liegt im Prüfverlauf.', { kind: 'editorial-run', document_id: id, run_id: run.id, mode: run.mode });
  }
}

async function submit(text: string, selection?: Intent, chosen?: { context_id?: string; chapter_id?: string }) {
  if (busy || !text.trim()) return;
  let intent = selection ?? routeIntent(text, 'auto', chatDraftContext ?? typeOf(project?.kind));
  const epoch = revision;
  busy = true; draft = ''; status = ''; clarify = '';
  controller = new AbortController();
  const signal = controller.signal;
  try {
    await ensureSession(text);
    if (epoch !== revision) return;
    chatModes.set(session!.id, mode);
    if (intent !== 'decision' && intent !== 'export') {
      const sid = session!.id;
      if (pendingDispatch?.session !== sid || pendingDispatch.text !== text) {
        pendingDispatch = { session: sid, text, id: crypto.randomUUID().replaceAll('-', '') };
      }
      const dispatched = await post<ChatDispatch>('/api/chat/dispatch', {
        workflow: 'chat', session_id: sid, request_id: pendingDispatch.id, text, default_lang: prefs.lang,
        mode: selection ?? mode, document_id: editor.doc?.id, image_options: options.image, research_options: options.research,
        ...chosen,
      });
      if (epoch !== revision) return;
      if (dispatched.choice && dispatched.choices?.length) {
        draft = text;
        pendingChoice = { text, kind: dispatched.choice, mode };
        showDialog(dispatched.choice === 'context' ? 'Welche Geschichte meinst du?' : 'Welches Dokument meinst du?',
          '<div class="organizer-menu">' + dispatched.choices.map(item =>
            button('choose-chat-target', item.label, 'text', 'button quiet', item.id)).join('') + '</div>');
        return;
      }
      await refreshChatContext(sid, epoch);
      if (epoch !== revision) return;
      if (dispatched.editorial) {
        pendingDispatch = undefined;
        await editorialFromChat(dispatched.editorial, text, epoch);
        return;
      }
      if (dispatched.handled) {
        messages = await api.messages(sid);
        pendingDispatch = undefined;
        return;
      }
      if (dispatched.activity && dispatched.activity !== 'auto') intent = dispatched.activity;
      pendingDispatch = undefined;
    }
    if (intent === 'clarify') {
      clarify = text;
      draft = text;
    } else if (intent === 'research' || intent === 'image') {
      await enqueue(intent, text);
    } else if (intent === 'export') {
      await exportFromChat(text);
    } else if (intent === 'decision') {
      const title = text.replace(/^.*?(?:[:—]|\bfest\s*,)\s*/iu, '').trim();
      await record('user', text);
      await saveDecision(title, 'beschlossen', '');
      await record('assistant', 'Die Entscheidung steht im Decision Log.');
    } else {
      await respond(intent, text, signal, epoch);
    }
  } catch (error) {
    if (epoch === revision) {
      if (signal.aborted) setStatus('Antwort gestoppt.');
      else {
        draft = text;
        const message = error instanceof Error && error.message === 'question_required' ? 'Welche Frage möchtest du recherchieren?' :
          error instanceof Error && error.message === 'image_prompt_required' ? 'Was soll auf dem Bild zu sehen sein?' :
            describe(error, 'Der Auftrag konnte nicht ausgeführt werden. Du kannst deine Nachricht erneut senden.');
        setStatus(message);
      }
    }
  } finally {
    if (epoch === revision) {
      busy = false; controller = undefined;
      render(clarify ? undefined : 'prompt');
      if (clarify) $('[data-action="clarify-tool"]')?.focus();
      refreshJobs();
      announce(status || 'Unterhaltung aktualisiert.');
      void loadNavigation().catch(() => {});
    }
  }
}

async function enqueue(kind: 'research' | 'image', text: string, retry?: { id: string; variant: boolean }) {
  const sid = session!.id;
  const body = { session_id: sid, project_id: project?.id, user_content: text };
  if (kind === 'research') {
    const question = text.replace(/^(?:bitte\s+)?(?:recherchiere(?:\s+(?:ausführlich|gründlich))?|deep research(?:\s+starten)?)[\s:,.!]+/iu, '').trim();
    if (!question || /^(?:recherchiere(?:\s+ausführlich)?|deep research)[.!]?$/iu.test(question)) {
      throw new Error('question_required');
    }
    await api.research({ ...options.research, ...body, question });
  } else if (retry) {
    await post('/api/images/regen', { ...body, image_id: retry.id, variant: retry.variant });
  } else {
    const prompt = text.replace(/^(?:bitte\s+)?(?:erstelle|generiere|zeichne|male)\s+(?:mir\s+)?(?:ein\s+)?(?:bild|foto|titelbild|cover|poster|eine illustration)\s+(?:von|mit|für)\s+/iu, '').trim();
    if (/\b(?:bild\s+von|bild\s+mit|ein bild|an image)\s*[.!]?$/iu.test(prompt)) throw new Error('image_prompt_required');
    await api.generate({ ...options.image, ...body, prompt });
  }
  if (session?.id === sid) messages = await api.messages(sid);
}

function draftContext() {
  return editor.doc ? editor.body : '';
}

async function respond(intent: 'story' | 'article' | 'game' | 'chat', text: string, signal: AbortSignal, epoch: number) {
  const original = session!;
  const prior = messages.slice(-22).flatMap(m => {
    if (!m.meta?.kind) return [{ role: m.role, content: m.content }];
    if (m.meta.kind !== 'chat-task' || !validId(m.meta.job_id)) return [];
    const id = chatTasks.get(m.meta.job_id)?.document_id;
    const doc = id && taskDocuments.get(id);
    return doc ? [{ role: 'assistant' as const, content: doc.body.slice(0, 16000) }] : [];
  }).slice(-18);
  let source = draftContext();
  if (!source && intent === 'article') {
    const lastDossier = [...messages].reverse().find(m => m.meta?.kind === 'research');
    const jobId = lastDossier?.meta?.job_id;
    const docId = validId(jobId) ? researchJobs.get(jobId)?.result?.document_id : undefined;
    if (validId(docId)) source = (await api.document(docId)).body;
  }
  if (signal.aborted || epoch !== revision) return;
  const writing = intent === 'story' || intent === 'article';
  if (intent === 'game' || writing) await ensureProject(intent, text);
  if (signal.aborted || epoch !== revision) return;

  messages.push({ id: crypto.randomUUID(), role: 'user', content: text });
  render();
  let partial = '';
  let target = $('#streaming');
  const token = (value: string) => {
    if (epoch !== revision) return;
    partial += value;
    target = $('#streaming');
    if (target) target.textContent = partial;
  };

  let answer: string;
  try {
    const locale = prefs.lang === 'en' ? 'English' : 'Deutsch';
    if (writing) {
      const description = intent === 'story' ? 'eine kurze Eröffnung der Geschichte in etwa 200 bis 350 Wörtern' : 'einen klaren Artikelentwurf in etwa 250 bis 450 Wörtern';
      const previous = prior.slice(-6).map(m => m.role + ': ' + m.content.slice(0, 1000)).join('\n');
      answer = await stream('/api/write', { model: 'creative-writing', session_id: original.id, user_content: text,
        project_id: project?.id, doc_id: editor.doc?.id, lang: prefs.lang,
        instruction: `Schreibauftrag: ${text}\nSchreibe auf ${locale} ${description}, passend zum Auftrag. Gib nur den Entwurf als Markdown aus.\n` +
          (source ? 'Arbeitsstand oder Quellenmaterial:\n' + source.slice(0, 24000) : '') +
          (previous ? '\nBisheriges Gespräch als Kontext:\n' + previous : ''),
      }, token, signal);
    } else {
      const role = intent === 'game' ? {
        partner: 'Entwickle die Spielidee gemeinsam weiter. Stelle höchstens eine konkrete Anschlussfrage.',
        critical: 'Prüfe Spielspaß und Umfang kritisch. Benenne einen umsetzbaren nächsten Schritt.',
        planner: 'Gliedere die Spielidee in realistische Prototyp- und Produktionsschritte.',
      }[gameRole] : 'Antworte hilfreich, direkt und knapp. Frage bei Bedarf nach.';
      answer = await chat({ model: 'research', sessionId: original.id, userContent: text, signal, onToken: token,
        messages: [{ role: 'system', content: role + ' Antworte auf ' + locale + '.' +
          (source ? '\nArbeitsstand als Kontext:\n' + source.slice(0, 16000) : '') }, ...prior, { role: 'user', content: text }],
      });
    }
  } catch (error) {
    if (epoch === revision) messages = await api.messages(original.id).catch(() => messages);
    throw error;
  }
  if (epoch !== revision) return;
  messages = await api.messages(original.id);
  if (epoch !== revision) return;
  if (intent === 'game' && project) {
    const question = answer.split('\n').map(line => line.trim()).filter(line => line.endsWith('?')).at(-1);
    const reply = messages.at(-1);
    if (question && reply?.role === 'assistant') {
      await post('/api/memories', { project_id: project.id, kind: 'question', key: reply.id, body: question.slice(0, 450) }).catch(() => {});
    }
  }
  if (epoch !== revision) return;
  if (writing && project) {
    const activeProject = project;
    chatDraftContext = intent;
    if (!editor.doc || /\b(?:neues|nächstes|weiteres|neuen|nächsten)\s+(?:kapitel|artikel|entwurf)\b/iu.test(text)) {
      const title = answer.match(/^#{1,3}\s+(.{1,160})$/mu)?.[1] ?? (intent === 'story' ? 'Erster Entwurf' : project.name);
      const result = await api.documents({ project_id: project.id, title, kind: intent === 'story' ? 'chapter' : 'article', body: answer, lang: prefs.lang });
      if (epoch !== revision) return;
      await record('assistant', 'Der Entwurf ist im Chat gespeichert.', { kind: 'document', document_id: result.id });
    } else {
      const reply = messages.at(-1);
      if (reply?.role === 'assistant') await record('assistant', 'Du kannst den Vorschlag im Editor als Entwurf übernehmen.',
        { kind: 'draft-option', document_id: editor.doc.id, message_id: reply.id });
    }
    const next = await api.project(activeProject.id);
    if (epoch === revision) project = next;
  }
}

async function exportFromChat(text: string) {
  await record('user', text);
  const format = /mdx/iu.test(text) ? 'mdx' : 'md';
  if (!editor.doc && project?.documents[0]) editor.open(await api.document(project.documents[0].id));
  if (!editor.doc) {
    await record('assistant', 'Öffne das Dokument in der Bibliothek. Im Editor kannst du das Exportformat auswählen.');
    return;
  }
  await editor.export(format);
  await record('assistant', format === 'mdx' ? 'Der Astro-MDX-Download wurde gestartet.' : 'Der Markdown-Download wurde gestartet.');
  keepLocation(editor.doc.id);
}

function updateJobCard(id: string, kind: string) {
  const card = main.querySelector<HTMLElement>(`[data-job="${id}"]`);
  if (!card) return;
  const opened = new Map(Array.from(card.querySelectorAll<HTMLDetailsElement>('details'),
    (detail, index) => [detail.dataset.jobDetail ?? String(index), detail.open]));
  const active = card.contains(document.activeElement) ? (document.activeElement as HTMLElement).dataset.action : '';
  card.innerHTML = jobContent(kind, id);
  card.querySelectorAll<HTMLDetailsElement>('details').forEach((detail, index) => {
    const wasOpen = opened.get(detail.dataset.jobDetail ?? String(index));
    if (wasOpen !== undefined) detail.open = wasOpen;
  });
  if (active) card.querySelector<HTMLElement>(`[data-action="${active}"]`)?.focus();
  if (active === 'pause-research' || active === 'resume-research') {
    card.querySelector<HTMLElement>('[data-action="pause-research"], [data-action="resume-research"]')?.focus();
  }
}

function refreshJobs() {
  for (const card of main.querySelectorAll<HTMLElement>('[data-job]')) {
    const id = card.dataset.job!;
    if (validId(id)) void poll(card.dataset.kind!, id);
  }
}

async function poll(kind: string, id: string, force = false) {
  if (polling.has(id)) return;
  const previous = kind === 'image' ? imageJobs.get(id) : kind === 'chat-task' ? chatTasks.get(id) :
    kind === 'story-job' ? storyJobs.get(id) : kind === 'production-job' ? productionJobs.get(id) : researchJobs.get(id);
  if (previous && ended(previous.status) && !force) return;
  polling.add(id);
  try {
    if (kind === 'production-job') {
      const job = await productionJob(id);
      let changed = JSON.stringify(job) !== JSON.stringify(previous);
      await Promise.all((job.chapter_results ?? []).map(async chapter => {
        if (productionDocuments.get(chapter.id)?.version === chapter.version) return;
        const document = await api.document(chapter.id);
        if (productionDocuments.get(chapter.id)?.version !== document.version) changed = true;
        productionDocuments.set(chapter.id, document);
      }));
      productionJobs.set(id, job);
      if (changed) updateJobCard(id, kind);
      if (previous && job.status !== previous.status && job.status === 'completed') {
        announce(job.kind === 'story' ? 'Die Geschichte ist fertig.' :
          job.kind === 'planning' && !job.plan_version ? 'Die Antwort liegt im Chat vor.' : 'Die Story-Planung liegt vor.');
      }
    } else if (kind === 'story-job') {
      const job = await storyJob(id);
      storyJobs.set(id, job);
      if (JSON.stringify(job) !== JSON.stringify(previous)) updateJobCard(id, kind);
      if (ended(job.status) && !ended(previous?.status ?? '')) {
        if (job.status === 'completed' && project?.id === job.project_id) {
          await refreshStory(job.project_id);
          const open = editor.doc;
          if (open?.id === job.document_id && !editor.dirty && job.action === 'generate' &&
              job.version && job.version > open!.version) {
            const updated = await api.document(job.document_id!);
            if (editor.doc === open && !editor.dirty) {
              editor.open(updated);
              renderEditor();
            }
          }
        }
        announce(job.status === 'completed' ? 'Schreibauftrag abgeschlossen.' : 'Schreibauftrag beendet.');
      }
    } else if (kind === 'chat-task') {
      const task = await json<Task>('/api/chat/tasks/' + id);
      if (validId(task.document_id) && !taskDocuments.has(task.document_id)) {
        taskDocuments.set(task.document_id, await api.document(task.document_id));
      }
      chatTasks.set(id, task);
      if (JSON.stringify(task) !== JSON.stringify(previous)) updateJobCard(id, kind);
      if (main.querySelector(`[data-job="${id}"]`) && session && validId(task.project_id) &&
          task.document_id && task.document_id !== (previous as Task | undefined)?.document_id) {
        const sid = session.id;
        const epoch = revision;
        await refreshChatContext(sid, epoch);
        if (epoch === revision && project?.id === task.project_id) await refreshStory(task.project_id);
      }
      if (ended(task.status) && !ended(previous?.status ?? '')) {
        announce(task.status === 'completed' ? 'Kreativauftrag abgeschlossen.' : 'Kreativauftrag beendet. Prüfe die einzelnen Schritte im Chat.');
      }
    } else if (kind === 'image') {
      const job = await json<ImageJob>('/api/images/jobs/' + id);
      imageJobs.set(id, job);
      if (JSON.stringify(job) !== JSON.stringify(previous)) updateJobCard(id, kind);
      if (job.status === 'completed' && previous?.status !== job.status) announce('Das Bild ist fertig.');
    } else {
      const job = await json<ResearchJob>('/api/research/' + id);
      const docId = job.result?.document_id;
      if (validId(docId) && !dossiers.has(docId)) dossiers.set(docId, await api.document(docId));
      researchJobs.set(id, job);
      if (JSON.stringify(job) !== JSON.stringify(previous)) updateJobCard(id, kind);
      if (job.status === 'completed' && previous?.status !== job.status) announce('Das Recherchedossier ist fertig.');
    }
  } catch {
    const card = main.querySelector(`[data-job="${id}"]`);
    if (!previous && card) card.textContent = 'Auftragsstatus vorübergehend nicht erreichbar. Das Studio versucht es erneut.';
  } finally { polling.delete(id); }
}

function closeNav() {
  if (navDialog.open) navDialog.close();
}

async function openDocument(id: string) {
  if (!validId(id)) return;
  if (!session) {
    go('#document/' + id);
    return;
  }
  const epoch = revision;
  const doc = await api.document(id);
  const nextProject = project?.id === doc.project_id ? project : await api.project(doc.project_id).catch(() => project);
  if (epoch !== revision) return;
  project = nextProject;
  await loadStory(nextProject).catch(() => {});
  if (epoch !== revision) return;
  editor.open(doc);
  keepLocation(id);
  render('editor');
}

function closeEditor() {
  editor.close();
  if (!session && project) {
    go('#project/' + project.id);
    return;
  }
  keepLocation();
  render();
  const open = $('[data-action="open-doc"]');
  (open ?? $('#prompt'))?.focus();
}

function createDocument(source?: Document) {
  if (!project) return;
  const p = project;
  const defaultTitle = source ? 'Entwurf: ' + source.title : p.kind === 'novel' || p.kind === 'story' ? 'Kapitel ' + (p.documents.length + 1) : '';
  dialogForm('Neues Dokument', `<label for="new-title">Titel</label><input id="new-title" class="field" name="title" required maxlength="180" value="${esc(defaultTitle)}">`, 'Erstellen', async data => {
    const kind = source ? 'article' : ['story', 'novel'].includes(p.kind) ? 'chapter' : p.kind === 'article' || p.kind === 'devlog' ? p.kind : 'doc';
    const { id } = await api.documents({ project_id: p.id, title: String(data.get('title')).trim(), body: source?.body ?? '', lang: p.lang, kind });
    project = await api.project(p.id);
    await openDocument(id);
  });
}

const getMemories = (id: string) => json<Memory[]>('/api/projects/' + id + '/memories');
async function projectNotes() {
  const p = project;
  if (!p) return;
  const [notes, decisions] = await Promise.all([
    getMemories(p.id),
    p.kind === 'game' ? json<Decision[]>('/api/projects/' + p.id + '/decisions') : [],
  ]);
  const entries = notes.filter(n => !['decision', 'image', 'document-image'].includes(n.kind));
  showDialog('Notizen', `${entries.length ? `<ul class="plain-list note-list">${entries.map(n =>
    `<li><strong>${esc(n.kind === 'voice-profile' ? 'Schreibstimme · ' + n.key : n.kind === 'question' ? 'Offene Frage' : n.key)}</strong>
      <p>${esc(n.body)}</p></li>`).join('')}</ul>` : '<p>Hier findest du Figuren, offene Fragen und andere Notizen zu diesem Chat.</p>'}
    <div class="dialog-actions">${button('add-note', 'Notiz hinzufügen', 'plus', 'button')}
    ${button('add-voice', 'Schreibstimme hinterlegen', undefined, 'button')}
    ${p.kind === 'story' || p.kind === 'novel' ? button('continuity', 'Kontinuität prüfen', undefined, 'button') : ''}
    ${decisions.length ? button('decisions', 'Decision Log', 'game', 'button') : ''}</div>`);
}

function addNote(voice: boolean) {
  const pid = project?.id;
  if (!pid) return;
  const kind = [['bible', 'Allgemein'], ['character', 'Figur'], ['place', 'Ort'], ['plot', 'Handlung'], ['timeline', 'Zeitlinie'], ['continuity', 'Kontinuität'], ['question', 'Offene Frage']];
  dialogForm(voice ? 'Schreibstimme' : 'Notiz', `<label for="note-key">Name</label><input id="note-key" class="field" name="key" maxlength="120" required>
    ${voice ? '' : `<label for="note-type">Kategorie</label><select id="note-type" class="field" name="kind">${kind.map(([k, l]) => option(k, l)).join('')}</select>`}
    <label for="note-body">${voice ? 'Stimme beschreiben' : 'Notiz'}</label><textarea id="note-body" class="field" name="body" rows="4" maxlength="5000" required></textarea>`,
  'Speichern', async data => {
    await post(voice ? '/api/voices' : '/api/memories', {
      project_id: pid, [voice ? 'name' : 'key']: String(data.get('key')).trim(), kind: data.get('kind'), body: String(data.get('body')).trim(),
    });
    announce(voice ? 'Schreibstimme gespeichert.' : 'Notiz gespeichert.');
    await projectNotes();
  });
}

async function checkContinuity() {
  if (!project || !editor.doc) {
    showDialog('Kontinuität prüfen', '<p>Öffne zuerst ein Kapitel im Editor.</p>');
    return;
  }
  const p = project;
  const text = editor.body;
  showDialog('Kontinuität prüfen', '<p id="continuity-output" role="status">Kapitel wird mit deinen Notizen verglichen …</p>');
  try {
    const notes = (await getMemories(p.id)).filter(n => !['image', 'decision', 'document-image'].includes(n.kind)).map(n => n.key + ': ' + n.body).join('\n');
    const answer = await stream('/api/write', { model: 'human-audit', lang: p.lang, mode: 'audit',
      instruction: 'Melde Widersprüche zwischen Notizen und Kapitel.\n' + notes.slice(0, 6000) + '\nKapitel:\n' + text.slice(0, 20000) }, () => {});
    if ($('#continuity-output', details)) showDialog('Kontinuität prüfen', '<div class="prose">' + markdown(answer) + '</div>');
  } catch (error) {
    const out = $('#continuity-output', details);
    if (out) out.textContent = describe(error, 'Die Kontinuitätsprüfung ist gerade fehlgeschlagen.');
  }
}

const decisionStatuses = { idee: 'Idee', diskussion: 'In Diskussion', vorgeschlagen: 'Vorgeschlagen', beschlossen: 'Beschlossen', verworfen: 'Verworfen', spaeter: 'Später prüfen' };
async function decisionLog() {
  if (!project) return;
  const p = project;
  const items = await json<Decision[]>('/api/projects/' + p.id + '/decisions');
  showDialog('Decision Log', `${items.length ? `<ul class="plain-list note-list">${items.map(d => `<li><strong>${esc(d.title)}</strong>
     <p>${esc(decisionStatuses[d.status as keyof typeof decisionStatuses] ?? d.status)}${d.rationale ? ' · ' + esc(d.rationale) : ''}</p>
     ${button('edit-decision', 'Bearbeiten', undefined, 'button quiet', d.key)}</li>`).join('')}</ul>` : '<p>Halte hier Entscheidungen zu deiner Spielidee fest.</p>'}
     <div class="dialog-actions">${button('new-decision', 'Entscheidung hinzufügen', 'plus', 'button primary')}${button('gdd', 'GDD herunterladen', 'text', 'button')}</div>`);
}

async function saveDecision(title: string, state: string, rationale: string, key?: string) {
  if (!project || !title.trim()) throw new Error('decision_required');
  await post('/api/decisions', { project_id: project.id, title, status: state, rationale, key, engine: /godot/i.test(title) ? 'Godot' : '' });
}

async function editDecision(key?: string) {
  if (!project) return;
  const item = key ? (await json<Decision[]>('/api/projects/' + project.id + '/decisions')).find(d => d.key === key) : undefined;
  dialogForm(item ? 'Entscheidung bearbeiten' : 'Neue Entscheidung', `<label for="decision-title">Entscheidung</label>
    <input id="decision-title" name="title" class="field" required maxlength="300" value="${esc(item?.title ?? '')}">
    <label for="decision-state">Stand</label><select id="decision-state" name="state" class="field">
      ${Object.entries(decisionStatuses).map(([k, v]) => option(k, v, k === (item?.status ?? 'beschlossen'))).join('')}</select>
    <label for="decision-reason">Begründung (optional)</label><textarea id="decision-reason" name="reason" class="field" rows="3" maxlength="2000">${esc(item?.rationale ?? '')}</textarea>`,
  'Speichern', async data => {
    await saveDecision(String(data.get('title')), String(data.get('state')), String(data.get('reason')), item?.key);
    announce('Entscheidung gespeichert.');
    await decisionLog();
  });
}

async function imageInfo(id: string, linked = false) {
  return json<ImageItem>('/api/images/gallery/' + id + (linked ? '?linked=1' : ''));
}

async function previewImage(id: string) {
  if (!safeImageId(id)) return;
  const item = await imageInfo(id, true);
  showDialog('Bildvorschau', `<img class="large-image" src="${imageUrl(id)}" alt="${esc(item.request?.prompt ?? 'Generiertes Bild')}">
    ${item.trashed ? '<p>Das Bild liegt im Papierkorb und wird noch verwendet.</p>' : `<div class="dialog-actions">${button('save-image', 'Zum Chat hinzufügen', undefined, 'button', id)}
      ${button('insert-image', 'In Dokument einfügen', undefined, 'button', id)}
      ${button('regen', 'Erneut generieren', undefined, 'button', id)}${button('variant', 'Variante erstellen', undefined, 'button', id)}
      ${organizer.menuButton({ kind: 'image', id, name: item.name ?? item.request?.prompt ?? 'Bild', folder_id: item.folder_id })}</div>`}`);
}

async function storeImage(id: string) {
  if (!safeImageId(id)) return;
  const item = await imageInfo(id);
  const save = async (sid: string, cover: boolean) => {
    const { project_id: pid } = await post<{project_id: string}>(`/api/sessions/${sid}/context`, { kind: 'image', lang: prefs.lang });
    await post('/api/memories', { project_id: pid, kind: 'image', key: id, body: item.request?.prompt ?? 'Generiertes Bild' });
    if (cover) await post('/api/projects/' + pid, { cover: id });
    if (session?.id === sid) await refreshChatContext(sid, revision);
    setStatus('Bild im Chat gespeichert.');
    announce('Bild im Chat gespeichert.');
  };
  if (session) {
    await save(session.id, false);
    if (details.open) details.close();
    return;
  }
  const list = await api.sessions();
  if (!list.length) { showDialog('Zum Chat hinzufügen', '<p>Öffne zuerst einen Chat.</p>'); return; }
  dialogForm('Zum Chat hinzufügen', `<label for="image-chat">Chat</label><select id="image-chat" name="chat" class="field" required>
    ${list.map(item => option(item.id, item.title || 'Unterhaltung')).join('')}</select>
    <label class="check-field"><input name="cover" type="checkbox"> Als Titelbild verwenden</label>`, 'Speichern',
    async data => save(String(data.get('chat')), data.has('cover')));
}

async function insertImage(id: string) {
  if (!safeImageId(id)) return;
  const image = await imageInfo(id);
  const alt = image.request?.prompt ?? 'Generiertes Bild';
  if (editor.doc) {
    if (details.open) details.close();
    editor.insertImage(id, alt);
    focusEditor();
    return;
  }
  const docs = await allDocuments();
  if (!docs.length) { showDialog('Bild in Dokument einfügen', '<p>Lege zuerst ein Dokument im Chat an.</p>'); return; }
  dialogForm('Bild in Dokument einfügen', `<label for="image-doc">Dokument</label><select id="image-doc" class="field" name="doc">
    ${docs.map(d => option(d.id, d.title || 'Ohne Titel')).join('')}</select>`, 'Einfügen', async data => {
    const doc = await api.document(String(data.get('doc')));
    project = await api.project(doc.project_id);
    editor.open(doc);
    keepLocation(doc.id);
    if (details.open) details.close();
    render('editor');
    editor.insertImage(id, alt);
  });
}

async function selectImageForEditor() {
  const list = await galleryPage();
  showDialog('Bild einfügen', list.length ? `<div class="gallery-grid dialog-gallery">${list.filter(im => safeImageId(im.id)).map(im =>
    `<button type="button" class="image-button" data-action="insert-image" data-value="${im.id}"><img src="${imageUrl(im.id)}" alt="${esc(im.request?.prompt?.slice(0, 100) || 'Generiertes Bild')}" loading="lazy"></button>`).join('')}</div>`
    : '<p>In der Galerie liegen noch keine Bilder. Du kannst im Chat ein Bild erstellen.</p>');
}

async function jobHistory() {
  const list = await json<Array<{ id: string; state: string; payload?: { request?: { prompt?: string } } }>>('/api/images/jobs');
  const groups = [
    ['Fehlgeschlagen oder abgebrochen', list.filter(job => ['failed', 'cancelled'].includes(job.state))],
    ['Laufend und abgeschlossen', list.filter(job => !['failed', 'cancelled'].includes(job.state))],
  ] as const;
  showDialog('Bildaufträge', list.length ? groups.map(([title, jobs]) => `<details${jobs.length ? ' open' : ''}><summary>${title} (${jobs.length})</summary>
    <ul class="plain-list note-list">${jobs.map(j => `<li><strong>${esc(imageStates[j.state] ?? j.state)}</strong>
      <p>${esc(j.payload?.request?.prompt ?? 'Bildauftrag')}</p>${!ended(j.state) ? button('cancel-image', 'Bildauftrag abbrechen', undefined, 'button', j.id) : ''}</li>`).join('')}</ul></details>`).join('')
    : '<p>Bildaufträge aus deinen Unterhaltungen erscheinen hier.</p>');
}

async function runAgain(id: string, variant: boolean) {
  if (!safeImageId(id) || busy) return;
  if (details.open) details.close();
  busy = true;
  const previous = revision;
  try {
    const text = variant ? 'Erstelle eine Variante dieses Bildes.' : 'Generiere dieses Bild erneut.';
    await ensureSession(text);
    await enqueue('image', text, { id, variant });
    if (previous === revision) {
      keepLocation(editor.doc?.id);
      announce('Bildauftrag gestartet.');
    }
  } finally {
    if (previous === revision) {
      busy = false;
      render('prompt');
      refreshJobs();
      void loadNavigation().catch(() => {});
    }
  }
}

async function search(query: string) {
  const output = $('#search-results')!;
  output.innerHTML = '<p>Suche läuft …</p>';
  const qs = query.trim();
  if (!qs) { output.textContent = 'Gib einen Suchbegriff ein.'; return; }
  const [chats, found] = await Promise.all([
    json<Session[]>('/api/sessions?q=' + encodeURIComponent(qs)),
    api.search(qs),
  ]);
  if (!output.isConnected) return;
  output.innerHTML = `${chats.length ? `<section class="collection-section"><h2>Unterhaltungen</h2>${chats.map(s => `<div class="organizer-row"><a class="history-item" href="#chat/${path(s.id)}">${icon('chat')}${esc(s.title || 'Unterhaltung')}</a>${organizer.menuButton(chatEntry(s))}</div>`).join('')}</section>` : ''}
    ${found.length ? `<section class="collection-section"><h2>Dokumente</h2><ul class="plain-list note-list">${found.map(d => `<li>${button('open-doc', d.title || 'Ohne Titel', 'text', 'button quiet', d.document_id)}<p>${esc(d.hit)}</p></li>`).join('')}</ul></section>` : ''}
    ${chats.length + found.length ? '' : '<p>Keine Treffer. Versuche einen anderen Suchbegriff.</p>'}`;
  announce(`${chats.length + found.length} Treffer`);
}

async function loadStory(p?: Project) {
  if (!p || !storyProject(p)) return;
  const next = await storyInfo(p.id);
  if (project?.id === p.id) {
    story = next;
    storyFor = p.id;
  }
}

async function refreshStory(id: string) {
  const epoch = revision;
  const current = await api.project(id);
  if (epoch !== revision || project?.id !== id) return;
  project = current;
  await loadStory(current);
  if (epoch !== revision) return;
  const section = $('.story-section');
  if (section && storyFor === id && story) section.outerHTML = storyMarkup(story);
  const outline = $('.project-outline');
  if (outline) outline.outerHTML = projectOverview(false);
  const tools = $('.story-chapter-tools');
  const chapter = story?.chapters.find(item => item.id === editor.doc?.id);
  if (tools && chapter) tools.outerHTML = chapterTools(chapter);
}

async function queueStory(request: StoryRequest, message: string) {
  const p = project;
  if (!p) return;
  if (['generate', 'review-chapter'].includes(request.action) && !request.values.document_id) {
    throw new ApiError(404, 'story_chapter_missing');
  }
  const epoch = revision;
  const ready = await ensureSession(message);
  if (ready.project_id !== p.id) {
    await post('/api/sessions/' + ready.id + '/context', { context_id: p.id });
    ready.project_id = p.id;
  }
  await storyPost(p.id, request.action, { ...request.values, message, session_id: ready.id });
  if (epoch !== revision) return;
  messages = await api.messages(ready.id);
  if (epoch !== revision) return;
  if (details.open) details.close();
  render();
  refreshJobs();
  void loadNavigation().catch(() => {});
}

async function handleStory(action: string, value: string) {
  if (action === 'story-open') {
    if (details.open) details.close();
    await openDocument(value);
    return;
  }
  const p = project;
  if (!p) return;
  if (action === 'story-cancel') {
    await storyPost(p.id, 'cancel', { job_id: value });
    await poll('story-job', value, true);
    return;
  }
  await loadStory(p);
  if (project?.id !== p.id) return;
  const info = story;
  if (!info || storyFor !== p.id) return;
  const chapter = info.chapters.find(item => item.id === value);
  if (action === 'story-menu') {
    showDialog('Story-Kapitel', storyMarkup(info, true, editor.doc?.id));
  } else if (action === 'story-settings') {
    settingsDialog(info, p.documents, async body => {
      await storyPost(p.id, 'settings', body);
      await refreshStory(p.id);
    });
  } else if (action === 'story-plan' || (action === 'story-edit-plan' && chapter)) {
    chapterPlanDialog(info, chapter, async body => {
      await storyPost(p.id, chapter ? 'edit-plan' : 'plan', body);
      await refreshStory(p.id);
    });
  } else if (action === 'story-outline') {
    requestDialog('outline', undefined, queueStory);
  } else if (action === 'story-review-all') {
    requestDialog('review-story', undefined, queueStory);
  } else if (action === 'story-next') {
    const next = info.chapters.find(item => item.status === 'planned');
    if (next) requestDialog('generate', next, queueStory);
  } else if (action === 'story-chapter' && chapter) {
    chapterMenu(chapter);
  } else if ((action === 'story-write' || action === 'story-redraft') && chapter) {
    if (editor.doc?.id === chapter.id && editor.dirty) throw new ApiError(409, 'story_save_first');
    requestDialog('generate', chapter, queueStory, action === 'story-redraft');
  } else if (action === 'story-review' && chapter) {
    requestDialog('review-chapter', chapter, queueStory);
  } else if ((action === 'story-approve' || action === 'story-draft') && chapter) {
    const approve = action === 'story-approve';
    if (editor.doc?.id === chapter.id && editor.dirty) throw new ApiError(409, 'story_save_first');
    dialogForm(approve ? 'Kapitel freigeben?' : 'Freigabe aufheben?',
      approve ? '<p>Die gespeicherte Fassung wird bis zum Aufheben der Freigabe vor Änderungen geschützt.</p>' :
        '<p>Das Kapitel kann wieder bearbeitet werden.</p>',
      approve ? 'Kapitel freigeben' : 'Freigabe aufheben', async () => {
        const version = editor.doc?.id === chapter.id ? editor.doc.version : chapter.version;
        await storyPost(p.id, 'status', { document_id: chapter.id, version, status: approve ? 'approved' : 'draft' });
        await refreshStory(p.id);
        if (editor.doc?.id === chapter.id) {
          editor.open(await api.document(chapter.id));
          renderEditor();
        }
        announce(approve ? 'Kapitel freigegeben.' : 'Freigabe aufgehoben.');
      });
  }
}

async function handleProduction(action: string, value: string) {
  const pid = validId(value) ? value : project?.id;
  const refresh = async () => {
    if (!session) return;
    messages = await api.messages(session.id);
    render();
    refreshJobs();
  };
  if (action === 'production-propose' || action === 'production-plan') {
    const info = pid ? await productionInfo(pid) : undefined;
    if (info?.plan && pid) { planDialog(info, pid); return; }
    if (info?.job && ['queued', 'running', 'paused', 'failed'].includes(info.job.status)) {
      setStatus('Die Planung steht im Chatverlauf.');
      return;
    }
    proposeDialog(prefs.lang, draft, async values => {
      const ready = await ensureSession('Story-Planung');
      const { project_id: id } = await post<{ project_id: string }>(`/api/sessions/${ready.id}/context`, { kind: 'story', lang: prefs.lang });
      await refreshChatContext(ready.id, revision);
      await productionAct(id, 'propose', { ...values, session_id: ready.id, image: options.image });
      draft = '';
      await refresh();
    });
    return;
  }
  if (action === 'production-plan-version') {
    const [projectId, version] = value.split(':');
    if (validId(projectId)) planDialog(await productionInfo(projectId, Number(version)), projectId);
    return;
  }
  if (action === 'production-audit-plan') {
    if (details.open) details.close();
    await submit('Prüfe unsere Story-Planung auf Widersprüche.', 'story');
    return;
  }
  if (action === 'production-adopt-plan' && pid) {
    const [job_id, version] = value.split(':');
    if (!validId(job_id)) return;
    await productionAct(pid, 'resume', { job_id, plan_version: Number(version) });
    if (details.open) details.close();
    await refresh();
    return;
  }
  if (action === 'production-edit' && pid) {
    const info = await productionInfo(pid);
    editPlanDialog(info, async values => {
      await productionAct(pid, 'save-plan', { ...values, session_id: session?.id });
      await refresh();
      const updated = await productionInfo(pid);
      if (updated.version !== info.version) planDialog(updated, pid);
    });
    return;
  }
  if ((action === 'production-approve' || action.startsWith('production-start-')) && pid) {
    const info = await productionInfo(pid);
    if (action === 'production-approve') {
      await productionAct(pid, 'approve-plan', { version: info.version, accept_impact: true });
      planDialog(await productionInfo(pid), pid);
    } else {
      await productionAct(pid, 'start', { version: info.version, session_id: session?.id,
        mode: action.endsWith('-together') ? 'together' : 'automatic' });
      if (details.open) details.close();
      await refresh();
    }
    return;
  }
  if (action === 'production-manuscript' && pid) {
    manuscriptDialog(await manuscript(pid), pid);
    return;
  }
  if (action === 'production-read-chapter' || action === 'production-export') {
    const [projectId, parameter] = value.split(':');
    if (!validId(projectId)) return;
    if (action === 'production-read-chapter') manuscriptDialog(await manuscript(projectId), projectId, Number(parameter));
    else await exportManuscript(projectId, parameter);
    return;
  }
  if (action === 'production-edit-chapter' && validId(value)) {
    await openDocument(value);
    if (editor.doc?.id === value && editor.doc.status === 'approved') {
      const doc = editor.doc;
      dialogForm('Kapitel zur Überarbeitung öffnen',
        '<p>Eine Änderung erfordert eine neue Prüfung des Kapitels und seiner Bildzuordnung.</p>', 'Freigabe aufheben', async () => {
          await storyPost(doc.project_id, 'status', { document_id: doc.id, version: doc.version, status: 'draft' });
          editor.open(await api.document(value));
          renderEditor();
        });
    }
    return;
  }
  if (action === 'production-export-chapter' && validId(value)) {
    const doc = await api.document(value);
    const asset = [...productionJobs.values()].flatMap(job => job.chapter_results ?? []).find(c => c.id === value && c.version === doc.version)?.image;
    const title = doc.title || 'Kapitel';
    const image = asset ? '\n\n![' + asset.alt.replace(/[\[\]\r\n]/g, ' ') + '](' + imageUrl(asset.id) + ')' : '';
    download(title.replace(/[\/\\]/g, '-') + '.md', '# ' + title + image + '\n\n' + doc.body);
    return;
  }
  if (action === 'production-art-variant') {
    const [id, number] = value.split(':');
    const production = productionJobs.get(id);
    if (!production) return;
    dialogForm('Illustration überarbeiten',
      '<label for="art-instruction">Was soll sich ändern?</label><textarea class="field" id="art-instruction" name="instruction" maxlength="400"></textarea>',
      'Bildvariante erzeugen', async data => {
        await productionAct(production.project_id, 'regenerate-art', { job_id: id, number: Number(number), instruction: data.get('instruction') });
        await poll('production-job', id, true);
      });
    return;
  }
  const job = productionJobs.get(value);
  if (job && action === 'production-approve-art') {
    artReviewDialog(job, imageMedia);
    return;
  }
  if (job && action === 'production-confirm-art') {
    await productionAct(job.project_id, 'approve-art', { job_id: job.id });
    if (details.open) details.close();
    await poll('production-job', value, true);
    return;
  }
  if (job && ['production-pause', 'production-resume', 'production-retry', 'production-cancel'].includes(action)) {
    await productionAct(job.project_id, action.slice('production-'.length), { job_id: value });
    await poll('production-job', value, true);
  }
}

async function handle(action: string, value: string) {
  if (action.startsWith('production-')) { await handleProduction(action, value); return; }
  if (action === 'write-unwritten' && /^[1-9]\d*$/.test(value)) { await submit('Schreibe Kapitel ' + value, 'story'); return; }
  if (action.startsWith('story-')) { await handleStory(action, value); return; }
  if (action.startsWith('organizer-')) { await organizer.handle(action, value); return; }
  switch (action) {
    case 'new': go('#chat'); break;
    case 'reload-view': await loadRoute(true); break;
    case 'search': case 'settings': case 'archive': case 'trash': go('#' + action); break;
    case 'library': go('#library/docs'); break;
    case 'close-nav': closeNav(); break;
    case 'theme': {
      prefs.theme = prefs.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = prefs.theme;
      if (route.view === 'settings') {
        render();
        main.querySelector<HTMLElement>('[data-action="theme"]')?.focus();
      } else {
        header();
        $('#header-actions button')?.focus();
      }
      break;
    }
    case 'tools': openTools(); break;
    case 'mode':
    case 'suggestion':
      if (details.open) details.close();
      if (value === 'auto' || value === 'chat' || tools.some(t => t.id === value)) selectTool(value as Mode, true);
      break;
    case 'clarify-tool': await submit(clarify, value as Intent); break;
    case 'stop': controller?.abort(); break;
    case 'research-options': toolsOptions('research'); break;
    case 'image-options': toolsOptions('image'); break;
    case 'game-role':
      showDialog('Rolle für die Spielidee', `<div class="dialog-actions">${Object.entries(roles).map(([k, v]) =>
        button('set-role', v, 'game', k === gameRole ? 'button primary' : 'button', k)).join('')}</div>`);
      break;
    case 'set-role':
      if (value in roles) gameRole = value as keyof typeof roles;
      details.close(); render('prompt');
      break;
    case 'contents': await openContents(); break;
    case 'switch-context':
      if (session) {
        const sid = session.id;
        await post('/api/sessions/' + sid + '/context', { context_id: value });
        editor.close();
        keepLocation();
        await refreshChatContext(sid, revision);
        render();
        await openContents();
      }
      break;
    case 'choose-chat-target': {
      const pending = pendingChoice;
      if (!pending) break;
      pendingChoice = undefined;
      if (details.open) details.close();
      mode = pending.mode;
      await submit(pending.text, undefined, pending.kind === 'context' ? {context_id: value} : {chapter_id: value});
      break;
    }
    case 'open-doc': await openDocument(value); break;
    case 'open-editorial-run': {
      const meta = messages.find(message => message.id === value)?.meta;
      if (validId(meta?.document_id) && validId(meta?.run_id)) {
        if (editor.doc?.id !== meta.document_id) await openDocument(meta.document_id);
        if (editor.doc?.id === meta.document_id) await editor.showEditorial(meta.run_id);
      }
      break;
    }
    case 'replace-draft': {
      const attachment = messages.find(message => message.id === value)?.meta;
      const source = messages.find(message => message.id === attachment?.message_id);
      if (validId(attachment?.document_id) && source?.role === 'assistant') {
        showDialog('Vorschlag übernehmen', '<p>Der Vorschlag ersetzt den Text im Editor. Deine gespeicherte Fassung bleibt bis zum Speichern erhalten.</p>' +
          button('apply-draft', 'Übernehmen', undefined, 'button primary', value));
      }
      break;
    }
    case 'apply-draft': {
      const attachment = messages.find(message => message.id === value)?.meta;
      const source = messages.find(message => message.id === attachment?.message_id);
      if (validId(attachment?.document_id) && source?.role === 'assistant') {
        details.close();
        if (editor.doc?.id !== attachment.document_id) await openDocument(attachment.document_id);
        if (editor.doc?.id === attachment.document_id) editor.applySuggestion(source.content);
        focusEditor();
      }
      break;
    }
    case 'close-editor': closeEditor(); break;
    case 'upload-attachment': if (session) await organizer.upload(await ensureProject('custom', session.title)); break;
    case 'create-document': if (session) { await ensureProject('custom', session.title); createDocument(); } break;
    case 'import-dossier': {
      const docs = (await allDocuments()).filter(d => d.kind === 'dossier');
      if (!docs.length) showDialog('Dossier verwenden', '<p>Starte zuerst eine Recherche im Chat, um ein Dossier zu erstellen.</p>');
      else dialogForm('Dossier verwenden', `<label for="dossier-doc">Dossier</label><select class="field" id="dossier-doc" name="doc">${docs.map(d => option(d.id, d.title)).join('')}</select>`,
        'Weiter', async data => { createDocument(await api.document(String(data.get('doc')))); });
      break;
    }
    case 'project-notes': await projectNotes(); break;
    case 'add-note': addNote(false); break;
    case 'add-voice': addNote(true); break;
    case 'continuity': await checkContinuity(); break;
    case 'decisions': await decisionLog(); break;
    case 'new-decision': await editDecision(); break;
    case 'edit-decision': await editDecision(value); break;
    case 'gdd': {
      const result = await post<{ gdd: string }>('/api/gdd', { project_id: project?.id });
      download('game-design.md', result.gdd);
      break;
    }
    case 'more-images': await loadImages(); break;
    case 'preview-image': await previewImage(value); break;
    case 'save-image': await storeImage(value); break;
    case 'insert-image': await insertImage(value); break;
    case 'editor-images': await selectImageForEditor(); break;
    case 'regen': case 'variant': await runAgain(value, action === 'variant'); break;
    case 'job-history': await jobHistory(); break;
    case 'cancel-image':
      if (validId(value)) {
        await post('/api/images/jobs/' + value + '/cancel');
        const parent = [...chatTasks.entries()].find(([, task]) => task.image?.id === value);
        await (parent ? poll('chat-task', parent[0], true) : poll('image', value, true));
        if (details.open) await jobHistory();
      }
      break;
    case 'cancel-research': case 'pause-research': case 'resume-research':
      if (validId(value)) {
        const command = action.split('-')[0];
        await post('/api/research/' + value + '/' + command);
        await poll('research', value, true);
        announce(command === 'pause' ? 'Recherche pausiert.' : command === 'cancel' ? 'Recherche abgebrochen.' : 'Recherche wird fortgesetzt.');
      }
      break;
    case 'services': {
      const available = await api.status();
      const upstream = available.upstream as Array<{ service: string; ok: boolean }>;
      const profiles = available.aliases as string[];
      showDialog('Dienste und Schreibprofile', `<ul class="plain-list note-list">${upstream.map(s =>
        `<li>${esc(s.service)} · ${s.ok ? 'Bereit' : 'Nicht erreichbar'}</li>`).join('')}</ul>
        <p>Schreibprofile</p><ul>${profiles.map(p => `<li>${esc(p)}</li>`).join('')}</ul>`);
      break;
    }
    default:
      if (action.startsWith('editor-')) await editor.action(action, value);
  }
}

document.addEventListener('click', event => {
  const button = (event.target as Element).closest<HTMLButtonElement>('button');
  if (!button) return;
  if (button === navToggle) {
    if (mobile.matches) navDialog.showModal();
    else {
      collapsed = !collapsed;
      $('#studio')!.classList.toggle('collapsed', collapsed);
    }
    header();
    return;
  }
  const { action, value } = button.dataset;
  if (!action || pendingButtons.has(button)) return;
  const epoch = revision;
  pendingButtons.add(button);
  void handle(action, value ?? '').catch(error => {
    if (epoch !== revision) return;
    const message = describe(error);
    if (details.open) {
      let failure = $('#dialog-status', details);
      if (!failure) {
        failure = document.createElement('p');
        failure.id = 'dialog-status';
        failure.setAttribute('role', 'status');
        $('.dialog-content', details)?.append(failure);
      }
      failure.textContent = message;
    } else setStatus(message);
  }).finally(() => { pendingButtons.delete(button); });
});

main.addEventListener('input', event => {
  const target = event.target as HTMLTextAreaElement;
  if (target.id === 'prompt') draft = target.value;
  if (target.id === 'doc-title' || target.id === 'draft') editor.input(target);
});
main.addEventListener('select', event => {
  const field = event.target as HTMLTextAreaElement;
  if (field.id === 'draft') editor.remember(field);
});
main.addEventListener('change', event => {
  const field = event.target as HTMLSelectElement;
  if (field.id === 'chat-activity' && field.value in activities) {
    mode = field.value as Mode;
    if (session) chatModes.set(session.id, mode);
  }
  if (field.id === 'response-lang') prefs.lang = field.value === 'en' ? 'en' : 'de';
  if (field instanceof HTMLInputElement && (field.hasAttribute('data-organizer-select') || field.hasAttribute('data-organizer-all'))) organizer.select(field);
  if (field.hasAttribute('data-organizer-sort')) field.form?.requestSubmit();
});
main.addEventListener('keydown', event => {
  const field = event.target as HTMLTextAreaElement;
  if (field.id === 'prompt' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if (field.value.trim() && !busy) field.form?.requestSubmit();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's' && editor.doc) {
    event.preventDefault();
    void editor.action('editor-save', '');
  }
});
main.addEventListener('submit', event => {
  event.preventDefault();
  const form = event.target as HTMLFormElement;
  const values = new FormData(form);
  if (form.hasAttribute('data-organizer-search')) void organizer.search(form).catch(error => setStatus(describe(error)));
  if (form.id === 'composer') void submit(String(values.get('prompt') ?? '').trim()).catch(error => setStatus(describe(error)));
  if (form.id === 'search-form') void search(String(values.get('q') ?? '')).catch(error => {
    if (form.isConnected) { $('#search-results')!.innerHTML = ''; setStatus(describe(error, 'Die Suche ist gerade nicht erreichbar.')); }
  });
});
document.addEventListener('toggle', event => {
  if (event.target instanceof HTMLDetailsElement && event.target.hasAttribute('data-studio-folder')) organizer.toggle(event.target);
}, true);
navDialog.addEventListener('click', event => {
  if ((event.target as Element).closest('a[href^="#"]')) closeNav();
});

const organizerDragType = 'application/x-studio-entry';
document.addEventListener('dragstart', event => {
  const source = (event.target as Element).closest<HTMLElement>('[data-organizer-drag]');
  if (!source || !event.dataTransfer) return;
  event.dataTransfer.setData(organizerDragType, source.dataset.organizerDrag!);
  event.dataTransfer.effectAllowed = 'move';
});
document.addEventListener('dragover', event => {
  const target = (event.target as Element).closest<HTMLElement>('[data-folder-destination]');
  if (!target || !event.dataTransfer?.types.includes(organizerDragType)) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  target.classList.add('organizer-drop-target');
});
document.addEventListener('dragleave', event => {
  const target = (event.target as Element).closest<HTMLElement>('[data-folder-destination]');
  if (target && (!event.relatedTarget || !target.contains(event.relatedTarget as Node))) target.classList.remove('organizer-drop-target');
});
document.addEventListener('drop', event => {
  const target = (event.target as Element).closest<HTMLElement>('[data-folder-destination]');
  const source = event.dataTransfer?.getData(organizerDragType);
  if (!target || !source) return;
  event.preventDefault();
  target.classList.remove('organizer-drop-target');
  void organizer.drop(source, target.dataset.folderDestination ?? '');
});
document.addEventListener('dragend', () => {
  document.querySelectorAll('.organizer-drop-target').forEach(node => node.classList.remove('organizer-drop-target'));
});

navDialog.addEventListener('close', header);
mobile.addEventListener('change', () => { if (!mobile.matches) closeNav(); header(); });
window.addEventListener('hashchange', () => void loadRoute(true));
$('.skip')?.addEventListener('click', event => {
  event.preventDefault();
  main.focus();
});
window.addEventListener('beforeunload', event => {
  if (editor.dirty) event.preventDefault();
});
setInterval(refreshJobs, 1800);
void loadRoute();
void loadNavigation().catch(error => setStatus(describe(error, 'Ordner und Chats konnten gerade nicht geladen werden.')));
