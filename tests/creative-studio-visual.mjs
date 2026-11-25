import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { firefox, expect } = require('playwright/test');
const base = process.env.CREATIVE_STUDIO_TEST_URL;
assert(base, 'Use a separate Studio fixture URL');
const browser = await firefox.launch();
const page = await browser.newPage({ acceptDownloads: true });
const errors = [];
page.on('pageerror', error => errors.push(error.message));

async function post(path, data) {
  const response = await page.request.post(base + '/api/' + path, { data });
  assert(response.ok(), await response.text());
  return response.json();
}

async function story(name) {
  const project = await post('projects', { name, kind: 'story', lang: 'de' });
  const chat = await post('sessions', { title: name, project_id: project.id });
  return { project: project.id, chat: chat.id };
}

async function profile(project) {
  const response = await page.request.get(base + '/api/projects/' + project + '/visual-profile');
  assert(response.ok(), await response.text());
  return (await response.json()).profile;
}

async function settings(chat) {
  await page.goto(base + '/#chat/' + chat);
  await page.getByRole('button', { name: 'Bildstil', exact: true }).click();
  return page.getByRole('dialog');
}

try {
  const first = await story('Grafikprofil QA');
  const second = await story('Storybuchprofil QA');
  const dialog = await settings(first.chat);
  await expect(dialog.getByLabel('Bildstil', { exact: true })).toHaveValue('anima-aesthetic');
  await expect(dialog.getByLabel('Bildformat')).toHaveValue('16:9');
  await dialog.getByLabel('Bildstil', { exact: true }).selectOption('graphic-novel');
  await dialog.getByLabel('Bildformat').selectOption('4:3');
  await dialog.getByRole('button', { name: 'Profil speichern' }).click();
  await expect(dialog).not.toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Bildstil', exact: true }).click();
  await expect(dialog.getByLabel('Bildstil', { exact: true })).toHaveValue('graphic-novel');
  await expect(dialog.getByLabel('Bildformat')).toHaveValue('4:3');
  await dialog.getByRole('button', { name: 'Visual Bible öffnen' }).click();
  await dialog.getByRole('button', { name: 'Figur hinzufügen' }).click();
  await dialog.getByLabel('Name', { exact: true }).fill('Ada');
  await dialog.getByLabel('Kleidung').fill('Roter Mantel');
  await dialog.getByLabel('Gültig ab Kapitel').fill('2');
  await dialog.getByRole('button', { name: 'Eintrag speichern' }).click();
  await expect(dialog.getByRole('button', { name: 'Ada', exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Dialog schließen' }).click();
  assert.equal((await profile(second.project)).template, 'anima-aesthetic');
  await page.goto(base + '/#chat/' + second.chat);
  await page.locator('#prompt').fill('Ich möchte ab jetzt alle Illustrationen dieser Geschichte im Painterly Storybook Stil.');
  await page.getByRole('button', { name: 'Nachricht senden' }).click();
  await expect.poll(async () => (await profile(second.project)).template).toBe('painterly-storybook');
  assert.equal((await profile(first.project)).template, 'graphic-novel');

  if (process.env.CREATIVE_STUDIO_REAL_VISUALS) {
    const cases = JSON.parse(await readFile(process.env.CREATIVE_STUDIO_REAL_VISUALS, 'utf8'));
    await page.goto(base + '/#chat/' + cases.A.chat);
    await page.getByRole('button', { name: 'Bild vergrößern' }).first().click();
    await expect(dialog.getByRole('img')).toBeVisible();
    assert(await dialog.getByRole('img').evaluate(image => image.complete && image.naturalWidth === 1024 && image.naturalHeight === 576));
    await dialog.getByText('Bilddetails', { exact: true }).click();
    await expect(dialog.getByText('Anima Aesthetic', { exact: false })).toBeVisible();
    const downloaded = page.waitForEvent('download');
    await dialog.getByRole('link', { name: 'Bild herunterladen' }).click();
    assert.match((await downloaded).suggestedFilename(), /^illustration-.*\.png$/);
    await dialog.getByRole('button', { name: 'Als Titelbild verwenden' }).click();
    const response = await page.request.get(base + '/api/projects/' + cases.A.project);
    assert.match((await response.json()).meta.cover, /^[a-f0-9]{32}$/);
    if (process.env.CREATIVE_STUDIO_VISUAL_SCREENSHOT) {
      await page.screenshot({ path: process.env.CREATIVE_STUDIO_VISUAL_SCREENSHOT });
    }
  }
  assert.deepEqual(errors, []);
  console.log('Firefox story profiles, chat style changes, Visual Bible and saved image actions passed.');
} finally {
  await browser.close();
}
