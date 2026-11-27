// Production monitor: renders the derived job state of a story production. Every text below comes from a
// stored backend fact (state, counts, word counts, persisted events) or a live signal. Nothing is estimated.
import { esc } from './core';
import { button } from './studio-ui';

export type Health = { level: 'ok' | 'waiting' | 'quiet' | 'stalled' | 'worker_down' | 'none'; reason: string; quiet_for: number | null;
  checks: { worker_alive?: boolean | null; heartbeat_age?: number | null; model_active?: boolean; slot_processing?: boolean | null; tokens?: number | null } };
export type ModelRequest = { alias: string; role: string; prompt_tokens?: number; timeout?: number; started_at: number;
  state: 'unknown' | 'prefill' | 'generating' | 'idle_slot'; decoded: number | null; observed: boolean; progress_at: number };
export type Activity = { server_time: number; known: boolean; active?: boolean; heartbeat_at?: number | null; progress_at?: number | null;
  progress_kind?: string | null; worker?: { alive: boolean | null; busy_with: string | null; process_started_at: number };
  model?: ModelRequest | null;
  last_model?: { alias: string; role: string; finished_at: number; duration: number; completion_tokens?: number | null; chars?: number | null;
    outcome: 'ok' | 'timeout' | 'error'; error?: string | null } | null };
export type Step = 'generate' | 'human_audit' | 'story_audit' | 'correction' | 'final_check' | 'image' | 'image_check' | 'finish';
export type StepStatus = 'done' | 'running' | 'pending' | 'failed' | 'paused' | 'blocked' | 'stopped';
export type ChapterView = { number: number; title: string; minimum: number; maximum: number; status: 'done' | 'review' | 'active' | 'pending';
  words: number | null; image: boolean; steps: Record<Step, StepStatus>; corrections: number };
export type LengthFacts = { number: number; words: number; minimum: number; maximum: number; state: 'short' | 'long' | 'ok'; missing: number;
  excess: number; attempts: number; failed_attempts: number; attempt_limit: number; passes: number; reasons: Record<string, number>; in_progress: boolean };
export type TimelineEvent = { at: number; id: string; number: number | null; step: string; status: string; duration: number | null;
  attempts?: number; ref: string | null; error?: string; words?: number; corrections?: number; blocked?: boolean };
export type Monitor = {
  state: string; awaiting: string | null; phase: string; step_started_at: number | null; last_saved_at: number; created_at: number;
  server_time: number; health: Health; activity: Activity | null; timeline: TimelineEvent[];
  title?: string; language?: string; planned_chapters?: number; current_chapter?: number | null;
  counts?: Record<'chapters' | 'images' | 'exports' | 'steps', { done: number; total: number }>;
  chapters?: ChapterView[]; length?: LengthFacts | null;
  failure?: { code: string | null; number: number | null; attempts: number; automatic_retries: number; exhausted: boolean;
    checkpoint: { chapter: number | null; words: number | null } } | null;
};
export type Link = { state: 'live' | 'polling' | 'lost'; lastOk?: number; failures: number; offset: number };

const number = new Intl.NumberFormat('de');
type Tone = 'work' | 'ok' | 'warn' | 'bad' | 'pause' | 'neutral';
export const stateInfo: Record<string, { label: string; tone: Tone; glyph: string; hint: string }> = {
  preparing: { label: 'Wird vorbereitet', tone: 'work', glyph: '◌', hint: 'Die Produktion wird eingerichtet.' },
  running: { label: 'Läuft', tone: 'work', glyph: '●', hint: 'Ein Backend-Schritt wird ausgeführt.' },
  model_wait: { label: 'Wartet auf Modell', tone: 'work', glyph: '◐', hint: 'Eine Modellanfrage wurde abgeschickt und ist noch nicht beantwortet.' },
  verifying: { label: 'Wird überprüft', tone: 'work', glyph: '◎', hint: 'Ein Audit oder eine Validierung läuft.' },
  correcting: { label: 'Wird automatisch korrigiert', tone: 'work', glyph: '✎', hint: 'Das Studio bearbeitet bestätigte Befunde.' },
  retrying: { label: 'Wird erneut versucht', tone: 'warn', glyph: '↻', hint: 'Ein begrenzter automatischer Wiederholungsversuch ist aktiv.' },
  paused: { label: 'Pausiert', tone: 'pause', glyph: 'II', hint: 'Die Produktion ist bewusst angehalten.' },
  needs_decision: { label: 'Benutzerentscheidung erforderlich', tone: 'warn', glyph: '!', hint: 'Ein bestätigter Konflikt lässt sich nicht selbstständig lösen.' },
  failed: { label: 'Fehlgeschlagen', tone: 'bad', glyph: '✕', hint: 'Ein Verarbeitungsschritt ist beendet, ohne sein Ziel zu erreichen.' },
  completed: { label: 'Abgeschlossen', tone: 'ok', glyph: '✓', hint: 'Alle erforderlichen Artefakte wurden validiert.' },
  cancelled: { label: 'Abgebrochen', tone: 'neutral', glyph: '–', hint: 'Die Produktion wurde abgebrochen.' },
  incomplete: { label: 'Unvollständig', tone: 'warn', glyph: '!', hint: 'Mindestens eine geprüfte Exportdatei fehlt.' },
  lost: { label: 'Verbindung unterbrochen', tone: 'warn', glyph: '⚠', hint: 'Das Studio kann den Backend-Status gerade nicht abrufen. Der Auftrag läuft im Backend weiter.' },
};
const stepLabels: Record<Step, string> = { generate: 'Textgenerierung', human_audit: 'Human-Writing-Prüfung', story_audit: 'Story-Writing-Prüfung',
  correction: 'Automatische Korrektur', final_check: 'Finale Textprüfung', image: 'Bildgenerierung', image_check: 'Bildprüfung', finish: 'Abschluss' };
const stepStatus: Record<StepStatus, string> = { done: 'abgeschlossen', running: 'läuft', pending: 'wartet', failed: 'fehlgeschlagen', paused: 'pausiert',
  blocked: 'wartet auf Entscheidung', stopped: 'abgebrochen' };
const stepGlyph: Record<StepStatus, string> = { done: '✓', running: '●', pending: '○', failed: '✕', paused: 'II', blocked: '!', stopped: '–' };
const phaseText: Record<string, string> = {
  writing: 'Kapitel {n} wird geschrieben', auditing: 'Kapitel {n}: Der Text wird geprüft', reviewed: 'Kapitel {n}: Befunde werden automatisch korrigiert',
  rewrite_audit: 'Kapitel {n}: Die Überarbeitung wird geprüft', text_finalize: 'Kapitel {n}: Finale Textprüfung', illustrating: 'Kapitel {n}: Bildszene wird vorbereitet',
  image_prompt: 'Kapitel {n}: Bildszene wird ausgewählt', image_queue: 'Kapitel {n}: Bildauftrag wird angelegt', image_wait: 'Kapitel {n}: Bild wird erzeugt',
  image_archive: 'Kapitel {n}: Bilddatei wird geprüft', finalizing: 'Kapitel {n} wird abgeschlossen', awaiting_chapter: 'Kapitel {n} wartet auf Freigabe',
  advance: 'Kapitel {n} abgeschlossen', cover: 'Titelbild wird erzeugt', manuscript: 'Das Gesamtmanuskript wird geprüft', export_generation: 'Die Exportdateien werden erzeugt',
  final_validation: 'Manuskript und Dateien werden validiert', art_variant: 'Bildvariante wird erzeugt', art_review: 'Illustrationen warten auf Sichtprüfung', done: 'Produktion abgeschlossen',
};
const reasonText: Record<string, string> = { anchor: 'ungültiger Anschlusspunkt', empty: 'leere Erweiterung', placeholder: 'Platzhaltertext', aside: 'Kommentar statt Erzähltext',
  repetition: 'wiederholter Text', range: 'Wortzahl außerhalb des Bereichs' };
const progressKind: Record<string, string> = { step: 'Arbeitsschritt gestartet', checkpoint: 'Zwischenstand gespeichert', model_request: 'Modellanfrage gesendet',
  tokens: 'neue Token empfangen', model_response: 'Modellantwort erhalten' };
const timelineLabels: Record<string, string> = { started: 'Produktion gestartet', writing: 'Kapitel {n} generiert', auditing: 'Human-Writing- und Story-Writing-Prüfung (Kapitel {n})',
  reviewed: 'Automatische Korrektur (Kapitel {n})', rewrite_audit: 'Überarbeitung geprüft (Kapitel {n})', text_finalize: 'Finale Textprüfung (Kapitel {n})',
  illustrating: 'Bildszene vorbereitet (Kapitel {n})', image_prompt: 'Bildszene ausgewählt (Kapitel {n})', image_queue: 'Bildjob angelegt (Kapitel {n})',
  image_wait: 'Bildjob abgewartet (Kapitel {n})', image_archive: 'Kapitelbild validiert (Kapitel {n})', finalizing: 'Kapitel {n} finalisiert',
  awaiting_chapter: 'Kapitel {n} zur Freigabe', advance: 'Kapitel {n} abgeschlossen', cover: 'Titelbild', manuscript: 'Gesamtmanuskript geprüft',
  export_generation: 'Exporte erzeugt', final_validation: 'Exporte validiert', art_variant: 'Bildvariante', art_review: 'Bildserie zur Sichtprüfung', done: 'Produktion abgeschlossen' };

// ---- time helpers --------------------------------------------------------------------------------------
export const serverNow = (link: Pick<Link, 'offset'>) => Date.now() / 1000 - link.offset;
export const clock = (seconds: number) => new Date(seconds * 1000).toLocaleTimeString('de', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
export function span(seconds: number) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} Min. ${s % 60} s`;
  return `${Math.floor(s / 3600)} Std. ${Math.floor((s % 3600) / 60)} Min.`;
}
const ago = (seconds: number) => seconds < 3 ? 'gerade eben' : 'vor ' + span(seconds);
// <time data-age> and <time data-elapsed> are refreshed every second without re-rendering the card.
const stamp = (at: number | null | undefined, mode: 'age' | 'elapsed' = 'age') => at
  ? `<time data-${mode}="${at}" datetime="${new Date(at * 1000).toISOString()}">${esc(clock(at))}</time>` : 'noch nicht erfasst';
export function refreshTimes(root: ParentNode, link: Pick<Link, 'offset'>) {
  const now = serverNow(link);
  root.querySelectorAll<HTMLElement>('time[data-age], time[data-elapsed]').forEach(node => {
    const at = Number(node.dataset.age ?? node.dataset.elapsed);
    node.textContent = node.dataset.age ? `${clock(at)} · ${ago(now - at)}` : span(now - at);
  });
}

// ---- derived presentation -------------------------------------------------------------------------------
export function chapterWords(chapter: ChapterView) {
  const range = `${number.format(chapter.minimum)}–${number.format(chapter.maximum)}`;
  if (chapter.status === 'done' || chapter.status === 'review') return `${number.format(chapter.words ?? 0)} Wörter`;
  return chapter.words === null ? `Ziel ${range} Wörter` : `${number.format(chapter.words)} Wörter · Ziel ${range}`;
}

function chapterStatus(chapter: ChapterView, monitor: Monitor) {
  if (chapter.status === 'done') return 'abgeschlossen';
  if (chapter.status === 'review') return 'wartet auf Freigabe';
  if (chapter.status === 'pending') return 'wartet';
  if (monitor.state === 'failed') return 'fehlgeschlagen';
  if (monitor.state === 'needs_decision') return 'Entscheidung erforderlich';
  if (monitor.state === 'paused') return 'pausiert';
  if (['reviewed', 'rewrite_audit', 'text_finalize'].includes(monitor.phase)) return 'Überarbeitung';
  if (monitor.phase === 'writing') return 'Schreiben';
  if (monitor.phase === 'auditing') return 'Prüfung';
  return 'Bild und Abschluss';
}

export function lengthSentence(facts: LengthFacts) {
  const range = `${number.format(facts.minimum)}–${number.format(facts.maximum)}`;
  if (facts.state === 'short') return `Kapitel ${facts.number}: ${number.format(facts.words)} von mindestens ${number.format(facts.minimum)} Wörtern. Es fehlen ${number.format(facts.missing)} Wörter.`;
  if (facts.state === 'long') return `Kapitel ${facts.number}: ${number.format(facts.words)} Wörter bei höchstens ${number.format(facts.maximum)}. Es sind ${number.format(facts.excess)} Wörter zu viel.`;
  return `Kapitel ${facts.number}: ${number.format(facts.words)} Wörter, Zielbereich ${range} erreicht.`;
}

function reasonList(facts: LengthFacts) {
  const entries = Object.entries(facts.reasons).map(([key, count]) => `${reasonText[key] ?? key} (${count}×)`);
  return entries.length ? entries.join(', ') : '';
}

export type FailureText = { headline: string; cause?: string; next?: string };
export function failureText(job: { error?: string; detail?: unknown; phase?: string }, monitor: Monitor, errors: Record<string, string>,
  phaseFailures: Record<string, string>): FailureText {
  const facts = monitor.length, failure = monitor.failure;
  const n = failure?.number ?? monitor.current_chapter ?? undefined;
  if (job.error === 'story_length_failed') {
    if (facts && facts.state === 'short') {
      const reasons = reasonList(facts);
      return failure?.exhausted
        ? { headline: `Kapitel ${facts.number} konnte die gewünschte Länge nach den automatischen Überarbeitungen nicht erreichen.`,
            cause: `${lengthSentence(facts)} ${facts.attempts} automatische Erweiterungsversuche wurden verworfen`
              + (reasons ? `: ${reasons}.` : '. Zur Ursache der einzelnen Versuche liegt keine Angabe vor.'),
            next: 'Du kannst den gespeicherten Text öffnen und selbst ergänzen oder die automatische Erweiterung erneut ausführen.' }
        : { headline: `Kapitel ${facts.number} ist noch zu kurz.`, cause: lengthSentence(facts), next: 'Der Schritt kann erneut ausgeführt werden.' };
    }
    if (facts && facts.state === 'long') {
      return { headline: `Kapitel ${facts.number} ist länger als der freigegebene Bereich.`, cause: lengthSentence(facts),
        next: 'Kürze den gespeicherten Text oder führe den Schritt erneut aus.' };
    }
    return { headline: `Kapitel ${n ?? ''} hat die verlangte Länge oder Textqualität nicht erreicht.`.replace('  ', ' '),
      cause: errors.story_length_failed, next: 'Der Schritt kann erneut ausgeführt werden.' };
  }
  const detail = job.detail && typeof job.detail === 'object' && !Array.isArray(job.detail) ? job.detail as Record<string, string> : {};
  if (detail.exception === 'TimeoutError') {
    return { headline: `${n ? `Kapitel ${n}: ` : ''}Die Modellanfrage hat das Zeitlimit überschritten.`,
      cause: 'Das lokale Modell hat innerhalb der erlaubten Zeit nicht geantwortet. Die automatischen Wiederholungsversuche sind ausgeschöpft.',
      next: 'Prüfe, ob das Modell geladen ist, und führe den Schritt erneut aus. Der gespeicherte Stand bleibt erhalten.' };
  }
  const phase = job.phase ? phaseFailures[job.phase] : undefined;
  return { headline: `${n ? `Kapitel ${n}: ` : ''}${phase ?? 'Der Schritt ist fehlgeschlagen'}.`,
    cause: (job.error && errors[job.error]) || errors.production_step_failed, next: 'Der gespeicherte Stand bleibt erhalten. Du kannst den Schritt erneut ausführen.' };
}

export function activityText(job: { image_state?: string; retry?: { attempt: number }; step?: string }, monitor: Monitor, failure?: FailureText) {
  const n = monitor.current_chapter ?? '';
  const base = (() => {
    if (monitor.state === 'completed') return 'Produktion abgeschlossen';
    if (monitor.state === 'cancelled') return 'Produktion abgebrochen';
    if (monitor.state === 'incomplete') return 'Produktion unvollständig: Exportdateien fehlen.';
    if (monitor.state === 'preparing') return 'Die Produktion wird eingerichtet.';
    let text = (phaseText[monitor.phase] ?? 'Produktion').replace('{n}', String(n));
    if (monitor.phase === 'image_wait' && job.image_state === 'waiting_gpu') text = `Kapitel ${n}: Das Bild wartet auf einen freien GPU-Slot`;
    if (monitor.phase === 'image_wait' && job.step === 'cover') text = 'Titelbild wird erzeugt';
    return text;
  })();
  if (monitor.state === 'failed' && failure) return failure.headline;
  if (monitor.state === 'needs_decision') return `Kapitel ${n}: Ein bestätigter Konflikt braucht eine Entscheidung.`;
  if (monitor.state === 'paused') {
    const why = { chapter_approval: 'Das Kapitel wartet auf deine Freigabe.', art_review: 'Die Bildserie wartet auf deine Sichtprüfung.',
      language_retry: 'Ein bestätigter Sprachfehler lässt sich automatisch korrigieren.', recheck: 'Das gespeicherte Kapitel kann erneut geprüft werden.' }[monitor.awaiting ?? ''];
    return why ?? `Angehalten: ${base}`;
  }
  if (monitor.state === 'retrying') return `Automatischer Wiederholungsversuch ${job.retry?.attempt ?? ''} von 2. ${base}`.replace('  ', ' ');
  return base;
}

export function healthText(monitor: Monitor, link: Link) {
  const { health, activity } = monitor;
  if (link.state === 'lost') {
    return { tone: 'warn' as Tone, label: 'Backend-Verbindung unterbrochen',
      text: 'Das Studio erreicht das Backend gerade nicht. Der Produktionsauftrag läuft dort unabhängig vom Browser weiter. Angezeigt wird der letzte bekannte Stand.' };
  }
  if (!['queued', 'running'].includes(storedStatus(monitor))) return null;
  const model = activity?.model;
  switch (health.level) {
    case 'ok':
      if (model?.state === 'generating') return { tone: 'ok' as Tone, label: 'Worker erreichbar, Modell generiert', text: `Das Modell meldet ${number.format(model.decoded ?? 0)} erzeugte Token.` };
      if (model?.state === 'prefill') return { tone: 'ok' as Tone, label: 'Worker erreichbar, Modell verarbeitet den Prompt', text: 'Der Modellslot ist belegt und liest den Prompt ein. Bei langem Kontext dauert das mehrere Minuten.' };
      if (model) return { tone: 'ok' as Tone, label: 'Worker erreichbar, Modellanfrage läuft', text: 'Der Modellfortschritt ist nicht einsehbar. Die Anfrage ist offen und innerhalb ihres Zeitlimits.' };
      return { tone: 'ok' as Tone, label: 'Worker erreichbar', text: health.reason === 'checkpoint_only' ? 'Es liegt kein Live-Signal vor. Angezeigt wird der zuletzt gespeicherte Stand.' : 'Der Arbeitsschritt läuft.' };
    case 'waiting': return { tone: 'warn' as Tone, label: 'Wartet auf den Worker', text: 'Der Produktions-Worker bearbeitet zuerst einen anderen Auftrag.' };
    case 'quiet': return { tone: 'warn' as Tone, label: 'Worker erreichbar, aber kein neuer Fortschritt',
      text: 'Seit längerer Zeit kein neuer Fortschritt bestätigt. Der Prozessstatus wird überprüft.' };
    case 'stalled': return { tone: 'bad' as Tone, label: 'Fortschritt ausgeblieben (geprüft)',
      text: health.reason === 'model_slot_idle' ? 'Die Modellanfrage ist offen, der Modellslot meldet aber keine Aktivität.'
        : 'Der Modellslot ist belegt, meldet aber seit längerer Zeit keine neuen Token.' };
    case 'worker_down': return { tone: 'bad' as Tone, label: 'Worker nicht erreichbar',
      text: health.reason === 'heartbeat_lost' ? 'Der Heartbeat des Produktions-Workers ist ausgeblieben.' : 'Der Produktions-Worker läuft nicht. Nach einem Neustart des Studios setzt der Auftrag an seinem gespeicherten Schritt an.' };
    default: return null;
  }
}
const storedStatus = (monitor: Monitor) => ['preparing', 'running', 'model_wait', 'verifying', 'correcting', 'retrying'].includes(monitor.state) ? 'running' : monitor.state;

// ---- markup --------------------------------------------------------------------------------------------
const badge = (key: string, link?: Link) => {
  const info = stateInfo[link?.state === 'lost' ? 'lost' : key] ?? stateInfo.running;
  return `<p class="prod-status" data-tone="${info.tone}" data-state="${esc(key)}"><span class="prod-glyph" aria-hidden="true">${info.glyph}</span>`
    + `<strong>${esc(info.label)}</strong></p>`;
};

function bar(label: string, done: number, total: number) {
  return `<div class="prod-meter"><span>${esc(label)}</span><progress max="${total}" value="${done}" aria-label="${esc(label)}: ${done} von ${total}"></progress>`
    + `<span class="prod-count">${number.format(done)} / ${number.format(total)}</span></div>`;
}

export function liveMarkup(monitor: Monitor, link: Link) {
  const status = healthText(monitor, link);
  const { activity } = monitor;
  const running = ['preparing', 'running', 'model_wait', 'verifying', 'correcting', 'retrying'].includes(monitor.state);
  const facts: Array<[string, string]> = [['Jobstatus', esc(stateInfo[monitor.state]?.label ?? monitor.state)],
    ['Verbindung', link.state === 'live' ? 'Live-Ereignisstrom' : link.state === 'polling' ? 'Abfrage alle 2 Sekunden' : 'unterbrochen']];
  if (running || link.state === 'lost') {
    facts.push(['Letzter Heartbeat', activity?.heartbeat_at ? stamp(activity.heartbeat_at) : 'kein Live-Signal seit dem Studio-Start']);
    facts.push(['Letzter Fortschritt', activity?.progress_at ? `${stamp(activity.progress_at)} (${esc(progressKind[activity.progress_kind ?? ''] ?? 'Fortschritt')})`
      : `${stamp(monitor.last_saved_at)} (Zwischenstand gespeichert)`]);
    const model = activity?.model, last = activity?.last_model;
    facts.push(['Modellanfrage', model ? `aktiv seit ${stamp(model.started_at, 'elapsed')} · ${esc(model.alias)}`
      : last ? `abgeschlossen ${stamp(last.finished_at)} · ${last.outcome === 'ok' ? 'beantwortet' : last.outcome === 'timeout' ? 'Zeitlimit überschritten' : 'Fehler'}`
        : 'keine aktive Anfrage']);
    if (model?.decoded) facts.push(['Empfangen', `${number.format(model.decoded)} Token`]);
    else if (!model && last?.completion_tokens) facts.push(['Empfangen', `${number.format(last.completion_tokens)} Token${last.chars ? ` · ${number.format(last.chars)} Zeichen gespeichert` : ''}`]);
    if (monitor.step_started_at) {
      facts.push(['Schritt gestartet', clock(monitor.step_started_at)], ['Bisherige Laufzeit', stamp(monitor.step_started_at, 'elapsed')]);
    }
  } else {
    facts.push(['Letzte gespeicherte Änderung', stamp(monitor.last_saved_at)]);
  }
  return `<div data-live-panel>${status ? `<p class="prod-health" data-tone="${status.tone}"><strong>${esc(status.label)}</strong><span>${esc(status.text)}</span></p>` : ''}
    <dl class="prod-facts">${facts.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl></div>`;
}

function timelineEntry(event: TimelineEvent, last: boolean) {
  const n = event.number ?? '';
  let text = (timelineLabels[event.step] ?? event.step).replace('{n}', String(n));
  let state = last && event.status === 'running' && event.duration === null ? 'läuft' : 'abgeschlossen';
  if (event.status === 'failed') {
    text = event.error === 'story_length_failed' ? `Wortzahlprüfung fehlgeschlagen (Kapitel ${n}${event.words ? `, ${number.format(event.words)} Wörter` : ''})` : `${text}: fehlgeschlagen`;
    state = 'fehlgeschlagen';
  } else if (event.status === 'paused') {
    text = event.blocked ? `Konflikt in Kapitel ${n} wartet auf Entscheidung` : `Pausiert (${text})`;
    state = event.blocked ? 'Entscheidung erforderlich' : 'pausiert';
  } else if (event.corrections && event.step === 'reviewed') {
    text += ` · ${event.corrections} Korrektur${event.corrections === 1 ? '' : 'en'}`;
  }
  if (event.attempts && event.attempts > 1) text += ` · Versuch ${event.attempts}`;
  return `<li><time datetime="${new Date(event.at * 1000).toISOString()}">${esc(clock(event.at))}</time>
    <span>${esc(text)}<span class="prod-event-meta"> · ${esc(state)}${event.duration !== null && event.duration >= 1 ? ' · ' + esc(span(event.duration)) : ''}
    · <code>${esc(event.id)}</code>${event.ref ? ` · Referenz <code>${esc(event.ref)}</code>` : ''}</span></span></li>`;
}

export function timelineMarkup(events: TimelineEvent[]) {
  const shown = [...events].reverse();
  return `<details data-job-detail="timeline"><summary>Aktivitätsverlauf (${events.length})</summary>
    <ol class="prod-timeline" aria-label="Aktivitätsverlauf, neueste zuerst">${shown.map((event, index) => timelineEntry(event, index === 0)).join('')}</ol></details>`;
}

export function stepsMarkup(chapter: ChapterView) {
  return `<ol class="prod-steps" aria-label="Arbeitsschritte Kapitel ${chapter.number}">${(Object.keys(stepLabels) as Step[]).map(step => {
    const status = chapter.steps[step];
    const extra = step === 'correction' && status === 'done' && chapter.corrections ? ` · ${chapter.corrections} Textfehler korrigiert` : '';
    return `<li data-step="${step}" data-status="${esc(status)}"><span class="prod-glyph" aria-hidden="true">${stepGlyph[status]}</span>`
      + `<span>${esc(stepLabels[step])}</span><span class="prod-step-state">${esc(stepStatus[status] + extra)}</span></li>`;
  }).join('')}</ol>`;
}

export function chapterSummary(chapter: ChapterView, monitor: Monitor) {
  const parts = [`Kapitel ${chapter.number}`, chapterStatus(chapter, monitor), chapterWords(chapter)];
  if (chapter.image) parts.push('Bild vorhanden');
  return parts.join(' – ');
}

export type Controls = { draft?: string; language_retry_available?: boolean; recheck_available?: boolean; pause_reason?: string;
  art_review_pending?: boolean; project_id: string; id: string; hasChapters: boolean; downloads?: string; images: boolean };
export function actionMarkup(monitor: Monitor, c: Controls) {
  const details = button('production-details', 'Details anzeigen', undefined, 'button quiet', c.id);
  const cancel = button('production-cancel', 'Abbrechen', undefined, 'button quiet', c.id);
  switch (monitor.state) {
    case 'paused':
      return (monitor.awaiting === 'art_review' ? button('production-approve-art', 'Illustrationen prüfen', undefined, 'button primary', c.id)
        : monitor.awaiting === 'language_retry' ? button('production-retry', 'Sprachkorrektur erneut versuchen', undefined, 'button primary', c.id)
        : button('production-resume', monitor.awaiting === 'chapter_approval' ? 'Kapitel freigeben und fortsetzen' :
          monitor.awaiting === 'recheck' ? 'Gespeichertes Kapitel erneut prüfen' : 'Fortsetzen', undefined, 'button primary', c.id)) + details + cancel;
    case 'needs_decision':
      return (c.draft ? button('production-edit-chapter', 'Konkreten Konflikt bearbeiten', undefined, 'button primary', c.draft) : '')
        + button('production-resume', 'Danach fortsetzen', undefined, 'button', c.id) + details;
    case 'failed':
      return button('production-retry', 'Fehlgeschlagenen Schritt erneut ausführen', undefined, 'button primary', c.id)
        + (c.draft ? button('open-doc', 'Gespeicherten Text öffnen', undefined, 'button', c.draft) : '') + details + cancel;
    case 'completed':
      return (c.hasChapters ? button('production-manuscript', 'Manuskript öffnen', 'book', 'button primary', c.project_id) : '')
        + (c.images ? button('production-view-images', 'Bilder ansehen', undefined, 'button', c.id) : '')
        + (c.art_review_pending ? button('production-approve-art', 'Illustrationen prüfen', undefined, 'button quiet', c.id) : '')
        + (c.downloads ?? '') + details;
    case 'incomplete': return button('production-recover', 'Produktion vervollständigen', undefined, 'button primary', c.project_id) + details;
    case 'cancelled': return details;
    default: // Running states never offer a retry for the step that is still running.
      return button('production-pause', 'Pausieren', undefined, 'button', c.id) + details;
  }
}

export function headMarkup(monitor: Monitor, link: Link, headline: string, failure?: FailureText) {
  const effective = monitor.state;
  const chapters = monitor.planned_chapters ?? 0;
  const lang = monitor.language === 'en' ? 'Englisch' : 'Deutsch';
  const hint = stateInfo[effective]?.hint ?? '';
  return `<header class="prod-head"><div><h3 class="prod-title">${esc(monitor.title ?? 'Story-Produktion')}</h3>
    <p class="prod-meta">${esc(lang)} · ${chapters} Kapitel geplant${monitor.current_chapter ? ` · aktuell Kapitel ${monitor.current_chapter}` : ''}</p></div>
    <div class="prod-status-wrap">${badge(effective)}${link.state === 'lost' ? badge('lost', link) : ''}</div></header>
    <p class="job-title prod-now" data-prod-now>${esc(headline)}</p>
    ${failure?.cause ? `<p class="prod-cause">${esc(failure.cause)}</p>` : ''}${failure?.next ? `<p class="prod-next">${esc(failure.next)}</p>` : ''}
    ${failure ? '' : `<p class="prod-hint">${esc(hint)}</p>`}`;
}

export function progressMarkup(monitor: Monitor) {
  const c = monitor.counts;
  if (!c) return '';
  return `<section class="prod-progress" aria-label="Fortschritt"><div class="prod-meter prod-total"><span>Gesamtfortschritt</span>
    <progress max="${c.steps.total}" value="${c.steps.done}" aria-label="Gesamtfortschritt: ${c.steps.done} von ${c.steps.total} Arbeitsschritten"></progress>
    <span class="prod-count">${c.steps.done} von ${c.steps.total} Arbeitsschritten</span></div>
    ${bar('Kapitel abgeschlossen', c.chapters.done, c.chapters.total)}${bar('Bilder geprüft', c.images.done, c.images.total)}${bar('Exporte fertig', c.exports.done, c.exports.total)}</section>`;
}
