import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';

const { firefox, expect } = createRequire(import.meta.url)('playwright/test');
const base = process.env.CREATIVE_STUDIO_TEST_URL;
assert(base, 'Use a separate Studio fixture URL');
const browser = await firefox.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));

async function api(path, data, status) {
  const response = data === undefined ? await page.request.get(base + '/api' + path)
    : await page.request.post(base + '/api' + path, { data });
  const result = await response.json();
  if (status !== undefined) assert.equal(response.status(), status, JSON.stringify(result));
  else assert(response.ok(), JSON.stringify(result));
  return result;
}

async function project(name, kind = 'story') {
  const { id: pid } = await api('/projects', { name, kind, lang: 'de' });
  const { id: sid } = await api('/sessions', { title: name, project_id: pid });
  return { pid, sid, plan: '/production/' + pid, messages: '/sessions/' + sid + '/messages' };
}

const input = text => ({ text, mode: 'auto', default_lang: 'de', workflow: 'chat', request_id: randomUUID().replaceAll('-', '') });
const dispatch = (context, text) => api('/chat/dispatch', { ...input(text), session_id: context.sid });
const inspect = id => api('/production/jobs/' + id);
async function jobDone(id) {
  await expect.poll(async () => (await inspect(id)).status, { timeout: 20_000 }).toBe('completed');
  return inspect(id);
}
async function send(text) {
  await expect(page.getByRole('button', { name: 'Nachricht senden', exact: true })).toBeVisible();
  const composer = page.getByRole('textbox', { name: 'Nachricht', exact: true });
  await composer.fill(text);
  await expect(composer).toHaveValue(text);
  try {
    const [response] = await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/api/chat/dispatch'), { timeout: 10_000 }),
      composer.press('Enter'),
    ]);
    return response.json();
  } catch (error) {
    throw new Error(`Chat submission failed for ${JSON.stringify(text)}\n${await page.locator('main').ariaSnapshot()}`, { cause: error });
  }
}

try {
  const ctx = await project('The Archive at Dusk');
  const example = JSON.parse(execFileSync('python3', ['-c', `
import json, runpy
fixture = runpy.run_path("tests/creative-studio-production.py")
print(json.dumps(fixture["example_plan"]()))
`], { encoding: 'utf8' }));
  const outline = { ...example, language: 'de', chapters: Array.from({ length: 8 }, (_, index) =>
    ({ ...example.chapters[0], number: index + 1, title: 'Drawer ' + (index + 1), beats: 'Mara finds record ' + (index + 1) + '.' })) };
  await api(ctx.plan + '/save-plan', { session_id: ctx.sid, plan: outline });
  await api(ctx.plan + '/start', { session_id: ctx.sid, version: 1, mode: 'automatic' }, 409);
  await page.goto(base + '/#chat/' + ctx.sid);
  await expect(page.getByRole('heading', { name: 'The Archive at Dusk' })).toBeVisible();

  // A – A dedicated audit receives all eight planned chapters while the manuscript is empty.
  const routed = await send('Prüfe unsere vollständige Planung auf Widersprüche.');
  const audit = await jobDone(routed.id);
  assert.deepEqual(audit.compared_chapters, [1, 2, 3, 4, 5, 6, 7, 8]);
  assert.equal(audit.planning_findings.length, 1);
  assert.equal(audit.plan_version, 2);
  await expect(page.getByText('Verglichene Kapitel · 1, 2, 3, 4, 5, 6, 7, 8')).toBeVisible();
  await expect(page.getByText('Nenne die Herkunft des Schlüssels.')).toBeVisible();
  assert.deepEqual((await api('/stories/' + ctx.pid)).chapters, []);

  // B – A targeted revision creates a separate draft and preserves other chapter plans.
  const revised = await jobDone((await send('Verbessere Kapitel 4 unserer Planung und überprüfe die Folgen für Kapitel 7.')).id);
  assert.equal(revised.plan_version, 3);
  const before = await api(ctx.plan + '?version=2');
  const current = await api(ctx.plan);
  assert.equal(current.approved, false);
  assert.equal(current.plan.chapters[3].continuity, 'Mara gibt Nera den Schlüssel.');
  assert.deepEqual(current.plan.chapters.filter(c => c.number !== 4), before.plan.chapters.filter(c => c.number !== 4));
  await page.locator('[data-job="' + revised.id + '"]').getByRole('button', { name: 'Planentwurf öffnen' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText(/Version 3\s*·\s*Entwurf/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Dialog schließen' }).click();

  // C – Conversation about the ending is read-only.
  const discussion = await jobDone((await send('Findest du das Ende unserer Geschichte überzeugend?')).id);
  assert.equal(discussion.answer, 'Das Ende löst Maras Suche ein.');
  await expect(page.getByText(discussion.answer)).toBeVisible();
  assert.equal((await api(ctx.plan)).version, 3);

  // D – Explicit grammar checking receives the actual chapter, through the editor.
  await api(ctx.plan + '/approve-plan', { version: 3, accept_impact: true });
  const chapter = await api('/stories/' + ctx.pid + '/plan', { title: 'Drawer 1', plan: 'Mara opens the drawer.' });
  await api('/documents/' + chapter.id, { version: 1, body: 'Mara look at the key. Then she left.' });
  const written = await api('/documents/' + chapter.id);
  const editorial = await send('Prüfe Kapitel 1 auf grammatische Fehler.');
  assert.equal(editorial.editorial.id, chapter.id);
  assert.equal(editorial.editorial.mode, 'audit');
  await expect(page.getByRole('textbox', { name: 'Dokumenttext in Markdown' })).toHaveValue(written.body);
  await expect(page.getByRole('button', { name: 'Prüfbericht öffnen' })).toBeVisible();
  await page.goto(base + '/#chat/' + ctx.sid);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'The Archive at Dusk' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Dokumenttext in Markdown' })).toBeHidden();

  // E – An explicitly requested, unwritten chapter offers generation without starting it.
  const missing = await send('Überarbeite den geschriebenen Text von Kapitel 5.');
  assert.equal(missing.missing_text, true);
  assert.equal(missing.chapter_number, 5);
  await expect(page.getByText('Kapitel 5 ist bisher nur geplant.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Kapitel schreiben', exact: true })).toBeVisible();
  assert.equal((await api('/stories/' + ctx.pid)).chapters.length, 1);

  // F – Plan work continues alongside the paused manuscript, which keeps its checkpoint.
  const { id: story } = await api(ctx.plan + '/start', { session_id: ctx.sid, version: 3, mode: 'automatic' });
  await api(ctx.plan + '/pause', { job_id: story });
  const checkpoint = await inspect(story);
  assert.equal(checkpoint.status, 'paused');
  const pauseReview = await jobDone((await send('Prüfe die acht Kapitel auf Widersprüche.')).id);
  assert(pauseReview.plan_version > 3);
  const pauseDiscussion = await jobDone((await send('Ist das Ende noch glaubwürdig?')).id);
  assert.equal(pauseDiscussion.plan_version, undefined);
  assert.deepEqual(await inspect(story), checkpoint);
  assert.equal((await api('/documents/' + chapter.id)).body, written.body);
  assert.equal((await api('/documents/' + chapter.id)).version, written.version);
  await api(ctx.plan + '/resume', { job_id: story, plan_version: pauseReview.plan_version }, 409);
  await api(ctx.plan + '/approve-plan', { version: pauseReview.plan_version }, 409);
  await api(ctx.plan + '/approve-plan', { version: pauseReview.plan_version, accept_impact: true });
  const conflict = await api(ctx.plan + '/resume', { job_id: story, plan_version: pauseReview.plan_version }, 409);
  assert.equal(conflict.error, 'production_plan_checkpoint_conflict');
  assert.deepEqual(await inspect(story), checkpoint);

  // An outline written only in the chat can be audited and is persisted only on explicit request.
  const legacy = await project('The Uncatalogued Ledger', 'custom');
  await api(legacy.messages, { role: 'assistant', content: 'Story-Bibel: Mara ist Archivarin. Kapitel 1: Mara opens the drawer.' });
  const textualAudit = await jobDone((await dispatch(legacy, 'Prüfe unsere Story-Planung auf Widersprüche.')).id);
  assert.equal(textualAudit.planning_findings.length, 0);
  assert.equal((await api(legacy.plan)).plan, null);
  const imported = await jobDone((await dispatch(legacy, 'Übernimm unsere Story-Planung aus dem Chat.')).id);
  assert.equal(imported.plan_version, 1);
  const importedPlan = await api(legacy.plan);
  assert.equal(importedPlan.approved, false);
  assert.equal(importedPlan.plan.chapters.length, 1);
  const free = await project('General discussion', 'custom');
  const generic = await dispatch(free, 'Was hältst du von einer Geschichte über einen Windpark?');
  assert.equal(generic.handled, false);
  assert.equal(generic.activity, 'chat');
  assert.deepEqual(errors, []);
  console.log('Firefox and HTTP API passed planning A–F, transcript audit/import and ordinary chat fallback.');
} finally {
  await browser.close();
}
