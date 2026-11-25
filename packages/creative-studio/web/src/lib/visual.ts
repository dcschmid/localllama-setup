import { esc, json, post } from './core';
import { $, announce, details, dialogForm, showDialog, sourceLink } from './studio-ui';

export type VisualReceipt = {
  name: string; version: number; model: string; recipe: string; ratio: string;
  palette: string; license?: string; license_url?: string; image_conditioning?: boolean;
  settings?: { size?: string; seed?: number; steps?: number; cfg_scale?: number; sampler?: string };
};

type VisualRecord = {
  name: string; from: number; to: number; attachment?: string; use_image?: boolean;
  [key: string]: string | number | boolean | undefined;
};
type Groups = Record<'characters' | 'locations', VisualRecord[]>;
type Profile = {
  id: string; version: number; template: string; name: string; ratio: string; model: string;
  recipe: string; consistency: boolean; bible: Groups; [key: string]: unknown;
};
type Info = {
  profile: Profile; templates: Profile[];
  models: Array<{ id: string; name: string; formats: Array<{ id: string; size: string }>;
    negative: boolean; license?: string; license_url?: string }>;
  recipes: Array<{ id: string; model: string; name?: string }>;
  reusable: Array<{ id: string; name: string; profile_name: string }>;
  attachments: Array<{ id: string; name: string }>;
};
const fields = { description: 'Beschreibung', style: 'Stilbeschreibung', palette: 'Palette für Szenen ohne Farbvorgabe',
  lighting: 'Licht', composition: 'Komposition', consistency_rules: 'Konsistenzregeln', negative: 'Negative Vorgaben',
  extra: 'Ergänzungen zum Bildprompt' };
const groupFields = {
  characters: { appearance: 'Erscheinungsbild', hair: 'Haare', eyes: 'Augen', clothing: 'Kleidung',
    proportions: 'Proportionen', features: 'Merkmale', objects: 'Gegenstände' },
  locations: { architecture: 'Architektur', landscape: 'Landschaft', materials: 'Materialien',
    lighting: 'Licht', colors: 'Farben', features: 'Merkmale' },
};
const option = (id: string, label: string, active = false) =>
  `<option value="${esc(id)}"${active ? ' selected' : ''}>${esc(label)}</option>`;
const field = (key: string, label: string, value: unknown = '', long = false) =>
  `<label for="visual-${key}">${esc(label)}</label>` + (long
    ? `<textarea class="field" id="visual-${key}" name="${key}" rows="2" maxlength="800">${esc(String(value))}</textarea>`
    : `<input class="field" id="visual-${key}" name="${key}" maxlength="500" value="${esc(String(value))}">`);
const endpoint = (id: string) => '/api/projects/' + encodeURIComponent(id) + '/visual-profile';

export function receiptMarkup(profile?: VisualReceipt) {
  if (!profile) return '';
  const license = profile.license_url ? sourceLink(profile.license_url, profile.license || 'Lizenz') : esc(profile.license || '');
  const settings = profile.settings;
  const capture = settings ? [settings.size?.replace('x', ' × '), settings.seed != null ? 'Seed ' + settings.seed : '',
    settings.steps != null ? settings.steps + ' Schritte' : '', settings.cfg_scale != null ? 'CFG ' + settings.cfg_scale : '',
    settings.sampler].filter(Boolean).join(' · ') : '';
  return `<details><summary>Bilddetails</summary><p>${esc(profile.name)} · Version ${profile.version} · ${esc(profile.ratio)}</p>
    <p>${esc(profile.model)}${profile.recipe ? ' · ' + esc(profile.recipe) : ''}</p>
    ${capture ? '<p>' + esc(capture) + '</p>' : ''}
    <p>${esc(profile.palette)}</p>${profile.image_conditioning ? '<p>Bildvorlage verwendet.</p>' : ''}
    ${license ? '<p>' + license + '</p>' : ''}</details>`;
}

export async function visualProfileDialog(pid: string) {
  const info = await json<Info>(endpoint(pid));
  const { profile } = info;
  const missing = [...new Set([profile.model, ...info.templates.map(t => t.model)])]
    .filter(id => !info.models.some(m => m.id === id));
  dialogForm('Bildstil der Geschichte', `
    <label for="visual-template">Bildstil</label>
    <select class="field" id="visual-template" name="template">${info.templates.map(t => option(t.template, t.name, t.template === profile.template)).join('')}</select>
    <label for="visual-ratio">Bildformat</label><select class="field" id="visual-ratio" name="ratio"></select>
    <p id="visual-format-message" class="muted" role="status" hidden></p>
    <label><input type="checkbox" name="consistency"${profile.consistency ? ' checked' : ''}> Visuelle Konsistenz</label>
    <div class="dialog-actions"><button class="button" type="button" id="visual-bible">Visual Bible öffnen</button></div>
    <details><summary>Erweitert</summary>
      ${field('name', 'Profilname', profile.name)}
      <label for="visual-model">Lokales Modell</label><select class="field" id="visual-model" name="model">
        ${info.models.map(m => option(m.id, m.name, m.id === profile.model)).join('')}
        ${missing.map(id => option(id, id + ' · nicht installiert', id === profile.model)).join('')}</select>
      <p class="muted" id="visual-license"></p>
      <label for="visual-recipe">Guided Preset</label><select class="field" id="visual-recipe" name="recipe"></select>
      ${Object.entries(fields).map(([key, label]) => field(key, label, profile[key], true)).join('')}
      ${info.reusable.length ? `<label for="visual-copy">Profil aus anderer Geschichte</label>
      <select class="field" id="visual-copy" name="copy_from">${option('', 'Aktuelles Profil bearbeiten')}
        ${info.reusable.map(p => option(p.id, p.name + ' · ' + p.profile_name)).join('')}</select>` : ''}
    </details>`, 'Profil speichern', async form => {
    const source = String(form.get('copy_from') ?? '');
    const values = source ? { copy_from: source } : {
      ...Object.fromEntries(Object.entries(fields).map(([key]) => [key, String(form.get(key) ?? '')])),
      ...Object.fromEntries(['name', 'model', 'recipe', 'ratio', 'template'].map(key => [key, String(form.get(key) ?? '')])),
      consistency: form.has('consistency'),
    };
    await post(endpoint(pid), { ...values, version: profile.version });
    announce('Bildstil gespeichert.');
  });
  const model = $<HTMLSelectElement>('#visual-model', details)!;
  const recipe = $<HTMLSelectElement>('#visual-recipe', details)!;
  const ratio = $<HTMLSelectElement>('#visual-ratio', details)!;
  const template = $<HTMLSelectElement>('#visual-template', details)!;
  const formatMessage = $<HTMLParagraphElement>('#visual-format-message', details)!;
  function update(selectedRecipe: string, selectedRatio: string) {
    const active = info.models.find(item => item.id === model.value);
    const formats = active?.formats ?? [];
    ratio.innerHTML = formats.map(fmt => option(fmt.id, fmt.id + ' · ' + fmt.size.replace('x', ' × '),
      fmt.id === selectedRatio)).join('');
    if (!formats.some(fmt => fmt.id === selectedRatio)) ratio.selectedIndex = -1;
    formatMessage.hidden = Boolean(active && ratio.value);
    formatMessage.textContent = !active ? 'Das bevorzugte Modell ist lokal nicht installiert.'
      : 'Das bisherige Bildformat ist für dieses Modell nicht verfügbar. Wähle ein verfügbares Format.';
    recipe.innerHTML = option('', 'Freie lokale Stilvorlage', !selectedRecipe) + info.recipes
      .filter(item => item.model === model.value)
      .map(item => option(item.id, item.name ?? item.id, selectedRecipe === item.id)).join('');
    $<HTMLParagraphElement>('#visual-license', details)!.innerHTML = active?.license_url
      ? sourceLink(active.license_url, active.license || 'Lizenz') : esc(active?.license || '');
    $<HTMLTextAreaElement>('#visual-negative', details)!.disabled = !active?.negative;
  }
  update(profile.recipe, profile.ratio);
  model.addEventListener('change', () => update('', ratio.value));
  ratio.addEventListener('change', () => { formatMessage.hidden = Boolean(ratio.value); });
  template.addEventListener('change', () => {
    const next = info.templates.find(item => item.template === template.value);
    if (!next) return;
    model.value = next.model;
    for (const key of ['name', ...Object.keys(fields)]) {
      $<HTMLInputElement>(`#visual-${key}`, details)!.value = String(next[key] ?? '');
    }
    update(next.recipe, ratio.value || next.ratio);
  });
  $('#visual-bible', details)!.addEventListener('click', () => showBible(info));
}

function showBible(info: Info) {
  const { profile } = info;
  const rowList = Object.entries(profile.bible).flatMap(([group, rows]) => rows.map((row, index) =>
    `<li><button class="button quiet" type="button" data-visual-row="${group}:${index}">${esc(row.name)}</button>
      <small>Kapitel ${row.from}–${row.to}${row.attachment ? ' · Referenzbild' : ''}</small></li>`));
  showDialog('Visual Bible', `<ul class="plain-list">${rowList.join('')}</ul><div class="dialog-actions">
    <button class="button" type="button" data-visual-row="characters:-1">Figur hinzufügen</button>
    <button class="button" type="button" data-visual-row="locations:-1">Schauplatz hinzufügen</button>
    <button class="button quiet" type="button" id="visual-back">Zum Bildstil</button></div>`);
  for (const node of details.querySelectorAll<HTMLButtonElement>('[data-visual-row]')) {
    node.onclick = () => {
      const [group, index] = node.dataset.visualRow!.split(':');
      if (group === 'characters' || group === 'locations') editRecord(info, group, Number(index));
    };
  }
  $('#visual-back', details)!.onclick = () => void visualProfileDialog(profile.id);
}

function fileData(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '');
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function editRecord(info: Info, group: keyof Groups, index: number) {
  const { profile } = info;
  const item = profile.bible[group][index];
  dialogForm(group === 'characters' ? 'Visuelle Figur' : 'Visueller Schauplatz', `
    ${field('name', 'Name', item?.name)}
    ${Object.entries(groupFields[group]).map(([key, label]) => field(key, label, item?.[key])).join('')}
    <label for="visual-from">Gültig ab Kapitel</label><input class="field" type="number" id="visual-from" name="from" min="1" max="150" value="${item?.from ?? 1}" required>
    <label for="visual-to">Gültig bis Kapitel</label><input class="field" type="number" id="visual-to" name="to" min="1" max="150" value="${item?.to ?? 150}" required>
    <label for="visual-attachment">Bildreferenz</label><select class="field" id="visual-attachment" name="attachment">
      ${option('', 'Keine Referenz')}${info.attachments.filter(a => /\.(png|jpe?g|webp)$/i.test(a.name))
        .map(a => option(a.id, a.name, a.id === item?.attachment)).join('')}</select>
    <label for="visual-upload">Referenzbild hochladen</label><input class="field" type="file" accept="image/png,image/jpeg,image/webp" id="visual-upload" name="upload">
    <label><input type="checkbox" name="use_image"${item?.use_image ? ' checked' : ''}> Als Bildvorlage für passende Szenen verwenden</label>
    ${item ? '<label><input type="checkbox" name="remove"> Eintrag aus dieser Visual Bible entfernen</label>' : ''}
    `, 'Eintrag speichern', async values => {
    const bible = structuredClone(profile.bible);
    if (values.has('remove') && item) {
      bible[group].splice(index, 1);
    } else {
      let attachment = String(values.get('attachment') ?? '');
      const file = values.get('upload');
      if (file instanceof File && file.size) {
        if (file.size > 10 * 1024 * 1024) throw new Error('attachment_too_large');
        const uploaded = await post<{ id: string }>('/api/attachments', { project_id: profile.id, name: file.name,
          data: await fileData(file) });
        attachment = uploaded.id;
      }
      const record: VisualRecord = {
        name: String(values.get('name') ?? ''), from: Number(values.get('from')), to: Number(values.get('to')),
        ...Object.fromEntries(Object.keys(groupFields[group]).map(key => [key, String(values.get(key) ?? '')])),
        use_image: values.has('use_image'), ...(attachment ? { attachment } : {}),
      };
      if (index < 0) bible[group].push(record);
      else bible[group][index] = record;
    }
    await post(endpoint(profile.id), { bible, version: profile.version });
    showBible(await json<Info>(endpoint(profile.id)));
  });
}
