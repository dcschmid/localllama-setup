import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { firefox, expect } = require('playwright/test');
const base = process.env.CREATIVE_STUDIO_TEST_URL;
assert(base, 'Use a separate Studio fixture URL');
const browser = await firefox.launch();
const output = await mkdtemp(join(tmpdir(), 'production-browser-'));
const page = await browser.newPage({ acceptDownloads: true });
const errors = [];
page.on('pageerror', error => errors.push(error.message));

try {
  const response = await page.request.post(base + '/api/projects', { data: { name: 'The Key in the Drawer', kind: 'story', lang: 'en' } });
  assert.equal(response.status(), 201);
  const project = await response.json();
  const session = await page.request.post(base + '/api/sessions', { data: { title: 'The Key in the Drawer', project_id: project.id } });
  const { id } = await session.json();
  await page.goto(base + '/#chat/' + id);
  const simulated = await page.request.post(base + `/api/sessions/${id}/messages`, { data: {
    role: 'assistant', meta: { model: 'research' },
    content: '*(Simuliertes Bild: Low-Poly, 16:9)*\n\n![Bild](/api/images/files/' + 'f'.repeat(32) + ')\n\n[Download Markdown](https://example.invalid/manuscript.md)',
  } });
  assert.ok(simulated.ok(), await simulated.text());
  await page.reload();
  await expect(page.getByText(/keinen belegten Produktionsabschluss/)).toBeVisible();
  await expect(page.locator(`img[src*="${'f'.repeat(32)}"]`)).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Download Markdown' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Story-Planung', exact: true }).click();
  await page.getByLabel('Was soll die Geschichte erzählen?').fill('Mara and Nera find a lost key and recover a record.');
  await page.getByLabel('Sprache', { exact: true }).selectOption('en');
  await page.getByLabel('Kapitel', { exact: true }).fill('1');
  await page.getByText('Wortzahl pro Kapitel').click();
  await page.getByLabel('Mindestens', { exact: true }).fill('38');
  await page.getByLabel('Höchstens', { exact: true }).fill('60');
  await page.getByRole('button', { name: 'Planung erstellen' }).click();
  await page.getByRole('button', { name: 'Planung öffnen' }).click({ timeout: 20_000 });
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Planung freigeben' }).click();
  await dialog.getByRole('button', { name: 'Geschichte vollständig erstellen' }).click();
  await expect(page.getByText('Geschichte fertig', { exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Illustrationen prüfen' }).click();
  await dialog.getByText('Titelbild', { exact: true }).click();
  await expect(dialog.getByRole('img', { name: 'Mara and Nera at the open drawer' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Bildserie freigeben' }).click();
  await expect(page.getByText('Geschichte fertig', { exact: true })).toBeVisible({ timeout: 20_000 });
  const chapter = page.locator('[data-production-chapter="1"]');
  await expect(chapter.getByText('When Mara opened the drawer', { exact: false })).toBeVisible();
  await expect(chapter.getByText(/Fixture claim/)).toBeHidden();
  await chapter.getByText('Prüfdetails', { exact: true }).click();
  await expect(chapter.getByText(/Unbestätigt.*Fixture claim/)).toBeVisible();
  await chapter.getByRole('button', { name: 'Bild vergrößern' }).click();
  await expect(dialog.locator('img')).toBeVisible();
  await dialog.getByRole('button', { name: 'Dialog schließen' }).click();
  await page.getByRole('button', { name: 'Manuskript öffnen' }).click();
  await expect(dialog.getByRole('navigation', { name: 'Kapitelnavigation' })).toBeVisible();
  const downloaded = page.waitForEvent('download');
  await dialog.getByRole('link', { name: 'ZIP herunterladen' }).click();
  for (const fmt of ['MD', 'MDX']) {
    const link = dialog.getByRole('link', { name: fmt + ' herunterladen', exact: true });
    const artifact = await page.request.get(base + await link.getAttribute('href'));
    assert.ok(artifact.ok());
    assert.ok((await artifact.text()).includes('When Mara opened the drawer'));
  }
  const file = join(output, 'manuscript.zip');
  await (await downloaded).saveAs(file);
  const archive = spawnSync('python3', ['-c', `
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    assert z.testzip() is None
    assert len([n for n in z.namelist() if n.endswith('.png')]) == 2
    for ext in ('.md', '.mdx'):
        text = z.read(next(n for n in z.namelist() if n.endswith(ext))).decode()
        assert 'When Mara opened the drawer' in text
        assert all(png in text for png in z.namelist() if png.endswith('.png'))
`, file], { encoding: 'utf-8' });
  assert.equal(archive.status, 0, archive.stderr);
  await dialog.getByRole('button', { name: 'Dialog schließen' }).click();
  const newChat = await page.request.post(base + '/api/sessions', { data: { title: 'Neuer Produktionsauftrag' } });
  const { id: briefChat } = await newChat.json();
  await page.goto(base + '/#chat/' + briefChat);
  await page.locator('#prompt').fill('Ich möchte eine vollständige Geschichte erstellen.\n# Der Salzsteg\nDrei Kapitel, jeweils 900–1.200 Wörter. Exportiere anschließend Markdown und MDX.');
  await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click();
  await expect(page.locator('[data-kind=production-job]')).toBeVisible();
  const afterBrief = await (await page.request.get(base + `/api/sessions/${briefChat}`)).json();
  assert.ok(afterBrief.project_id);
  const briefReport = await (await page.request.get(base + `/api/production/${afterBrief.project_id}/report`)).json();
  assert.equal(briefReport[0].payload.count, 3);
  assert.equal(briefReport[0].payload.minimum, 900);
  assert.equal(briefReport[0].payload.maximum, 1200);
  // A free-wording release must release exactly the stored plan and start one real production.
  const api = async path => (await page.request.get(base + path)).json();
  const planInChat = async title => {
    const chat = await (await page.request.post(base + '/api/sessions', { data: { title } })).json();
    await page.goto(base + '/#chat/' + chat.id);
    await page.locator('#prompt').fill('Ich möchte eine vollständige Geschichte erstellen.\n# Das Glas\nEin Kapitel, 38–60 Wörter. Zeige mir zuerst die Planung.');
    await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click();
    await expect(page.locator('[data-kind=production-job]')).toBeVisible();
    await expect.poll(async () => (await api(`/api/sessions/${chat.id}`)).project_id, { timeout: 30_000 }).toBeTruthy();
    const project = (await api(`/api/sessions/${chat.id}`)).project_id;
    await expect.poll(async () => (await api(`/api/production/${project}`)).stage, { timeout: 60_000 }).toBe('PLAN_READY');
    return { chat: chat.id, project };
  };
  const typed = await planInChat('Freigabe im Chat');
  const release = 'Die Planung ist freigegeben. Erstelle jetzt die vollständige Geschichte mit allen Kapiteln und Illustrationen. '
    + 'Prüfe und korrigiere die Texte automatisch und stelle mir am Ende die Markdown- und MDX-Dateien zum Herunterladen bereit.';
  await page.locator('#prompt').fill(release);
  await page.getByRole('button', { name: 'Nachricht senden', exact: true }).click();
  await expect(page.locator('[data-kind=production-job]').nth(1)).toBeVisible({ timeout: 30_000 });
  const released = await api(`/api/production/${typed.project}`);
  assert.equal(released.approved, true);
  assert.ok(['PRODUCTION_RUNNING', 'PRODUCTION_COMPLETED', 'PRODUCTION_PAUSED'].includes(released.stage), released.stage);
  const kinds = (await api(`/api/production/${typed.project}/report`)).map(job => job.payload.kind);
  assert.equal(kinds.filter(kind => kind === 'story').length, 1, kinds.join());
  assert.ok(!kinds.includes('planning'), 'the release must not run a planning review: ' + kinds.join());
  await expect(page.getByText('Planung prüfen', { exact: true })).toHaveCount(0);

  // The web UI offers the same in one click on the plan dialog.
  const clicked = await planInChat('Ein-Klick-Freigabe');
  await page.getByRole('button', { name: 'Planung öffnen' }).click({ timeout: 30_000 });
  await dialog.getByRole('button', { name: 'Freigeben und vollständig erstellen' }).click();
  await expect(page.locator('[data-kind=production-job]').nth(1)).toBeVisible({ timeout: 30_000 });
  assert.ok(['PRODUCTION_RUNNING', 'PRODUCTION_COMPLETED', 'PRODUCTION_PAUSED'].includes((await api(`/api/production/${clicked.project}`)).stage));
  assert.deepEqual(errors, []);
  console.log('Firefox production workflow, chat release, one-click release, chat image, manuscript and ZIP passed.');
} finally {
  await browser.close();
  await rm(output, { recursive: true, force: true });
}
