import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { firefox, expect } = require('playwright/test');
const axe = require.resolve('axe-core/axe.min.js');
const base = process.env.CREATIVE_STUDIO_TEST_URL?.replace(/\/+$/, '');
const output = process.env.CREATIVE_STUDIO_TEST_OUTPUT;
if (!base) throw new Error('Set CREATIVE_STUDIO_TEST_URL to an isolated Creative Studio instance.');

const browser = await firefox.launch();
const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
const main = page.locator('main');
const sidebar = page.locator('#sidebar');
const dialog = page.locator('#details');
const errors = [];
page.on('pageerror', error => errors.push(error.message));

const button = (name, scope = page) => scope.getByRole('button', { name, exact: true });
const heading = name => main.getByRole('heading', { name, exact: true });
const rowMenu = (name, scope = main) => button('Aktionen für ' + name, scope);

async function audit(current, name) {
  await current.addScriptTag({ path: axe });
  const results = await current.evaluate(() => window.axe.run({
    runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'],
  }));
  assert.deepEqual(results.violations.map(issue => [issue.id, issue.nodes.map(node => node.target)]), []);
  console.log(name + ' · axe ' + results.violations.length + ' Verstöße');
  for (const issue of results.incomplete) {
    console.log('Manuell prüfen', issue.id, issue.nodes.map(node => node.target));
  }
  if (output) {
    await mkdir(output, { recursive: true });
    await current.screenshot({ path: join(output, name + '.png'), animations: 'disabled' });
  }
}

async function send(path, data) {
  const response = await page.request.post(base + '/api' + path, { data });
  assert.ok(response.ok(), path + ': ' + await response.text());
  return response.json();
}

async function createFolder(name, opener) {
  await button(opener, opener === 'Neuer Ordner' ? sidebar : main).click();
  await dialog.getByLabel('Ordnername').fill(name);
  await button('Erstellen', dialog).click();
  await expect(heading(name)).toBeVisible();
}

async function openAction(name, action, scope = main) {
  await rowMenu(name, scope).click();
  await button(action, dialog).click();
}

try {
  await page.goto(base);
  await expect(heading('Was möchtest du heute machen?')).toBeVisible();
  await createFolder('Erzählungen', 'Neuer Ordner');
  const folderId = new URL(page.url()).hash.split('/')[1];
  await createFolder('Entwürfe', 'Unterordner');
  const subId = new URL(page.url()).hash.split('/')[1];
  await button('Neuer Chat hier', main).click();
  await dialog.getByLabel('Chatname').fill('Am Abend');
  await button('Erstellen', dialog).click();
  await expect(heading('Am Abend')).toBeVisible();
  const chatId = new URL(page.url()).hash.split('/')[1];
  await send(`/sessions/${chatId}/messages`, { role: 'user', content: 'Eine Nebelbank zieht auf.' });
  await page.reload();
  await expect(main.getByText('Eine Nebelbank zieht auf.')).toBeVisible();

  const chatLink = sidebar.getByRole('link', { name: 'Am Abend' });
  const rootFolder = sidebar.locator(`summary[data-folder-destination="${folderId}"]`);
  await chatLink.dragTo(rootFolder);
  await expect.poll(async () => {
    const response = await page.request.get(base + '/api/sessions/' + chatId);
    return (await response.json()).folder_id;
  }).toBe(folderId);
  await expect(chatLink).toBeVisible();
  await rootFolder.focus();
  await page.keyboard.press('Enter');
  await expect(chatLink).toBeHidden();
  await page.keyboard.press('Enter');
  await expect(chatLink).toBeVisible();

  await expect(button('Projekte', sidebar)).toHaveCount(0);
  await page.goto(base + '/#chats');
  await expect(heading('Chats')).toBeVisible();
  await main.getByLabel('Chats durchsuchen').fill('NEBELBANK');
  await button('Suchen', main).click();
  await expect(main.getByRole('link', { name: 'Am Abend' })).toBeVisible();
  await expect(main.getByRole('link', { name: 'Bestandschat' })).toHaveCount(0);
  await main.getByLabel('Sortieren nach').selectOption('oldest');

  const trigger = rowMenu('Am Abend');
  await trigger.focus();
  await page.keyboard.press('Enter');
  await expect(button('Öffnen', dialog)).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
  await openAction('Am Abend', 'Umbenennen');
  await dialog.getByLabel('Name').fill('Nebel am Abend');
  await button('Speichern', dialog).click();
  await expect(main.getByRole('link', { name: 'Nebel am Abend' })).toBeVisible();
  const second = await send('/sessions', { title: 'Zweiter Nebel' });
  await send('/sessions/' + second.id + '/messages', { role: 'user', content: 'Eine zweite Nebelbank.' });
  await button('Suchen', main).click();
  await expect(main.getByRole('link', { name: 'Zweiter Nebel' })).toBeVisible();
  await main.getByRole('checkbox', { name: 'Nebel am Abend auswählen' }).check();
  await main.getByRole('checkbox', { name: 'Zweiter Nebel auswählen' }).check();
  await button('Archivieren', main).click();
  await expect(main.getByText('Keine Chats gefunden.')).toBeVisible();
  await button('Archiv', sidebar).click();
  await expect(heading('Archiv')).toBeVisible();
  await openAction('Nebel am Abend', 'Aus Archiv holen');
  await expect(main.getByRole('link', { name: 'Nebel am Abend' })).toHaveCount(0);
  await openAction('Zweiter Nebel', 'Aus Archiv holen');
  await expect(main.getByText('Das Archiv ist leer.')).toBeVisible();

  await page.goto(base + '/#chat/' + chatId);
  await expect(heading('Nebel am Abend')).toBeVisible();
  await button('Inhalte', main).click();
  await button('Anhang hinzufügen', dialog).click();
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'Notizen.txt', mimeType: 'text/plain', buffer: Buffer.from('Licht am Kai'),
  });
  await button('Hinzufügen', dialog).click();
  await expect(dialog).toBeHidden();
  await button('Inhalte', main).click();
  await expect(dialog.getByRole('link', { name: 'Notizen.txt' })).toBeVisible();
  await page.keyboard.press('Escape');
  await openAction('Nebel am Abend', 'In den Papierkorb');
  await expect(dialog.getByText(/Chat · Nebel am Abend/)).toBeVisible();
  await expect(dialog.getByText(/Anhang · Notizen.txt/)).toBeVisible();
  await audit(page, 'organizer-loeschvorschau');
  await button('In den Papierkorb', dialog).click();
  await expect(heading('Papierkorb')).toBeVisible();
  await expect(main.getByText(/Chat · Erzählungen/)).toBeVisible();
  await audit(page, 'organizer-papierkorb');
  await main.getByRole('checkbox', { name: 'Nebel am Abend auswählen' }).check();
  await button('Wiederherstellen', main).click();
  await expect(main.getByText('Der Papierkorb ist leer.')).toBeVisible();
  await expect(main).toBeFocused();

  await page.goto(base + '/#chats');
  await openAction('Zweiter Nebel', 'In den Papierkorb');
  await button('In den Papierkorb', dialog).click();
  await expect(main.getByRole('link', { name: 'Zweiter Nebel' })).toHaveCount(0);
  await button('Papierkorb', sidebar).click();
  await openAction('Zweiter Nebel', 'Endgültig löschen');
  await expect(dialog.getByText('Diese Aktion ist dauerhaft.', { exact: false })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(rowMenu('Zweiter Nebel')).toBeFocused();
  await openAction('Zweiter Nebel', 'Endgültig löschen');
  await button('Endgültig löschen', dialog).click();
  await expect(main.getByText('Der Papierkorb ist leer.')).toBeVisible();

  const mobile = await browser.newPage({ viewport: { width: 320, height: 720 }, colorScheme: 'dark' });
  await mobile.goto(base + '/#folder/' + subId);
  await expect(mobile.getByRole('heading', { name: 'Entwürfe', exact: true })).toBeVisible();
  await button('Seitenleiste öffnen', mobile).click();
  const drawer = mobile.locator('#nav-dialog');
  await expect(drawer.locator('summary').filter({ hasText: 'Erzählungen' })).toBeVisible();
  await audit(mobile, 'organizer-seitenleiste-mobil');
  await mobile.keyboard.press('Escape');
  await expect(button('Seitenleiste öffnen', mobile)).toBeFocused();
  const reflows = await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
  assert.ok(reflows, 'Ordneransicht erzeugt bei 320 px keinen horizontalen Seitenüberlauf');
  assert.deepEqual(errors, []);
  console.log('Ordner, Drag & Drop, Chatsuche, Archiv, Anhänge, Papierkorb und Wiederherstellung geprüft.');
} finally {
  await browser.close();
}
