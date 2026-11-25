import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { firefox, expect } = require('playwright/test');
const axe = require.resolve('axe-core/axe.min.js');
const { CREATIVE_STUDIO_TEST_URL: base, CREATIVE_STUDIO_EDITORIAL_PHASE: phase,
  CREATIVE_STUDIO_TEST_OUTPUT: directory } = process.env;
if (!base || !['run', 'reopen', 'partial', 'chat', 'unavailable'].includes(phase)) {
  throw new Error('Set CREATIVE_STUDIO_TEST_URL to the isolated copy and CREATIVE_STUDIO_EDITORIAL_PHASE to run, reopen, chat, partial or unavailable.');
}
const output = directory ?? 'output/playwright/creative-studio';
const project = '49ec6f7da7bb4fda8c670faa32d30a6f';
const documentId = '265f60bdab0c489982871b4814f643a5';
const chat = 'f5450658233346528b4fec0e80f093c2';
const image = '828341396ac64d25aee9a399dfd96dba';
const docPath = '/api/documents/' + documentId;
const testsPath = docPath + '/editorial';
const messagesPath = '/api/sessions/' + chat + '/messages';
const imagePath = '/api/images/files/' + image;
const linksPath = '/api/projects/' + project + '/memories';
const timeout = 300_000;
const caseFile = process.env.CREATIVE_STUDIO_TEST_STATE ?? join(output, 'editorial-test-state.json');
const digest = text => createHash('sha256').update(text).digest('hex');

await mkdir(output, { recursive: true });
const browser = await firefox.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const editor = page.getByRole('textbox', { name: 'Dokumenttext in Markdown' });
const dialog = page.getByRole('dialog');
const button = (name, within = page) => within.getByRole('button', { name, exact: true });
const close = () => page.keyboard.press('Escape');
const snapshot = name => page.screenshot({ path: join(output, 'editorial-' + name + '.png'), animations: 'disabled' });

async function get(path) {
  const response = await page.request.get(base + path);
  assert.ok(response.ok(), path + ' returned ' + response.status());
  return response.json();
}

async function auditA11y(name) {
  await page.addScriptTag({ path: axe });
  const results = await page.evaluate(() => window.axe.run({ runOnly: [
    'wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa',
  ] }));
  assert.deepEqual(results.violations.map(issue => [issue.id, issue.nodes.map(node => node.target)]), []);
  console.log(name + ': axe ohne Verstöße (' + results.incomplete.length + ' manuell zu prüfende Regeln).');
}

async function open() {
  await page.goto(base + '/#chat/' + chat + '/' + documentId);
  await editor.waitFor();
}

async function imageHash() {
  const response = await page.request.get(base + imagePath);
  assert.equal(response.headers()['content-type'], 'image/png');
  const png = await response.body();
  assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  return createHash('sha256').update(png).digest('hex');
}

async function runResponse() {
  const response = await page.waitForResponse(r => r.url().endsWith(testsPath) && r.request().method() === 'POST', { timeout });
  assert.equal(response.status(), 201, await response.text());
  return response.json();
}

function evidence(result, model, mode) {
  assert.equal(result.evidence?.model, model);
  assert.equal(result.evidence?.mode, mode);
  assert.equal(result.evidence?.language, 'en');
  assert.ok(result.evidence?.skill_version && result.evidence.skill_version !== 'unknown');
  const refs = result.evidence.rules.map(rule => rule.reference);
  for (const name of ['SKILL.md', 'references/style-en.md', 'references/creative-writing.md']) {
    assert.ok(refs.includes(name), name);
  }
  if (mode === 'rewrite') assert.ok(refs.includes('references/fidelity-rules.md'));
}

async function verifyChat() {
  const received = [];
  const collect = async response => {
    if (response.url().endsWith(testsPath) && response.request().method() === 'POST' && response.status() === 201) {
      received.push(await response.json());
    }
  };
  page.on('response', collect);
  await page.getByRole('textbox', { name: 'Nachricht', exact: true }).fill(
    'Bitte prüfe unsere Geschichte mit meinem Human Writing Skill und schlage eine natürlichere Fassung vor.');
  await button('Nachricht senden').click();
  await expect(dialog.getByRole('heading', { name: 'Vorher und nachher' })).toBeVisible({ timeout });
  await expect.poll(() => received.map(result => result.mode)).toEqual(['audit', 'rewrite']);
  evidence(received[0], 'human-audit', 'audit');
  evidence(received[1], 'human-rewrite', 'rewrite');
  await button('Vorschlag verwerfen', dialog).click();
  await expect(dialog).toBeHidden();
  assert.equal((await get(testsPath + '/' + received[1].id)).state, 'discarded');
  assert.equal((await get(docPath)).version, 3);
  await expect(page.getByText('Ein Überarbeitungsvorschlag liegt zur Freigabe vor.', { exact: true })).toBeVisible();
  const invalid = await page.request.post(base + testsPath, { data: { mode: 'rewrite', version: 3, range: [12, 999999] } });
  assert.equal(invalid.status(), 422);
  assert.equal((await invalid.json()).error, 'editorial_range_invalid');
  console.log('D bestanden: Chat verwendet dieselbe Pipeline, Vorschlag verworfen, fehlerhafte Markierung verständlich abgefangen.');
}

try {
  await open();
  await expect(button('Text prüfen')).toBeVisible();
  await expect(button('Text verbessern')).toBeVisible();

  if (phase === 'unavailable') {
    const before = await get(docPath);
    const auditReady = runResponse();
    await button('Text prüfen').click();
    const audit = await auditReady;
    assert.equal(audit.state, 'partial');
    assert.equal(audit.model_error, 'writing_service_unavailable');
    assert.ok(audit.lint.skill_version);
    await expect(dialog.getByText('Die Modellprüfung war gerade nicht verfügbar.', { exact: true }).first()).toBeVisible();
    await close();
    await button('Text verbessern').click();
    const failureResponse = page.waitForResponse(response => response.url().endsWith(testsPath)
      && response.request().method() === 'POST');
    await button('Vorschlag erstellen', dialog).click();
    assert.equal((await failureResponse).status(), 502);
    await expect(dialog.getByText('Das Schreibmodell oder der Human Writing Skill ist gerade nicht erreichbar.', { exact: true })).toBeVisible();
    assert.deepEqual(await get(docPath), before);
    console.log('Fehlerzustand bestanden: Bei unerreichbarem Router bleiben echte lokale Befunde und das Original erhalten.');
  } else if (phase === 'chat') {
    const current = await get(docPath);
    assert.equal(current.version, 3);
    const prior = await get(docPath + '/versions');
    const revised = await get(docPath + '/versions/' + prior.find(version => version.version === 2).id);
    const audit = (await get(testsPath)).runs.find(run => run.mode === 'audit' && run.base_version === 1);
    assert.ok(audit);
    await verifyChat();
    await writeFile(caseFile, JSON.stringify({ originalHash: digest(current.body), revisedHash: digest(revised.body),
      auditId: audit.id, imageHash: await imageHash() }));
  } else if (phase === 'partial') {
    const runId = process.env.CREATIVE_STUDIO_TEST_PROPOSAL;
    const candidate = await get(testsPath + '/' + runId);
    const before = await get(docPath);
    assert.equal(before.body, candidate.original);
    assert.equal(before.version, candidate.base_version);
    assert.ok(candidate.choices?.length >= 2);
    await button('Prüfverlauf').click();
    await dialog.locator('button[data-value="' + runId + '"]').click();
    await expect(dialog.getByRole('heading', { name: 'Vorher und nachher' })).toBeVisible();
    await dialog.getByText('Einzelne Absätze übernehmen', { exact: true }).click();
    const choices = dialog.getByRole('checkbox');
    assert.equal(await choices.count(), candidate.choices.length);
    for (const field of await choices.all()) await field.uncheck();
    await button('Überarbeitung übernehmen', dialog).click();
    await expect(dialog.getByText('Wähle mindestens einen Absatz aus.', { exact: true })).toBeVisible();
    assert.deepEqual(await get(docPath), before);
    await choices.first().check();
    await button('Überarbeitung übernehmen', dialog).click();
    await expect(dialog).toBeHidden();
    const next = await get(docPath);
    assert.equal(next.version, before.version + 1);
    const [first, second] = candidate.choices;
    assert.ok(next.body.includes(first.after) && next.body.includes(second.before));
    assert.ok(!next.body.includes(second.after));
    const consumed = await get(testsPath + '/' + runId);
    assert.equal(consumed.text, next.body);
    console.log('Absatzauswahl bestanden: Leere Auswahl schützt die alte Fassung, Teilfreigabe speichert nur gewählte Änderungen.');
  } else if (phase === 'reopen') {
    const state = JSON.parse(await readFile(caseFile, 'utf8'));
    const current = await get(docPath);
    assert.equal(current.version, 3);
    assert.equal(digest(current.body), state.originalHash);
    const history = await get(docPath + '/versions');
    assert.deepEqual(history.map(version => version.version), [2, 1]);
    for (const [i, hash] of [state.revisedHash, state.originalHash].entries()) {
      assert.equal(digest((await get(docPath + '/versions/' + history[i].id)).body), hash);
    }
    assert.equal(await imageHash(), state.imageHash);
    assert.ok((await get(testsPath)).runs.some(run => run.id === state.auditId));
    await button('Prüfverlauf').click();
    await expect(dialog.getByText('Textprüfung', { exact: true }).first()).toBeVisible();
    await button('Öffnen', dialog).first().click();
    await expect(dialog.getByRole('heading', { name: 'Vorher und nachher' })).toBeVisible();
    console.log('E bestanden: Fassungen, Bild und Prüfverlauf nach echtem Serverneustart.');
  } else {
    const original = await get(docPath);
    assert.equal(original.title, 'Das letzte Licht');
    assert.equal(original.lang, 'en');
    assert.equal(original.version, 1, 'Use a fresh copy of the existing database.');
    const beforeMessages = await get(messagesPath);
    const beforeProject = await get('/api/projects/' + project);
    const beforeLinks = await get(linksPath);
    assert.ok(beforeLinks.some(link => link.kind === 'document-image' && link.key === documentId + '/' + image));
    const originalImage = await imageHash();
    await expect(editor).toHaveValue(original.body);
    await expect(page.getByText('Human Writing aktiv', { exact: true })).toBeVisible();
    await page.getByText('Human Writing aktiv', { exact: true }).click();
    await expect(page.getByText(/creative-writing · Skill/)).toBeVisible();
    await page.getByText('Human Writing aktiv', { exact: true }).click();

    await button('Text prüfen').focus();
    await page.keyboard.press('Tab');
    await expect(button('Text verbessern')).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(button('Text prüfen')).toBeFocused();
    const auditReady = runResponse();
    await page.keyboard.press('Enter');
    const audit = await auditReady;
    assert.equal(audit.state, 'completed');
    evidence(audit, 'human-audit', 'audit');
    assert.ok(audit.observations.length >= 2 && audit.strengths.length >= 1, JSON.stringify(audit));
    for (const item of [...audit.observations, ...audit.strengths]) assert.ok(original.body.includes(item.quote));
    await expect(dialog.getByRole('heading', { name: 'Automatische Linter-Funde' })).toBeVisible();
    await expect(dialog.getByRole('heading', { name: 'Redaktionelle Einschätzungen des Modells' })).toBeVisible();
    await expect(dialog.getByRole('heading', { name: 'Gelungene Stellen' })).toBeVisible();
    assert.deepEqual(await get(docPath), original);
    await auditA11y('Audit Desktop');
    await snapshot('audit-desktop');
    const reviewReady = runResponse();
    await button('Story Quality Review', dialog).click();
    const review = await reviewReady;
    assert.equal(review.mode, 'review');
    assert.equal(review.state, 'completed');
    assert.ok(review.observations.length);
    await expect(dialog.getByRole('heading', { name: 'Story Quality Review' })).toBeVisible();
    await close();
    console.log('A bestanden: echte Linter- und Modellprüfung, konkrete Originalstellen, optionale literarische Prüfung, Wortlaut unverändert.');

    await button('Text verbessern').click();
    await dialog.getByLabel('Eigene Anweisung (optional)').fill(
      'Ungefähr 350 englische Wörter. Straffe die erklärende Stelle zu Elaras Einsamkeit und vereinfache überladene Vergleiche bei der Sichtung des Schiffs. Bewahre Elara, die Marella, 1943, die Grundhandlung und die Atmosphäre.');
    const rewriteReady = runResponse();
    await button('Vorschlag erstellen', dialog).click();
    const proposal = await rewriteReady;
    evidence(proposal, 'human-rewrite', 'rewrite');
    assert.equal(proposal.state, 'ready');
    assert.equal(proposal.original, original.body);
    assert.ok(proposal.words >= 315 && proposal.words <= 385, String(proposal.words));
    assert.notEqual(proposal.text, original.body);
    assert.ok(proposal.reasons.length, JSON.stringify(proposal));
    for (const part of ['Elara', '*Marella*', '1943']) assert.ok(proposal.text.includes(part));
    assert.deepEqual(await get(docPath), original);
    await expect(dialog.getByRole('heading', { name: 'Vorher und nachher' })).toBeVisible();
    await expect(dialog.getByRole('heading', { name: 'Warum diese Änderungen vorgeschlagen werden' })).toBeVisible();
    assert.ok(await dialog.locator('.editions ins').count());
    assert.ok(await dialog.locator('.editions del').count());
    await auditA11y('Vergleich Desktop');
    await snapshot('vergleich-desktop');
    for (const [name, viewport] of Object.entries({ tablet: [834, 1112], mobil: [390, 844], reflow: [320, 780] })) {
      await page.setViewportSize({ width: viewport[0], height: viewport[1] });
      assert.ok(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth + 1), name);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), name);
      if (name === 'mobil') await auditA11y('Vergleich Mobil');
      await snapshot('vergleich-' + name);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    console.log('B bestanden: echtes Rewrite, ' + proposal.words + ' englische Wörter, keine Änderung vor Freigabe, Vergleich auf vier Breiten.');

    await button('Überarbeitung übernehmen', dialog).click();
    await expect(editor).toHaveValue(proposal.text);
    const v2 = await get(docPath);
    assert.equal(v2.version, 2);
    assert.equal(v2.version_origin, 'human-writing');
    const v1 = (await get(docPath + '/versions'))[0];
    assert.equal(v1.version, 1);
    assert.equal((await get(docPath + '/versions/' + v1.id)).body, original.body);
    await button('Versionen').click();
    await button('Fassungen vergleichen', dialog).click();
    await expect(dialog.getByRole('heading', { name: 'Versionsvergleich' })).toBeVisible();
    await button('Zur Versionshistorie', dialog).click();
    await dialog.getByRole('button', { name: /^Version 1 ·/ }).click();
    await expect(dialog.getByRole('heading', { name: 'Version 1', exact: true })).toBeVisible();
    await button('Als neue Version wiederherstellen', dialog).click();
    await expect(editor).toHaveValue(original.body);
    assert.equal((await get(docPath)).version, 3);
    const versions = await get(docPath + '/versions');
    assert.deepEqual(versions.map(version => version.version), [2, 1]);
    assert.equal((await get(docPath + '/versions/' + versions[0].id)).body, proposal.text);
    assert.deepEqual(await get(messagesPath), beforeMessages);
    assert.deepEqual((await get('/api/projects/' + project)).meta, beforeProject.meta);
    assert.equal((await get(docPath)).project_id, project);
    assert.deepEqual(await get(linksPath), beforeLinks);
    assert.equal(await imageHash(), originalImage);
    console.log('C bestanden: Freigabe, Vergleich, Wiederherstellung, Original, Projekt, bisheriger Chatverlauf und Bild nachgewiesen.');

    await verifyChat();

    await writeFile(caseFile, JSON.stringify({ originalHash: digest(original.body), revisedHash: digest(proposal.text),
      auditId: audit.id, imageHash: originalImage }));
  }
} finally {
  await browser.close();
}
