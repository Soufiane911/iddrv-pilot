import { test, expect } from '@playwright/test';

test('sites, clavier, modal native et reflow 320px — API interceptée, pas un test backend', async ({ page }) => {
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    return route.fulfill({ json: path.endsWith('/auth/me') ? { id: 'audit', email: 'audit@example.test', role: 'admin', site_ids: [1] } : path.endsWith('/sites') ? [{ id: 1, name: 'Atelier audit', timezone: 'Europe/Paris', status: 'active' }] : [] });
  });
  await page.goto('/sites');
  const trigger = page.getByRole('button', { name: 'Nouveau site' });
  await expect(trigger).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Aller au contenu' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  for (let i = 0; i < 12 && !(await trigger.evaluate(el => el === document.activeElement)); i++) await page.keyboard.press('Tab');
  await expect(trigger).toBeFocused();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(page.getByLabel('Nom du site')).toBeFocused();
  expect(await dialog.evaluate(el => el.matches(':modal'))).toBe(true);
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: 'Créer le site' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Nom du site')).toBeFocused();
  expect(await page.getByLabel('Nom du site').evaluate(el => getComputedStyle(el).outlineStyle)).toBe('solid');
  await page.setViewportSize({ width: 320, height: 740 });
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: '/tmp/iddrv-a11y-id/site-modal-320.png' });
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const more = page.getByRole('button', { name: 'Plus', exact: true });
  await more.focus(); await page.keyboard.press('Enter'); await page.keyboard.press('Tab'); await page.keyboard.press('Escape');
  await expect(more).toBeFocused();
});

test('auth : reflow 320 et agrandissement texte 200%, noms accessibles', async ({ page }) => {
  await page.route('**/api/**', route => route.fulfill({ status: 401, json: { message: 'Session absente' } }));
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto('/login');
  await expect(page.getByLabel('Adresse e-mail')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.addStyleTag({ content: '.login-card { font-size: 200%; } .login-card label, .login-card p, .login-card h1 { font-size: 1em; }' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Tab'); await expect(page.getByLabel('Adresse e-mail')).toBeFocused();
  await page.keyboard.press('Tab'); await expect(page.getByLabel('Mot de passe')).toBeFocused();
  await page.screenshot({ path: '/tmp/iddrv-a11y-id/login-text-200.png' });
});
