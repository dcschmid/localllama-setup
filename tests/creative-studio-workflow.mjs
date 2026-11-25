import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { firefox, expect } = require('playwright/test');
const base = process.env.CREATIVE_STUDIO_TEST_URL;
if (!base) throw new Error('Set CREATIVE_STUDIO_TEST_URL to an isolated Creative Studio instance.');
const report = process.env.CREATIVE_STUDIO_TEST_OUTPUT ?? 'output/playwright/creative-studio';
const input = `Ich möchte mit dir eine neue Mystery-Geschichte entwickeln.

**Titel:** Das letzte Licht

**Handlung:** Eine junge Leuchtturmwärterin lebt allein auf einer abgelegenen Insel in der Ostsee. Eines Nachts entdeckt sie ein unbekanntes Schiff, das seit über 80 Jahren als verschollen gilt.

1. Schreibe eine atmosphärische englische Anfangsszene mit ungefähr 350 Wörtern.
2. Verwende meinen Human Writing Skill.
3. Erstelle anschließend mit meinem lokalen Image AI Service eine passende Illustration im Format 16:9. Stil: düstere, hochwertige Graphic-Novel-Illustration mit dramatischem Mondlicht, stürmischer Ostsee und einem einsamen Leuchtturm.
4. Zeige das fertige Bild direkt hier in unserem Chat an, nicht nur als Dateipfad oder Link.
5. Speichere die Geschichte und das Bild gemeinsam in einem Projekt namens „Das letzte Licht“.`;

await mkdir(report, { recursive: true });
const browser = await firefox.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 }, colorScheme: 'light' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base);
  await page.getByRole('heading', { name: 'Was möchtest du heute machen?' }).waitFor();
  await page.evaluate(() => localStorage.setItem('cs-lang', 'de'));
  const card = page.getByRole('region', { name: 'Kreativauftrag' }).first();
  let id, sessionId;
  const reopen = process.env.CREATIVE_STUDIO_TEST_REOPEN;
  if (reopen) {
    await page.goto(new URL(reopen, base).href);
    id = await card.getAttribute('data-job');
    sessionId = new URL(page.url()).hash.split('/')[1];
  } else {
    const poster = page.waitForResponse(response => response.url().endsWith('/api/chat/dispatch') && response.status() === 202);
    await page.getByRole('textbox', { name: 'Nachricht' }).fill(input);
    await page.getByRole('button', { name: 'Nachricht senden' }).click();
    const response = await poster;
    const dispatcher = response.request().postDataJSON();
    ({ id } = await response.json());
    sessionId = dispatcher.session_id;
    const duplicate = await page.request.post(new URL('/api/chat/dispatch', base).href, { data: dispatcher });
    assert.equal(duplicate.status(), 202);
    assert.equal((await duplicate.json()).id, id);
  }
  const read = async route => (await page.request.get(new URL(route, base).href)).json();
  const taskRoute = '/api/chat/tasks/' + id;
  const initialTask = await read(taskRoute);
  assert.deepEqual(initialTask.requirements, { language: 'en', word_range: [315, 385], image_size: '1024x576', project_name: 'Das letzte Licht' });

  await card.getByText('Text gespeichert', { exact: false }).waitFor({ timeout: 270_000 });
  const withText = await read(taskRoute);
  const finalCheck = withText.steps.writing.diagnostics.at(-1);
  assert.equal(finalCheck.model, 'creative-writing');
  assert.match(finalCheck.skill_version, /^\d+\.\d+\.\d+/);
  assert.ok(finalCheck.rules.some(rule => rule.reference === 'references/creative-writing.md'));
  assert.ok(finalCheck.rules.some(rule => rule.reference === 'references/style-en.md'));
  assert.deepEqual(finalCheck.validation.issues, []);
  assert.equal(finalCheck.validation.language, 'en');
  assert.ok(finalCheck.validation.words >= 315 && finalCheck.validation.words <= 385);
  assert.ok(Number.isInteger(withText.steps.writing.audit.finding_count));
  const doc = await read('/api/documents/' + withText.document_id);
  assert.equal(doc.lang, 'en');
  assert.equal(doc.project_id, withText.project_id);
  await expect(card.locator('[lang=en]')).toContainText(doc.body.split('\n').find(line => line.length > 20).trim().slice(0, 20));
  console.log('Echter englischer Text gespeichert:', finalCheck.validation.words, 'Wörter; Skill', finalCheck.skill_version,
    'Stilbefunde', withText.steps.writing.audit.finding_count);

  await expect.poll(async () => (await read(taskRoute)).image?.id, { timeout: 45_000 }).toMatch(/^[a-f0-9]{32}$/);
  const queued = await read(taskRoute);
  console.log('Persistenter Bildauftrag:', queued.image.id, 'Status:', queued.image.status);
  const rendered = card.getByRole('img');
  await rendered.waitFor({ timeout: 420_000 });
  await rendered.scrollIntoViewIfNeeded();
  assert.deepEqual(await rendered.evaluate(async image => {
    await image.decode();
    return [image.naturalWidth, image.naturalHeight];
  }), [1024, 576]);

  const task = await read(taskRoute);
  await expect(card.getByText('Auftrag abgeschlossen', { exact: true })).toBeVisible();
  assert.equal(task.status, 'completed');
  const job = await read('/api/images/jobs/' + task.image.id);
  assert.equal(job.queued_request.meta.session_id, sessionId);
  assert.equal(job.queued_request.meta.document_id, doc.id);
  assert.equal(job.queued_request.meta.project_id, doc.project_id);
  assert.equal(job.request.size, '1024x576');
  const gallery = await read('/api/images/gallery/' + task.image.image_id);
  assert.equal(gallery.id, task.image.image_id);
  const memories = await read('/api/projects/' + doc.project_id + '/memories');
  assert.ok(memories.some(m => m.kind === 'image' && m.key === gallery.id));
  assert.ok(memories.some(m => m.kind === 'document-image' && m.key === doc.id + '/' + gallery.id));
  const messages = await read('/api/sessions/' + sessionId + '/messages');
  assert.equal(messages.filter(m => m.role === 'user' && m.content === input).length, 1);
  assert.equal(messages.filter(m => m.meta.kind === 'chat-task' && m.meta.job_id === id).length, 1);
  assert.ok(!JSON.stringify(messages).includes('base64,'));
  await page.reload();
  await rendered.scrollIntoViewIfNeeded();
  await rendered.evaluate(image => image.decode());
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path: join(report, 'last-light-workflow.png'), fullPage: true });
  assert.deepEqual(errors, []);
  console.log('✓ Projekt, Archiv-PNG 1024×576 und Bild im gleichen Chat, inklusive Neuladen.');
  console.log('Wiederöffnen:', page.url(), 'Auftrag:', id, 'Bild:', gallery.id);
} finally {
  await browser.close();
}
