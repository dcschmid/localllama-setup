import { diffLines, diffWordsWithSpace, type Change } from 'diff';
import { esc } from './core';
import { button, formatDate } from './studio-ui';

export interface EditorialEvidence {
  model: string;
  skill_version: string;
  mode: string;
  language: 'en' | 'de';
  rules: Array<{ reference: string }>;
}
export interface Finding {
  rule: string;
  category: string;
  severity: string;
  line: number;
  col: number;
  excerpt: string;
  why: string;
  fix: string;
}
interface Anchor { line: number; quote: string; anchor?: 'quote' | 'paragraph' }
interface Observation extends Anchor { topic?: string; note: string; suggestion?: string }
interface AuditOutcome { findings: number; observations: number; model_error?: string }
export interface RunSummary {
  id: string;
  document_id?: string;
  mode: 'audit' | 'review' | 'rewrite';
  state: string;
  created: number;
  base_version: number;
  accepted_version?: number;
}
export interface EditorialRun extends RunSummary {
  document_id: string;
  evidence?: EditorialEvidence;
  lint?: { findings: Finding[]; skill_version: string; lang: string };
  model_error?: string;
  observations?: Observation[];
  strengths?: Observation[];
  original?: string;
  text?: string;
  goal?: keyof typeof goals;
  instruction?: string;
  range?: [number, number] | null;
  reasons?: Array<Anchor & { reason: string }>;
  words?: number;
  before_findings?: number;
  after_findings?: number;
  choices?: Array<{ paragraph: number; before: string; after: string }>;
}
export interface EditorialHistory {
  runs: RunSummary[];
  evidence?: EditorialEvidence;
  lint?: { skill_version: string; lang: string };
  model_error?: string;
  last_audit?: AuditOutcome;
}
export interface Edition { label: string; body: string; title?: string | null; lang?: string | null }

const categories: Record<string, [string, string]> = {
  signposting: ['Einleitung mit Füllformel', 'Beginne bei der Szene oder Aussage selbst.'],
  'artificial-contrast': ['Kontrastformel', 'Prüfe, ob der Kontrast inhaltlich nötig ist.'],
  'promotional-inflation': ['Überhöhter Ausdruck', 'Suche ein präzises Detail, das die Aussage trägt.'],
  'empty-conclusion': ['Wiederholter Schluss', 'Prüfe, was der letzte Satz zur Geschichte oder Aussage beiträgt.'],
  'synthetic-enthusiasm': ['Übersteigerte Betonung', 'Prüfe, ob die Betonung zur Stimme und Situation passt.'],
  repetition: ['Wiederholung', 'Behalte Wiederholungen, die Rhythmus, Bedeutung oder ein Motiv tragen.'],
  rhythm: ['Gleichförmiger Satzrhythmus', 'Prüfe, ob kürzere und längere Sätze unterschiedlich wirken können.'],
  'rule-of-three': ['Dreierreihe', 'Prüfe, ob alle drei Teile etwas Eigenes beitragen.'],
  'formatting-overuse': ['Dichte Hervorhebungen', 'Setze Hervorhebungen dort ein, wo sie die Leseführung stützen.'],
  'generic-transition': ['Allgemeiner Übergang', 'Verbinde die Absätze über ihren Inhalt.'],
  'pseudo-profundity': ['Vage Aussage', 'Ersetze die Abstraktion durch einen konkreten Gedanken oder ein beobachtbares Detail.'],
  hedging: ['Gehäufte Abschwächung', 'Behalte Abschwächungen, die echte Unsicherheit oder die Stimme zeigen.'],
};
export const goals = {
  clarity: 'Natürlicher und klarer',
  concise: 'Straffer erzählen',
  dialogue: 'Dialoge und Figurenstimmen',
  scene: 'Atmosphäre und Erzähltempo',
  custom: 'Eigener Auftrag',
  finding: 'Gewählten Befund bearbeiten',
} as const;
export function findingHint(f: Finding) {
  return categories[f.category] ?? ['Stilhinweis', f.fix || f.why];
}

export const modeLabel = (mode: string) =>
  ({ audit: 'Textprüfung', review: 'Story Quality Review', rewrite: 'Überarbeitung', generate: 'Texterstellung' })[mode] ?? mode;

export function proofMarkup(value?: Pick<EditorialHistory, 'evidence' | 'lint' | 'model_error' | 'last_audit'>) {
  if (!value?.evidence && !value?.lint) return '';
  return `<details class="writing-proof"><summary>Human Writing aktiv</summary><ul class="plain-list">
    ${value.evidence ? `<li>${esc(value.evidence.model)} · Skill ${esc(value.evidence.skill_version)} · ${esc(modeLabel(value.evidence.mode))}</li>
      <li>${value.evidence.rules.map(rule => esc(rule.reference.replace(/^references\//, ''))).join(', ')}</li>` : ''}
    ${value.lint ? `<li>Lokaler Linter · Skill ${esc(value.lint.skill_version)} · ${value.lint.lang === 'en' ? 'Englisch' : 'Deutsch'}</li>` : ''}
    ${value.last_audit ? `<li>Letzte Prüfung · ${value.last_audit.findings} Linter-Funde · ${value.last_audit.observations} redaktionelle Befunde${value.last_audit.model_error ? ' · ' + esc(modelMessage(value.last_audit.model_error)) : ''}</li>` : ''}
    ${value.model_error ? '<li>' + esc(modelMessage(value.model_error)) + '</li>' : ''}</ul></details>`;
}

export function modelMessage(code: string) {
  return ({
    writing_template_mismatch: 'Das Modell konnte die erforderlichen Skill-Regeln nicht nachweisen.',
    editorial_no_anchors: 'Das Modell lieferte keine überprüfbaren Zitate.',
    editorial_text_limit: 'Für die Modellprüfung ist eine kürzere Textpassage nötig.',
  } as Record<string, string>)[code] ?? 'Die Modellprüfung war gerade nicht verfügbar.';
}

export function auditMarkup(run: EditorialRun) {
  const findings = run.lint?.findings ?? [];
  const observations = run.observations ?? [];
  return `<div class="editorial-report">
    <p class="muted">Geprüft am ${esc(formatDate(run.created))} · Ausgangsversion ${run.base_version}${run.range ? ' · Markierter Ausschnitt' : ''}</p>
    <section class="editorial-section"><h3>Automatische Linter-Funde</h3>
    <p>${findings.length ? `${findings.length} ${findings.length === 1 ? 'Fund' : 'Funde'} des lokalen Skills` : 'Der lokale Linter hat keine Fundstellen markiert.'}</p>
    ${findings.length ? `<ul class="plain-list editorial-findings">${findings.map((finding, index) => {
      const [label, hint] = findingHint(finding);
      return `<li><strong>${esc(label)}</strong> <span class="muted">· Zeile ${finding.line}</span>
        ${finding.excerpt ? `<blockquote>${esc(finding.excerpt)}</blockquote>` : ''}
        <p>${esc(hint)}</p>${button('editor-finding', 'Diese Stelle verbessern', undefined, 'button quiet', String(index))}</li>`;
    }).join('')}</ul>` : ''}</section>
    <section class="editorial-section"><h3>Redaktionelle Einschätzungen des Modells</h3>
    ${run.model_error ? `<p>${esc(modelMessage(run.model_error))}</p>` : ''}
    ${observations.length ? `<ul class="plain-list editorial-findings">${observations.map((item, index) => `<li>
      <strong>${esc(item.topic ?? 'Textstelle')}</strong> <span class="muted">· Zeile ${item.line}${item.anchor === 'paragraph' ? ' · Absatzbezug' : ''}</span>
      <blockquote>${esc(item.quote)}</blockquote><p>${esc(item.note)}</p>${item.suggestion ? `<p>${esc(item.suggestion)}</p>
      ${button('editor-observation', 'Diese Stelle verbessern', undefined, 'button quiet', String(index))}` : ''}</li>`).join('')}</ul>` : ''}
    ${run.strengths?.length ? `<h4>Gelungene Stellen</h4><ul class="plain-list editorial-findings">${run.strengths.map(item =>
      `<li><blockquote>${esc(item.quote)}</blockquote><p>${esc(item.note)}</p></li>`).join('')}</ul>` : ''}
    </section>${proofMarkup(run)}</div>`;
}

function diffPane(parts: Change[], added: boolean) {
  return parts.map(part => part.added
    ? (added ? `<ins>${esc(part.value)}</ins>` : '')
    : part.removed ? (added ? '' : `<del>${esc(part.value)}</del>`) : esc(part.value)).join('');
}

export function compareMarkup(before: Edition, after: Edition) {
  const same = before.body === after.body && (!before.title || !after.title || before.title === after.title);
  const changes = before.body.length + after.body.length < 20_000
    ? diffWordsWithSpace(before.body, after.body, { timeout: 100, maxEditLength: 2500 })
    : diffLines(before.body, after.body, { timeout: 100, maxEditLength: 2000 });
  const titleChanged = before.title && after.title && before.title !== after.title;
  const titles = titleChanged ? [
    `<p>Titel <del>${esc(before.title!)}</del></p>`, `<p>Titel <ins>${esc(after.title!)}</ins></p>`,
  ] : ['', ''];
  const content = (value: Edition, index: number) => `<section class="edition-pane">
    <h3 id="edition-${index}">${esc(value.label)}</h3>${titles[index]}
    <pre class="edition-text" tabindex="0" aria-labelledby="edition-${index}"${value.lang ? ` lang="${esc(value.lang)}"` : ''}>${changes ? diffPane(changes, index === 1) : esc(value.body)}</pre></section>`;
  return `<p class="muted">${same ? 'Die Fassungen sind identisch.' : changes ?
    '<del>Entfernt</del> <span aria-hidden="true">·</span> <ins>Hinzugefügt</ins>' :
    'Beide Texte stehen zum direkten Lesen bereit.'}</p>
    <div class="editions">${content(before, 0)}${content(after, 1)}</div>`;
}

export function versionNote(origin?: string, note?: string) {
  const kind = ({ generated: 'Erster Entwurf', 'human-writing': 'Human Writing', restored: 'Wiederhergestellt' } as Record<string, string>)[origin ?? ''] ?? '';
  return kind && note && !note.startsWith(kind) ? [kind, note].join(' · ') : note || kind;
}
