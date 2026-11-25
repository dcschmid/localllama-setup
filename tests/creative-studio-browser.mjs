import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const require = createRequire(import.meta.url);
const { firefox, expect } = require('playwright/test');
const axe = require.resolve('axe-core/axe.min.js');
const base = process.env.CREATIVE_STUDIO_TEST_URL;
if (!base) throw new Error('Set CREATIVE_STUDIO_TEST_URL to an isolated Creative Studio instance.');
const output = process.env.CREATIVE_STUDIO_TEST_OUTPUT ?? 'output/playwright/creative-studio';
const timeout = 240_000;
const tags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'];
const views = { desktop: { width: 1440, height: 900 }, tablet: { width: 834, height: 1112 }, mobil: { width: 390, height: 844 }, reflow: { width: 320, height: 780 } };
let imageChat = process.env.CREATIVE_STUDIO_TEST_IMAGE_CHAT;

await mkdir(output, { recursive: true });
const browser = await firefox.launch();
console.log('Firefox', browser.version());

async function axeCheck(page) {
  await page.addScriptTag({ path: axe });
  const scan = await page.evaluate(runOnly => window.axe.run({ runOnly }), tags);
  assert.deepEqual(scan.violations.map(v => [v.id, v.nodes.map(n => n.target)]), []);
  const manual = scan.incomplete.flatMap(v => v.nodes.map(n => [v.id, n.target, n.failureSummary]));
  if (manual.length) console.log('Manuelle Prüfung erforderlich', JSON.stringify(manual));
}

async function capture(page, name) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: join(output, name + '.png'), animations: 'disabled', fullPage: true });
}

async function compareDesign(page, name, viewport, colorScheme) {
  const designUrl = process.env.CREATIVE_STUDIO_TEST_DESIGN_URL;
  if (!designUrl) return;
  const design = await browser.newPage({ viewport, colorScheme });
  try {
    await design.goto(designUrl);
    await design.getByRole('heading', { name: 'Was möchtest du heute machen?' }).waitFor();
    await design.evaluate(() => document.fonts.ready);
    const reference = join(output, 'design-a-composer-' + name + '.png');
    const implementation = join(output, 'live-composer-' + name + '.png');
    await design.locator('.welcome-inner').screenshot({ path: reference, animations: 'disabled' });
    await page.locator('.welcome-inner').screenshot({ path: implementation, animations: 'disabled' });
    const comparison = spawnSync('magick', ['compare', '-metric', 'AE', reference, implementation, 'null:'], { encoding: 'utf8' });
    assert.equal(comparison.status, 0, name + ': Layout weicht vom geprüften Entwurf ab. ' + comparison.stderr);
  } finally { await design.close(); }
}

async function submit(page, value) {
  await page.getByRole('textbox', { name: 'Nachricht' }).fill(value);
  await page.getByRole('button', { name: 'Nachricht senden' }).click();
}

async function start(page) {
  await page.goto(base);
  await page.getByRole('heading', { name: 'Was möchtest du heute machen?' }).waitFor();
}

async function selectToolOptions(page, name) {
  await page.getByRole('button', { name: 'Werkzeugoptionen', exact: true }).click();
  await page.getByRole('button', { name, exact: true }).click();
}

async function verifyImage(page) {
  const url = process.env.CREATIVE_STUDIO_TEST_IMAGE_CHAT;
  if (url) {
    await page.goto(new URL(url, base).href);
  } else {
    await start(page);
    await selectToolOptions(page, 'Bildoptionen');
    await page.getByLabel('Auflösung').selectOption('512x512');
    await page.getByRole('button', { name: 'Übernehmen' }).click();
    const accepted = page.waitForResponse(r => r.url().endsWith('/api/chat/dispatch') && r.status() === 202);
    await submit(page, 'Erstelle ein Bild von einer kleinen grünen Fähre im Morgennebel als Buchumschlag.');
    assert.ok((await (await accepted).json()).id);
  }
  const enlarge = page.getByRole('button', { name: 'Bild vergrößern' }).first();
  await enlarge.waitFor({ timeout: 360_000 });
  const image = page.locator('.job-card img').first();
  await image.evaluate(node => node.decode());
  assert.ok(await image.evaluate(node => node.naturalWidth > 0));
  await enlarge.click();
  await page.getByRole('dialog', { name: 'Bildvorschau' }).waitFor();
  await page.locator('.large-image').evaluate(node => node.decode());
  await axeCheck(page);
  await capture(page, 'live-bild');
  await page.keyboard.press('Escape');
  await page.reload();
  await enlarge.waitFor();
  imageChat = new URL(page.url()).hash;
  console.log('✓ Bildauftrag, persistentes Bild, Großansicht und Wiederöffnen');
}

async function verifyStory(page) {
  await start(page);
  const ready = page.waitForResponse(r => r.url().endsWith('/api/chat') && r.status() === 200, { timeout });
  await submit(page, 'Antworte bitte in einem Satz: Was kann ich heute schreiben?');
  await ready;
  await page.locator('.message.assistant .prose').first().waitFor({ timeout });
  await expect(page.getByRole('button', { name: 'Nachricht senden' })).toBeVisible({ timeout });
  assert.ok((await page.locator('.message.assistant .prose').first().innerText()).trim().length > 5);
  console.log('✓ Sofortiger Chat mit echter llama.cpp-Antwort');

  await start(page);
  await submit(page, 'Ich möchte einen neuen Fantasyroman namens „Die Nachtfähre“ schreiben. Eine Fährfrau begegnet mitten in der Nacht einem stummen Fahrgast. Schreibe einen kurzen Auftakt.');
  await page.getByRole('button', { name: 'Entwurf öffnen', exact: true }).waitFor({ timeout });
  const chatHash = new URL(page.url()).hash;
  await page.getByRole('button', { name: 'Entwurf öffnen', exact: true }).click();
  const editor = page.getByRole('textbox', { name: 'Dokumenttext in Markdown' });
  await editor.waitFor();
  const initial = await editor.inputValue();
  assert.ok(initial.trim().length > 30);
  await editor.fill(initial + '\n\nAm Kai sang der Wind.');
  await page.getByRole('button', { name: 'Vorschau', exact: true }).click();
  await page.getByText('Am Kai sang der Wind.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Speichern', exact: true }).click();
  await page.getByText('Dokument gespeichert.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Versionen', exact: true }).click();
  await page.getByRole('button', { name: /Version 1/ }).click();
  await page.getByRole('button', { name: 'Als neue Version wiederherstellen' }).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Text prüfen' }).click();
  await page.getByRole('dialog', { name: 'Human Writing Audit' }).waitFor({ timeout });
  await expect(page.getByRole('dialog', { name: 'Human Writing Audit' })).toContainText(/Automatische Linter-Funde/);
  await axeCheck(page);
  await page.keyboard.press('Escape');
  await capture(page, 'live-editor-desktop-light');

  await page.getByRole('button', { name: 'Markdown bearbeiten' }).click();
  const beforeRewrite = await editor.inputValue();
  const excerpt = 'Am Kai sang der Wind.';
  const startOfExcerpt = beforeRewrite.indexOf(excerpt);
  assert.ok(startOfExcerpt >= 0);
  await editor.focus();
  await editor.evaluate((field, range) => field.setSelectionRange(...range), [startOfExcerpt, startOfExcerpt + excerpt.length]);
  await page.getByRole('button', { name: 'Text verbessern' }).click();
  const rewrite = page.getByRole('dialog', { name: 'Text verbessern' });
  await rewrite.getByRole('textbox').fill('Schreibe diesen einen Satz schlichter und konkreter.');
  await rewrite.getByRole('button', { name: 'Vorschlag erstellen' }).click();
  await page.getByRole('dialog', { name: 'Vorher und nachher' }).waitFor({ timeout });
  await expect(editor).toHaveValue(beforeRewrite);
  await page.getByRole('button', { name: 'Vorschlag verwerfen', exact: true }).click();
  await expect(editor).toHaveValue(beforeRewrite);

  await page.goto(new URL(chatHash, base).href);
  await page.getByRole('button', { name: 'Entwurf öffnen' }).click();
  await expect(editor).toHaveValue(/Am Kai sang der Wind\./);
  await page.getByRole('heading', { name: 'Die Nachtfähre', exact: true, level: 1 }).waitFor();
  await page.locator('main').getByRole('button', { name: 'Aktionen für Die Nachtfähre', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Umbenennen', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Name').fill('Die Nachtfähre am Kai');
  await page.getByRole('dialog').getByRole('button', { name: 'Speichern', exact: true }).click();
  await page.getByRole('heading', { name: 'Die Nachtfähre am Kai', exact: true, level: 1 }).waitFor();
  console.log('✓ Geschichte per natürlicher Sprache, Editor, Vorschau, Speicherung, Version, Human Writing Audit, Wiederöffnen und Umbenennen');
}

async function verifyArticle(page) {
  await start(page);
  await submit(page, 'Schreibe einen Artikel namens „Salzwiesen und Küstenschutz“. Er soll die Bedeutung von Pflanzen einfach erklären und unter 250 Wörter lang sein.');
  await page.getByRole('button', { name: 'Entwurf öffnen' }).click({ timeout });
  await page.getByRole('textbox', { name: 'Dokumenttext in Markdown' }).waitFor();
  const download = page.waitForEvent('download', { timeout: 30_000 });
  await submit(page, 'Exportiere den Artikel als Astro MDX.');
  const file = await download;
  assert.match(file.suggestedFilename(), /\.mdx$/);
  assert.match(await readFile(await file.path(), 'utf8'), /^---\ntitle: "[\s\S]+\n---\n\n\S/);
  await page.getByRole('button', { name: 'Exportieren' }).click();
  const downloadMd = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: 'Markdown', exact: true }).click();
  assert.match((await downloadMd).suggestedFilename(), /\.md$/);
  console.log('✓ Artikel erstellt, Astro-MDX aus Chat und Markdown aus dem Editor heruntergeladen');
}

async function verifyGame(page) {
  await start(page);
  await submit(page, 'Lass uns eine Spielidee für Godot namens „Moosmaschinen“ entwickeln. Im Wald reparieren kleine Roboter alte Pumpen.');
  await page.locator('.message.assistant .prose').first().waitFor({ timeout });
  await expect(page.getByRole('button', { name: 'Nachricht senden' })).toBeVisible({ timeout });
  await page.getByRole('button', { name: 'Creative Partner' }).click();
  await page.getByRole('button', { name: 'Critical Designer' }).click();
  await submit(page, 'Merke die Entscheidung: Reparieren verändert die Pflanzenwelt.');
  await page.getByText('Die Entscheidung steht im Decision Log.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Inhalte', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Decision Log', exact: true }).click();
  await page.getByText('Reparieren verändert die Pflanzenwelt.', { exact: true }).waitFor();
  await page.getByText('Beschlossen', { exact: true }).waitFor();
  await page.keyboard.press('Escape');
  await page.reload();
  await page.getByRole('heading', { name: 'Moosmaschinen', exact: true, level: 1 }).waitFor();
  await page.getByRole('button', { name: 'Inhalte', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Decision Log', exact: true }).click();
  await page.getByText('Reparieren verändert die Pflanzenwelt.', { exact: true }).waitFor();
  console.log('✓ Spielidee mit echter Modellantwort, Rollenwahl, Decision Log und Persistenz');
}

async function verifyResearch(page) {
  await start(page);
  await selectToolOptions(page, 'Rechercheoptionen');
  await page.getByLabel('Tiefe', { exact: true }).selectOption('quick');
  await page.getByRole('button', { name: 'Übernehmen' }).click();
  await submit(page, 'Recherchiere ausführlich: Warum ist das Wattenmeer UNESCO-Weltnaturerbe?');
  await page.getByRole('button', { name: 'Pausieren' }).click({ timeout: 30_000 });
  await page.getByText('Recherche pausiert', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Fortsetzen' }).click();
  await page.getByText('Dossier fertig', { exact: true }).waitFor({ timeout: 360_000 });
  await page.getByText(/Quellen \(\d+\)/).click();
  assert.ok(await page.locator('.job-card a').count() > 0);
  await capture(page, 'live-recherche');
  await page.getByRole('button', { name: 'Dossier öffnen' }).click();
  const body = await page.getByRole('textbox', { name: 'Dokumenttext in Markdown' }).inputValue();
  assert.ok(body.trim().length > 100);
  console.log('✓ Deep Research mit Pause, Fortsetzen, echten Quellen und gespeichertem Dossier');
}

async function verifyLayouts() {
  for (const [name, viewport] of Object.entries(views)) {
    for (const colorScheme of ['light', 'dark']) {
      const page = await browser.newPage({ viewport, colorScheme, reducedMotion: 'reduce' });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await start(page);
      assert.equal(await page.locator('.suggestion').count(), 4);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await axeCheck(page);
      if (name !== 'reflow') {
        await capture(page, 'live-' + name + '-' + colorScheme);
        await compareDesign(page, name + '-' + colorScheme, viewport, colorScheme);
      }
      await page.keyboard.press('Tab');
      assert.equal(await page.locator(':focus').textContent(), 'Zum Inhalt springen');
      await page.keyboard.press('Enter');
      assert.equal(await page.locator(':focus').getAttribute('id'), 'main');
      if (name === 'mobil') {
        const toggle = page.getByRole('button', { name: 'Seitenleiste öffnen' });
        await toggle.focus();
        await page.keyboard.press('Enter');
        await page.getByRole('dialog', { name: 'Seitenleiste' }).waitFor();
        await page.keyboard.press('Escape');
        assert.equal(await toggle.evaluate(el => el === document.activeElement), true);
      }
      assert.deepEqual(errors, []);
      await page.close();
    }
  }
  console.log('✓ Desktop, Tablet, Mobil, 320-Pixel-Reflow, Hell/Dunkel und Tastatur');
}

async function verifyRegressions(page) {
  await start(page);
  let started;
  const requested = new Promise(resolve => { started = resolve; });
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/sessions?*', async intercepted => {
    started();
    await gate;
    await intercepted.continue();
  });
  await page.evaluate(() => { location.hash = '#stories'; });
  await requested;
  await page.evaluate(() => { location.hash = '#research'; });
  await page.getByRole('heading', { name: 'Was möchtest du heute machen?' }).waitFor();
  release();
  await expect(page.getByRole('textbox', { name: 'Nachricht' })).toHaveValue(/Recherchiere ausführlich/);
  await page.unroute('**/api/sessions?*');
  await page.getByRole('button', { name: 'Bibliothek', exact: true }).click();
  await page.getByRole('link', { name: 'Bilder', exact: true }).click();
  const first = page.locator('#library-content .image-button img');
  await first.first().waitFor();
  const count = await first.count();
  assert.ok(count > 0);
  if (count === 60) {
    const more = page.getByRole('button', { name: 'Weitere Bilder laden' });
    const fetched = page.waitForResponse(r => new URL(r.url()).pathname === '/api/images/gallery'
      && new URL(r.url()).searchParams.get('offset') === '60');
    await more.click();
    const second = await (await fetched).json();
    await expect(first).toHaveCount(count + second.images.length);
    const urls = await first.evaluateAll(images => images.map(image => image.getAttribute('src')));
    assert.equal(urls.length, new Set(urls).size);
  }
  await first.first().evaluate(node => node.decode());
  console.log('✓ Verspätete Navigation, persistente Galerie und Folgeseiten');
}

async function verifyAssetActions(page) {
  assert.ok(imageChat, 'The image workflow needs a completed image in a Studio chat.');
  await page.goto(new URL(imageChat, base).href);
  const card = page.locator('.job-card').filter({ has: page.getByRole('button', { name: 'Bild vergrößern' }) }).first();
  const source = await card.locator('img').getAttribute('src');
  const sid = new URL(page.url()).hash.split('/')[1];
  await card.getByRole('button', { name: 'Zum Chat hinzufügen' }).click();
  await page.getByText('Bild im Chat gespeichert.', { exact: true }).first().waitFor();
  const list = await (await page.request.get(new URL('/api/sessions', base).href)).json();
  const imageSession = await (await page.request.get(new URL('/api/sessions/' + sid, base).href)).json();
  const links = await (await page.request.get(new URL('/api/projects/' + imageSession.project_id + '/memories', base).href)).json();
  assert.ok(links.some(link => link.kind === 'image' && link.key === source.split('/').at(-1)));
  const target = list.find(item => item.title === 'Die Nachtfähre am Kai');
  const stored = await (await page.request.get(new URL('/api/projects/' + target.project_id, base).href)).json();
  await card.getByRole('button', { name: 'In Dokument einfügen' }).click();
  await page.getByLabel('Dokument', { exact: true }).selectOption(stored.documents[0].id);
  await page.getByRole('button', { name: 'Einfügen', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Dokumenttext in Markdown' })).toHaveValue(new RegExp(source));
  await page.getByRole('button', { name: 'Speichern', exact: true }).click();
  await page.getByText('Dokument gespeichert.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Exportieren' }).click();
  const pending = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('button', { name: 'Astro MDX' }).click();
  const archive = await pending;
  assert.match(archive.suggestedFilename(), /\.zip$/);
  const contents = spawnSync('unzip', ['-Z1', await archive.path()], { encoding: 'utf8' });
  assert.equal(contents.status, 0, contents.stderr);
  assert.match(contents.stdout, /\/index\.mdx\n/);
  assert.match(contents.stdout, /\/images\/[0-9a-f]{32}\.png\n/);
  console.log('✓ Bild im Chat gespeichert, in Markdown eingefügt und gemeinsam mit MDX exportiert');
}

const page = await browser.newPage({ viewport: views.desktop, colorScheme: 'light', acceptDownloads: true });
const failures = [];
page.on('pageerror', error => failures.push(error.message));
page.on('response', response => { if (response.status() >= 400) failures.push(response.status() + ' ' + new URL(response.url()).pathname); });
const checks = { image: verifyImage, story: verifyStory, article: verifyArticle, game: verifyGame, research: verifyResearch, layout: verifyLayouts, regression: verifyRegressions, assets: verifyAssetActions };
try {
  for (const check of (process.env.CREATIVE_STUDIO_TEST_FLOWS ?? Object.keys(checks).join(',')).split(',')) {
    if (!checks[check]) throw new Error('Unknown flow ' + check);
    await checks[check](page);
  }
  assert.deepEqual(failures, []);
} catch (error) {
  console.error('Browser-Fehler', failures);
  await capture(page, 'live-journey-error').catch(() => {});
  throw error;
} finally {
  await browser.close();
}
