import { esc, json, post } from './core';
import { button, dialogForm, showDialog, storyErrors } from './studio-ui';

export type StoryChapter = {
  id: string; title: string; number: number; plan: string; minimum: number; maximum: number;
  status: string; version: number; words: number; lang: string;
};
type Settings = { lang: 'en' | 'de'; minimum: number; maximum: number; opening: string | null };
export type StoryInfo = { settings: Settings; bible: Record<string, string>; chapters: StoryChapter[] };
export type StoryAction = 'outline' | 'generate' | 'review-chapter' | 'review-story';
export type StoryRequest = { action: StoryAction; values: Record<string, unknown> };
export type StoryJob = {
  id: string; status: string; action: StoryAction; project_id: string; document_id?: string;
  version?: number;
  bible_saved?: boolean; stage?: string; completed_sections?: number; total_sections?: number; words?: number;
  title?: string; error?: string; chapter_ids?: string[]; chapter_status?: string; planned?: number;
  review?: {
    summary?: string; error?: string; chapters_reviewed?: number; repetitions?: string[];
    discarded_findings?: number;
    findings?: Array<{ quote: string; category: string; issue: string }>;
    style?: { skill_version: string; finding_count: number; findings: Array<{ excerpt?: string; why?: string; fix?: string; rule: string }> };
  };
};
type Source = { id: string; title: string; story_number?: number | null };
const chapterStatus: Record<string, string> = { planned: 'Geplant', draft: 'Entwurf', review: 'Zur Freigabe', approved: 'Freigegeben' };
const sections = {
  characters: 'Figuren', relationships: 'Beziehungen', places: 'Schauplätze', world: 'Weltregeln',
  timeline: 'Chronologie', events: 'Wichtige Ereignisse', threads: 'Offene Handlungsstränge',
  perspective: 'Erzählperspektive', voice: 'Stil und Ton',
};
const number = new Intl.NumberFormat('de');
export const chapterLabel = (status: string) => chapterStatus[status] ?? status;
const chapterName = (chapter: StoryChapter) =>
  chapter.number + '. ' + (chapter.title.replace(/^\s*(?:(?:chapter|kapitel)\s+)?\d+\s*[.):–-]\s*/iu, '') || chapter.title);
export const storyInfo = (id: string) => json<StoryInfo>('/api/stories/' + id);
export const storyPost = <T>(id: string, action: string, body: object) => post<T>('/api/stories/' + id + '/' + action, body);
export const storyJob = (id: string) => json<StoryJob>('/api/stories/jobs/' + id);
const numberField = (name: string, label: string, value: number) =>
  `<label for="story-${name}">${label}</label><input class="field" id="story-${name}" name="${name}" type="number"
    min="1" max="2147483647" required value="${value}">`;
const textField = (name: string, label: string, value = '', limit = 5000, required = false) =>
  `<label for="story-${name}">${esc(label)}</label><textarea class="field" id="story-${name}" name="${name}"
    maxlength="${limit}" rows="3"${required ? ' required' : ''}>${esc(value)}</textarea>`;
const wordFields = (range: Pick<Settings, 'minimum' | 'maximum'>) =>
  `<div class="story-word-range"><div>${numberField('minimum', 'Mindestens Wörter', range.minimum)}</div>
    <div>${numberField('maximum', 'Höchstens Wörter', range.maximum)}</div></div>`;

export function storyProgress(chapters: StoryChapter[]) {
  const written = chapters.filter(chapter => chapter.words > 0).length;
  const approved = chapters.filter(chapter => chapter.status === 'approved').length;
  const words = chapters.reduce((total, chapter) => total + chapter.words, 0);
  const min = chapters.reduce((total, chapter) => total + chapter.minimum, 0);
  const max = chapters.reduce((total, chapter) => total + chapter.maximum, 0);
  return chapters.length ?
    `${written} von ${chapters.length} geschrieben · ${approved} freigegeben · ${number.format(words)} von ${number.format(min)}–${number.format(max)} Wörtern` :
    'Noch keine Kapitel geplant.';
}

function chapterList(chapters: StoryChapter[], compact: boolean, active?: string) {
  return chapters.length ? `<ol class="story-chapters plain-list">${chapters.map(chapter => `<li>
    <div class="story-chapter-line"><div>${button('story-open', chapterName(chapter), 'text', 'button quiet', chapter.id)}
    <small>${chapterLabel(chapter.status)} · ${number.format(chapter.words)} Wörter${compact ? '' : ` · Ziel ${number.format(chapter.minimum)}–${number.format(chapter.maximum)}`}</small></div>
    ${chapter.id === active ? '<span class="muted">Geöffnet</span>' : ''}
    ${!compact ? button('story-chapter', 'Aktionen', undefined, 'button quiet', chapter.id) : ''}</div>
    ${!compact ? `<details><summary>Kapitelplan</summary><p>${esc(chapter.plan)}</p></details>` : ''}</li>`).join('')}</ol>` : '';
}

export function storyMarkup(info: StoryInfo, compact = false, active?: string) {
  const chapters = info.chapters;
  const actions = `<div class="editor-actions">${button('story-settings', 'Story-Bibel', 'book', 'button')}
    ${button('story-outline', 'Kapitelübersicht erstellen', undefined, 'button')}
    ${button('story-plan', 'Kapitel planen', 'plus', 'button')}
    ${chapters.some(chapter => chapter.status === 'planned') ? button('story-next', 'Nächstes Kapitel schreiben', undefined, 'button') : ''}
    ${chapters.some(chapter => chapter.words > 0) ? button('story-review-all', 'Gesamte Geschichte prüfen', undefined, 'button') : ''}
    </div>`;
  if (compact) {
    return `<p class="muted">${storyProgress(chapters)}</p>${chapterList(chapters, true, active)}${actions}`;
  }
  return `<section class="collection-section story-section"><h2>Kapitel</h2><p>${storyProgress(chapters)}</p>${actions}${chapterList(chapters, false)}</section>`;
}

export function settingsDialog(info: StoryInfo, documents: Source[], save: (body: object) => Promise<void>) {
  const profile = info.settings;
  const sources = documents.filter(doc => doc.story_number == null);
  const selected = (value: string, current: string | null) => value === current ? ' selected' : '';
  dialogForm('Story-Bibel', `<label for="story-lang">Sprache für neue Kapitel</label><select class="field" id="story-lang" name="lang">
    <option value="de"${selected('de', profile.lang)}>Deutsch</option><option value="en"${selected('en', profile.lang)}>Englisch</option></select>
    ${wordFields(profile)}
    <label for="story-opening">Vorhandene Eröffnung für Kapitel 1</label><select class="field" id="story-opening" name="opening"><option value="">Keine auswählen</option>
    ${sources.map(doc => `<option value="${esc(doc.id)}"${selected(doc.id, profile.opening)}>${esc(doc.title || 'Ohne Titel')}</option>`).join('')}</select>
    <p class="muted">Die gewählte Eröffnung wird wortgetreu an den Anfang des neuen Kapitelentwurfs übernommen.</p>
    <details open><summary>Figuren, Welt und Erzählung</summary><div class="story-fields">
    ${Object.entries(sections).map(([key, label]) => textField(key, label, info.bible[key])).join('')}</div></details>`,
    'Speichern', data => save({ lang: data.get('lang'), minimum: Number(data.get('minimum')), maximum: Number(data.get('maximum')),
      opening: data.get('opening') || null, bible: Object.fromEntries(Object.keys(sections).map(key => [key, data.get(key)])) }));
}

export function chapterPlanDialog(info: StoryInfo, chapter: StoryChapter | undefined, save: (body: object) => Promise<void>) {
  const titleField = chapter ? '' : `<label for="story-title">Kapiteltitel</label>
    <input class="field" id="story-title" name="title" maxlength="180" required autofocus>`;
  dialogForm(chapter ? 'Kapitelplan bearbeiten' : 'Kapitel planen', titleField + wordFields(chapter ?? info.settings) +
    textField('plan', 'Was soll in diesem Kapitel passieren?', chapter?.plan, 5000, true),
  'Plan speichern', data => save({ document_id: chapter?.id, title: data.get('title'), plan: data.get('plan'),
    minimum: Number(data.get('minimum')), maximum: Number(data.get('maximum')) }));
}

const actionTitles: Record<StoryAction, string> = {
  outline: 'Kapitelübersicht erstellen', generate: 'Kapitel schreiben',
  'review-chapter': 'Kapitel auf Konsistenz prüfen', 'review-story': 'Gesamte Geschichte prüfen',
};

export function requestDialog(action: StoryAction, chapter: StoryChapter | undefined,
  run: (request: StoryRequest, message: string) => Promise<void>, replaceDraft = false) {
  const generating = action === 'generate';
  const outline = action === 'outline';
  const title = replaceDraft ? 'Neuen Entwurf schreiben' : actionTitles[action];
  dialogForm(title, `${outline ? numberField('count', 'Anzahl neuer Kapitel', 8) : ''}
    ${chapter ? `<p>${chapter.number}. ${esc(chapter.title)} · ${number.format(chapter.minimum)}–${number.format(chapter.maximum)} Wörter</p>` : ''}
    ${replaceDraft ? '<p>Die bisherige Fassung bleibt im Versionsverlauf erhalten.</p>' : ''}
    ${generating || outline ? textField('instruction', outline ? 'Was soll die Geschichte erzählen?' : 'Hinweise für dieses Kapitel') : ''}
    ${generating ? '<label class="check-field"><input type="checkbox" name="for_review" checked> Entwurf zur Freigabe vorlegen</label>' : ''}`,
  outline ? 'Übersicht erstellen' : generating ? 'Entwurf schreiben' : 'Prüfen', async data => {
    const instruction = String(data.get('instruction') ?? '').trim();
    await run({ action, values: { document_id: chapter?.id, count: outline ? Number(data.get('count')) : undefined,
      for_review: data.has('for_review'), version: chapter?.version, replace_draft: replaceDraft, instruction } }, title +
      (chapter ? ' – ' + chapter.title : '') + (instruction ? '\n\n' + instruction : ''));
  });
}

export function chapterMenu(chapter: StoryChapter) {
  const id = chapter.id;
  showDialog(chapterName(chapter), '<div class="organizer-menu">' +
    button('story-open', 'Im Editor öffnen', 'text', 'button quiet', id) +
    (chapter.status === 'approved' ? button('story-draft', 'Freigabe aufheben', undefined, 'button quiet', id) :
      button('story-edit-plan', 'Kapitelplan bearbeiten', undefined, 'button quiet', id)) +
    (chapter.status === 'planned' && !chapter.words ? button('story-write', 'Kapitel schreiben', undefined, 'button quiet', id) : '') +
    (chapter.words && chapter.status !== 'approved' ? button('story-redraft', 'Neuen Entwurf schreiben', undefined, 'button quiet', id) : '') +
    (chapter.words ? button('story-review', 'Kapitel auf Konsistenz prüfen', undefined, 'button quiet', id) : '') +
    (chapter.words && chapter.status !== 'approved' ? button('story-approve', 'Kapitel freigeben', undefined, 'button quiet', id) : '') + '</div>');
}

export function chapterTools(chapter: StoryChapter) {
  return `<div class="editor-actions story-chapter-tools">${button('story-chapter', 'Kapitelaktionen', 'book', 'button quiet', chapter.id)}
    ${chapter.status === 'planned' ? button('story-write', 'Kapitel schreiben', undefined, 'button', chapter.id) :
      button('story-review', 'Kapitel auf Konsistenz prüfen', undefined, 'button', chapter.id)}</div>`;
}

export function storyJobMarkup(job?: StoryJob) {
  if (!job) return '<p>Schreibauftrag wird geladen …</p>';
  if (job.status === 'cancelled') return '<p>Schreibauftrag abgebrochen.</p>';
  if (job.status === 'failed') {
    return '<p>Der Schreibauftrag konnte nicht abgeschlossen werden.</p>' +
      (job.error ? '<p>' + esc(storyErrors[job.error] ?? 'Bitte versuche es erneut.') + '</p>' : '');
  }
  if (job.status !== 'completed') {
    const progress = job.stage === 'checking' ? 'Stil und Kontinuität werden geprüft …' : job.action === 'outline' ?
      'Kapitelübersicht wird erstellt …' : 'Kapitel wird geschrieben …';
    return `<p>${progress}</p>${job.total_sections ? `<label>Abschnitte · ${job.completed_sections ?? 0} von ${job.total_sections}
      <progress value="${job.completed_sections ?? 0}" max="${job.total_sections}"></progress></label>` : ''}
      ${button('story-cancel', 'Schreibauftrag abbrechen', undefined, 'button quiet', job.id)}`;
  }
  if (job.action === 'outline') {
    return `<p>${job.bible_saved ? 'Story-Bibel gespeichert.' : ''} ${job.chapter_ids?.length ?? 0} Kapitel geplant.</p>${button('contents', 'Inhalte öffnen', 'book', 'button')}`;
  }
  const review = job.review;
  return `<p>${job.action === 'generate' ? esc(chapterLabel(job.chapter_status ?? 'draft')) + ' · ' + number.format(job.words ?? 0) + ' Wörter' :
    review?.chapters_reviewed ? review.chapters_reviewed + ' Kapitel geprüft' : 'Kapitelprüfung gespeichert.'}</p>
    ${job.document_id ? button('open-doc', 'Kapitel öffnen', 'text', 'button', job.document_id) : ''}
    ${review ? `<details><summary>Stil und Kontinuität</summary>
      ${review.summary ? `<p>${esc(review.summary)}</p>` : ''}
      ${review.error ? '<p>Die Modellprüfung konnte nicht vollständig ausgeführt werden.</p>' : ''}
      ${review.style ? `<p>Human Writing ${esc(review.style.skill_version)} · ${review.style.finding_count} Stilhinweise</p>` : ''}
      ${review.style?.findings.length ? `<ul>${review.style.findings.map(item =>
        `<li>${esc(item.excerpt || item.rule)}${item.fix ? ' · ' + esc(item.fix) : ''}</li>`).join('')}</ul>` : ''}
      ${review.findings?.length ? '<ul>' + review.findings.map(item =>
        `<li><q>${esc(item.quote)}</q> <span>${esc(item.issue)}</span></li>`).join('') + '</ul>' : ''}
      ${review.discarded_findings ? `<p>${review.discarded_findings} Modellhinweise ohne überprüfbaren Textbeleg.</p>` : ''}
      ${review.repetitions?.length ? '<h4>Wiederholte Stellen</h4><ul>' + review.repetitions.map(quote => '<li>' + esc(quote) + '</li>').join('') + '</ul>' : ''}
      </details>` : ''}`;
}

