import { ApiError, api, esc, json, post, type Project, type Session } from './core';
import { icon, type IconName } from './icons';
import { $, announce, button, describe, details, dialogForm, download, formatDate, iconButton, showDialog } from './studio-ui';

export type EntryKind = 'folder' | 'chat' | 'project' | 'document' | 'image' | 'attachment';
export type Entry = {
  kind: EntryKind; id: string; name: string; folder_id?: string | null; project_id?: string | null;
  location?: string; deleted_at?: number; archived_at?: number; updated?: number; inherited?: boolean;
};
export type ManagedView = 'folder' | 'chats' | 'archive' | 'trash';
type DeleteAction = 'trash' | 'purge' | 'empty';
type Preview = { entries: Entry[]; versions: number; notes: number; images: { id: string; name: string }[];
  preserved_documents: string[]; token: string };

const glyphs: Record<EntryKind, IconName> = {
  folder: 'folder', chat: 'chat', project: 'book', document: 'text', image: 'picture', attachment: 'paperclip',
};
const labels: Record<EntryKind, string> = {
  folder: 'Ordner', chat: 'Chat', project: 'Chatinhalte', document: 'Dokument', image: 'Bild', attachment: 'Anhang',
};
const routes = { folder: 'folder', chat: 'chat', project: 'project', document: 'document', attachment: '' };
const collator = new Intl.Collator('de', { numeric: true });
const key = (entry: Entry) => entry.kind + '/' + entry.id;
const entriesRequest = (entries: Entry[]) => entries.map(({ kind, id }) => ({ kind, id }));
const endpoint = (name: string) => '/api/organizer/' + name;
const idPattern = /^[a-f0-9]{32}$/;
const option = (value: string, label: string, selected = false) =>
  `<option value="${esc(value)}"${selected ? ' selected' : ''}>${esc(label)}</option>`;
const nameField = (label: string, name = '') =>
  `<label for="organizer-name">${esc(label)}</label><input class="field" id="organizer-name" name="name" value="${esc(name)}" required maxlength="180" autofocus>`;
const folderData = (id?: string | null) => `data-folder-destination="${esc(id ?? '')}"`;

type KnowledgeEntry = { id: string; category: string; title: string; content: string; source: string;
  status: string; version: number; folder_name?: string };
type KnowledgeView = { folder_id: string; chain: { id: string; name: string }[]; entries: KnowledgeEntry[];
  own: KnowledgeEntry[]; inherited: KnowledgeEntry[]; conflicts: [KnowledgeEntry, KnowledgeEntry][];
  suggestions: Array<{ id: string; category: string; title: string; content: string; origin: string }>;
  profile: Record<string, string> | null; hint: { folder_id: string; name: string; count: number } | null };
const knowledgePath = (id: string) => '/api/folders/' + id + '/knowledge';
const knowledgeStatus = (value: string) =>
  ({ confirmed: 'Bestätigt', reference: 'Referenz', idea: 'Idee', unresolved: 'Ungeklärt' } as Record<string, string>)[value] ?? value;
const knowledgeRow = (item: KnowledgeEntry, actions: string[]) =>
  `<li class="knowledge-row"><div class="knowledge-head"><strong>${esc(item.category)} · ${esc(item.title)}</strong>
  <span class="knowledge-meta">${esc(knowledgeStatus(item.status))} · v${item.version}${item.folder_name ? ' · ' + esc(item.folder_name) : ''}</span></div>
  <p>${esc(item.content)}</p>${item.source ? `<p class="knowledge-source">Quelle: ${esc(item.source)}</p>` : ''}
  <div class="knowledge-actions">${actions.join('')}</div></li>`;

export const chatEntry = (chat: Session): Entry => ({
  ...chat, kind: 'chat', name: chat.title || 'Unterhaltung',
});
export const projectEntry = (project: Project): Entry => ({ ...project, kind: 'project' });

export class Organizer {
  private entries = new Map<string, Entry>();
  private folderEntries: Entry[] = [];
  private sessions: Session[] = [];
  private selected = new Set<string>();
  private openFolders = this.storedFolders();
  private query = '';
  private sort = 'recent';
  private load = 0;
  private viewed: ManagedView | undefined;
  private selectNext?: string;

  constructor(private callbacks: {
    navigate: (hash: string) => void;
    refresh: (action: string, entries: Entry[]) => Promise<void>;
    previewImage: (entry: Entry) => Promise<void>;
    status: (message: string) => void;
  }) {}

  async fetchFolders() {
    return json<Entry[]>(endpoint('folders'));
  }

  hasFolder(id?: string) {
    return this.folderEntries.some(entry => entry.kind === 'folder' && entry.id === id);
  }

  remember(sessions: Session[], folders: Entry[]) {
    this.sessions = sessions;
    this.folderEntries = folders;
  }

  menuButton(entry: Entry) {
    this.entries.set(key(entry), entry);
    return iconButton('organizer-menu', 'Aktionen für ' + entry.name, 'more', key(entry));
  }

  private storedFolders(): Set<string> {
    try {
      const stored: unknown = JSON.parse(localStorage.getItem('studio.open-folders') || '[]');
      return new Set(Array.isArray(stored) ? stored.filter(id => typeof id === 'string' && idPattern.test(id)) : []);
    } catch { return new Set(); }
  }

  private expand(id: string, open: boolean) {
    if (this.openFolders.has(id) === open) return;
    if (open) this.openFolders.add(id);
    else this.openFolders.delete(id);
    localStorage.setItem('studio.open-folders', JSON.stringify([...this.openFolders]));
    for (const node of document.querySelectorAll<HTMLDetailsElement>(`details[data-studio-folder="${id}"]`)) {
      if (node.open !== open) node.open = open;
    }
  }

  reveal(id: string | undefined) {
    let next = this.folderEntries.find(entry => entry.kind === 'folder' && entry.id === id);
    while (next) {
      this.expand(next.id, true);
      next = this.folderEntries.find(entry => entry.kind === 'folder' && entry.id === next!.folder_id);
    }
  }

  toggle(node: HTMLDetailsElement) {
    const id = node.dataset.studioFolder;
    if (id && idPattern.test(id)) this.expand(id, node.open);
  }

  private content() {
    return [...this.folderEntries, ...this.sessions.map(chatEntry)];
  }

  private href(entry: Entry) {
    if (entry.kind === 'attachment') return '/api/attachments/' + entry.id;
    if (entry.kind === 'image') return '';
    return '#' + routes[entry.kind] + '/' + entry.id;
  }

  private link(entry: Entry, active = false) {
    const glyph = icon(glyphs[entry.kind]);
    const content = `${glyph}<span>${esc(entry.name)}</span>`;
    const meta = entry.archived_at || entry.deleted_at ? '' : ` draggable="true" data-organizer-drag="${key(entry)}"`;
    if (entry.deleted_at) return `<span class="organizer-link">${content}</span>`;
    if (entry.kind === 'image') {
      this.entries.set(key(entry), entry);
      return `<button type="button" class="organizer-link" data-action="organizer-open" data-value="${key(entry)}"${meta}>${content}</button>`;
    }
    return `<a class="organizer-link" href="${this.href(entry)}"${active ? ' aria-current="page"' : ''}${meta}>${content}</a>`;
  }

  tree(active?: string) {
    const grouped = new Map<string, Entry[]>();
    for (const entry of this.content()) {
      if (entry.kind !== 'folder' && (entry.kind !== 'chat' || !entry.folder_id)) continue;
      const parent = entry.folder_id ?? '';
      const siblings = grouped.get(parent) ?? [];
      siblings.push(entry);
      grouped.set(parent, siblings);
    }
    const render = (folder = '', depth = 0): string => (grouped.get(folder) ?? []).sort((a, b) =>
      Number(b.kind === 'folder') - Number(a.kind === 'folder') || collator.compare(a.name, b.name)).map(entry => {
      if (entry.kind !== 'folder') return `<li class="organizer-row">${this.link(entry, entry.id === active)}${this.menuButton(entry)}</li>`;
      return `<li class="organizer-folder"><details data-studio-folder="${entry.id}"${this.openFolders.has(entry.id) ? ' open' : ''}>
        <summary ${folderData(entry.id)}${entry.id === active ? ' aria-current="page"' : ''}
          draggable="true" data-organizer-drag="${key(entry)}"><span>${icon('chevron')}${icon('folder')}<span>${esc(entry.name)}</span></span></summary>
        <ul class="organizer-tree${depth >= 6 ? ' organizer-deep' : ''}">${render(entry.id, depth + 1)}</ul>
      </details><div class="organizer-folder-menu">${this.menuButton(entry)}</div></li>`;
    }).join('');
    const recent = this.sessions.filter(chat => !chat.folder_id).slice(0, 8).map(chat => this.row(chatEntry(chat), false, active)).join('');
    return `<section class="side-history"><div class="organizer-heading" ${folderData()}><h2>Ordner</h2>
      ${iconButton('organizer-new-folder', 'Neuer Ordner', 'plus')}</div>
      <ul class="organizer-tree">${render()}</ul></section>
      <section class="side-history"><div class="organizer-heading"><h2>Chats</h2>
      <a href="#chats"${location.hash === '#chats' ? ' aria-current="page"' : ''}>Alle</a></div>
      <ul class="organizer-tree">${recent}</ul></section>`;
  }

  private row(entry: Entry, select = false, active?: string, subtitle = '') {
    const checked = this.selected.has(key(entry));
    return `<li class="organizer-row"${entry.kind === 'folder' && !entry.deleted_at ? ' ' + folderData(entry.id) : ''}>
      ${select ? `<input type="checkbox" data-organizer-select="${key(entry)}" aria-label="${esc(entry.name)} auswählen"${checked ? ' checked' : ''}>` : ''}
      <div class="organizer-row-main">${this.link(entry, entry.id === active)}
      ${subtitle ? `<small>${esc(subtitle)}</small>` : ''}</div>${this.menuButton(entry)}</li>`;
  }

  reset(view?: ManagedView) {
    this.viewed = view;
    this.load++;
    this.selected.clear();
  }

  html(view: ManagedView) {
    const form = view === 'chats' ? `<form data-organizer-search class="organizer-search">
      <label for="chat-query">Chats durchsuchen</label>
      <input type="search" id="chat-query" class="field" name="q" maxlength="500" placeholder="Name oder Nachricht" value="${esc(this.query)}">
      <button class="button" type="submit">Suchen</button>
      <label for="chat-order">Sortieren nach</label><select id="chat-order" class="field" name="sort" data-organizer-sort>
      ${option('recent', 'Zuletzt geändert', this.sort === 'recent')}${option('oldest', 'Älteste Änderung zuerst', this.sort === 'oldest')}</select>
      </form>` : '';
    return form + '<div id="organizer-content" aria-busy="true"><p>Lädt …</p></div>';
  }

  async list(view: ManagedView, id?: string) {
    const region = $('#organizer-content');
    if (!region || this.viewed !== view) return;
    const epoch = ++this.load;
    let entries: Entry[];
    let pendingImages = 0;
    if (view === 'folder') {
      const folder = this.folderEntries.find(entry => entry.kind === 'folder' && entry.id === id);
      if (!folder) {
        region.innerHTML = '<p>Dieser Ordner ist nicht verfügbar.</p>';
        region.setAttribute('aria-busy', 'false');
        return;
      }
      entries = this.content().filter(entry => entry.folder_id === id).sort((a, b) =>
        Number(b.kind === 'folder') - Number(a.kind === 'folder') || collator.compare(a.name, b.name));
      const heading = $('#organizer-title');
      if (heading) heading.textContent = folder.name;
    } else if (view === 'chats') {
      const query = new URLSearchParams({ q: this.query, sort: this.sort });
      entries = (await json<Session[]>('/api/sessions?' + query)).map(chatEntry);
    } else {
      if (view === 'trash') {
        const trash = await json<{ entries: Entry[]; pending_images: number }>(endpoint('trash?summary=1'));
        entries = trash.entries.filter(entry => entry.kind !== 'project' || !entry.inherited);
        pendingImages = trash.pending_images;
      } else entries = await json<Entry[]>(endpoint(view));
      entries.sort((a, b) => (b.deleted_at ?? b.archived_at ?? 0) - (a.deleted_at ?? a.archived_at ?? 0));
    }
    if (epoch !== this.load || !region.isConnected) return;
    const available = new Set(entries.map(key));
    this.selected = new Set([...this.selected].filter(value => available.has(value)));
    if (view === 'chats' && this.selectNext) {
      if (available.has(this.selectNext)) this.selected.add(this.selectNext);
      this.selectNext = undefined;
    }
    const select = view === 'chats' || view === 'trash';
    const actions = view === 'folder' ? [
      button('organizer-new-folder', 'Unterordner', 'plus', 'button', id),
      button('organizer-new-chat', 'Neuer Chat hier', 'chat', 'button', id),
      this.menuButton(this.folderEntries.find(entry => entry.kind === 'folder' && entry.id === id)!),
    ].join('') : view === 'chats' ? button('organizer-new-chat', 'Chat anlegen', 'plus', 'button') :
      view === 'trash' && entries.length ? button('organizer-empty', 'Papierkorb leeren', 'trash', 'button') : '';
    const empty = view === 'chats' ? 'Keine Chats gefunden.' : view === 'archive' ? 'Das Archiv ist leer.' :
      view === 'trash' ? 'Der Papierkorb ist leer.' : 'Dieser Ordner ist leer.';
    const focused = document.activeElement as HTMLElement | null;
    const hadFocus = region.contains(focused);
    region.innerHTML = `<div class="editor-actions"${view === 'folder' ? ' ' + folderData(id) : ''}>${actions}</div>
      ${pendingImages ? `<div class="editor-actions"><p role="status">Bestätigte Bildlöschungen werden noch abgeschlossen.</p>
        ${button('reload-view', 'Aktualisieren', undefined, 'button quiet')}</div>` : ''}
      ${select && entries.length ? '<div class="organizer-selection" role="group" aria-label="Mehrfachauswahl"><label><input type="checkbox" data-organizer-all> Alle auswählen</label><div id="organizer-bulk" class="editor-actions"></div></div>' : ''}
      ${entries.length ? `<ul class="plain-list organizer-list">${entries.map(entry => {
        const date = entry.deleted_at ?? entry.archived_at ?? entry.updated;
        const where = entry.location ? ' · ' + entry.location : '';
        return this.row(entry, select, undefined, labels[entry.kind] + where + (date ? ' · ' + formatDate(date) : ''));
      }).join('')}</ul>` : '<p class="muted">' + empty + '</p>'}`;
    region.setAttribute('aria-busy', 'false');
    this.bulk();
    if (hadFocus && focused) {
      const target = [...region.querySelectorAll<HTMLElement>('button, a, input')].find(node =>
        focused.dataset.action ? node.dataset.action === focused.dataset.action && node.dataset.value === focused.dataset.value :
          focused.dataset.organizerSelect ? node.dataset.organizerSelect === focused.dataset.organizerSelect :
            focused.hasAttribute('data-organizer-all') ? node.hasAttribute('data-organizer-all') :
              node.getAttribute('href') === focused.getAttribute('href') && node instanceof HTMLAnchorElement);
      (target ?? region.closest('main'))?.focus({ preventScroll: true });
    }
  }

  async search(form: HTMLFormElement) {
    const data = new FormData(form);
    this.query = String(data.get('q') ?? '').trim();
    this.sort = String(data.get('sort') ?? 'recent');
    this.selected.clear();
    await this.list('chats');
  }

  select(input: HTMLInputElement) {
    const checkboxes = document.querySelectorAll<HTMLInputElement>('[data-organizer-select]');
    if (input.hasAttribute('data-organizer-all')) {
      for (const box of checkboxes) {
        box.checked = input.checked;
        if (input.checked) this.selected.add(box.dataset.organizerSelect!);
        else this.selected.delete(box.dataset.organizerSelect!);
      }
    } else {
      const id = input.dataset.organizerSelect!;
      if (input.checked) this.selected.add(id);
      else this.selected.delete(id);
    }
    this.bulk();
  }

  private bulk() {
    const toolbar = $('#organizer-bulk');
    if (!toolbar) return;
    const count = this.selected.size;
    const all = $<HTMLInputElement>('[data-organizer-all]')!;
    const total = document.querySelectorAll('[data-organizer-select]').length;
    all.checked = count === total && count > 0;
    all.indeterminate = count > 0 && count < total;
    toolbar.innerHTML = !count ? '' : `<span role="status">${count} ausgewählt</span>` +
      (this.viewed === 'trash' ?
        button('organizer-bulk-restore', 'Wiederherstellen', undefined, 'button') +
        button('organizer-bulk-purge', 'Endgültig löschen', undefined, 'button') :
        button('organizer-bulk-move', 'Verschieben', 'folder', 'button') +
        button('organizer-bulk-archive', 'Archivieren', 'archive', 'button') +
        button('organizer-bulk-trash', 'In den Papierkorb', 'trash', 'button'));
  }

  private open(entry: Entry) {
    if (entry.kind === 'image') return this.callbacks.previewImage(entry);
    if (details.open) details.close();
    if (entry.kind === 'attachment') {
      const link = document.createElement('a');
      link.href = this.href(entry);
      link.download = '';
      link.click();
    } else this.callbacks.navigate(this.href(entry));
  }

  private menu(entry: Entry) {
    const action = (name: string, label: string, glyph?: IconName) =>
      button('organizer-' + name, label, glyph, 'button quiet', key(entry));
    const items = entry.deleted_at
      ? [action('restore', 'Wiederherstellen'), action('purge', 'Endgültig löschen', 'trash')]
      : [action('open', 'Öffnen', glyphs[entry.kind]), action('rename', 'Umbenennen'),
        action('move', 'Verschieben', 'folder'),
        ...(entry.kind === 'folder' ? [button('organizer-knowledge', 'Ordnerwissen verwalten', 'book', 'button quiet', key(entry)),
          button('organizer-new-chat', 'Chat hier erstellen', 'chat', 'button quiet', entry.id),
          button('organizer-new-folder', 'Unterordner anlegen', 'plus', 'button quiet', entry.id)] : []),
        ...(entry.kind === 'chat' && !entry.archived_at ? [action('select', 'Für Mehrfachauswahl markieren')] : []),
        ...(entry.kind === 'chat' || entry.kind === 'project' ?
          [entry.archived_at ? action('unarchive', 'Aus Archiv holen', 'archive') : action('archive', 'Archivieren', 'archive')] : []),
        action('trash', 'In den Papierkorb', 'trash')];
    showDialog(entry.name, '<div class="organizer-menu" role="group" aria-label="Aktionen">' + items.join('') + '</div>');
    $('.organizer-menu button', details)?.focus();
  }

  private async mutate(action: string, entries: Entry[], values: object = {}) {
    const data = await post<{ id?: string }>(endpoint(action), { entries: entriesRequest(entries), ...values });
    if (details.open) details.close();
    await this.callbacks.refresh(action, entries);
    const feedback: Record<string, string> = {
      folder: 'Ordner erstellt.', rename: 'Name gespeichert.',
      move: 'Verschoben.', archive: 'Archiviert.', unarchive: 'Aus dem Archiv geholt.',
      trash: 'In den Papierkorb verschoben.', restore: 'Wiederhergestellt.', purge: 'Endgültig gelöscht.', empty: 'Papierkorb geleert.',
    };
    announce(feedback[action] ?? 'Gespeichert.');
    this.callbacks.status(feedback[action] ?? 'Gespeichert.');
    return data;
  }

  private async confirm(operation: DeleteAction, entries: Entry[]) {
    const preview = await post<Preview>(endpoint('preview'), { operation, entries: entriesRequest(entries) });
    if (!preview.entries.length) return;
    const summaries = preview.entries.map(entry =>
      `<li>${esc(labels[entry.kind] + ' · ' + entry.name + ' · ' + (entry.location ?? 'Studio') +
        (preview.preserved_documents.includes(entry.id) ? ' · bleibt verknüpft' : ''))}</li>`).join('');
    const images = preview.images.length ? `<p>Mit der Bibliothek verknüpfte Bilder aus dem Chat</p><ul>
      ${preview.images.map(image => '<li>' + esc(image.name) + '</li>').join('')}</ul>` : '';
    const title = operation === 'empty' ? 'Papierkorb leeren?' : operation === 'trash' ? 'In den Papierkorb verschieben?' : 'Endgültig löschen?';
    const note = operation === 'trash' ? 'Diese Einträge kannst du im Papierkorb wiederherstellen.' :
      'Diese Aktion ist dauerhaft. Die Einträge können anschließend nicht wiederhergestellt werden.';
    dialogForm(title, `<p>${note}</p><details class="deletion-impact" open><summary>${preview.entries.length} betroffene Einträge</summary>
      <ul>${summaries}</ul>${preview.versions ? `<p>Dokumentversionen · ${preview.versions}</p>` : ''}
      ${preview.notes ? `<p>Notizen · ${preview.notes}</p>` : ''}${images}</details>`,
    operation === 'trash' ? 'In den Papierkorb' : 'Endgültig löschen',
    async () => { await this.mutate(operation, entries, { token: preview.token }); });
  }

  async knowledgeDialog(entry: Entry) {
    const view = await json<KnowledgeView>(knowledgePath(entry.id));
    const statusButton = (item: KnowledgeEntry) =>
      `<button class="button quiet" type="button" data-knowledge="confirm" data-id="${esc(item.id)}">Bestätigen</button>
       <button class="button quiet" type="button" data-knowledge="versions" data-id="${esc(item.id)}">Versionen</button>
       <button class="button quiet" type="button" data-knowledge="delete" data-id="${esc(item.id)}">Löschen</button>`;
    const categories = ['general', 'fact', 'character', 'place', 'organization', 'rule', 'event', 'term',
      'reference-document', 'image-reference', 'visual-style', 'idea'];
    showDialog('Ordnerwissen · ' + entry.name, `<div class="knowledge-panel" data-folder="${esc(entry.id)}">
      <p>${view.hint ? `Weltwissen aktiv: ${esc(view.hint.name)} (${view.entries.length} Einträge inklusive Vererbung) – Chats in diesem Ordner nutzen es automatisch.`
        : 'Noch kein Wissen hinterlegt. Leere Ordner funktionieren wie bisher.'}</p>
      ${view.conflicts.length ? `<p class="knowledge-conflict">${view.conflicts.length} ungeklärte Konflikte zwischen Ordner und Unterordner – beide Fassungen bleiben erhalten und werden als ungeklärt gemeldet.</p>` : ''}
      <form data-knowledge-form="add"><h3>Eintrag hinzufügen</h3>
        <div class="knowledge-grid">
          <label>Kategorie<select class="field" name="category">${categories.map(name => option(name, name)).join('')}</select></label>
          <label>Titel<input class="field" name="title" maxlength="200" required></label>
          <label>Status<select class="field" name="status">${option('reference', 'Referenz (unbestätigt)')}${option('confirmed', 'Bestätigter Kanon')}${option('idea', 'Kreative Idee')}${option('unresolved', 'Ungeklärt')}</select></label>
          <label>Quelle<input class="field" name="source" maxlength="300" placeholder="z. B. Referenzdokument"></label>
        </div>
        <label>Inhalt<textarea class="field" name="content" rows="3" maxlength="20000" required></textarea></label>
        <button class="button primary" type="submit">Hinzufügen</button></form>
      <details class="knowledge-section" open><summary>Eigene Einträge (${view.own.length})</summary>
        <ul class="knowledge-list">${view.own.map(item => knowledgeRow(item, [statusButton(item)])).join('') || '<li class="knowledge-empty">Keine eigenen Einträge.</li>'}</ul></details>
      <details class="knowledge-section"><summary>Geerbt (${view.inherited.length})</summary>
        <ul class="knowledge-list">${view.inherited.map(item => knowledgeRow(item, [])).join('') || '<li class="knowledge-empty">Keine geerbten Einträge.</li>'}</ul></details>
      <details class="knowledge-section"${view.suggestions.length ? ' open' : ''}><summary>Vorschläge prüfen (${view.suggestions.length})</summary>
        <ul class="knowledge-list">${view.suggestions.map(item => `<li class="knowledge-row"><div class="knowledge-head">
          <strong>${esc(item.category)} · ${esc(item.title)}</strong><span class="knowledge-meta">${esc(item.origin)}</span></div>
          <p>${esc(item.content)}</p><div class="knowledge-actions">
          <button class="button quiet" type="button" data-knowledge="accept" data-id="${esc(item.id)}">Bestätigen</button>
          <button class="button quiet" type="button" data-knowledge="keep" data-id="${esc(item.id)}">Als Referenz</button>
          <button class="button quiet" type="button" data-knowledge="reject" data-id="${esc(item.id)}">Verwerfen</button></div></li>`).join('')
          || '<li class="knowledge-empty">Keine offenen Vorschläge. Generierte Fakten landen hier erst nach deiner Bestätigung im Kanon.</li>'}</ul></details>
      <form data-knowledge-form="profile"><h3>Visuelles Standardprofil (optional)</h3>
        <div class="knowledge-grid">
          <label>Vorlage<input class="field" name="template" maxlength="100" value="${esc(view.profile?.template ?? '')}"></label>
          <label>Format<input class="field" name="ratio" maxlength="20" value="${esc(view.profile?.ratio ?? '')}" placeholder="16:9"></label>
          <label>Stil<input class="field" name="style" maxlength="400" value="${esc(view.profile?.style ?? '')}"></label>
          <label>Palette<input class="field" name="palette" maxlength="400" value="${esc(view.profile?.palette ?? '')}"></label>
        </div><p class="knowledge-source">Chats und Geschichten können das Profil ausdrücklich überschreiben; Profile anderer Geschichten bleiben unverändert.</p>
        <button class="button" type="submit">Profil speichern</button></form>
      <p class="knowledge-actions"><button class="button" type="button" data-knowledge="export-markdown">Markdown exportieren</button>
      <button class="button" type="button" data-knowledge="export-json">JSON exportieren</button></p></div>`, true);
    const panel = $('[data-folder]', details);
    if (!panel) return;
    const rerender = () => void this.knowledgeDialog(entry);
    panel.querySelectorAll<HTMLFormElement>('form[data-knowledge-form]').forEach(form => {
      form.addEventListener('submit', async event => {
        event.preventDefault();
        const values = Object.fromEntries(new FormData(form));
        const body = form.dataset.knowledgeForm === 'profile' ? { action: 'profile', profile: values }
          : { action: 'add', ...values };
        try {
          await post(knowledgePath(entry.id), body);
          announce('Ordnerwissen gespeichert.');
          rerender();
        } catch (error) {
          announce(describe(error));
        }
      });
    });
    panel.addEventListener('click', async event => {
      const target = (event.target as HTMLElement).closest<HTMLElement>('[data-knowledge]');
      if (!target) return;
      const kind = target.dataset.knowledge!;
      const id = target.dataset.id ?? '';
      try {
        if (kind === 'export-markdown' || kind === 'export-json') {
          const format = kind === 'export-json' ? 'json' : 'markdown';
          const result = await json<{ content: unknown }>(knowledgePath(entry.id) + '?format=' + format);
          download('ordnerwissen-' + entry.name + '.' + (format === 'json' ? 'json' : 'md'),
            format === 'json' ? JSON.stringify(result.content, null, 2) : String(result.content),
            format === 'json' ? 'application/json' : 'text/markdown');
          return;
        }
        if (kind === 'versions') {
          const history = await post<{ versions: Array<{ version: number; title: string; content: string; status: string; created: number }> }>(
            knowledgePath(entry.id), { action: 'versions', entry_id: id });
          details.insertAdjacentHTML('beforeend', `<div class="knowledge-versions"><h3>Frühere Versionen</h3>
            <ul>${history.versions.map(item => `<li>v${item.version} · ${formatDate(item.created)} · ${esc(item.content.slice(0, 80))}
            <button class="button quiet" type="button" data-knowledge="restore" data-id="${esc(id)}" data-version="${item.version}">Wiederherstellen</button></li>`).join('')}</ul></div>`);
          return;
        }
        if (kind === 'restore') {
          await post(knowledgePath(entry.id), { action: 'restore', entry_id: id, version: Number(target.dataset.version) });
          announce('Version wiederhergestellt.');
        } else {
          await post(knowledgePath(entry.id), (kind === 'accept' || kind === 'keep' || kind === 'reject')
            ? { action: kind, suggestion_id: id } : { action: kind, entry_id: id, status: 'confirmed' });
          announce(kind === 'delete' ? 'Eintrag gelöscht.' : kind === 'reject' ? 'Vorschlag verworfen.' : 'Gespeichert.');
        }
        rerender();
      } catch (error) { announce(describe(error)); }
    });
  }

  private moveDialog(entries: Entry[]) {
    const selectedFolders = new Set(entries.filter(entry => entry.kind === 'folder').map(entry => entry.id));
    const folders = this.folderEntries.filter(entry => entry.kind === 'folder')
      .filter(entry => {
        let cursor: Entry | undefined = entry;
        while (cursor) {
          if (selectedFolders.has(cursor.id)) return false;
          cursor = this.folderEntries.find(folder => folder.kind === 'folder' && folder.id === cursor?.folder_id);
        }
        return true;
      }).map(entry => ({ id: entry.id, label: [entry.folder_id ? entry.location : '', entry.name].filter(Boolean).join(' / ') }))
      .sort((a, b) => collator.compare(a.label, b.label));
    dialogForm('Verschieben', `<label for="organizer-destination">Zielordner</label><select class="field" id="organizer-destination" name="destination">
      ${option('', 'Oberste Ebene', entries[0]?.folder_id == null)}
      ${folders.map(folder => option(folder.id, folder.label, entries.length === 1 && entries[0].folder_id === folder.id)).join('')}
    </select>`, 'Verschieben', async data => {
      const folder = String(data.get('destination')) || null;
      if (folder) this.reveal(folder);
      await this.mutate('move', entries, { folder_id: folder });
    });
  }

  async upload(project: Project, folder?: string) {
    dialogForm('Anhang hinzufügen', '<label for="organizer-file">Datei (bis 10 MB)</label><input class="field" type="file" name="file" id="organizer-file" required>',
      'Hinzufügen', async form => {
        const file = form.get('file');
        if (!(file instanceof File)) return;
        if (file.size > 10 * 1024 * 1024) throw new ApiError(413, 'attachment_too_large');
        const data = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.addEventListener('load', () => resolve(String(reader.result).split(',')[1]));
          reader.addEventListener('error', () => reject(reader.error));
          reader.readAsDataURL(file);
        });
        await post('/api/attachments', { project_id: project.id, folder_id: folder, name: file.name, data });
        if (details.open) details.close();
        await this.callbacks.refresh('upload', [projectEntry(project)]);
        announce('Anhang hinzugefügt.');
      });
  }

  async handle(raw: string, value: string) {
    const mode = raw.replace(/^organizer-/, '');
    if (mode === 'new-folder') {
      dialogForm(value ? 'Neuer Unterordner' : 'Neuer Ordner', nameField('Ordnername'), 'Erstellen', async data => {
        if (value) this.reveal(value);
        const { id } = await this.mutate('folder', [], { name: data.get('name'), folder_id: value || null });
        if (id) this.callbacks.navigate('#folder/' + id);
      });
      return;
    }
    if (mode === 'new-chat') {
      dialogForm('Neuer Chat', nameField('Chatname'), 'Erstellen', async data => {
        const folder = value || undefined;
        const { id } = await api.createSession({ title: data.get('name'), folder_id: folder });
        if (folder) this.reveal(folder);
        if (details.open) details.close();
        this.callbacks.navigate('#chat/' + id);
        await this.callbacks.refresh('create-chat', []);
      });
      return;
    }
    if (mode === 'empty') return this.confirm('empty', []);
    const single = this.entries.get(value);
    const entries = mode.startsWith('bulk-') ? [...this.selected].map(k => this.entries.get(k)).filter((e): e is Entry => !!e)
      : single ? [single] : [];
    const first = entries[0];
    if (!first) return;
    const action = mode.replace(/^bulk-/, '');
    if (action === 'menu') return this.menu(first);
    if (action === 'open') return this.open(first);
    if (action === 'select') {
      if (details.open) details.close();
      const box = $<HTMLInputElement>(`[data-organizer-select="${key(first)}"]`);
      if (box) { box.checked = true; this.select(box); box.focus(); }
      else {
        this.query = '';
        this.selectNext = key(first);
        this.callbacks.navigate('#chats');
      }
      return;
    }
    if (action === 'trash' || action === 'purge') return this.confirm(action, entries);
    if (action === 'move') return this.moveDialog(entries);
    if (action === 'knowledge' && first.kind === 'folder') return this.knowledgeDialog(first);
    if (action === 'rename') {
      dialogForm('Umbenennen', nameField('Name', first.name), 'Speichern', async data => {
        await this.mutate(action, entries, { name: data.get('name') });
      });
      return;
    }
    await this.mutate(action, entries);
  }

  async drop(source: string, folder: string) {
    const entry = this.entries.get(source);
    if (!entry || (entry.kind === 'folder' && entry.id === folder) || entry.folder_id === (folder || null)) return;
    try {
      if (folder) this.reveal(folder);
      await this.mutate('move', [entry], { folder_id: folder || null });
    } catch (error) {
      const message = describe(error);
      announce(message);
      this.callbacks.status(message);
    }
  }
}
