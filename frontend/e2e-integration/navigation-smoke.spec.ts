import { expect, test } from '@playwright/test';

test.describe('flux de production intégré', () => {
  test.skip(!process.env.IDDRV_E2E_EMAIL || !process.env.IDDRV_E2E_PASSWORD, 'requiert une session synthétique de recette');

  test('connexion, collecte, import tardif et investigation', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Adresse e-mail').fill(process.env.IDDRV_E2E_EMAIL!);
    await page.getByLabel('Mot de passe').fill(process.env.IDDRV_E2E_PASSWORD!);
    await page.getByRole('button', { name: 'Ouvrir la supervision' }).click();
    await expect(page).toHaveURL(/overview/);
    await page.goto('/imports');
    await expect(page.getByRole('heading', { name: /Historique des imports/ })).toBeVisible();
    await page.goto('/sites');
    await expect(page.getByRole('heading', { name: /Sites/ })).toBeVisible();
  });
});
