import { api, esc, json, post, type Document, type DocVersion } from './core';
import { $, announce, button, describe, details, dialogForm, download, formatDate, iconButton, imageUrl, markdown, showDialog } from './studio-ui';
import { auditMarkup, compareMarkup, findingHint, goals, modeLabel, proofMarkup, versionNote,
  type Edition, type EditorialHistory, type EditorialRun } from './editorial-ui';
import { chapterLabel } from './story';

type Export = { files: Array<{ path: string; content?: string; base64?: string; content_type?: string }>; archive?: string; slug: string };
type Draft = { body: string; title: string; base: Document; undo: Array<{ body: string; title: string }> };
type RewriteOptions = { range?: [number, number]; goal?: keyof typeof goals; instruction?: string };

export class Editor {
  doc?: Document;
  preview = false;
  private drafts = new Map<string, Draft>();
  private history?: EditorialHistory;
  private shownRun?: EditorialRun;
  private runOptions = new Map<string, RewriteOptions>();
  private runSource = new Map<string, { body: string; title: string }>();
  private saving?: Promise<void>;
  private textStatus = '';
  private selection = { start: 0, end: 0 };

  constructor(private changed: () => void, private links: () => string,
    private saved: (doc: Document) => void = () => {}) {}

  open(doc: Document) {
    this.doc = doc;
    this.preview = false;
    this.textStatus = '';
    this.selection = { start: 0, end: 0 };
    const prior = this.drafts.get(doc.id);
    const base = { ...doc };
    if (!prior || (prior.body === prior.base.body && prior.title === prior.base.title)) {
      this.drafts.set(doc.id, { body: doc.body, title: doc.title, base, undo: prior?.undo ?? [] });
    }
    this.history = undefined;
    this.shownRun = undefined;
    void this.refreshEditorial().catch(() => {});
  }

  close() { this.doc = undefined; }
  private get draft() { return this.drafts.get(this.doc!.id)!; }
  get dirty() { return this.doc && (this.draft.body !== this.draft.base.body || this.draft.title !== this.draft.base.title); }
  get body() { return this.doc ? this.draft.body : ''; }

  html() {
    if (!this.doc) return '';
    const approved = this.doc.story_number != null && this.doc.status === 'approved';
    return `<section class="editor" aria-labelledby="editor-title"><div class="editor-inner">
      <div class="editor-top"><h2 class="serif" id="editor-title">Dokument</h2>${iconButton('close-editor', 'Editor schließen', 'x')}</div>
      ${this.links()}
      <label class="sr-only" for="doc-title">Dokumenttitel</label>
      <input class="title-field" id="doc-title" value="${esc(this.draft.title)}" maxlength="180" placeholder="Dokumenttitel"${approved ? ' readonly' : ''}>
      <p class="editor-meta" id="doc-version">${this.versionLabel()}</p>
      <section class="writing-tools" aria-label="Human Writing">
        <div class="editor-actions">
          ${button('editor-lint', 'Text prüfen', 'search', 'button')}
          ${button('editor-rewrite', 'Text verbessern', 'mark', 'button')}
          ${button('editor-history', 'Prüfverlauf')}
        </div><div id="writing-status">${proofMarkup(this.history)}</div>
      </section>
      <div class="editor-actions">
        ${button('editor-preview', this.preview ? 'Markdown bearbeiten' : 'Vorschau', 'text')}
        ${button('editor-undo', 'Rückgängig')}
        ${button('editor-versions', 'Versionen')}
      </div>
      ${this.preview ? `<div class="draft-preview prose">${markdown(this.draft.body) || '<p>Das Dokument ist leer.</p>'}</div>`
        : `<label for="draft" class="sr-only">Dokumenttext in Markdown</label><textarea id="draft" rows="15"${approved ? ' readonly' : ''}>\n${esc(this.draft.body)}</textarea>`}
      <div class="editor-actions">
        ${approved ? '' : button('editor-save', 'Speichern', undefined, 'button primary') + button('editor-images', 'Bild einfügen')}
        ${button('editor-export', 'Exportieren')}
      </div>
      <p class="editor-meta" id="editor-status" role="status">${esc(this.textStatus)}</p>
    </div></section>`;
  }

  input(field: HTMLInputElement | HTMLTextAreaElement) {
    if (!this.doc) return;
    if (field.id === 'draft') {
      this.draft.body = field.value;
      this.remember(field as HTMLTextAreaElement);
    }
    if (field.id === 'doc-title') this.draft.title = field.value;
    this.version();
  }

  remember(field: HTMLTextAreaElement) {
    this.selection = { start: field.selectionStart, end: field.selectionEnd };
  }

  private version() {
    const version = $('#doc-version');
    if (version && this.doc) version.textContent = this.versionLabel();
  }

  private versionLabel() {
    const version = this.draft.base.version;
    const count = this.draft.body.replace(/^\s*#{1,6}\s+[^\n]*$/gm, '').replace(/!\[[^\]]*\]\([^)]*\)/g, '')
      .replace(/\x60{3}[\s\S]*?\x60{3}/g, '').match(/[\p{L}\p{N}]+(?:[’'-][\p{L}\p{N}]+)*/gu)?.length ?? 0;
    const chapter = this.doc?.story_number == null ? '' : ` · ${chapterLabel(this.doc.status)} · ${count.toLocaleString('de')} Wörter`;
    return `Version ${version}${chapter}${this.dirty ? ' · Änderungen offen' : ''}${version !== this.doc?.version ? ' · Neuere Fassung vorhanden' : ''}`;
  }

  private status(text: string) {
    this.textStatus = text;
    const target = $('#editor-status');
    if (target) target.textContent = text;
  }

  private replace(body: string, title = this.draft.title) {
    const draft = this.draft;
    draft.undo.push({ body: draft.body, title: draft.title });
    Object.assign(draft, { body, title });
    this.changed();
  }

  applySuggestion(body: string) {
    this.replace(body);
    this.status('Vorschlag übernommen. Speichere, um diese Fassung zu behalten.');
  }

  insertImage(id: string, alt: string) {
    if (!this.doc) return;
    if (this.doc.story_number != null && this.doc.status === 'approved') {
      this.status('Hebe die Freigabe vor dem Bearbeiten auf.');
      return;
    }
    const short = alt.replace(/[\r\n\[\]\\]/gu, ' ').trim().slice(0, 140) || 'Bild';
    const snippet = `\n\n![${short}](${imageUrl(id)})\n`;
    const at = this.selection.end || this.draft.body.length;
    this.replace(this.draft.body.slice(0, at) + snippet + this.draft.body.slice(at));
    this.status('Bild eingefügt. Speichere, um diese Fassung zu behalten.');
  }

  async save(note = 'Editor') {
    if (this.saving) return this.saving;
    const doc = this.doc;
    if (!doc || !this.dirty) return;
    const draft = this.draft;
    const title = draft.title.trim() || 'Ohne Titel';
    const body = draft.body;
    this.saving = (async () => {
      this.status('Wird gespeichert …');
      try {
        const { version, status } = await api.editDocument(doc.id, { title, body, version: draft.base.version, note });
        draft.undo.push({ body: draft.base.body, title: draft.base.title });
        Object.assign(doc, { title, body, version, status: status ?? doc.status, version_note: note, version_origin: 'user', updated: Date.now() / 1000 });
        draft.base = { ...doc };
        this.saved(doc);
        if (this.doc === doc) {
          this.version();
          this.status('Dokument gespeichert.');
        }
      } finally { this.saving = undefined; }
    })();
    return this.saving;
  }

  async export(format: 'md' | 'mdx') {
    const doc = this.doc;
    if (!doc) return;
    if (this.dirty) await this.save('Export');
    const payload = await post<Export>('/api/export', { doc_id: doc.id, format, bundle: true });
    if (payload.archive) download(payload.slug + '.zip', Uint8Array.from(atob(payload.archive), c => c.charCodeAt(0)), 'application/zip');
    else {
      for (const file of payload.files) {
        const name = file.path.split('/').at(-1) ?? 'dokument.' + format;
        download(name, file.base64 ? Uint8Array.from(atob(file.base64), c => c.charCodeAt(0)) : file.content ?? '', file.content_type);
      }
    }
    announce(format === 'mdx' ? 'Astro-MDX-Export bereit.' : 'Markdown-Export bereit.');
  }

  private path(runId?: string) {
    return '/api/documents/' + this.doc!.id + '/editorial' + (runId ? '/' + encodeURIComponent(runId) : '');
  }

  private async refreshEditorial() {
    const doc = this.doc!;
    const result = await json<EditorialHistory>(this.path());
    if (this.doc !== doc) return;
    this.history = result;
    const host = $('#writing-status');
    if (host) {
      const expanded = host.querySelector('details')?.open;
      host.innerHTML = proofMarkup(result);
      if (expanded) host.querySelector('details')?.setAttribute('open', '');
    }
  }

  private showRun(run: EditorialRun) {
    if (this.doc?.id !== run.document_id) return;
    this.shownRun = run;
    if (run.mode !== 'rewrite') {
      showDialog(run.mode === 'review' ? 'Story Quality Review' : 'Human Writing Audit',
        auditMarkup(run) + `<div class="dialog-actions">
          ${button('editor-rewrite', 'Text verbessern', 'mark', 'button')}
          ${run.mode === 'audit' ? button('editor-review', 'Story Quality Review', 'book', 'button quiet') : ''}
        </div>`, true);
      return;
    }
    const original = run.original ?? '';
    const proposal = run.text ?? '';
    const editable = run.state === 'ready';
    showDialog('Vorher und nachher', `<p class="muted">${run.accepted_version
      ? 'Gespeichert als Version ' + run.accepted_version
      : run.state === 'discarded' ? 'Vorschlag verworfen' : 'Übernehmen speichert eine neue Version.'}</p>
      ${compareMarkup({ label: 'Originalfassung', body: original, lang: run.evidence?.language },
        { label: 'Vorgeschlagene Überarbeitung', body: proposal, lang: run.evidence?.language })}
      ${run.reasons?.length ? `<section class="editorial-section"><h3>Warum diese Änderungen vorgeschlagen werden</h3>
        <ul class="plain-list editorial-findings">${run.reasons.map(reason =>
          `<li><span class="muted">Zeile ${reason.line}${reason.anchor === 'paragraph' ? ' · Absatzbezug' : ''}</span><blockquote>${esc(reason.quote)}</blockquote><p>${esc(reason.reason)}</p></li>`).join('')}</ul></section>` : ''}
      <p class="muted">${typeof run.words === 'number' ? run.words + ' Wörter im Vorschlag · ' : ''}
        Linter-Funde in der Passage ${run.before_findings ?? 0} → ${run.after_findings ?? 0}</p>
      ${proofMarkup(run)}
      ${editable && run.choices?.length ? `<details class="writing-proof">
        <summary>Einzelne Absätze übernehmen</summary>
        <fieldset class="editorial-choices"><legend>Überarbeitete Absätze auswählen</legend>
        ${run.choices.map(choice => `<label class="editorial-choice">
          <input type="checkbox" name="editorial-paragraph" value="${choice.paragraph}" checked>
          <span><strong>Absatz ${choice.paragraph}</strong><br>${esc(choice.after.trim().slice(0, 135))}${choice.after.trim().length > 135 ? ' …' : ''}</span>
        </label>`).join('')}</fieldset></details>` : ''}
      ${editable ? `<div class="dialog-actions">
        ${original !== proposal ? button('editor-accept', 'Überarbeitung übernehmen', undefined, 'button primary', run.id) : ''}
        ${button('editor-discard', 'Vorschlag verwerfen', undefined, 'button', run.id)}
        ${button('editor-retry', 'Erneut überarbeiten', undefined, 'button quiet', run.id)}</div>` : ''}
      <p id="editorial-dialog-status" role="status"></p>`, true);
  }

  private async execute(mode: 'audit' | 'review' | 'rewrite', options: RewriteOptions = {}) {
    const doc = this.doc!;
    const source = { body: this.draft.body, title: this.draft.title };
    const path = this.path();
    showDialog(mode === 'rewrite' ? 'Text verbessern' : mode === 'review' ? 'Story Quality Review' : 'Text prüfen',
      `<p id="editorial-progress" role="status">${mode === 'rewrite'
        ? 'Das Modell erstellt einen Vergleichsvorschlag …' : 'Der Skill prüft den Text. Das Modell liest die Passage für die redaktionelle Einschätzung …'}</p>`);
    const progress = $('#editorial-progress', details);
    try {
      const run = await post<EditorialRun>(path, { mode, version: this.draft.base.version, text: source.body,
        title: source.title, ...options });
      if (this.doc === doc) {
        this.runOptions.set(run.id, options);
        this.runSource.set(run.id, source);
        this.status(mode === 'rewrite' ? 'Überarbeitungsvorschlag bereit.' : 'Prüfung gespeichert.');
        if (progress?.isConnected && details.open) this.showRun(run);
        void this.refreshEditorial().catch(() => {});
      }
      return run;
    } catch (error) {
      if (this.doc === doc && progress?.isConnected) progress.textContent = describe(error, 'Der Schreibauftrag konnte nicht abgeschlossen werden.');
      throw error;
    }
  }

  private selectedRange(): [number, number] | undefined {
    const field = $<HTMLTextAreaElement>('#draft');
    if (field && field.selectionStart !== field.selectionEnd) this.remember(field);
    const { start, end } = this.selection;
    return !this.preview && start < end && this.body.slice(start, end).trim() ? [start, end] : undefined;
  }

  private rewriteForm(options: RewriteOptions = {}, useSelection = true) {
    if (!this.body.trim()) { this.status('Schreibe zuerst einen Text.'); return; }
    const range = options.range ?? (useSelection ? this.selectedRange() : undefined);
    const instruction = options.instruction ?? '';
    const goal = options.goal ?? (instruction ? 'custom' : 'clarity');
    dialogForm('Text verbessern', `<label for="rewrite-scope">Umfang</label>
      <select class="field" id="rewrite-scope" name="scope">${range ? '<option value="selection">Gewählte Textstelle</option>' : ''}
      <option value="all">Ganzes Dokument</option></select>
      <label for="rewrite-goal">Was soll besser werden?</label><select class="field" id="rewrite-goal" name="goal">
        ${Object.entries(goals).filter(([key]) => key !== 'finding' || goal === 'finding')
          .map(([key, label]) => `<option value="${key}"${key === goal ? ' selected' : ''}>${label}</option>`).join('')}</select>
      <label for="rewrite-prompt">Eigene Anweisung (optional)</label>
      <textarea class="field" id="rewrite-prompt" name="instruction" rows="3" maxlength="1200"
        placeholder="Beispiel: ungefähr 350 englische Wörter.">${esc(instruction)}</textarea>`, 'Vorschlag erstellen', async values => {
      const selected = String(values.get('goal')) as keyof typeof goals;
      const text = String(values.get('instruction')).trim();
      if ((selected === 'custom' || selected === 'finding') && !text) {
        const input = $<HTMLTextAreaElement>('#rewrite-prompt', details)!;
        input.setCustomValidity('Gib eine Anweisung ein.');
        input.reportValidity();
        input.addEventListener('input', () => input.setCustomValidity(''), { once: true });
        throw new Error('instruction_required');
      }
      await this.execute('rewrite', { goal: selected, instruction: text, range: values.get('scope') === 'selection' ? range : undefined });
    });
  }

  private useFinding(model: boolean, index: number) {
    const report = this.shownRun;
    const item = model ? report?.observations?.[index] : report?.lint?.findings[index];
    if (!item || !report) return;
    const exact = 'quote' in item ? item.quote : item.excerpt;
    let start = exact ? this.body.indexOf(exact) : -1;
    if (start >= 0 && this.body.lastIndexOf(exact) !== start) {
      const lines = this.body.split('\n');
      const offset = lines.slice(0, item.line - 1).reduce((size, line) => size + line.length + 1, 0);
      const onLine = lines[item.line - 1]?.indexOf(exact) ?? -1;
      start = onLine >= 0 ? offset + onLine : -1;
    }
    if (start < 0) {
      const status = $('#finding-status', details) ?? document.createElement('p');
      status.id = 'finding-status';
      status.setAttribute('role', 'status');
      status.textContent = 'Die Stelle ließ sich im aktuellen Text nicht eindeutig finden. Prüfe die aktuelle Fassung erneut.';
      if (!status.isConnected) $('.dialog-content', details)?.append(status);
      return;
    }
    const from = this.body.lastIndexOf('\n\n', start - 1);
    const to = this.body.indexOf('\n\n', start + exact.length);
    const hint = 'quote' in item ? item.suggestion ?? item.note : findingHint(item)[1];
    this.rewriteForm({ range: [from < 0 ? 0 : from + 2, to < 0 ? this.body.length : to],
      goal: 'finding', instruction: hint + '\nFundstelle: ' + exact }, false);
  }

  private async editorialHistory() {
    const history = await json<EditorialHistory>(this.path());
    showDialog('Prüfverlauf', history.runs.length ? `<ul class="plain-list editorial-findings">${history.runs.map(run =>
      `<li><strong>${modeLabel(run.mode)}</strong><p class="muted">Version ${run.base_version} · ${formatDate(run.created)}${run.accepted_version
        ? ' · Übernommen als Version ' + run.accepted_version : run.state === 'discarded' ? ' · Verworfen' : ''}</p>
        ${button('editor-open-report', 'Öffnen', undefined, 'button quiet', run.id)}</li>`).join('')}</ul>`
      : '<p>Hier erscheinen deine Textprüfungen und Überarbeitungsvorschläge.</p>');
  }

  async showEditorial(runId: string) {
    const doc = this.doc;
    if (!doc) return;
    const run = await json<EditorialRun>(this.path(runId));
    if (this.doc === doc) this.showRun(run);
  }

  private async accept() {
    const run = this.shownRun;
    const doc = this.doc;
    if (!run || !doc) return;
    const source = this.runSource.get(run.id);
    if ((source && (source.body !== this.body || source.title !== this.draft.title)) || (!source && this.dirty)) {
      $('#editorial-dialog-status', details)!.textContent = 'Der Entwurf wurde geändert. Erstelle einen Vorschlag für den aktuellen Text.';
      return;
    }
    const snapshot = { body: this.body, title: this.draft.title };
    const choices = [...details.querySelectorAll<HTMLInputElement>('input[name="editorial-paragraph"]')];
    const selected = choices.filter(input => input.checked).map(input => Number(input.value));
    if (choices.length && !selected.length) {
      $('#editorial-dialog-status', details)!.textContent = 'Wähle mindestens einen Absatz aus.';
      return;
    }
    const saved = await post<{ version: number }>(this.path(run.id) + '/accept',
      selected.length < choices.length ? { paragraphs: selected } : {});
    const next = await api.document(doc.id);
    if (this.doc !== doc) return;
    this.drafts.delete(doc.id);
    this.open(next);
    this.saved(next);
    this.draft.undo.push(snapshot);
    this.changed();
    details.close();
    this.status('Überarbeitung als Version ' + saved.version + ' gespeichert.');
    ($('#draft') ?? $('#doc-title'))?.focus();
  }

  private edition(doc: Document, label: string): Edition {
    return { label, body: doc.body, title: doc.title, lang: doc.lang };
  }

  private async versionEdition(doc: Document, key: string): Promise<Edition> {
    if (key === 'saved') return this.edition(doc, 'Version ' + doc.version);
    if (key === 'draft') return { label: 'Arbeitsentwurf', body: this.body, title: this.draft.title, lang: doc.lang };
    const older = await json<DocVersion & { body: string }>(`/api/documents/${doc.id}/versions/${encodeURIComponent(key)}`);
    return { label: 'Version ' + older.version, body: older.body, title: older.title, lang: doc.lang };
  }

  async versions(compare = false) {
    const doc = this.doc!;
    const history = await api.versions(doc.id);
    if (this.doc !== doc) return;
    const editions = [
      ['saved', 'Version ' + doc.version + ' · gespeichert'],
      ...(this.dirty ? [['draft', 'Arbeitsentwurf']] : []),
      ...history.map(v => [v.id, 'Version ' + v.version]),
    ];
    const choices = (picked: string) => editions.map(([value, label]) =>
      `<option value="${esc(value)}"${value === picked ? ' selected' : ''}>${esc(label)}</option>`).join('');
    showDialog('Versionen', `<p>Aktuelle Fassung · Version ${doc.version}${doc.version_origin ? ' · ' + esc(versionNote(doc.version_origin, doc.version_note)) : ''}</p>
      ${editions.length > 1 ? `<form id="compare-form" class="version-compare-form">
        <label for="edition-before">Ausgangsfassung</label><select class="field" id="edition-before" name="before">${choices(history[0]?.id ?? 'saved')}</select>
        <label for="edition-after">Vergleichsfassung</label><select class="field" id="edition-after" name="after">${choices(this.dirty ? 'draft' : 'saved')}</select>
        <button class="button primary" type="submit">Fassungen vergleichen</button><p id="versions-status" role="status"></p></form>` : ''}
      ${history.length ? `<ul class="plain-list editorial-findings">${history.map(v =>
        `<li>${button('editor-version', `Version ${v.version} · ${formatDate(v.created)}`, 'text', 'button quiet', v.id)}
          ${versionNote(v.origin, v.note) ? '<small>' + esc(versionNote(v.origin, v.note)) + '</small>' : ''}</li>`).join('')}</ul>`
      : '<p>Ältere Fassungen erscheinen nach dem nächsten Speichern.</p>'}`, true);
    const form = $<HTMLFormElement>('#compare-form', details);
    form?.addEventListener('submit', async event => {
      event.preventDefault();
      const data = new FormData(form);
      try {
        const [before, after] = await Promise.all([
          this.versionEdition(doc, String(data.get('before'))), this.versionEdition(doc, String(data.get('after'))),
        ]);
        if (this.doc === doc && form.isConnected) showDialog('Versionsvergleich',
          compareMarkup(before, after) + button('editor-versions', 'Zur Versionshistorie', undefined, 'button'), true);
      } catch (error) { $('#versions-status', form)!.textContent = describe(error); }
    });
    if (compare) form?.requestSubmit();
  }

  private async showVersion(id: string) {
    const doc = this.doc!;
    const old = await this.versionEdition(doc, id);
    if (this.doc !== doc) return;
    showDialog(old.label, `<div class="prose"${old.lang ? ` lang="${esc(old.lang)}"` : ''}>${markdown(old.body)}</div>
      <button type="button" class="button primary" id="restore-version">Als neue Version wiederherstellen</button>
      <p id="restore-status" role="status"></p>`, true);
    $('#restore-version')!.addEventListener('click', async event => {
      if (this.doc !== doc) return;
      const submit = event.currentTarget as HTMLButtonElement;
      submit.disabled = true;
      try {
        const snapshot = { body: this.body, title: this.draft.title };
        const restored = await api.editDocument(doc.id, { body: old.body, title: old.title ?? doc.title,
          version: this.draft.base.version, note: old.label, origin: 'restored' });
        const next = await api.document(doc.id);
        if (this.doc !== doc) return;
        this.drafts.delete(doc.id);
        this.open(next);
        this.saved(next);
        this.draft.undo.push(snapshot);
        this.changed();
        details.close();
        this.status('Fassung als Version ' + restored.version + ' wiederhergestellt.');
        ($('#draft') ?? $('#doc-title'))?.focus();
      } catch (error) { $('#restore-status', details)!.textContent = describe(error); }
      finally { submit.disabled = false; }
    });
  }

  async fromChat(mode: 'audit' | 'review' | 'rewrite' | 'both' | 'compare', instruction: string, scoped = false) {
    if (mode === 'compare') { await this.versions(true); return []; }
    const range = scoped ? this.selectedRange() : undefined;
    if (scoped && !range) {
      this.status('Markiere den gewünschten Absatz im Editor.');
      return [];
    }
    if (mode === 'both') return [await this.execute('audit', { range }),
      await this.execute('rewrite', { range, goal: 'custom', instruction })];
    return [await this.execute(mode, mode === 'rewrite' ? { range, goal: 'custom', instruction } : { range })];
  }

  async action(action: string, value: string) {
    if (!this.doc) return;
    try {
      switch (action) {
        case 'editor-save': await this.save(); break;
        case 'editor-preview':
          this.preview = !this.preview;
          this.changed();
          $('[data-action="editor-preview"]')?.focus();
          break;
        case 'editor-undo': {
          const prior = this.draft.undo.pop() ?? (this.dirty ? this.doc : undefined);
          if (prior) {
            Object.assign(this.draft, { body: prior.body, title: prior.title });
            this.changed();
            this.status('Vorherigen Text wiederhergestellt.');
          }
          $('[data-action="editor-undo"]')?.focus();
          break;
        }
        case 'editor-lint': await this.execute('audit', { range: this.selectedRange() }); break;
        case 'editor-review': await this.execute('review', { range: this.shownRun?.range ?? undefined }); break;
        case 'editor-history': await this.editorialHistory(); break;
        case 'editor-open-report': await this.showEditorial(value); break;
        case 'editor-finding': this.useFinding(false, Number(value)); break;
        case 'editor-observation': this.useFinding(true, Number(value)); break;
        case 'editor-accept': await this.accept(); break;
        case 'editor-discard':
          await post(this.path(value) + '/discard');
          details.close();
          this.status('Vorschlag verworfen.');
          void this.refreshEditorial().catch(() => {});
          break;
        case 'editor-retry': {
          const run = this.shownRun;
          if (!run || run.id !== value) break;
          const options = this.runOptions.get(value) ?? {
            goal: run.goal, instruction: run.instruction, range: run.range ?? undefined,
          };
          const range = options.range && this.body.slice(...options.range) === run.original ? options.range : undefined;
          this.rewriteForm({ ...options, range }, false);
          break;
        }
        case 'editor-versions': await this.versions(); break;
        case 'editor-version': await this.showVersion(value); break;
        case 'editor-rewrite': this.rewriteForm(); break;
        case 'editor-export':
          showDialog('Dokument exportieren', `<p>${this.dirty ? 'Deine Änderungen werden vor dem Export gespeichert.' : 'Wähle ein Dateiformat.'}</p>
            <div class="dialog-actions">${button('editor-download', 'Markdown', 'text', 'button', 'md')}
            ${button('editor-download', 'Astro MDX', 'text', 'button', 'mdx')}</div><p role="status" id="export-status"></p>`);
          break;
        case 'editor-download':
          $('#export-status')!.textContent = 'Export wird vorbereitet …';
          await this.export(value === 'mdx' ? 'mdx' : 'md');
          if (details.open) details.close();
          break;
      }
    } catch (error) {
      const text = describe(error, 'Die Dokumentaktion ist fehlgeschlagen. Dein Entwurf bleibt erhalten.');
      const target = $('#editorial-dialog-status, #export-status', details);
      if (target) target.textContent = text;
      this.status(text);
    }
  }
}
