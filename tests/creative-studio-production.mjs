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
  await page.getByRole('button', { name: 'Illustrationen prüfen' }).click({ timeout: 30_000 });
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
  await dialog.getByRole('button', { name: 'ZIP herunterladen' }).click();
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
  assert.deepEqual(errors, []);
  console.log('Firefox production workflow, chat image, manuscript and ZIP passed.');
} finally {
  await browser.close();
  await rm(output, { recursive: true, force: true });
}
