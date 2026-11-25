import type { IconName } from './icons';

export type Tool = 'story' | 'research' | 'image' | 'game' | 'article';
export type Intent = Tool | 'chat' | 'export' | 'decision' | 'clarify';
export type Mode = 'auto' | 'chat' | Tool;

export const suggestions: Array<{ id: Tool; icon: IconName; label: string; prompt: string }> = [
  { id: 'story', icon: 'book', label: 'Geschichte schreiben', prompt: 'Lass uns gemeinsam eine Geschichte schreiben.' },
  { id: 'research', icon: 'research', label: 'Deep Research starten', prompt: 'Recherchiere ausführlich: ' },
  { id: 'image', icon: 'picture', label: 'Bild erstellen', prompt: 'Erstelle ein Bild von ' },
  { id: 'game', icon: 'game', label: 'Spielidee entwickeln', prompt: 'Lass uns eine Spielidee entwickeln: ' },
];
export const tools = [...suggestions, {
  id: 'article' as const, icon: 'text' as const, label: 'Artikel schreiben', prompt: 'Schreibe einen Artikel über ',
}];

function matches(text: string, what: RegExp, action: RegExp) {
  return what.test(text) && action.test(text);
}

const create = /\b(?:erstell\w*|generier\w*|mach\w*|zeichn\w*|mal(?:e|en)|schreib\w*|verfass\w*|draft|write|create|generate|draw|paint|entwick(?:el|l)\w*|plan\w*|starte\w*|beginn\w*|anfang\w*|arbeiten|möchte\w*|will|lass uns|let.s|start|brainstorm\w*|work on|build)\b/iu;
const makeImage = /\b(?:erstell\w*|generier\w*|mach\w*|zeichn\w*|mal(?:e|en)|create|generate|draw|paint|design|render)\b/iu;
const write = /\b(?:schreib\w*|verfass\w*|erzäh\w*|write|draft)\b/iu;
const startWriting = /\b(?:möcht\w*|will|lass uns|starte\w*|beginn\w*|start|let.s)\b/iu;

export function routeIntent(text: string, mode: Mode, context?: Tool): Intent {
  const prompt = text.normalize('NFKC').trim();
  if (matches(prompt, /\b(?:markdown|mdx|astro|artikel|dokument|export|datei|attachment)\b/iu,
    /\b(?:exportier\w*|herunterlad\w*|export|download)\b/iu)) return 'export';
  if (context === 'game' && /^(?:bitte\s+)?(?:merke|notiere|speichere|halte)\b/iu.test(prompt)
    && /entscheidung|beschluss|fest|entscheidungslog/iu.test(prompt)) return 'decision';
  if (mode !== 'auto') return mode;

  const possible: Tool[] = [];
  if (/(?:^|[.!?]\s+)(?:bitte\s+)?(?:recherchier\w*|research\b)|\bdeep research\b|\b(?:gründlich|ausführlich|detailliert|in depth|kannst du|bitte)\b.{0,110}\b(?:recherchier\w*|nachforsch\w*|research)\b/iu.test(prompt)) {
    possible.push('research');
  }
  if (matches(prompt, /\b(?:bild\w*|foto\w*|titelbild\w*|cover\w*|illustration\w*|artwork|image|picture|poster|konzeptbild\w*)\b/iu, makeImage)) {
    possible.push('image');
  }
  const writingRequest = write.test(prompt) || (!possible.includes('image') && startWriting.test(prompt));
  if (writingRequest && /\b(?:geschichte\w*|fantasyroman\w*|roman\w*|kapitel\w*|kurzgeschichte\w*|novelle\w*|story|novel|chapter|fiction)\b/iu.test(prompt)) {
    possible.push('story');
  }
  if (writingRequest && /\b(?:artikel\w*|devlog\w*|blogbeitrag\w*|aufsatz|article|blog post|textentwurf)\b/iu.test(prompt)) {
    possible.push('article');
  }
  if (matches(prompt, /\b(?:spielidee\w*|game idea|game design|videospiel\w*|godot|defold|spielkonzept\w*)\b|\bspiel\w*\b.{0,25}\bentwickeln\b/iu, create)) {
    possible.push('game');
  }
  if (possible.length > 1 || (possible.length && /\b(?:vielleicht|entweder|oder|eventuell|maybe)\b/iu.test(prompt))) return 'clarify';
  if (possible[0] && /(?:\b(?:kein(?:e|en)?|nicht|don't|do not|without)\b.{0,48}\b(?:erstell\w*|generier\w*|recherch\w*|schreib\w*|create|generate|write|research)\b|^wie (?:erstelle|recherchiere|schreibe|entwickle)\b)/iu.test(prompt)) return 'chat';
  if (possible[0]) return possible[0];
  if (context === 'game') return 'game';
  if ((context === 'story' || context === 'article') && /\b(?:weiter\w*|fortsetz\w*|ergänz\w*|überarbeit\w*|kürz\w*|änder\w*|schreib\w*)\b/iu.test(prompt)) return context;
  return 'chat';
}

export function projectTitle(text: string, fallback: string) {
  const quoted = text.match(/[„“"«]([^”“"»\n]{3,100})[”“"»]/u)?.[1];
  const cleaned = text.replace(/^(?:bitte\s+)?(?:lass uns|ich möchte|ich will|erstelle|generiere|schreibe|entwickle|recherchiere|write|create)\s+/iu, '')
    .replace(/^(?:gemeinsam |mir |mit mir |einen? |eine |ein )+/iu, '').replace(/\s+/gu, ' ').trim();
  const title = quoted || cleaned || fallback;
  const short = title.length <= 64 ? title : (title.slice(0, 64).replace(/\s+\S*$/u, '') + '…');
  return short.replace(/^./u, first => first.toLocaleUpperCase('de'));
}
