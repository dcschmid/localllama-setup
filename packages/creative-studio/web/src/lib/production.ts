import { receiptMarkup, type VisualReceipt } from './visual';
import { esc, json, post } from './core';
import { button, dialogForm, markdown, productionErrors, showDialog } from './studio-ui';
import { actionMarkup, activityText, chapterSummary, failureText, headMarkup, lengthSentence, liveMarkup, progressMarkup, stepsMarkup,
  timelineMarkup, type Link, type Monitor } from './production-monitor';

type Section = Record<string, string>;
type Image = { visual_profile?: VisualReceipt; id: string; alt: string };
type Finding = { quote: string; issue: string; severity?: string; chapter?: string; category?: string; status?: string;
  method?: string; correction?: string; related_quote?: string; verification?: string; line?: number };
type Chapter = { id: string; number: number; title: string; version: number; words: number; status: string;
  body?: string; image?: Image; corrections?: number; findings?: Finding[]; skills?: Record<string, string> };
export type ProductionPlan = {
  title: string; subtitle: string; afterword: string;
  bible: Section; bible_records?: Record<string, Section[]>; visual: Section; chapters: Array<{ title: string; number: number; minimum: number; maximum: number }>;
  language: 'de' | 'en'; chapter_count: number; target_words: number; motifs: string[];
};
export type ProductionJob = {
  id: string; project_id: string; status: string; kind: 'plan' | 'planning' | 'story'; step: string; number?: number; total?: number;
  downloads?: Partial<Record<'md' | 'mdx' | 'zip', string>>;
  manifest?: { completed_chapters: number; expected_chapters: number; verified_images: number; required_images: number };
  phase?: string; image_state?: string; image_waiting?: string; retry?: { attempt: number; code: string };
  language_retry_available?: boolean; answer?: string; planning_findings?: Finding[]; compared_chapters?: number[]; plan_version?: number; proposal_stale?: boolean;
  skills?: Record<string, string>; audit_lane?: string; art_review_pending?: boolean;
  model?: { alias: string; variant?: string | null; quantization?: string | null }; retries?: { automatic: number; manual: number };
  monitor?: Monitor; pause_reason?: string; draft_document_id?: string; corrections?: number; last_completed?: number; recheck_available?: boolean; cover?: Image; waiting?: string; error?: string; findings?: Finding[]; detail?: unknown; chapter_results?: Chapter[];
};
export type ProductionInfo = { plan: ProductionPlan | null; version: number | null; approved: boolean; historical?: boolean; reviewing?: boolean; stage?: string;
  history: Array<{ version: number; state: string }>;
  narrative: Array<{ number: number; summary: string; title: string; memory: Array<{ status: string; kind: string; fact: string; quote: string }> }>;
  impact?: { findings: Finding[]; outline_findings?: Finding[]; versions?: Record<string, number>;
    changed_chapters?: number[]; global_change?: boolean }; job: ProductionJob | null };
export type Manuscript = { title: string; subtitle: string; language: string; complete: boolean; words: number; cover?: Image;
  afterword: string; downloads?: ProductionJob['downloads']; chapters: Chapter[]; whole_review?: { reviews?: Array<{ assessment: string; findings: Finding[] }>; repetitions?: Finding[] } };

const root = (pid: string) => '/api/production/' + encodeURIComponent(pid);
export const productionInfo = (pid: string, version?: number) => json<ProductionInfo>(root(pid) + (version ? '?version=' + version : ''));
export const productionJob = (id: string) => json<ProductionJob>('/api/production/jobs/' + encodeURIComponent(id));
export const productionAct = (pid: string, action: string, values: object) => post(root(pid) + '/' + action, values);
export const manuscript = (pid: string) => json<Manuscript>(root(pid) + '/manuscript');

const mainLabels = {
  title: 'Arbeitstitel', subtitle: 'Untertitel', genre: 'Genre', audience: 'Zielgruppe', perspective: 'Erzählperspektive', tone: 'Tonalität',
  setting: 'Setting', main_characters: 'Hauptfiguren', supporting_characters: 'Nebenfiguren',
  character_goals: 'Ziele', character_conflicts: 'Charakterkonflikte', backstory: 'Vorgeschichte',
  central_conflict: 'Zentraler Konflikt', dramatic_arc: 'Dramaturgie', turning_points: 'Wendepunkte',
  climax: 'Höhepunkt', resolution: 'Auflösung', ending: 'Art des Endes', afterword: 'Nachwort',
};
const bibleLabels = { characters: 'Figuren und Beziehungen', world: 'Weltregeln', locations: 'Schauplätze',
  chronology: 'Chronologie und Reisezeiten', main_plot: 'Haupthandlung', subplots: 'Nebenhandlungen',
  open_questions: 'Offene Fragen', revealed_secrets: 'Enthüllte Geheimnisse', unrevealed_secrets: 'Verborgene Informationen',
  foreshadowing: 'Foreshadowing', payoffs: 'Payoffs', character_knowledge: 'Figurenwissen' };
const bibleRecordLabels: Record<string, { label: string; fields: Section }> = {
  characters: { label: 'Figuren', fields: { name: 'Name', age: 'Alter', role: 'Rolle', personality: 'Persönlichkeit',
    motivation: 'Motivation', relationships: 'Beziehungen', background: 'Hintergrund', voice: 'Sprechweise',
    arc: 'Entwicklung', known: 'Bekannte Informationen', secrets: 'Geheimnisse' } },
  locations: { label: 'Schauplätze', fields: { name: 'Ort', description: 'Beschreibung', geography: 'Geografie',
    history: 'Geschichte', rules: 'Regeln' } },
  chronology: { label: 'Chronologie', fields: { event: 'Ereignis', when: 'Zeitpunkt', duration: 'Zeitabstand',
    travel: 'Weg und Reisezeit', depends_on: 'Voraussetzung' } },
  knowledge: { label: 'Figurenwissen', fields: { character: 'Figur', fact: 'Information',
    learns_when: 'Erfährt es wann', how: 'Erfährt es wie' } },
  objects: { label: 'Gegenstände', fields: { name: 'Name', quantity: 'Anzahl', markings: 'Merkmale',
    initial_holder: 'Anfangs bei', location: 'Ort', transitions: 'Wechsel' } },
  threads: { label: 'Handlungsstränge', fields: { name: 'Handlungsstrang', status: 'Stand',
    foreshadowing: 'Foreshadowing', payoff: 'Payoff' } },
};
const visualLabels = { style: 'Stil', palette: 'Palette', characters: 'Aussehen', wardrobe: 'Kleidung',
  locations: 'Schauplätze', atmosphere: 'Atmosphäre' };
const chapterFields = { title: 'Titel', perspective: 'Erzählperspektive', opening: 'Ausgangssituation',
  conflict: 'Hauptkonflikt', beats: 'Handlungsschritte', development: 'Charakterentwicklung', revelations: 'Neue Informationen',
  tension: 'Spannungsentwicklung', closing: 'Kapitelabschluss', continuity: 'Kontinuitätsinformationen', illustration: 'Illustrationsmotiv' };
const number = new Intl.NumberFormat('de');
const stateLabels: Record<string, string> = { planning: 'Geschichte wird geplant', planning_chapters: 'Geschichte wird geplant', planning_review: 'Planung wird geprüft', planning_repair: 'Planung wird verbessert', impact: 'Planauswirkungen prüfen',
  planning_audit: 'Planung wird geprüft', planning_revise: 'Planung wird überarbeitet', planning_discuss: 'Antwort wird vorbereitet',
  planning_import: 'Planung wird übernommen', planning_done: 'Story-Planung',
  plan_ready: 'Story-Planung liegt vor', writing: 'Kapitel wird geschrieben', auditing: 'Human Writing prüft das Kapitel',
  reviewed: 'Automatische Überarbeitung', rewrite_audit: 'Überarbeitung wird geprüft', text_finalize: 'Kapiteltext wird finalisiert',
  illustrating: 'Illustration vorbereiten', image_prompt: 'Bildszene wird ausgewählt', image_queue: 'Bildauftrag wird angelegt',
  image_wait: 'Bildauftrag wartet', image_archive: 'Bilddatei wird geprüft', finalizing: 'Kapitel wird abgeschlossen',
  awaiting_chapter: 'Kapitel zur Freigabe', advance: 'Kapitel abgeschlossen', cover: 'Titelbild',
  manuscript: 'Manuskript wird geprüft', export_generation: 'Manuskript wird exportiert',
  final_validation: 'Manuskript und Dateien werden validiert', art_variant: 'Bildvariante erzeugen', art_review: 'Illustrationen zur Sichtprüfung', done: 'Produktion abgeschlossen' };

const failureLabels: Record<string, string> = {
  writing: 'Schreiben fehlgeschlagen', auditing: 'Textprüfung fehlgeschlagen', reviewed: 'Automatische Überarbeitung fehlgeschlagen',
  rewrite_audit: 'Prüfung der Überarbeitung fehlgeschlagen', text_finalize: 'Finalisierung des Texts fehlgeschlagen',
  image_prompt: 'Auswahl der Bildszene fehlgeschlagen', image_queue: 'Anlegen des Bildauftrags fehlgeschlagen',
  image_wait: 'Bildauftrag fehlgeschlagen', image_archive: 'Prüfung der Bilddatei fehlgeschlagen',
  finalizing: 'Kapitelabschluss fehlgeschlagen',
};

const qualityStatus: Record<string, string> = { confirmed: 'Bestätigt', unconfirmed: 'Unbestätigt', refuted: 'Widerlegt' };
const qualitySeverity: Record<string, string> = { blocking: 'Blockierend', automatic: 'Automatisch korrigierbar',
  editorial: 'Redaktionell', note: 'Hinweis' };
const qualityMethod: Record<string, string> = { model_claim: 'Modellhinweis', independent_audit: 'Unabhängige Modellprüfung',
  time_interval: 'Zeitintervall', local_text: 'Lokale Textprüfung', word_overlap: 'Wortübereinstimmung',
  editorial_heuristic: 'Stilprüfung', word_count: 'Wortzählung' };
const qualityCategory: Record<string, string> = { punctuation: 'Zeichensetzung', grammar: 'Grammatik', repetition: 'Wiederholung',
  continuity: 'Kontinuität', character: 'Figuren', scene: 'Szene', plot: 'Handlung', naturalness: 'Sprache', pacing: 'Erzähltempo',
  dialogue: 'Dialog', tension: 'Spannung', emotion: 'Emotion', originality: 'Originalität', effect: 'Wirkung' };

const planStages: Record<string, string> = { outline: 'Gliederung und Story-Bibel', chapters: 'Kapitelplanung', validate: 'Validierung der Planung',
  repair: 'Ergänzung der Story-Bibel', review: 'Gesamtprüfung der Gliederung', impact: 'Prüfung bestehender Kapitel', save: 'Speichern der Planung' };
const invalidReasons: Record<string, string> = { empty: 'leer', missing: 'nicht vorhanden', too_long: 'zu lang', type: 'kein Text' };

// Field paths come from the backend validation. Only the path is shown, never the content.
function fieldLabel(field: string) {
  const bible = /^bible\.(\w+)$/.exec(field), visual = /^visual\.(\w+)$/.exec(field), chapter = /^chapters\[(\d+)\]\.(\w+)$/.exec(field),
    record = /^bible_records\.(\w+)\[(\d+)\]\.(\w+)$/.exec(field);
  if (bible) return `Story-Bibel · ${(bibleLabels as Record<string, string>)[bible[1]] ?? bible[1]}`;
  if (visual) return `Bildideen · ${(visualLabels as Record<string, string>)[visual[1]] ?? visual[1]}`;
  if (chapter) return `Kapitel ${chapter[1]} · ${(chapterFields as Record<string, string>)[chapter[2]] ?? chapter[2]}`;
  if (record) return `Story-Bibel-Eintrag ${bibleRecordLabels[record[1]]?.label ?? record[1]} ${record[2]}`;
  return (mainLabels as Record<string, string>)[field] ?? field;
}

const jobDetail = (job: ProductionJob) => job.detail && typeof job.detail === 'object' && !Array.isArray(job.detail)
  ? job.detail as Record<string, string> : {};

// The affected step of a failed planning job, from the stored error code and its validated detail.
export function planningFailure(job: ProductionJob) {
  if (!job.error || job.status !== 'failed' || (job.kind !== 'plan' && job.kind !== 'planning')) return undefined;
  const detail = jobDetail(job);
  const where = planStages[detail.stage] ? ` (${planStages[detail.stage]})` : '';
  switch (job.error) {
    case 'story_input_invalid':
    case 'production_plan_invalid': {
      const area = detail.field?.startsWith('chapters') ? 'Kapitelstruktur' : detail.field?.startsWith('bible') ? 'Story-Bibel' : 'Planung';
      return `Story-Planung: ${area} konnte nicht validiert werden` + (detail.field
        ? ` – „${fieldLabel(detail.field)}“ ist ${invalidReasons[detail.reason] ?? 'ungültig'}.` : '.');
    }
    case 'story_output_truncated': return `Story-Planung: Modellantwort unvollständig${where}.`;
    case 'story_model_format': return `Story-Planung: Die Modellantwort hatte kein gültiges strukturiertes Format${where}.`;
    case 'story_outline_incomplete': return 'Story-Planung: Das Modell hat nicht alle angeforderten Kapitel geliefert.';
    case 'production_upstream_unavailable':
      return `Story-Planung: Modellanfrage überschritt das Zeitlimit oder der Modelldienst war nicht erreichbar${where}.`;
    case 'production_upstream_http': return `Story-Planung: Der Modelldienst hat den Aufruf mit einem HTTP-Fehler beendet${where}.`;
    case 'production_checkpoint_write': return 'Story-Planung: Speichern der Planung fehlgeschlagen.';
    case 'story_context_changed': return 'Story-Planung: Ein Kapitel wurde während der Planung geändert.';
    default: return undefined;
  }
}

export function technicalDetails(job: ProductionJob) {
  const detail = jobDetail(job);
  const model = job.model ? [job.model.alias, job.model.variant, job.model.quantization].filter(Boolean).join(' · ') : '';
  const skills = Object.entries(job.skills ?? {}).map(([name, version]) => `${name} ${version}`).join(' · ');
  const rows: Array<[string, string]> = [['Fehlercode', job.error ?? ''],
    ['Schritt', [planStages[detail.stage] ?? '', detail.stage ?? job.phase ?? job.step].filter(Boolean).join(' · ')]];
  if (detail.field) rows.push(['Feld', `${fieldLabel(detail.field)} (${detail.field}) · ${invalidReasons[detail.reason] ?? detail.reason ?? ''}`]);
  for (const [key, label] of [['http_status', 'HTTP-Status'], ['sqlite_error', 'Datenbankfehler'], ['exception', 'Ausnahme']]) {
    if (detail[key]) rows.push([label, String(detail[key])]);
  }
  const monitor = job.monitor;
  if (monitor) {
    rows.push(['Gespeicherter Status', job.status], ['Schritt-ID', `${monitor.current_chapter ?? '-'}:${monitor.phase}`],
      ['Live-Prüfung', `${monitor.health.level} · ${monitor.health.reason}`]);
    if (monitor.length) rows.push(['Wortzahl', `${monitor.length.words} (Bereich ${monitor.length.minimum}–${monitor.length.maximum}), Versuche ${monitor.length.attempts}`]);
  }
  rows.push(['Job-ID', job.id], ['Modell', model || 'nicht erfasst'], ['Skills', skills || 'nicht erfasst'],
    ['Wiederholungen', job.retries ? `automatisch ${job.retries.automatic} · manuell ${job.retries.manual}` : 'nicht erfasst']);
  return '<dl class="job-facts">' + rows.filter(([, value]) => value).map(([key, value]) =>
    `<dt>${esc(key)}</dt><dd>${esc(value)}</dd>`).join('') + '</dl>';
}

function issueMarkup(findings: Finding[] = []) {
  return findings.length ? '<ul>' + findings.map(f => {
    const classification = [f.status && qualityStatus[f.status], f.severity && qualitySeverity[f.severity],
      f.category && qualityCategory[f.category], f.method && qualityMethod[f.method]].filter(Boolean).join(' · ');
    return `<li>${f.chapter ? `Kapitel ${esc(f.chapter)} · ` : ''}${f.line ? `Zeile ${f.line} · ` : ''}${classification ? esc(classification) + ' · ' : ''}${esc(f.issue)}
      ${f.quote ? `<blockquote>${esc(f.quote)}</blockquote>` : ''}
      ${f.related_quote ? `<blockquote>${esc(f.related_quote)}</blockquote>` : ''}
      ${f.verification ? `<p>${esc(f.verification)}</p>` : ''}
      ${f.correction ? `<p>${esc(f.correction)}</p>` : ''}</li>`;
  }).join('') + '</ul>' : '';
}

function textarea(name: string, label: string, value = '', optional = false) {
  return `<label for="${esc(name)}">${esc(label)}</label><textarea class="field" id="${esc(name)}" name="${esc(name)}"
    ${optional ? '' : 'required'} rows="3">${esc(value)}</textarea>`;
}

function integer(name: string, label: string, value: number, max: number) {
  return `<label for="${name}">${label}</label><input class="field" id="${name}" name="${name}" type="number"
    min="1" max="${max}" required value="${value}">`;
}

export function proposeDialog(lang: string, brief: string, submit: (values: object) => Promise<void>) {
  dialogForm('Geschichte planen', textarea('production-brief', 'Was soll die Geschichte erzählen?', brief)
    + `<label for="production-language">Sprache</label><select class="field" name="language" id="production-language">
        <option value="de"${lang === 'de' ? ' selected' : ''}>Deutsch</option><option value="en"${lang === 'en' ? ' selected' : ''}>Englisch</option></select>
      ${integer('count', 'Kapitel', 8, 150)}
      <details><summary>Wortzahl pro Kapitel</summary><div class="story-word-range">
        <div>${integer('minimum', 'Mindestens', 1000, 20000)}</div><div>${integer('maximum', 'Höchstens', 1500, 20000)}</div>
      </div></details>`, 'Planung erstellen', data => submit({ brief: data.get('production-brief'), count: Number(data.get('count')),
        minimum: Number(data.get('minimum')), maximum: Number(data.get('maximum')), language: data.get('language') }));
}

export function planDialog(info: ProductionInfo, pid: string) {
  const plan = info.plan;
  if (!plan) return;
  const meta = `<p>${plan.chapter_count} Kapitel · ${number.format(plan.target_words)} Wörter angestrebt · Version ${info.version}
    ${info.reviewing && !info.historical ? ' · In Prüfung' : info.approved ? ' · Freigegeben' : ' · Entwurf'}</p>`;
  const section = (title: string, labels: Section, data: object) => `<details><summary>${esc(title)}</summary>
    <dl>${Object.entries(labels).filter(([k]) => (data as Section)[k]).map(([k, label]) =>
      '<dt>' + esc(label) + '</dt><dd>' + esc((data as Section)[k]) + '</dd>').join('')}</dl></details>`;
  const active = ['queued', 'running', 'paused', 'failed'].includes(info.job?.status ?? '');
  const futureChanges = info.impact?.changed_chapters ?? [];
  const adoptable = info.approved && info.job?.status === 'paused' && info.job.plan_version !== info.version &&
    ['chapter', 'user'].includes(info.job.pause_reason ?? '') && !info.impact?.global_change &&
    futureChanges.length > 0 && futureChanges.every(chapter => chapter > (info.job?.number ?? 1));
  const status: Record<string, string> = { established: 'Belegt', proposal: 'Vorschlag', question: 'Offene Frage', interpretation: 'Deutung' };
  showDialog(plan.title, meta + section('Handlung und Figuren', mainLabels, plan) + section('Story-Bibel', bibleLabels, plan.bible)
    + Object.entries(plan.bible_records ?? {}).filter(([, values]) => values.length).map(([key, values]) => {
      const group = bibleRecordLabels[key];
      return `<details><summary>${esc(group.label)}</summary>${values.map(row =>
        section(row.name ?? row.event ?? row.character, group.fields, row)).join('')}</details>`;
    }).join('')
    + section('Bildideen aus der Planung', visualLabels, plan.visual) + `<details><summary>Kapitelübersicht</summary>
    ${plan.chapters.map(c => section(c.number + '. ' + c.title + ' · ' + c.minimum + '–' + c.maximum + ' Wörter', chapterFields, c)).join('')}
    </details>` + (!info.historical && info.narrative.length ? `<details><summary>Story-Bibel aus geschriebenen Kapiteln</summary>
    ${info.narrative.map(c => `<details><summary>${c.number}. ${esc(c.title)}</summary><p>${esc(c.summary)}</p>
      ${issueMarkup(c.memory.map(m => ({ issue: (status[m.status] ?? m.status) + ' · ' + m.fact, quote: m.quote })))}</details>`).join('')}</details>` : '')
    + (info.history.length > 1 ? '<details><summary>Planversionen</summary><div class="editor-actions">' + info.history.map(item =>
      button('production-plan-version', 'Version ' + item.version + (item.state === 'approved' ? ' · Freigegeben' : ' · Vorschlag'),
        undefined, 'button quiet', pid + ':' + item.version)).join('') + '</div></details>' : '')
    + (plan.motifs.length ? '<p>Leitmotive · ' + esc(plan.motifs.join(' · ')) + '</p>' : '')
    + (info.impact?.outline_findings?.length ? '<details open><summary>Befunde zur Kapitelplanung</summary>'
      + issueMarkup(info.impact.outline_findings) + '</details>' : '')
    + (futureChanges.length ? '<p>Geänderte Kapitelpläne · ' + esc(futureChanges.join(', ')) + '</p>' : '')
    + (info.impact?.global_change ? '<p>Diese Version ändert auch die übergreifende Planung.</p>' : '')
    + (info.impact?.versions && Object.keys(info.impact.versions).length ? '<details open><summary>Auswirkungen auf bestehende Kapitel</summary>'
      + (issueMarkup(info.impact.findings) || '<p>Die Prüfung hat keine Konflikte belegt.</p>') + '</details>' : '')
    + (active && info.job?.kind === 'story' && info.job.plan_version && info.job.plan_version !== info.version
      ? '<p>Die laufende Produktion verwendet weiterhin Planversion ' + String(info.job.plan_version) + '.</p>' : '')
    + '<div class="editor-actions">' + (info.historical ? '' : button('visual-profile', 'Bildstil', undefined, 'button', pid)
      + button('production-edit', 'Plan bearbeiten', undefined, 'button', pid)
      + button('production-audit-plan', 'Planung prüfen', undefined, 'button', pid)
      + (info.approved ? (!active ? button('production-start-together', 'Gemeinsam schreiben', undefined, 'button', pid)
        + button('production-start-automatic', 'Geschichte vollständig erstellen', undefined, 'button primary', pid) : '')
        + (adoptable ? button('production-adopt-plan', 'Freigegebene Version übernehmen und fortsetzen', undefined, 'button primary',
          info.job!.id + ':' + info.version) : '')
        : button('production-approve', 'Planung freigeben', undefined, 'button', pid)
          + button('production-approve-start', 'Freigeben und vollständig erstellen', undefined, 'button primary', pid))) + '</div>', true);
}

export function editPlanDialog(info: ProductionInfo, submit: (values: object) => Promise<void>) {
  const plan = info.plan;
  if (!plan) return;
  const controls = (prefix: string, labels: Section, data: object) => Object.entries(labels).map(([key, label]) =>
    textarea(prefix + key, label, (data as Section)[key], ['audience', 'subtitle', 'afterword', 'model', 'preset'].includes(key) || (data as Section)[key] === '')).join('');
  const group = (title: string, body: string) => `<details><summary>${esc(title)}</summary>${body}</details>`;
  dialogForm('Story-Planung bearbeiten',
    group('Handlung und Figuren', controls('plan-', mainLabels, plan)) +
    group('Story-Bibel', controls('bible-', bibleLabels, plan.bible) +
      Object.entries(plan.bible_records ?? {}).filter(([, values]) => values.length).map(([key, values]) =>
        group(bibleRecordLabels[key].label, values.map((row, index) => group(row.name ?? row.event ?? row.character,
          controls('bible-record-' + key + '-' + index + '-', bibleRecordLabels[key].fields, row))).join(''))).join('')) +
    group('Bildideen aus der Planung', controls('visual-', visualLabels, plan.visual)) +
    group('Kapitelübersicht', plan.chapters.map(c => group(c.number + '. ' + c.title,
      controls('chapter-' + c.number + '-', chapterFields, c) +
      integer('minimum-' + c.number, 'Mindestens Wörter', c.minimum, 20000) +
      integer('maximum-' + c.number, 'Höchstens Wörter', c.maximum, 20000))).join('')) +
    group('Leitmotive', textarea('motifs', 'Ein beabsichtigtes Leitmotiv pro Zeile', plan.motifs.join('\n'), true)),
    'Planversion speichern', data => {
      const collect = (prefix: string, labels: Section) => Object.fromEntries(Object.keys(labels).map(key => [key, data.get(prefix + key)]));
      const records = Object.fromEntries(Object.entries(plan.bible_records ?? {}).map(([key, values]) => [key,
        values.map((_, index) => collect('bible-record-' + key + '-' + index + '-', bibleRecordLabels[key].fields))]));
      return submit({ version: info.version, plan: { ...plan, ...collect('plan-', mainLabels), bible: collect('bible-', bibleLabels),
        bible_records: records, visual: { ...plan.visual, ...collect('visual-', visualLabels) },
        motifs: String(data.get('motifs')).split('\n').map(s => s.trim()).filter(Boolean),
        chapters: plan.chapters.map(c => ({ ...c, ...collect('chapter-' + c.number + '-', chapterFields),
          minimum: Number(data.get('minimum-' + c.number)), maximum: Number(data.get('maximum-' + c.number)) })) } });
    });
}

const liveLink: Link = { state: 'live', failures: 0, offset: 0 };

function downloadAnchors(links: ProductionJob['downloads']) {
  const names = { md: 'Markdown', mdx: 'MDX', zip: 'ZIP' };
  return Object.entries(links ?? {}).map(([fmt, url]) =>
    /^\/api\/production\/jobs\/[a-f0-9]{32}\/files\/manuscript\.(md|mdx|zip)$/.test(url)
      ? `<a class="button" href="${esc(url)}" download>${names[fmt as 'md'] ?? esc(fmt.toUpperCase())} herunterladen</a>` : '').join('');
}

function storyCard(job: ProductionJob, monitor: Monitor, chapters: Map<string, { body: string; version: number }>,
  media: (id: string, alt: string, actions?: boolean) => string, link: Link) {
  const items = job.chapter_results ?? [];
  const failure = monitor.state === 'failed' ? failureText(job, monitor, productionErrors, failureLabels) : undefined;
  const skillMarkup = (loaded?: Record<string, string>) => loaded && Object.keys(loaded).length ?
    '<p>' + esc(Object.entries(loaded).map(([name, version]) => name + ' ' + version).join(' · ')) + '</p>' : '';
  const facts = monitor.length;
  const working = ['correcting', 'retrying', 'verifying', 'running', 'model_wait'].includes(monitor.state);
  const lengthLine = facts && facts.state !== 'ok' && working
    ? `<p class="prod-length" data-prod-length>${esc(lengthSentence(facts))}${monitor.state === 'correcting' && facts.state === 'short' ? ' Das Studio versucht, die Szene sinnvoll zu erweitern.' : ''}</p>` : '';
  const controls = actionMarkup(monitor, { draft: job.draft_document_id, project_id: job.project_id, id: job.id, hasChapters: items.length > 0,
    art_review_pending: job.art_review_pending, downloads: downloadAnchors(job.downloads), images: items.some(c => c.image) || !!job.cover,
    language_retry_available: job.language_retry_available, recheck_available: job.recheck_available, pause_reason: job.pause_reason });
  const chapterList = monitor.chapters ?? [];
  const rows = chapterList.map(view => {
    const done = items.find(c => c.number === view.number);
    const doc = done ? chapters.get(done.id) : undefined;
    const open = chapterList.length === 1 || (view.status === 'active' && ['failed', 'needs_decision'].includes(monitor.state));
    const length = facts && facts.number === view.number && facts.state !== 'ok' ? `<p class="prod-length">${esc(lengthSentence(facts))}</p>` : '';
    return `<li><details data-production-chapter="${view.number}" data-job-detail="chapter-${view.number}"${open ? ' open' : ''}>
      <summary>${esc(chapterSummary(view, monitor))}</summary>
      <p class="prod-chapter-title">${esc(view.title)}</p>${stepsMarkup(view)}${length}
      ${done ? `${done.image ? media(done.image.id, done.image.alt, false) + receiptMarkup(done.image.visual_profile) + button('variant', 'Bildvariante erstellen', undefined, 'button quiet', done.image.id) : ''}
        ${done.corrections ? `<p>${done.corrections} Textfehler automatisch korrigiert.</p>` : ''}
        ${done.findings?.length || skillMarkup(done.skills) ? `<details data-job-detail="chapter-${view.number}-quality"><summary>Prüfdetails</summary>
          ${skillMarkup(done.skills)}${done.findings?.length ? issueMarkup(done.findings) : ''}</details>` : ''}
        <div class="prose">${doc ? markdown(doc.body) : '<p>Kapitel wird geladen …</p>'}</div>
        <div class="editor-actions">${button('open-doc', 'Kapitel öffnen', 'text', 'button', done.id)}
        ${button('production-edit-chapter', 'Überarbeiten', undefined, 'button', done.id)}
        ${button('production-export-chapter', 'Kapitel exportieren', undefined, 'button quiet', done.id)}</div>`
      : view.status === 'active' && job.draft_document_id ? `<div class="editor-actions">${button('open-doc', 'Gespeicherten Kapiteltext öffnen', 'text', 'button quiet', job.draft_document_id)}</div>` : ''}
    </details></li>`;
  }).join('');
  const detail = job.error || job.monitor ? `<details data-job-detail="technical-error"><summary>Technische Details</summary>${technicalDetails(job)}</details>` : '';
  return `<div class="production-view" data-production-state="${esc(monitor.state)}" data-production-link="${link.state}">
    <div class="prod-main">
      ${headMarkup(monitor, link, activityText(job, monitor, failure), failure)}
      ${lengthLine}${progressMarkup(monitor)}
      ${job.image_waiting === 'writer_gpu_release' ? '<p>Das Schreibmodell gibt den GPU-Slot frei.</p>' : ''}
      ${job.waiting === 'gpu' ? '<p>Wartet auf einen freien GPU-Slot.</p>' : ''}
      ${job.corrections ? `<p class="prod-note">${job.corrections} Textfehler in diesem Kapitel automatisch korrigiert.</p>` : ''}
      ${job.language_retry_available ? '<p class="prod-note">Ein bestätigter Sprachfehler lässt sich automatisch korrigieren. Die Produktion wird danach fortgesetzt.</p>' : ''}
      ${job.recheck_available ? '<p class="prod-note">Das gespeicherte Kapitel kann mit der aktualisierten Qualitätsprüfung fortgesetzt werden.</p>' : ''}
      ${(skillMarkup(job.skills) || job.findings?.length) ? '<details data-job-detail="current-quality"><summary>Prüfdetails</summary>'
        + skillMarkup(job.skills) + (job.findings?.length ? issueMarkup(job.findings) : '') + '</details>' : ''}
      <div class="editor-actions prod-actions" role="group" aria-label="Aktionen">${controls}</div>
      <section class="prod-chapters" aria-labelledby="prod-chapters-${esc(job.id)}"><h4 id="prod-chapters-${esc(job.id)}">Kapitel</h4><ol>${rows}</ol></section>
      ${job.cover ? `<details data-job-detail="cover"><summary>Titelbild</summary>${media(job.cover.id, job.cover.alt, false)}${receiptMarkup(job.cover.visual_profile)}</details>` : ''}
    </div>
    <aside class="prod-aside" aria-label="Live-Aktivität"><h4>Live-Aktivität</h4>${liveMarkup(monitor, link)}${timelineMarkup(monitor.timeline)}${detail}</aside>
  </div>`;
}

export function imagesDialog(job: ProductionJob, media: (id: string, alt: string, actions?: boolean) => string) {
  const assets = [...(job.cover ? [{ title: 'Titelbild', image: job.cover }] : []),
    ...(job.chapter_results ?? []).filter(c => c.image).map(c => ({ title: `Kapitel ${c.number}: ${c.title}`, image: c.image! }))];
  showDialog('Bilder der Produktion', assets.length ? assets.map(({ title, image }) => `<figure><figcaption>${esc(title)}</figcaption>`
    + media(image.id, image.alt, false) + '</figure>').join('') : '<p>Für diese Produktion sind keine geprüften Bilder gespeichert.</p>', true);
}

export function productionCard(job: ProductionJob | undefined, chapters: Map<string, { body: string; version: number }>,
  media: (id: string, alt: string, actions?: boolean) => string, link: Link = liveLink) {
  if (!job) return '<p>Produktionsstatus wird geladen …</p>';
  if (job.kind === 'story' && job.monitor) return storyCard(job, job.monitor, chapters, media, link);
  const term = ['completed', 'cancelled', 'incomplete'].includes(job.status);
  const phase = job.phase ?? job.step;
  let label = stateLabels[phase] ?? 'Produktion';
  if (phase === 'image_wait' && job.image_state === 'waiting_gpu') label = 'Bildauftrag wartet auf einen freien GPU-Slot';
  if (phase === 'image_wait' && ['loading', 'generating'].includes(job.image_state ?? '')) {
    label = job.step === 'cover' ? 'Titelbild wird generiert' : 'Kapitelbild wird generiert';
  }
  if (phase === 'image_wait' && job.image_state === 'submitting') label = 'Bildauftrag wird an den Bilddienst übergeben';
  if (job.status === 'incomplete') label = 'Produktion unvollständig';
  if (job.status === 'failed') label = failureLabels[phase] ?? label + ' fehlgeschlagen';
  if (job.number && job.total && job.number <= job.total) {
    label = phase === 'writing' ? `Kapitel ${job.number} von ${job.total} wird geschrieben`
      : ['reviewed', 'rewrite_audit'].includes(phase) ? `Kapitel ${job.number} wird verbessert`
      : `Kapitel ${job.number} von ${job.total} · ${label}`;
  }
  if (job.status === 'paused' && job.pause_reason !== 'chapter') label = 'Pausiert · ' + label;
  if (job.status === 'cancelled') label = 'Produktion abgebrochen';
  const controls = job.status === 'paused' && job.pause_reason === 'art' ?
    button('production-approve-art', 'Illustrationen prüfen', undefined, 'button primary', job.id)
    : job.status === 'completed' && job.art_review_pending ? button('production-approve-art', 'Illustrationen prüfen', undefined, 'button quiet', job.id)
    : job.language_retry_available ? button('production-retry', 'Sprachkorrektur erneut versuchen', undefined, 'button', job.id)
    : job.status === 'paused' ?
    button('production-resume', job.pause_reason === 'chapter' ? 'Kapitel freigeben und fortsetzen' :
      job.recheck_available ? 'Gespeichertes Kapitel erneut prüfen' : 'Fortsetzen', undefined, 'button', job.id)
    : job.status === 'incomplete' ? button('production-recover', 'Produktion vervollständigen', undefined, 'button', job.project_id)
    : job.status === 'failed' ? button('production-retry', 'Schritt erneut ausführen', undefined, 'button', job.id)
    : term ? '' : button('production-pause', 'Pausieren', undefined, 'button', job.id);
  const items = job.chapter_results ?? [];
  const skillMarkup = (loaded?: Record<string, string>) => loaded && Object.keys(loaded).length ?
    '<p>' + esc(Object.entries(loaded).map(([name, version]) => name + ' ' + version).join(' · ')) + '</p>' : '';
  const detail = typeof job.detail === 'string' ? job.detail : '';
  const error = job.error && (planningFailure(job) ?? productionErrors[detail] ?? productionErrors[job.error] ?? productionErrors.production_step_failed);
  return `<p class="job-title">${esc(label)}</p>${job.waiting === 'gpu' ? '<p>Wartet auf einen freien GPU-Slot.</p>' : ''}${error ? `<p>${esc(error)}</p>
    <details data-job-detail="technical-error"><summary>Technische Details</summary>${technicalDetails(job)}</details>` : ''}
    ${job.status !== 'failed' && job.image_waiting === 'writer_gpu_release' ? '<p>Das Schreibmodell gibt den GPU-Slot frei.</p>' : ''}
    ${job.audit_lane === 'continuity' ? '<p>Story Writing prüft die Kontinuität.</p>' : ''}
    ${job.retry && !job.error ? `<p>Automatischer Wiederholungsversuch ${job.retry.attempt}.</p>` : ''}
    ${job.answer ? '<div class="prose">' + markdown(job.answer, false) + '</div>' : ''}
    ${job.compared_chapters?.length ? '<p>Verglichene Kapitel · ' + esc(job.compared_chapters.join(', ')) + '</p>' : ''}
    ${job.planning_findings?.length ? '<details open><summary>Befunde zur Planung</summary>' + issueMarkup(job.planning_findings) + '</details>' : ''}
    ${job.proposal_stale ? '<p>Die Planung hat sich während der Prüfung geändert. Prüfe die aktuelle Version erneut.</p>' : ''}
    ${job.last_completed && job.step !== 'advance' ? `<p>Kapitel ${job.last_completed} abgeschlossen.</p>` : ''}
    ${job.corrections ? `<p>${job.corrections} Textfehler automatisch korrigiert.</p>` : ''}
    ${job.pause_reason === 'blocker' && !job.recheck_available && !job.language_retry_available ? '<p>Ein bestätigter Konflikt braucht eine Entscheidung.</p>' : ''}
    ${job.language_retry_available ? '<p>Ein bestätigter Sprachfehler lässt sich automatisch korrigieren. Die Produktion wird danach fortgesetzt.</p>' : ''}
    ${job.recheck_available ? '<p>Das gespeicherte Kapitel kann mit der aktualisierten Qualitätsprüfung fortgesetzt werden.</p>' : ''}
    ${(skillMarkup(job.skills) || job.findings?.length || Array.isArray(job.detail)) ? '<details data-job-detail="current-quality"><summary>Prüfdetails</summary>'
      + skillMarkup(job.skills) + (job.findings?.length ? issueMarkup(job.findings) :
        Array.isArray(job.detail) ? issueMarkup(job.detail as Finding[]) : '') + '</details>' : ''}
    <div class="editor-actions">${controls}${job.pause_reason === 'blocker' && !job.recheck_available && job.draft_document_id ?
      button('production-edit-chapter', 'Konflikt im Kapitel bearbeiten', undefined, 'button', job.draft_document_id) : ''}
    ${job.draft_document_id && !items.some(ch => ch.id === job.draft_document_id) ?
      button('open-doc', 'Gespeicherten Kapiteltext öffnen', undefined, 'button quiet', job.draft_document_id) : ''}
    ${term ? '' : button('production-cancel', 'Abbrechen', undefined, 'button quiet', job.id)}
    ${job.kind === 'plan' && job.status === 'completed' ? button('production-plan', 'Planung öffnen', 'book', 'button', job.project_id) : ''}
    ${job.kind === 'planning' && job.plan_version ? button('production-plan-version', 'Planentwurf öffnen', 'book', 'button', job.project_id + ':' + job.plan_version) : ''}
    ${job.manifest ? `<p>${job.manifest.completed_chapters} / ${job.manifest.expected_chapters} Kapitel · ${job.manifest.verified_images} / ${job.manifest.required_images} geprüfte Bilder</p>` : ''}
    ${downloadLinks(job.downloads)}
    ${job.kind === 'story' && items.length ? button('production-manuscript', 'Manuskript öffnen', 'book', 'button', job.project_id) : ''}</div>
    ${items.map(ch => {
      const doc = chapters.get(ch.id);
      return `<details data-production-chapter="${ch.number}" data-job-detail="chapter-${ch.number}"${items.length === 1 ? ' open' : ''}>
        <summary>${ch.number}. ${esc(ch.title)} · ${number.format(ch.words)} Wörter · ${doc && doc.version !== ch.version ? 'Erneut prüfen' :
          ch.status === 'approved' ? 'Geprüft' : 'Zur Freigabe'}</summary>
        ${ch.image ? media(ch.image.id, ch.image.alt, false) + receiptMarkup(ch.image.visual_profile) + button('variant', 'Bildvariante erstellen', undefined, 'button quiet', ch.image.id) : ''}
        ${ch.corrections ? `<p>${ch.corrections} Textfehler automatisch korrigiert.</p>` : ''}
        ${ch.findings?.length || skillMarkup(ch.skills) ? `<details data-job-detail="chapter-${ch.number}-quality"><summary>Prüfdetails</summary>
          ${skillMarkup(ch.skills)}${ch.findings?.length ? issueMarkup(ch.findings) : ''}</details>` : ''}
        <div class="prose">${doc ? markdown(doc.body) : '<p>Kapitel wird geladen …</p>'}</div>
        <div class="editor-actions">${button('open-doc', 'Kapitel öffnen', 'text', 'button', ch.id)}
        ${button('production-edit-chapter', 'Überarbeiten', undefined, 'button', ch.id)}
        ${button('production-export-chapter', 'Kapitel exportieren', undefined, 'button quiet', ch.id)}</div>
      </details>`;
    }).join('')}
    ${job.cover ? `<details data-job-detail="cover"><summary>Titelbild</summary>
      ${media(job.cover.id, job.cover.alt, false)}${receiptMarkup(job.cover.visual_profile)}</details>` : ''}`;
}

export function artReviewDialog(job: ProductionJob, media: (id: string, alt: string, actions?: boolean) => string) {
  const assets = [
    ...(job.cover ? [{ title: 'Titelbild', image: job.cover, number: 0 }] : []),
    ...(job.chapter_results ?? []).filter(c => c.image).map(c => ({ title: c.number + '. ' + c.title, image: c.image!, number: c.number })),
  ];
  showDialog('Illustrationen prüfen', '<p>Gleiche Motive und Figuren mit den Kapiteln ab. Bestätige die Bildserie, wenn alle Zuordnungen stimmen.</p>'
    + assets.map(({ title, image, number }) => '<details><summary>' + esc(title) + '</summary>'
      + media(image.id, image.alt, false) + button('production-art-variant', 'Neue Fassung für das Manuskript',
        undefined, 'button quiet', job.id + ':' + number) + '</details>').join('')
    + '<div class="editor-actions">' + button('production-confirm-art', 'Bildserie freigeben', undefined, 'button primary', job.id) + '</div>', true);
}

export function manuscriptDialog(doc: Manuscript, pid: string, chapterNumber = 1) {
  const chapter = doc.chapters.find(c => c.number === chapterNumber);
  const thumbnail = (image?: Image) => image ? `<figure class="image-result"><button class="image-button" type="button"
    data-action="preview-image" data-value="${esc(image.id)}" aria-label="Bild vergrößern">
    <img src="/api/images/files/${esc(image.id)}" alt="${esc(image.alt)}"></button></figure>` : '';
  showDialog(doc.title, `${doc.subtitle ? '<p>' + esc(doc.subtitle) + '</p>' : ''}
    <p>${doc.complete ? 'Fertig' : 'Teilabschluss'} · ${number.format(doc.words)} Wörter</p>${chapterNumber === 1 ? thumbnail(doc.cover) : ''}
    <nav class="editor-actions" aria-label="Kapitelnavigation">${doc.chapters.map(c =>
      `<button type="button" class="button quiet" data-action="production-read-chapter" data-value="${esc(pid)}:${c.number}"
        ${c.number === chapterNumber ? 'aria-current="page"' : ''}>${c.number}. ${esc(c.title)}</button>`).join('')}</nav>
    ${chapter ? `<article class="prose"><h3>${esc(chapter.title)}</h3>${thumbnail(chapter.image)}${markdown(chapter.body ?? '', false)}</article>` : ''}
    ${chapterNumber === doc.chapters.length && doc.afterword ? '<div class="prose"><h3>Nachwort</h3>' + markdown(doc.afterword) + '</div>' : ''}
    ${doc.whole_review ? `<details><summary>Manuskriptprüfung</summary>${(doc.whole_review.reviews ?? []).map(r =>
      '<p>' + esc(r.assessment) + '</p>' + issueMarkup(r.findings)).join('')}${issueMarkup(doc.whole_review.repetitions)}</details>` : ''}
    ${doc.complete ? downloadLinks(doc.downloads) : ''}`, true);
}

function downloadLinks(links: ProductionJob['downloads']) {
  if (!links || !Object.keys(links).length) return '';
  return '<div class="editor-actions">' + Object.entries(links).map(([fmt, url]) =>
    /^\/api\/production\/jobs\/[a-f0-9]{32}\/files\/manuscript\.(md|mdx|zip)$/.test(url)
      ? `<a class="button" href="${esc(url)}" download>${esc(fmt.toUpperCase())} herunterladen</a>` : '').join('') + '</div>';
}

export async function exportManuscript(pid: string, format: string) {
  if (format !== 'md' && format !== 'mdx' && format !== 'zip') return;
  const document = await manuscript(pid);
  const url = document.downloads?.[format];
  if (!url || !/^\/api\/production\/jobs\/[a-f0-9]{32}\/files\/manuscript\.(md|mdx|zip)$/.test(url)) {
    throw new Error('production_manuscript_partial');
  }
  const link = window.document.createElement('a');
  link.href = url;
  link.download = '';
  link.click();
}
