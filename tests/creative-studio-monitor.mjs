// Firefox test of the production monitor.
//
//   python3 tests/creative-studio-production.py --serve-fixture 18702
//   CREATIVE_STUDIO_TEST_URL=http://127.0.0.1:18702 node tests/creative-studio-monitor.mjs
//
// Scenario states are served by intercepting the job record of one real, completed fixture production, so every shape
// is the real one. The backend derivation of those states is covered by tests/creative-studio-monitor.py.
// The real job "Donner über Thunderforge" runs in a second block on a private copy of the live database:
//
//   python3 tests/creative-studio-monitor.py --serve-real 18731
//   CREATIVE_STUDIO_REAL_URL=http://127.0.0.1:18731 CREATIVE_STUDIO_REAL_SESSION=<session id> node tests/creative-studio-monitor.mjs
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { firefox, expect } = require('playwright/test');
const base = process.env.CREATIVE_STUDIO_TEST_URL;
const realBase = process.env.CREATIVE_STUDIO_REAL_URL;
const shots = process.env.CREATIVE_STUDIO_MONITOR_SHOTS;
assert(base || realBase, 'Set CREATIVE_STUDIO_TEST_URL (fixture) and/or CREATIVE_STUDIO_REAL_URL');
if (shots) await mkdir(shots, { recursive: true });
const browser = await firefox.launch();
const errors = [];
let passed = 0;
const check = async (name, run) => { await run(); passed += 1; console.log('✓ ' + name); };
const open = async (viewport = { width: 1440, height: 1000 }, colorScheme = 'light') => {
  const context = await browser.newContext({ viewport, colorScheme, acceptDownloads: true });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  return page;
};
const shot = async (page, name) => { if (shots) await page.screenshot({ path: join(shots, name + '.png'), fullPage: true }); };
const now = () => Date.now() / 1000;
const announced = page => page.locator('#announcement');

// ---- scenario builder ---------------------------------------------------------------------------------------
const STEPS = ['generate', 'human_audit', 'story_audit', 'correction', 'final_check', 'image', 'image_check', 'finish'];
const stepsAt = (index, status = 'running') => Object.fromEntries(STEPS.map((step, i) => [step, i < index ? 'done' : i === index ? status : 'pending']));
const health = (level, reason, extra = {}) => ({ level, reason, quiet_for: 3, checks: { worker_alive: true, heartbeat_age: 1, model_active: true, slot_processing: true, tokens: null }, ...extra });

function threeChapters(template, { chapter = 2, phase = 'reviewed', state = 'running', length = null, failure = null, activity = null, h = health('ok', 'recent_progress'),
  status = 'running', error = undefined, detail = undefined, retry = undefined, timeline = [], awaiting = null, stepStatus = 'running', started = now() - 125 } = {}) {
  const job = structuredClone(template);
  const done = job.chapter_results[0];
  const mk = (n, state2, steps, words) => ({ number: n, title: `Kapitel ${n}`, minimum: 900, maximum: 1200, status: state2, words, image: n === 1, steps, corrections: 0 });
  Object.assign(job, { status, kind: 'story', phase, number: chapter, total: 3, error, detail, retry, downloads: undefined, cover: undefined, art_review_pending: false,
    draft_document_id: chapter > 1 ? 'c'.repeat(32) : undefined, manifest: { completed_chapters: 1, expected_chapters: 3, verified_images: 1, required_images: 4 } });
  job.chapter_results = [{ ...done, number: 1, title: 'Vor dem Sturm', words: 1053 }];
  job.monitor = {
    state, awaiting, phase, step_started_at: started, last_saved_at: now() - 30, created_at: now() - 4000, server_time: now(), health: h, activity, timeline,
    title: 'Donner über Thunderforge', language: 'de', planned_chapters: 3, current_chapter: chapter,
    counts: { chapters: { done: chapter - 1, total: 3 }, images: { done: chapter - 1, total: 4 }, exports: { done: 0, total: 3 }, steps: { done: 2 * (chapter - 1), total: 10 } },
    chapters: [mk(1, 'done', stepsAt(8), 1053), mk(2, chapter === 2 ? 'active' : chapter > 2 ? 'done' : 'pending', stepsAt(chapter === 2 ? 3 : 8, chapter === 2 ? stepStatus : 'done'), length?.words ?? null),
      mk(3, chapter === 3 ? 'active' : 'pending', chapter === 3 ? stepsAt(0, stepStatus) : stepsAt(-1), null)],
    length, failure,
  };
  return job;
}
const generating = (tokens, extra = {}) => ({ server_time: now(), known: true, active: true, heartbeat_at: now() - 1, progress_at: now() - 2, progress_kind: 'tokens',
  worker: { alive: true, busy_with: 'x', process_started_at: now() - 9999 }, last_model: null,
  model: { alias: 'creative-writing', role: 'rewrite', started_at: now() - 125, state: 'generating', decoded: tokens, observed: true, progress_at: now() - 2 }, ...extra });
const shortLength = { number: 2, words: 827, minimum: 900, maximum: 1200, state: 'short', missing: 73, excess: 0, version: 2, attempts: 4, failed_attempts: 4, attempt_limit: 2, passes: 2, reasons: {}, in_progress: false };

async function serve(page, jobId, get) {
  await page.route('**/api/production/jobs/' + jobId, route => route.request().method() === 'GET'
    ? route.fulfill({ json: get() }) : route.continue());
  await page.route('**/api/production/jobs/' + jobId + '/events', route => route.abort());   // the polling fallback takes over
}

// ---- a real completed production on the fixture ---------------------------------------------------------------
if (base) {
  const setup = await open();
  const session = await (await setup.request.post(base + '/api/sessions', { data: { title: 'Monitor' } })).json();
  await setup.goto(base + '/#chat/' + session.id);
  await setup.reload();
  await setup.waitForLoadState('networkidle');
  const brief = 'Create an English-language story titled The Quiet Key. One chapter of 38–60 words. Mara and Nera find a lost key.';
  await setup.locator('#prompt').fill(brief);
  await expect(setup.locator('#prompt')).toHaveValue(brief);
  await setup.getByRole('button', { name: 'Nachricht senden', exact: true }).click();
  await expect(setup.getByText('Produktion abgeschlossen', { exact: true })).toBeVisible({ timeout: 60_000 });
  const jobId = await setup.locator('[data-kind=production-job]').getAttribute('data-job');
  const template = await (await setup.request.get(base + '/api/production/jobs/' + jobId)).json();
  assert.ok(template.monitor, 'the backend sends the derived monitor record');
  await setup.context().close();
  const url = base + '/#chat/' + session.id;

  await check('12 completed production shows real images, exports and counters, and the job opens after a reload', async () => {
    const page = await open();
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view).toHaveAttribute('data-production-state', 'completed');
    await expect(view.locator('.prod-status[data-state="completed"]')).toHaveText(/Abgeschlossen/);
    await expect(view.getByText('Produktion abgeschlossen', { exact: true })).toBeVisible();
    await expect(view.getByRole('progressbar', { name: /Gesamtfortschritt: 6 von 6/ })).toBeVisible();
    await expect(view.getByRole('progressbar', { name: /Exporte fertig: 3 von 3/ })).toBeVisible();
    await expect(view.getByRole('progressbar', { name: /Bilder geprüft: 2 von 2/ })).toBeVisible();
    for (const [name, ext] of [['Markdown herunterladen', 'md'], ['MDX herunterladen', 'mdx'], ['ZIP herunterladen', 'zip']]) {
      const link = view.getByRole('link', { name, exact: true });
      const response = await page.request.get(base + await link.getAttribute('href'));
      assert.ok(response.ok(), `${ext} download`);
    }
    const chapter = view.locator('[data-production-chapter="1"]');
    await expect(chapter.getByText('When Mara opened the drawer', { exact: false })).toBeVisible();
    assert.ok(await chapter.getByRole('img').first().evaluate(image => image.complete && image.naturalWidth > 0), 'the chapter image is really loaded');
    await view.getByRole('button', { name: 'Bilder ansehen' }).click();
    await expect(page.getByRole('dialog').getByRole('img').first()).toBeVisible();
    await page.getByRole('dialog').getByRole('button', { name: 'Dialog schließen' }).click();
    await view.getByRole('button', { name: 'Manuskript öffnen' }).click();
    await expect(page.getByRole('dialog').getByRole('navigation', { name: 'Kapitelnavigation' })).toBeVisible();
    await page.getByRole('dialog').getByRole('button', { name: 'Dialog schließen' }).click();
    assert.equal(await view.getByRole('button', { name: 'Fehlgeschlagenen Schritt erneut ausführen' }).count(), 0);
    assert.equal(await view.getByRole('button', { name: 'Pausieren' }).count(), 0);
    await shot(page, 'monitor-completed-desktop-light');
    await page.context().close();
  });

  await check('9 browser refresh restores the running production, its chapters and the activity from the backend', async () => {
    const page = await open();
    let step = 'generate';
    await serve(page, jobId, () => threeChapters(template, { chapter: 2, phase: 'writing', state: 'model_wait', stepStatus: 'running', activity: generating(1800),
      h: health('ok', 'model_generating'), timeline: [{ at: now() - 600, id: '1:finalizing', number: 1, step: 'finalizing', status: 'running', duration: 12, ref: null }] }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.getByText('Wartet auf Modell', { exact: true }).first()).toBeVisible();
    await page.reload();
    await expect(view.getByText('Wartet auf Modell', { exact: true }).first()).toBeVisible();
    await expect(view.locator('[data-production-chapter="1"] > summary')).toContainText('Kapitel 1 – abgeschlossen – 1.053 Wörter – Bild vorhanden');
    await view.getByText('Aktivitätsverlauf', { exact: false }).click();
    await expect(view.getByText('Kapitel 1 finalisiert')).toBeVisible();
    assert.equal(step, 'generate');
    await page.context().close();
  });

  await check('1 running text generation shows the real state, the model request and the received tokens', async () => {
    const page = await open();
    await serve(page, jobId, () => threeChapters(template, { chapter: 2, phase: 'writing', state: 'model_wait', activity: generating(4200), h: health('ok', 'model_generating') }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.locator('.prod-status[data-state="model_wait"]')).toHaveText(/Wartet auf Modell/);
    await expect(view.getByText('Kapitel 2 wird geschrieben')).toBeVisible();
    await expect(view.getByText('Worker erreichbar, Modell generiert')).toBeVisible();
    await expect(view.getByText('4.200 erzeugte Token')).toBeVisible();
    await expect(view.locator('.prod-facts')).toContainText('Letzter Heartbeat');
    await expect(view.locator('.prod-facts')).toContainText('Letzter Fortschritt');
    await expect(view.locator('.prod-facts')).toContainText('neue Token empfangen');
    await expect(view.locator('.prod-facts')).toContainText('Modellanfrage');
    await expect(view.locator('.prod-facts')).toContainText('creative-writing');
    await expect(view.locator('.prod-facts')).toContainText('Bisherige Laufzeit');
    await expect(view.getByRole('button', { name: 'Pausieren' })).toBeVisible();
    assert.equal(await view.getByRole('button', { name: /erneut ausführen/ }).count(), 0, 'no retry while the step runs');
    await expect(view.getByText('Fehlgeschlagen')).toHaveCount(0);
    await page.context().close();
  });

  await check('2 a long prefill phase is neither an error nor a stall', async () => {
    const page = await open();
    const prefill = { ...generating(0), progress_kind: 'model_request', progress_at: now() - 1200, model: { ...generating(0).model, state: 'prefill', started_at: now() - 1200, decoded: 0 } };
    let level = health('ok', 'recent_progress');
    await serve(page, jobId, () => threeChapters(template, { phase: 'reviewed', state: 'correcting', activity: prefill, h: level, length: shortLength }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.getByText('Worker erreichbar, Modell verarbeitet den Prompt')).toBeVisible();
    level = health('quiet', 'verifying', { quiet_for: 1200 });
    await expect(view.getByText('Seit längerer Zeit kein neuer Fortschritt bestätigt. Der Prozessstatus wird überprüft.', { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(view.getByText('Fehlgeschlagen')).toHaveCount(0);
    await expect(view.getByText(/ausgeblieben|nicht erreichbar/)).toHaveCount(0);
    await expect(view.locator('.prod-status[data-state="correcting"]')).toBeVisible();
    await expect(announced(page)).toContainText('kein neuer Fortschritt');
    await page.context().close();
  });

  await check('3 and 4 a missing heartbeat, a quiet model and a proven stall are told apart', async () => {
    const page = await open();
    let level = health('worker_down', 'heartbeat_lost', { quiet_for: null });
    let activity = generating(300, { heartbeat_at: now() - 90 });
    await serve(page, jobId, () => threeChapters(template, { phase: 'writing', state: 'model_wait', activity, h: level }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.getByText('Worker nicht erreichbar')).toBeVisible();
    await expect(view.getByText('Der Heartbeat des Produktions-Workers ist ausgeblieben.')).toBeVisible();
    activity = generating(777, { progress_at: now() - 700, model: { ...generating(777).model, progress_at: now() - 700 } });
    level = health('quiet', 'verifying', { quiet_for: 700 });
    await expect(view.getByText('Worker erreichbar, aber kein neuer Fortschritt')).toBeVisible({ timeout: 10_000 });
    level = health('stalled', 'no_new_tokens', { quiet_for: 2600 });
    await expect(view.getByText('Fortschritt ausgeblieben (geprüft)')).toBeVisible({ timeout: 10_000 });
    await expect(view.getByText('meldet aber seit längerer Zeit keine neuen Token')).toBeVisible();
    await expect(view.locator('.prod-status[data-state="model_wait"]')).toBeVisible();   // the job itself is not declared failed
    await page.context().close();
  });

  await check('5 a model timeout ends in an understandable failure with the saved checkpoint', async () => {
    const page = await open();
    await serve(page, jobId, () => threeChapters(template, { phase: 'writing', state: 'failed', status: 'failed', error: 'production_upstream_unavailable',
      detail: { exception: 'TimeoutError' }, h: { level: 'none', reason: 'failed', quiet_for: null, checks: {} }, stepStatus: 'failed',
      failure: { code: 'production_upstream_unavailable', number: 2, attempts: 0, automatic_retries: 2, exhausted: false, checkpoint: { chapter: 1, words: 1053 } } }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.getByText('Kapitel 2: Die Modellanfrage hat das Zeitlimit überschritten.')).toBeVisible();
    await expect(view.getByText('Der gespeicherte Stand bleibt erhalten.')).toBeVisible();
    await expect(view.getByText('production_upstream_unavailable')).toBeHidden();
    await expect(view.getByRole('button', { name: 'Fehlgeschlagenen Schritt erneut ausführen' })).toBeVisible();
    await page.context().close();
  });

  await check('6 story_length_failed shows stored word counts first and the technical code only in the details', async () => {
    const page = await open();
    await serve(page, jobId, () => threeChapters(template, { state: 'failed', status: 'failed', error: 'story_length_failed', detail: { words: 827 }, length: shortLength, stepStatus: 'failed',
      h: { level: 'none', reason: 'failed', quiet_for: null, checks: {} },
      failure: { code: 'story_length_failed', number: 2, attempts: 2, automatic_retries: 0, exhausted: true, checkpoint: { chapter: 1, words: 1053 } } }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.locator('.prod-status[data-state="failed"]')).toBeVisible();
    await expect(view.getByText('Kapitel 2 konnte die gewünschte Länge nach den automatischen Überarbeitungen nicht erreichen.')).toBeVisible();
    await expect(view.getByText('Kapitel 2: 827 von mindestens 900 Wörtern. Es fehlen 73 Wörter.').first()).toBeVisible();
    await expect(view.getByText(/4 automatische Erweiterungsversuche/)).toBeVisible();
    await expect(view.getByText('wird verbessert')).toHaveCount(0);
    await expect(view.getByText('story_length_failed')).toBeHidden();
    for (const name of ['Fehlgeschlagenen Schritt erneut ausführen', 'Gespeicherten Text öffnen', 'Details anzeigen', 'Abbrechen']) {
      await expect(view.getByRole('button', { name })).toBeVisible();
    }
    await view.getByRole('button', { name: 'Details anzeigen' }).click();
    await expect(view.locator('[data-job-detail="technical-error"] .job-facts')).toContainText('story_length_failed');
    await expect(view.locator('[data-job-detail="technical-error"] .job-facts')).toContainText('Wortzahl');
    // 8 the chapter and image finished before the failure stay visible and openable
    const first = view.locator('[data-production-chapter="1"]');
    await expect(first.locator(':scope > summary')).toContainText('Kapitel 1 – abgeschlossen – 1.053 Wörter – Bild vorhanden');
    await first.locator(':scope > summary').click();
    await expect(first.getByText('When Mara opened the drawer', { exact: false })).toBeVisible();
    assert.ok(await first.getByRole('img').first().evaluate(image => image.complete && image.naturalWidth > 0));
    const second = view.locator('[data-production-chapter="2"]');
    await expect(second.locator(':scope > summary')).toContainText('Kapitel 2 – fehlgeschlagen – 827 Wörter · Ziel 900–1.200');
    await expect(second.locator('[data-step="correction"]')).toContainText('fehlgeschlagen');
    await expect(second.locator('[data-step="generate"]')).toContainText('abgeschlossen');
    await expect(view.locator('[data-production-chapter="3"] > summary')).toContainText('Kapitel 3 – wartet');
    await shot(page, 'monitor-length-failed-desktop-light');
    await page.context().close();
  });

  await check('6 while the studio is still extending the chapter it says so, with the same numbers', async () => {
    const page = await open();
    await serve(page, jobId, () => threeChapters(template, { state: 'correcting', length: { ...shortLength, words: 742, missing: 158, attempts: 1, failed_attempts: 0, passes: 1 }, activity: generating(900),
      h: health('ok', 'model_generating') }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.getByText('Kapitel 2: 742 von mindestens 900 Wörtern. Es fehlen 158 Wörter. Das Studio versucht, die Szene sinnvoll zu erweitern.')).toBeVisible();
    await expect(view.locator('.prod-status[data-state="correcting"]')).toHaveText(/Wird automatisch korrigiert/);
    assert.equal(await view.getByRole('button', { name: /erneut ausführen/ }).count(), 0);
    await page.context().close();
  });

  await check('7 an automatic retry is visible without a retry button, a second job or any request', async () => {
    const page = await open();
    const posts = [];
    page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/api/production/')) posts.push(request.url()); });
    await serve(page, jobId, () => threeChapters(template, { phase: 'writing', state: 'retrying', retry: { attempt: 1, code: 'production_upstream_unavailable' }, activity: null,
      h: health('ok', 'recent_progress'), timeline: [{ at: now() - 300, id: '2:writing', number: 2, step: 'writing', status: 'failed', duration: 600, attempts: 2, ref: 'abc12345/3/production_upstream_unavailable', error: 'production_upstream_unavailable' }] }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.locator('.prod-status[data-state="retrying"]')).toHaveText(/Wird erneut versucht/);
    await expect(view.getByText('Automatischer Wiederholungsversuch 1 von 2.')).toBeVisible();
    assert.equal(await view.getByRole('button', { name: /erneut ausführen|Retry/ }).count(), 0);
    await view.getByText('Aktivitätsverlauf', { exact: false }).click();
    await expect(view.getByText('Kapitel 2: fehlgeschlagen'.replace('Kapitel 2: ', ''), { exact: false }).first()).toBeVisible();
    await expect(view.getByText('abc12345/3/production_upstream_unavailable')).toBeVisible();
    await expect(page.locator('[data-kind=production-job]')).toHaveCount(1);
    assert.deepEqual(posts, []);
    await page.context().close();
  });

  await check('10 a lost network connection never turns into a failed job and recovers by itself', async () => {
    const page = await open();
    let online = true;
    const job = () => threeChapters(template, { phase: 'writing', state: 'model_wait', activity: generating(500), h: health('ok', 'model_generating') });
    await page.route('**/api/production/jobs/' + jobId, route => online ? route.fulfill({ json: job() }) : route.abort('connectionrefused'));
    await page.route('**/api/production/jobs/' + jobId + '/events', route => route.abort());
    const posts = [];
    page.on('request', request => { if (request.method() === 'POST') posts.push(request.url()); });
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.locator('.prod-status[data-state="model_wait"]')).toBeVisible();
    online = false;
    await expect(view.locator('.prod-status[data-state="lost"]')).toHaveText(/Verbindung unterbrochen/, { timeout: 15_000 });
    await expect(view.getByText('Backend-Verbindung unterbrochen')).toBeVisible();
    await expect(view.getByText('läuft dort unabhängig vom Browser weiter')).toBeVisible();
    await expect(view.locator('.prod-status[data-state="model_wait"]')).toBeVisible();   // the last known job state stays
    await expect(view.getByText('Fehlgeschlagen')).toHaveCount(0);
    await expect(announced(page)).toContainText('Verbindung zum Studio unterbrochen');
    await shot(page, 'monitor-connection-lost-desktop-light');
    online = true;
    await expect(view.locator('.prod-status[data-state="lost"]')).toHaveCount(0, { timeout: 15_000 });
    await expect(announced(page)).toContainText('Verbindung zum Studio wiederhergestellt');
    assert.deepEqual(posts.filter(url2 => /cancel|pause|retry/.test(url2)), [], 'a lost connection must not send any job action');
    await page.context().close();
  });

  await check('11 the change from chapter 1 to chapter 2 updates statuses and is announced without a reload', async () => {
    const page = await open();
    let chapter = 1;
    await serve(page, jobId, () => chapter === 1
      ? threeChapters(template, { chapter: 1, phase: 'finalizing', state: 'running', stepStatus: 'running', h: health('ok', 'recent_progress') })
      : threeChapters(template, { chapter: 2, phase: 'writing', state: 'model_wait', stepStatus: 'running', activity: generating(10), h: health('ok', 'model_generating') }));
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.getByText('aktuell Kapitel 1')).toBeVisible();
    chapter = 2;
    await expect(view.getByText('aktuell Kapitel 2')).toBeVisible({ timeout: 10_000 });
    await expect(view.getByRole('progressbar', { name: /Kapitel abgeschlossen: 1 von 3/ })).toBeVisible();
    await expect(view.locator('[data-production-chapter="1"] > summary')).toContainText('abgeschlossen');
    await expect(view.locator('[data-production-chapter="2"] > summary')).toContainText('Kapitel 2 – Schreiben');
    await expect(announced(page)).toContainText('Kapitel 2 gestartet.');
    await page.context().close();
  });

  await check('9 double clicks send one request and never create a second job', async () => {
    const page = await open();
    let retries = 0;
    await serve(page, jobId, () => threeChapters(template, { state: 'failed', status: 'failed', error: 'story_length_failed', length: shortLength, stepStatus: 'failed',
      h: { level: 'none', reason: 'failed', quiet_for: null, checks: {} }, failure: { code: 'story_length_failed', number: 2, attempts: 2, automatic_retries: 0, exhausted: true, checkpoint: { chapter: 1, words: 1053 } } }));
    await page.route('**/api/production/*/retry', async route => { retries += 1; await new Promise(done => setTimeout(done, 700)); await route.fulfill({ status: retries === 1 ? 200 : 409, json: { id: jobId, status: 'queued', error: 'production_transition_invalid' } }); });
    await page.goto(url);
    const view = page.locator('.production-view');
    const retry = view.getByRole('button', { name: 'Fehlgeschlagenen Schritt erneut ausführen' });
    await retry.dblclick();
    await retry.click({ force: true }).catch(() => {});
    await page.waitForTimeout(1200);
    assert.equal(retries, 1, 'exactly one retry request');
    await expect(page.locator('[data-kind=production-job]')).toHaveCount(1);
    await expect(page.locator('#feedback, .feedback')).not.toContainText('production_transition_invalid');
    await page.context().close();
  });

  await check('13 desktop uses the width in two columns, mobile stays in one column without horizontal scrolling', async () => {
    const wide = await open({ width: 1440, height: 1000 });
    await serve(wide, jobId, () => threeChapters(template, { state: 'failed', status: 'failed', error: 'story_length_failed', length: shortLength, stepStatus: 'failed',
      h: { level: 'none', reason: 'failed', quiet_for: null, checks: {} }, failure: { code: 'story_length_failed', number: 2, attempts: 2, automatic_retries: 0, exhausted: true, checkpoint: { chapter: 1, words: 1053 } } }));
    await wide.goto(url);
    await expect(wide.locator('.production-view')).toBeVisible();
    const box = async (page, selector) => page.locator(selector).first().boundingBox();
    const main = await box(wide, '.prod-main'), aside = await box(wide, '.prod-aside'), card = await box(wide, '.job-card');
    assert.ok(card.width > 900, `the production view uses the screen width (${card.width}px)`);
    assert.ok(aside.x >= main.x + main.width - 1 && Math.abs(aside.y - main.y) < 40, 'live activity sits beside the main column');
    await shot(wide, 'monitor-length-failed-desktop-dark');
    await wide.context().close();
    for (const scheme of ['light', 'dark']) {
      const narrow = await open({ width: 390, height: 844 }, scheme);
      await serve(narrow, jobId, () => threeChapters(template, { phase: 'writing', state: 'model_wait', activity: generating(2400), h: health('ok', 'model_generating') }));
      await narrow.goto(url);
      await expect(narrow.locator('.production-view')).toBeVisible();
      const geometry = await narrow.evaluate(() => ({ width: document.documentElement.scrollWidth, inner: innerWidth,
        wide: [...document.querySelectorAll('.production-view *')].filter(node => { const r = node.getBoundingClientRect(); return r.width > 0 && r.right > innerWidth + 1; }).map(node => node.className || node.tagName) }));
      assert.ok(geometry.width <= geometry.inner, `no horizontal scroll (${geometry.width} > ${geometry.inner})`);
      assert.deepEqual(geometry.wide, [], 'nothing is cut off at the right edge');
      const [m2, a2, c2] = [await box(narrow, '.prod-main > .prod-actions'), await box(narrow, '.prod-aside'), await box(narrow, '.prod-chapters')];
      assert.ok(a2.y >= m2.y && c2.y >= a2.y, 'one column: actions, then live activity, then the chapters');
      for (const control of await narrow.locator('.prod-actions button').all()) {
        const r = await control.boundingBox();
        assert.ok(r.x >= 0 && r.x + r.width <= 390 && r.height >= 40, 'actions are reachable and large enough');
      }
      await shot(narrow, `monitor-running-mobile-${scheme}`);
      await narrow.context().close();
    }
  });

  await check('14 keyboard operation, visible focus, names and calm screen reader announcements', async () => {
    const page = await open();
    let tokens = 100;
    let state = 'model_wait';
    await serve(page, jobId, () => { tokens += 40; return threeChapters(template, { phase: 'writing', state, activity: generating(tokens), h: health('ok', 'model_generating'),
      timeline: [{ at: now() - 60, id: '1:finalizing', number: 1, step: 'finalizing', status: 'running', duration: 5, ref: null }] }); });
    let pauses = 0;
    await page.route('**/api/production/*/pause', route => { pauses += 1; route.fulfill({ json: { id: jobId, status: 'paused' } }); });
    await page.goto(url);
    const view = page.locator('.production-view');
    await expect(view.getByRole('progressbar', { name: /Gesamtfortschritt/ })).toBeVisible();
    await expect(view.locator('ol.prod-timeline')).toHaveAttribute('aria-label', 'Aktivitätsverlauf, neueste zuerst');
    await expect(view.getByRole('group', { name: 'Aktionen' })).toBeVisible();
    // the token counter changes at every poll but must not be announced
    const changes = await page.evaluate(() => new Promise(resolve => {
      let count = 0;
      new MutationObserver(list => { count += list.length; }).observe(document.querySelector('#announcement'), { childList: true, characterData: true, subtree: true });
      setTimeout(() => resolve(count), 6000);
    }));
    assert.equal(changes, 0, 'token updates are not announced');
    // keyboard: Tab to the pause button, visible focus ring, activate with the space bar
    const pause = view.getByRole('button', { name: 'Pausieren' });
    await pause.focus();
    assert.notEqual(await pause.evaluate(node => getComputedStyle(node).outlineStyle), 'none', 'visible keyboard focus');
    await page.keyboard.press('Tab');
    await expect(view.getByRole('button', { name: 'Details anzeigen' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(view.locator('[data-job-detail="technical-error"] .job-facts')).toBeVisible();
    await expect(view.locator('[data-job-detail="technical-error"] > summary')).toBeFocused();
    const timeline = view.locator('[data-job-detail="timeline"] > summary');
    await timeline.focus();
    await page.keyboard.press('Enter');
    await expect(view.getByText('Kapitel 1 finalisiert')).toBeVisible();
    await expect(timeline).toBeFocused();   // a card refresh keeps the keyboard position
    await page.waitForTimeout(2200);
    await expect(timeline).toBeFocused();
    await pause.focus();
    await page.keyboard.press('Space');
    await expect.poll(() => pauses).toBe(1);
    // state changes are announced once, with a readable text
    state = 'paused';
    await page.unroute('**/api/production/*/pause');
    await expect(announced(page)).toContainText('Produktion: Pausiert.', { timeout: 10_000 });
    await page.context().close();
  });

  await check('14 axe finds no WCAG 2.2 AA violation in the production view (light and dark, running and failed)', async () => {
    const axe = await readFile(require.resolve('axe-core/axe.min.js'), 'utf8');
    for (const scheme of ['light', 'dark']) {
      for (const failed of [false, true]) {
        const page = await open({ width: 1280, height: 900 }, scheme);
        await page.addInitScript(`localStorage.setItem('studio-theme', '${scheme}')`);
        await serve(page, jobId, () => failed
          ? threeChapters(template, { state: 'failed', status: 'failed', error: 'story_length_failed', length: shortLength, stepStatus: 'failed',
            h: { level: 'none', reason: 'failed', quiet_for: null, checks: {} }, failure: { code: 'story_length_failed', number: 2, attempts: 2, automatic_retries: 0, exhausted: true, checkpoint: { chapter: 1, words: 1053 } } })
          : threeChapters(template, { phase: 'writing', state: 'model_wait', activity: generating(2400), h: health('quiet', 'verifying', { quiet_for: 900 }) }));
        await page.goto(url);
        await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, scheme);
        await expect(page.locator('.production-view')).toBeVisible();
        await page.locator('.production-view [data-job-detail="timeline"] > summary').click();
        await page.locator('.production-view [data-production-chapter="1"] > summary').click();
        await page.addScriptTag({ content: axe });
        const result = await page.evaluate(() => globalThis.axe.run(document.querySelector('.job-card'), { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } }));
        assert.deepEqual(result.violations.map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).join(' | ')}`), [], `${scheme}/${failed ? 'failed' : 'running'}`);
        await page.context().close();
      }
    }
  });

  await check('15 reduced motion: the view contains no animation or transition', async () => {
    const context = await browser.newContext({ reducedMotion: 'reduce' });
    const page = await context.newPage();
    await serve(page, jobId, () => threeChapters(template, { phase: 'writing', state: 'model_wait', activity: generating(2400), h: health('ok', 'model_generating') }));
    await page.goto(url);
    await expect(page.locator('.production-view')).toBeVisible();
    const moving = await page.evaluate(() => [...document.querySelectorAll('.production-view, .production-view *')]
      .filter(node => { const s = getComputedStyle(node); return (s.animationName !== 'none' && parseFloat(s.animationDuration) > 0) || parseFloat(s.transitionDuration) > 0; }).length);
    assert.equal(moving, 0);
    await context.close();
  });

  await check('live event stream: the real server pushes the job and heartbeats, and the card follows it', async () => {
    const page = await open();
    const frames = [];
    await page.exposeFunction('seen', name => frames.push(name));
    await page.addInitScript(({ id }) => {
      const Original = window.EventSource;
      window.EventSource = class extends Original {
        constructor(address) { super(address); for (const name of ['job', 'heartbeat', 'end']) this.addEventListener(name, () => window.seen(name)); }
      };
    }, { id: jobId });
    await page.goto(url);
    await expect(page.locator('.production-view')).toHaveAttribute('data-production-state', 'completed');
    await expect.poll(() => frames.includes('job'), { timeout: 15_000 }).toBeTruthy();
    await expect.poll(() => frames.includes('end'), { timeout: 15_000 }).toBeTruthy();
    const stream = await page.request.get(base + '/api/production/jobs/' + jobId + '/events', { timeout: 15_000 });
    assert.match(await stream.text(), /event: job\ndata: \{/);
    await page.context().close();
  });
}

// ---- the real job "Donner über Thunderforge", read from a private copy of the live database ---------------------------
if (realBase) {
  await check('real job: Donner über Thunderforge shows one consistent failed state with the stored numbers', async () => {
    const session = process.env.CREATIVE_STUDIO_REAL_SESSION;
    assert(session, 'CREATIVE_STUDIO_REAL_SESSION');
    const before = await (await fetch(realBase + '/api/production/jobs/71410090bf0448529c3987c87f37cb63')).json();
    for (const [scheme, viewport] of [['dark', { width: 1440, height: 1000 }], ['light', { width: 390, height: 900 }]]) {
      const page = await open(viewport, scheme);
      await page.goto(realBase + '/#chat/' + session);
      const view = page.locator('.production-view');
      await expect(view).toHaveAttribute('data-production-state', 'failed');
      await expect(view.getByRole('heading', { name: 'Donner über Thunderforge' })).toBeVisible();
      await expect(view.getByText('Deutsch · 3 Kapitel geplant · aktuell Kapitel 2')).toBeVisible();
      await expect(view.locator('.prod-status[data-state="failed"]')).toHaveText(/Fehlgeschlagen/);
      await expect(view.getByText('Kapitel 2: 827 von mindestens 900 Wörtern. Es fehlen 73 Wörter.').first()).toBeVisible();
      await expect(view.getByText('Kapitel 2 wird verbessert')).toHaveCount(0);
      await expect(view.locator('.prod-main').getByText('story_length_failed')).toHaveCount(0);
      await expect(view.getByRole('progressbar', { name: /Kapitel abgeschlossen: 1 von 3/ })).toBeVisible();
      await expect(view.getByRole('progressbar', { name: /Bilder geprüft: 1 von 4/ })).toBeVisible();
      await expect(view.getByRole('button', { name: 'Fehlgeschlagenen Schritt erneut ausführen' })).toBeVisible();
      await expect(view.getByRole('button', { name: 'Gespeicherten Text öffnen' })).toBeVisible();
      await expect(view.getByRole('button', { name: 'Pausieren' })).toHaveCount(0);
      await expect(page.getByText('Story-Produktion', { exact: true }).first()).toBeVisible();
      const first = view.locator('[data-production-chapter="1"]');
      await expect(first.locator(':scope > summary')).toContainText('Kapitel 1 – abgeschlossen – 1.053 Wörter – Bild vorhanden');
      await first.locator(':scope > summary').click();
      await expect.poll(() => first.getByRole('img').first().evaluate(image => image.complete && image.naturalWidth > 0), { message: 'the real chapter image loads' }).toBe(true);
      await view.getByText('Aktivitätsverlauf', { exact: false }).click();
      await expect(view.locator('.prod-timeline li').first()).toContainText('Wortzahlprüfung fehlgeschlagen');
      await expect(view.locator('.prod-timeline code').filter({ hasText: '71410090/' }).first()).toBeVisible();
      await page.reload();
      await expect(view).toHaveAttribute('data-production-state', 'failed');
      await shot(page, `real-job-${scheme}-${viewport.width}`);
      await page.context().close();
    }
    const after = await (await fetch(realBase + '/api/production/jobs/71410090bf0448529c3987c87f37cb63')).json();
    assert.equal(after.monitor.state, before.monitor.state, 'viewing the job changes nothing');
  });
}

await browser.close();
assert.deepEqual(errors, []);
console.log(`Firefox production monitor: ${passed} checks passed.`);
