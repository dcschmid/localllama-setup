const paths = {
  mark: '<path d="M4 20h16M7 15.5l1.2-4L16.5 3l4 4-8.4 8.4L7 17zM14.5 5l4 4"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  library: '<path d="M5 5v14M9 5v14M13 5v14M17 6l3 13"/>',
  search: '<circle cx="10.5" cy="10.5" r="5.5"/><path d="m15 15 4.5 4.5"/>',
  settings: '<path d="M5 6h14M5 12h14M5 18h14M9 4v4m6 2v4m-5 2v4"/>',
  chat: '<path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 3z"/>',
  book: '<path d="M12 6c-3-2-6-2.5-9-1v13c3-1.5 6-1 9 1m0-13c3-2 6-2.5 9-1v13c-3-1.5-6-1-9 1m0-13v13"/>',
  research: '<circle cx="10.5" cy="10.5" r="6"/><path d="M10.5 7v7M7 10.5h7m1 4.5 5 5"/>',
  picture: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.15"/><path d="m4 17 5-4 3 2 4-5 5 5"/>',
  game: '<path d="M7.5 7h9a3.4 3.4 0 0 1 3.4 2.8l1 4.7a2.5 2.5 0 0 1-4.15 2.35L14.6 15H9.4l-2.15 1.85A2.5 2.5 0 0 1 3.1 14.5l1-4.7A3.4 3.4 0 0 1 7.5 7zM8 9.5v3M6.5 11h3m6.5-1h.01m2 2h.01"/>',
  arrow: '<path d="M4 12h15m-5-5 5 5-5 5"/>',
  turn: '<path d="M5 6v8h14m-4-4 4 4-4 4"/>',
  up: '<path d="M12 19V5m-6 6 6-6 6 6"/>',
  moon: '<path d="M20.5 14.1a8.4 8.4 0 0 1-10.6-10.6A8.5 8.5 0 1 0 20.5 14z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  text: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8m-8 4h8m-8 4h5"/>',
};

function icon(name) {
  return '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths[name] + '</svg>';
}

const projects = [
  { id: 'story', title: 'Die letzte Fähre', type: 'Geschichte', updated: 'Heute', step: 'Kapitel 1 im Entwurf', icon: 'book' },
  { id: 'game', title: 'Moos & Maschinen', type: 'Spielidee', updated: 'Gestern', step: 'Kernmechanik in Arbeit', icon: 'game' },
  { id: 'article', title: 'Leben mit der Tide', type: 'Artikel', updated: 'Vor 3 Tagen', step: 'Gliederung angelegt', icon: 'text' },
];

const suggestions = [
  { id: 'story', icon: 'book', label: 'Geschichte schreiben', prompt: 'Lass uns gemeinsam eine Geschichte schreiben.' },
  { id: 'research', icon: 'research', label: 'Deep Research starten', prompt: 'Recherchiere ausführlich, wie sich das Wattenmeer an den steigenden Meeresspiegel anpasst.' },
  { id: 'image', icon: 'picture', label: 'Bild erstellen', prompt: 'Erstelle ein Titelbild mit einer kleinen Fähre im Nebel, in gedeckten Farben.' },
  { id: 'game', icon: 'game', label: 'Spielidee entwickeln', prompt: 'Lass uns ein ruhiges Erkundungsspiel für Godot entwickeln.' },
];

const examples = {
  story: {
    prompt: 'Ich möchte eine Geschichte schreiben. Eine Fährfrau nimmt mitten in der Nacht einen seltsamen Fahrgast an Bord.',
    answer: 'Beginnen wir mit einer Entscheidung, die deine Fährfrau eigentlich längst getroffen hat: Nach Mitternacht setzt sie niemanden mehr über. Umso spannender wird der Moment, in dem sie ihre eigene Regel bricht.',
    draft: '# Die letzte Fähre\n\nUm zwölf löschte Ada das Licht über der Rampe. Der Mann am Kai blieb stehen. Die Flut hatte den Sand unter seinen Schuhen dunkel gefärbt.\n\n„Die Fähre fährt nicht mehr“, sagte sie.\n\nEr hielt die Hand auf. Auf seiner Handfläche lag ihr Schlüssel.',
  },
  research: {
    title: 'Recherche zum Wattenmeer',
    prompt: 'Recherchiere ausführlich, wie sich das Wattenmeer an den steigenden Meeresspiegel anpasst.',
    answer: 'Die Recherche beginnt bei der Sedimentbilanz. Danach geht es um Unterschiede zwischen Wattflächen und Salzwiesen und um die Frage, wo die Anpassung an Grenzen stößt.',
  },
  game: {
    prompt: 'Ich möchte ein ruhiges Godot-Spiel über winzige Reparaturroboter im Wald entwickeln.',
    answer: 'Stell dir vor, jede reparierte Maschine verändert einen kleinen Ausschnitt des Waldes. Eine alte Pumpe füllt einen Tümpel. Plötzlich lassen sich am anderen Ufer Spuren lesen. Was soll im Mittelpunkt stehen: die Reparatur selbst oder die Folgen im Ökosystem?',
  },
  article: {
    prompt: 'Hilf mir, einen kurzen Artikel über Salzwiesen und Hochwasser zu schreiben.',
    answer: 'Für den Einstieg eignet sich ein konkreter Ort. Wir können beschreiben, was bei Flut auf einer Salzwiese passiert, und dann erklären, wie Pflanzen und Gelände die Wellen abbremsen.',
    draft: '# Leben mit der Tide\n\nDie Salzwiese liegt zwischen Land und Meer. Bei Hochwasser wird sie für einige Stunden Teil des Watts. Ihre Funktion für den Küstenschutz beginnt mit den Pflanzen, die dort wachsen.',
  },
  image: {
    title: 'Umschlag im Nebel',
    answer: 'Im fertigen Studio erscheint hier der Bildauftrag. Sobald ein Bild vorliegt, lässt es sich im Chat öffnen, als Variante neu anstoßen oder in ein Dokument übernehmen.',
  },
};

const state = {
  view: 'home', current: null, messages: [], intent: null, editor: false, preview: false,
  paused: false, collapsed: false, draft: '', savedDraft: '', previous: '', version: 1,
  chatDraft: '',
};
const root = document.documentElement;
const main = document.querySelector('#main');
const announcement = document.querySelector('#announcement');
const navToggle = document.querySelector('#nav-toggle');
const themeToggle = document.querySelector('#theme-toggle');
const navDialog = document.querySelector('#nav-dialog');
const details = document.querySelector('#details');
const mobile = matchMedia('(max-width: 60rem)');
const isWorkspace = root.dataset.concept === 'b';

function escape(value) {
  const text = document.createElement('span');
  text.textContent = value;
  return text.innerHTML.replaceAll('"', '&quot;');
}

function notice(text) {
  announcement.textContent = text;
}

function button(action, label, glyph, className = 'button quiet') {
  return '<button type="button" class="' + className + '" data-action="' + action + '">' + (glyph ? icon(glyph) : '') + label + '</button>';
}

function mark() {
  return '<span class="brand-mark">' + icon('mark') + '</span>';
}

function navigation() {
  const item = (id, text, glyph, current) => '<button class="nav-item' + (id === 'new' ? ' new-chat' : '') + '" type="button" data-action="' + id + '"' +
    (current ? ' aria-current="page"' : '') + '>' + icon(glyph) + '<span>' + text + '</span></button>';
  const chat = (id, title) => '<button type="button" class="history-item" data-example="' + id + '"' +
    (state.current === id ? ' aria-current="page"' : '') + '>' + icon('chat') + '<span>' + title + '</span></button>';
  document.querySelectorAll('[data-navigation]').forEach(region => {
    const drawer = region.closest('dialog');
    region.innerHTML = `<div class="side-content">
      <div class="side-brand">${mark()}<span>Creative Studio</span>${drawer ? button('close-nav', '<span class="sr-only">Seitenleiste schließen</span>', 'x', 'icon-button') : ''}</div>
      <nav aria-label="Hauptnavigation">
        <div class="nav-stack">
          ${item('new', 'Neuer Chat', 'plus', state.view === 'home')}
          ${item('projects', 'Projekte', 'folder', state.view === 'projects')}
          ${item('library', 'Bibliothek', 'library', state.view === 'library')}
        </div>
        <div class="nav-stack">${item('search', 'Suche', 'search', state.view === 'search')}</div>
      </nav>
      <div class="side-history">
        <h2>Letzte Unterhaltungen</h2>
        ${chat('story', 'Die letzte Fähre')}
        ${chat('research', 'Recherche zum Wattenmeer')}
        ${chat('game', 'Moos & Maschinen')}
      </div>
      <div class="side-footer">${item('settings', 'Einstellungen', 'settings', state.view === 'settings')}</div>
    </div>`;
  });
}

function renderControls() {
  const open = mobile.matches ? navDialog.open : !state.collapsed;
  navToggle.setAttribute('aria-expanded', String(open));
  navToggle.setAttribute('aria-controls', mobile.matches ? 'nav-dialog' : 'sidebar');
  navToggle.setAttribute('aria-label', open ? 'Seitenleiste schließen' : 'Seitenleiste öffnen');
  navToggle.innerHTML = icon('panel');
  const dark = root.dataset.theme === 'dark';
  themeToggle.setAttribute('aria-label', dark ? 'Helles Erscheinungsbild verwenden' : 'Dunkles Erscheinungsbild verwenden');
  themeToggle.innerHTML = icon(dark ? 'sun' : 'moon');
}

function composer() {
  const tool = suggestions.find(item => item.id === state.intent);
  return `<form class="composer" id="composer">
    <label for="prompt" class="sr-only">Nachricht</label>
    <textarea id="prompt" name="prompt" rows="2" required placeholder="${state.view === 'home' ? 'Womit möchtest du anfangen?' : 'Nachricht schreiben …'}">${escape(state.chatDraft)}</textarea>
    <div class="composer-actions">
      <div class="composer-tools">${button('tools', tool?.label ?? 'Werkzeuge', tool?.icon ?? 'settings', 'button quiet tool-label')}</div>
      <button class="button primary send" type="submit" aria-label="Nachricht senden">${icon('up')}</button>
    </div>
  </form>`;
}

function projectCard(project) {
  return `<button type="button" class="project-card" data-example="${project.id}">
    <span class="cover ${project.id}">${icon(project.icon)}</span>
    <span><strong>${project.title}</strong><small>${project.type} · ${project.updated}</small><small>${project.step}</small></span>
    ${icon('arrow')}
  </button>`;
}

function home() {
  return `<div class="home">
    <section class="welcome" aria-labelledby="welcome-title">
      <div class="welcome-inner">
        <h1 id="welcome-title" class="welcome-title">Was möchtest du <em>heute machen?</em></h1>
        <div class="suggestions" role="group" aria-label="Vorschläge">
          ${suggestions.map(item => `<button type="button" class="suggestion" data-suggestion="${item.id}">${icon(item.icon)}<span>${item.label}</span>${icon('turn')}</button>`).join('')}
        </div>
        ${composer()}
      </div>
    </section>
    ${isWorkspace ? `<aside class="workspace-rail" aria-labelledby="workspace-title">
      <h2 id="workspace-title">Weiterarbeiten</h2>
      <div class="workspace-list">${projects.slice(0, 2).map(projectCard).join('')}</div>
      ${button('projects', 'Alle Projekte', 'arrow', 'button quiet all-projects')}
    </aside>` : ''}
  </div>`;
}

function researchPreview() {
  const step = state.paused ? 'Pausiert · Quellen sichten' : 'Quellen sichten · Runde 2 von 3';
  return `<section class="research-card" aria-label="Beispiel für Recherchefortschritt">
    <h3>Recherchevorschau</h3>
    <p>${step}</p>
    <progress value="2" max="3" aria-label="2 von 3 Rechercherunden"></progress>
    <details><summary>Quellen (2)</summary><ul>
      <li>Nationalpark Wattenmeer · Sediment und Lebensräume</li>
      <li>Umweltbundesamt · Meeresspiegelanstieg</li>
    </ul></details>
    <details open><summary>Offene Frage (1)</summary><p>Welche Wattflächen können mit dem Meeresspiegelanstieg Schritt halten?</p></details>
    ${button('pause', state.paused ? 'Vorschau fortsetzen' : 'Vorschau pausieren', '', 'button')}
  </section>`;
}

function markdownPreview(text) {
  return text.trim().split(/\n\s*\n/).map(block => {
    const heading = block.match(/^#{1,6} (.+)$/);
    return heading ? '<h3>' + escape(heading[1]) + '</h3>' : '<p>' + escape(block).replaceAll('\n', '<br>') + '</p>';
  }).join('');
}

function editor() {
  const title = projects.find(project => project.id === state.current)?.title ?? 'Dokument';
  return `<section class="editor" aria-labelledby="editor-title"><div class="editor-inner">
    <div class="editor-top"><h2 class="serif" id="editor-title">${title}</h2>
      ${button('editor', '<span class="sr-only">Editor schließen</span>', 'x', 'icon-button')}
    </div>
    <p class="editor-meta">Entwurf · Version ${state.version}</p>
    ${isWorkspace ? `<details class="project-outline"><summary>Projektübersicht</summary>
      <p>${title} · ${state.current === 'story' ? 'Kapitel 1 im Entwurf' : 'Gliederung angelegt'}</p>
    </details>` : ''}
    <div class="editor-actions">
      ${button('preview', state.preview ? 'Markdown bearbeiten' : 'Vorschau', 'text')}
      ${button('undo', 'Rückgängig')}
      ${button('versions', 'Versionen')}
    </div>
    ${state.preview ? '<div class="draft-preview">' + markdownPreview(state.draft) + '</div>'
    : '<textarea id="draft" aria-label="Dokumenttext in Markdown">' + escape(state.draft) + '</textarea>'}
    <div class="editor-actions">
      ${button('save', 'Speichern', '', 'button primary')}
      ${button('rewrite', 'Auswahl bearbeiten')}
      ${button('audit', 'Schreibstil prüfen')}
      ${button('export', 'Exportieren')}
    </div>
  </div></section>`;
}

function conversation() {
  const project = projects.find(item => item.id === state.current);
  const title = project?.title ?? examples[state.current]?.title ?? 'Unterhaltung';
  const draftAvailable = Boolean(examples[state.current]?.draft);
  return `<div class="conversation${state.editor ? ' with-editor' : ''}">
    <section class="chat-column" aria-labelledby="chat-title">
      <div class="chat-heading"><h1 id="chat-title">${title}</h1>
        ${project ? `<div class="project-context">${project.type}
          ${draftAvailable ? button('editor', state.editor ? 'Editor schließen' : 'Editor öffnen', 'text') : button('decisions', 'Entscheidungen', 'text')}
        </div>` : ''}
      </div>
      <div class="transcript" role="group" aria-label="Chatverlauf">
        ${state.messages.map(message => {
          if (message.role === 'user') return '<article class="message user"><h2>Du</h2><div class="message-content"><p>' + escape(message.text) + '</p></div></article>';
          return `<article class="message assistant">${mark()}<div class="message-content">
            <h2>Studio · Beispielantwort</h2><p>${escape(message.text)}</p>
            ${message.attachment === 'research' ? researchPreview() : ''}
            ${!state.editor && ['story', 'article'].includes(message.attachment) ? button('editor', 'Entwurf öffnen', 'text', 'button') : ''}
          </div></article>`;
        }).join('')}
      </div>
      ${composer()}
    </section>
    ${state.editor ? editor() : ''}
  </div>`;
}

function collection() {
  const entries = projects.map(projectCard).join('');
  const pages = {
    projects: `<h1>Projekte</h1>${button('new', 'Mit einem neuen Chat beginnen', 'plus', 'button primary')}<div class="project-list">${entries}</div>`,
    library: `<h1>Bibliothek</h1><p>Entwürfe, Recherchen und Bilder aus deinen Projekten.</p>
      <div class="project-list">${projectCard(projects[0])}${projectCard(projects[2])}
      ${button('example-research', 'Recherche zum Wattenmeer', 'research', 'project-card')}
      ${button('example-image', 'Umschlag im Nebel · Bildablauf ansehen', 'picture', 'project-card')}</div>`,
    search: '<h1>Suche</h1><form id="search-form"><label for="search">Projekte durchsuchen</label><input class="field" type="search" id="search" name="q" required><button class="button" type="submit">Suchen</button></form><div class="project-list" id="search-results"></div>',
    settings: '<h1>Einstellungen</h1><div><h2 class="serif">Erscheinungsbild</h2>' + button('theme', root.dataset.theme === 'dark' ? 'Hell verwenden' : 'Dunkel verwenden', '', 'button') + '</div>',
  };
  return '<section class="collection">' + pages[state.view] + '</section>';
}

const viewLabels = { home: 'Neuer Chat', chat: 'Unterhaltung', projects: 'Projekte', library: 'Bibliothek', settings: 'Einstellungen', search: 'Suche' };
function render(focus = 'main') {
  navigation();
  renderControls();
  document.querySelector('#location-label').textContent = viewLabels[state.view];
  main.innerHTML = state.view === 'home' ? home() : state.view === 'chat' ? conversation() : collection();
  if (focus === 'editor-button') main.querySelector('.project-context [data-action="editor"]')?.focus();
  else if (focus === 'editor') (main.querySelector('#draft') ?? main.querySelector('.editor-top button'))?.focus();
  else if (focus === 'prompt') main.querySelector('#prompt')?.focus();
  else if (focus === 'main') main.focus({ preventScroll: true });
}

function setExample(id) {
  const example = examples[id];
  state.view = 'chat';
  state.current = id;
  state.intent = null;
  state.editor = false;
  state.preview = false;
  state.paused = false;
  state.draft = example.draft ?? '';
  state.savedDraft = state.draft;
  state.previous = '';
  state.version = 1;
  state.chatDraft = '';
  state.messages = [];
  if (example.prompt) state.messages.push({ role: 'user', text: example.prompt });
  state.messages.push({ role: 'assistant', text: example.answer, attachment: id });
}

function selectSuggestion(id) {
  const suggestion = suggestions.find(item => item.id === id);
  const prompt = main.querySelector('#prompt');
  if (!prompt) return;
  if (!prompt.value.trim()) prompt.value = suggestion.prompt;
  state.chatDraft = prompt.value;
  state.intent = id;
  main.querySelector('[data-action="tools"]').innerHTML = icon(suggestion.icon) + suggestion.label;
  prompt.focus();
}

function showDialog(title, body) {
  details.innerHTML = `<div class="dialog-content"><div class="dialog-top"><h2 id="details-title">${title}</h2>
    <form method="dialog"><button class="icon-button" aria-label="Dialog schließen">${icon('x')}</button></form>
    </div>${body}</div>`;
  details.showModal();
}

function closeDrawer() {
  if (navDialog.open) {
    navDialog.close();
    renderControls();
  }
}

document.addEventListener('click', event => {
  const target = event.target.closest('button');
  if (!target) return;
  const { action, suggestion, example, tool } = target.dataset;
  if (suggestion || tool) {
    if (details.open) details.close();
    selectSuggestion(suggestion ?? tool);
    return;
  }
  if (example || action?.startsWith('example-')) {
    closeDrawer();
    setExample(example ?? action.slice(8));
    render();
    return;
  }
  if (target === navToggle) {
    if (mobile.matches) navDialog.showModal();
    else {
      state.collapsed = !state.collapsed;
      document.querySelector('.app').classList.toggle('collapsed', state.collapsed);
    }
    renderControls();
    return;
  }
  if (action === 'close-nav') closeDrawer();
  if (['new', 'projects', 'search', 'library', 'settings'].includes(action)) {
    closeDrawer();
    Object.assign(state, { view: action === 'new' ? 'home' : action, current: null, intent: null, editor: false, messages: [], chatDraft: '' });
    render(action === 'new' ? 'prompt' : 'main');
  }
  if (action === 'theme') {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('studio-prototype-theme', root.dataset.theme);
    renderControls();
    if (state.view === 'settings' && target !== themeToggle) {
      target.textContent = root.dataset.theme === 'dark' ? 'Hell verwenden' : 'Dunkel verwenden';
    }
  }
  if (action === 'about') showDialog('Designprototyp', `
    <p>${isWorkspace ? 'B · Creative Workspace' : 'A · Minimal Creative Assistant'}</p>
    <p>Die Beispielunterhaltungen zeigen den Bedienablauf. Eingaben bleiben auf dieser Seite. Die lokalen Dienste sind hier nicht verbunden.</p>
    <div class="dialog-actions"><a href="?design=a">Minimal Creative Assistant</a><a href="?design=b">Creative Workspace</a></div>`);
  if (action === 'tools') showDialog('Werkzeuge', '<p>Du kannst frei schreiben oder einen Auftrag als Ausgangspunkt wählen.</p><div class="dialog-actions">' +
    suggestions.map(item => `<button type="button" class="button" data-tool="${item.id}">${icon(item.icon)}${item.label}</button>`).join('') + '</div>');
  if (action === 'editor') {
    state.editor = !state.editor;
    render(state.editor ? 'editor' : 'editor-button');
  }
  if (action === 'preview') {
    state.preview = !state.preview;
    render(false);
    main.querySelector('[data-action="preview"]').focus();
  }
  if (action === 'pause') {
    state.paused = !state.paused;
    render(false);
    main.querySelector('[data-action="pause"]').focus();
    notice(state.paused ? 'Recherchevorschau pausiert' : 'Recherchevorschau fortgesetzt');
  }
  if (action === 'save' && state.draft !== state.savedDraft) {
    state.previous = state.savedDraft;
    state.savedDraft = state.draft;
    state.version += 1;
    main.querySelector('.editor-meta').textContent = 'Entwurf · Version ' + state.version;
    notice('Demofassung gespeichert');
  }
  if (action === 'undo') {
    state.draft = state.draft === state.savedDraft ? state.previous || state.savedDraft : state.savedDraft;
    if (state.preview) main.querySelector('.draft-preview').innerHTML = markdownPreview(state.draft);
    else main.querySelector('#draft').value = state.draft;
    notice('Letzte Demofassung geladen');
  }
  if (action === 'versions') showDialog('Versionen', '<p>Aktuelle Demofassung · Version ' + state.version + '</p>' +
    (state.version > 1 ? '<p>Vorherige Demofassung · Version ' + (state.version - 1) + '</p>' : ''));
  if (action === 'rewrite') showDialog('Auswahl bearbeiten', '<p>Im Studio kannst du eine markierte Passage mit einem Auftrag an das Schreibmodell überarbeiten und den Vorschlag vor der Übernahme lesen.</p>');
  if (action === 'audit') showDialog('Schreibstil prüfen', '<p>Hier erscheinen die Hinweise aus dem Human Writing Audit zur aktuellen Fassung.</p>');
  if (action === 'export') showDialog('Exportieren', '<p>Im Studio stehen Markdown und Astro MDX als Download zur Verfügung.</p><div class="dialog-actions">' +
    button('download-md', 'Demo als Markdown', '', 'button') + button('download-mdx', 'Demo als MDX', '', 'button') + '</div>');
  if (action === 'download-md' || action === 'download-mdx') {
    const blob = new Blob([state.draft], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'studio-entwurf.' + action.slice(9);
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  if (action === 'decisions') showDialog('Entscheidungen', '<p><strong>Offen</strong> · Sollen Reparaturen direkt steuerbar sein oder über Veränderungen in der Umgebung sichtbar werden?</p>');
});

main.addEventListener('input', event => {
  if (event.target.id === 'draft') state.draft = event.target.value;
  if (event.target.id === 'prompt') state.chatDraft = event.target.value;
});

main.addEventListener('keydown', event => {
  if (event.target.id === 'prompt' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if (event.target.value.trim()) event.target.form.requestSubmit();
  }
});

main.addEventListener('submit', event => {
  event.preventDefault();
  const fields = new FormData(event.target);
  if (event.target.id === 'search-form') {
    const term = fields.get('q').trim().toLocaleLowerCase('de');
    const matches = projects.filter(project => (project.title + ' ' + project.type).toLocaleLowerCase('de').includes(term));
    main.querySelector('#search-results').innerHTML = matches.length ? matches.map(projectCard).join('') : '<p>Keine passenden Beispielprojekte gefunden.</p>';
    notice(matches.length + ' Projekte gefunden');
  }
  if (event.target.id !== 'composer') return;
  const text = fields.get('prompt').trim();
  if (!text) return;
  state.chatDraft = '';
  if (state.view === 'home') {
    const example = state.intent ?? (
      /recherch|research/i.test(text) ? 'research' :
      /(?:titel|erstelle.+)bild|illustration/i.test(text) ? 'image' :
      /spielidee|spiel entwickeln|godot/i.test(text) ? 'game' :
      /geschichte|roman|erzäh/i.test(text) ? 'story' : null
    );
    if (example) setExample(example);
    else state.view = 'chat';
    state.messages = [{ role: 'user', text }, {
      role: 'assistant',
      text: examples[example]?.answer ?? 'Im fertigen Studio erscheint hier die Antwort auf deine Nachricht. Über „Prototyp“ kannst du zwischen den Entwürfen wechseln.',
      attachment: example,
    }];
  } else {
    state.messages.push({ role: 'user', text }, {
      role: 'assistant', text: 'Hier würde das Studio an deine letzte Nachricht anknüpfen.',
    });
  }
  render('prompt');
  main.querySelector('.transcript').lastElementChild.scrollIntoView({ block: 'nearest' });
  notice('Beispielantwort im Chat verfügbar');
});

navDialog.addEventListener('close', renderControls);
mobile.addEventListener('change', () => {
  if (!mobile.matches) closeDrawer();
  renderControls();
});
render(false);
