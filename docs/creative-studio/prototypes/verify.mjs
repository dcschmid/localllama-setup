import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { firefox } = require('playwright');
const axe = require.resolve('axe-core/axe.min.js');
const base = process.argv[2] ?? 'http://127.0.0.1:4370/';
const output = process.argv[3] ?? 'output/playwright/creative-studio';

const screens = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 834, height: 1112 },
  mobil: { width: 390, height: 844 },
  reflow: { width: 320, height: 780 },
};
const tags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'];
const missing = new Map();

async function screenshot(page, name) {
  await page.screenshot({ path: join(output, name + '.png'), fullPage: true, animations: 'disabled' });
}

async function audit(page, label) {
  await page.addScriptTag({ path: axe });
  const results = await page.evaluate(runOnly => window.axe.run({ runOnly }), tags);
  for (const item of results.incomplete) {
    missing.set(item.id, (missing.get(item.id) ?? 0) + 1);
  }
  assert.deepEqual(results.violations.map(({ id, nodes }) => [id, nodes.map(n => n.target)]), [], label);
}

async function noOverflow(page, label) {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, label);
}

await mkdir(output, { recursive: true });
const browser = await firefox.launch();
console.log('Firefox ' + browser.version());
try {
  for (const variant of ['a', 'b']) {
    for (const [screen, viewport] of Object.entries(screens)) {
      for (const theme of ['light', 'dark']) {
        const page = await browser.newPage({ viewport, colorScheme: theme, reducedMotion: 'reduce' });
        const errors = [];
        const pageLabel = `${variant}-${screen}-${theme}`;
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(new URL('?design=' + variant, base).href);
        await page.getByRole('heading', { name: 'Was möchtest du heute machen?' }).waitFor();
        await page.evaluate(() => document.fonts.ready);
        await noOverflow(page, pageLabel);
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
        assert.equal(await page.locator('.suggestion').count(), 4);
        assert.equal(await page.getByRole('textbox', { name: 'Nachricht' }).isVisible(), true);
        await audit(page, pageLabel);
        if (screen !== 'reflow') await screenshot(page, pageLabel);
        assert.deepEqual(errors, [], pageLabel);
        await page.close();
      }
    }

    const phone = await browser.newPage({ viewport: screens.mobil, colorScheme: 'light', acceptDownloads: true });
    const errors = [];
    phone.on('pageerror', error => errors.push(error.message));
    await phone.goto(new URL('?design=' + variant, base).href);
    await phone.keyboard.press('Tab');
    assert.equal(await phone.locator(':focus').textContent(), 'Zum Inhalt springen');
    await phone.keyboard.press('Enter');
    assert.equal(await phone.locator(':focus').getAttribute('id'), 'main');
    const openNav = phone.getByRole('button', { name: 'Seitenleiste öffnen' });
    await openNav.focus();
    await phone.keyboard.press('Enter');
    await phone.getByRole('dialog', { name: 'Seitenleiste' }).waitFor();
    assert.equal(await phone.locator(':focus').getAttribute('data-action'), 'close-nav');
    await audit(phone, variant + ' mobile navigation');
    await phone.keyboard.press('Escape');
    assert.equal(await openNav.evaluate(button => button === document.activeElement), true);
    await phone.getByRole('button', { name: 'Deep Research starten' }).click();
    const prompt = phone.getByRole('textbox', { name: 'Nachricht' });
    assert.match(await prompt.inputValue(), /^Recherchiere ausführlich/);
    await phone.keyboard.press('Enter');
    await phone.getByRole('heading', { name: 'Recherchevorschau' }).waitFor();
    await phone.getByRole('button', { name: 'Vorschau pausieren' }).click();
    await phone.getByText('Pausiert · Quellen sichten').waitFor();
    await phone.getByRole('button', { name: 'Vorschau fortsetzen' }).click();
    await phone.getByText('Quellen sichten · Runde 2 von 3').waitFor();
    await phone.getByText('Quellen (2)', { exact: true }).click();
    await phone.getByText('Umweltbundesamt', { exact: false }).waitFor();
    await audit(phone, variant + ' research preview');
    await noOverflow(phone, variant + ' research preview');
    if (variant === 'a') await screenshot(phone, 'a-recherche-mobil-light');

    await openNav.click();
    await phone.getByRole('button', { name: 'Neuer Chat' }).click();
    await prompt.fill('Ich möchte eine Geschichte schreiben.');
    await phone.getByRole('button', { name: 'Nachricht senden' }).click();
    await phone.getByRole('button', { name: 'Entwurf öffnen' }).click();
    const editor = phone.getByRole('textbox', { name: 'Dokumenttext in Markdown' });
    assert.equal(await editor.evaluate(field => field === document.activeElement), true);
    const original = await editor.inputValue();
    await editor.fill(original + '\n\nDer Nebel zog auf.');
    await phone.getByRole('button', { name: 'Vorschau', exact: true }).click();
    await phone.getByText('Der Nebel zog auf.', { exact: true }).waitFor();
    await phone.getByRole('button', { name: 'Speichern' }).click();
    await phone.getByText('Entwurf · Version 2').waitFor();
    await phone.getByRole('button', { name: 'Rückgängig' }).click();
    assert.equal(await phone.getByText('Der Nebel zog auf.', { exact: true }).count(), 0);
    await phone.getByRole('button', { name: 'Versionen' }).click();
    await phone.getByText('Vorherige Demofassung · Version 1').waitFor();
    await phone.keyboard.press('Escape');
    await phone.getByRole('button', { name: 'Exportieren' }).click();
    const download = phone.waitForEvent('download');
    await phone.getByRole('button', { name: 'Demo als MDX' }).click();
    assert.equal((await download).suggestedFilename(), 'studio-entwurf.mdx');
    await phone.keyboard.press('Escape');
    await audit(phone, variant + ' editor preview');
    await noOverflow(phone, variant + ' editor preview');
    if (variant === 'b') await screenshot(phone, 'b-editor-mobil-light');
    await phone.getByRole('button', { name: 'Editor schließen' }).click();
    assert.equal(await phone.getByRole('button', { name: 'Editor öffnen' }).evaluate(el => el === document.activeElement), true);
    await phone.getByRole('button', { name: 'Dunkles Erscheinungsbild verwenden' }).click();
    await phone.reload();
    assert.equal(await phone.locator('html').getAttribute('data-theme'), 'dark');
    assert.deepEqual(errors, []);
    await phone.close();

    const desktop = await browser.newPage({ viewport: screens.desktop, colorScheme: 'light' });
    await desktop.goto(new URL('?design=' + variant, base).href);
    await desktop.getByRole('button', { name: 'Projekte', exact: true }).click();
    await desktop.getByRole('heading', { name: 'Projekte', exact: true }).waitFor();
    await desktop.getByRole('button', { name: /Die letzte Fähre Geschichte/ }).click();
    await desktop.getByRole('button', { name: 'Editor öffnen' }).click();
    await desktop.getByRole('textbox', { name: 'Dokumenttext in Markdown' }).waitFor();
    await desktop.getByRole('heading', { name: 'Die letzte Fähre', level: 1 }).waitFor();
    await desktop.evaluate(() => document.activeElement.blur());
    await audit(desktop, variant + ' desktop editor');
    await screenshot(desktop, variant + '-editor-desktop-light');
    await desktop.getByRole('button', { name: 'Seitenleiste schließen' }).click();
    assert.equal(await desktop.getByRole('navigation', { name: 'Hauptnavigation' }).isVisible(), false);
    await desktop.getByRole('button', { name: 'Seitenleiste öffnen' }).click();
    assert.equal(await desktop.getByRole('navigation', { name: 'Hauptnavigation' }).isVisible(), true);
    await desktop.close();
    console.log(variant.toUpperCase() + ' · 8 Layouts, Tastatur, Recherchevorschau, Tour Chat › Editor, Demo-Download und Themenwechsel geprüft');
  }
  console.log('axe · keine Verstöße. Manuell zu prüfen: ' + JSON.stringify(Object.fromEntries(missing)));
} finally {
  await browser.close();
}
