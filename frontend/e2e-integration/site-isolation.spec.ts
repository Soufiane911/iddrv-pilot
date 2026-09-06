import { expect, test } from '@playwright/test';

test.describe('isolement des sites', () => {
  test.skip(!process.env.IDDRV_E2E_EMAIL || !process.env.IDDRV_E2E_PASSWORD, 'requiert une session synthétique de recette');

  test('une session voit le périmètre qui lui est attribué', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Adresse e-mail').fill(process.env.IDDRV_E2E_EMAIL!);
    await page.getByLabel('Mot de passe').fill(process.env.IDDRV_E2E_PASSWORD!);
    await page.getByRole('button', { name: 'Ouvrir la supervision' }).click();
    await expect(page).toHaveURL(/overview/);
    await expect(page.getByText('Périmètre autorisé')).toBeVisible();
  });
});
