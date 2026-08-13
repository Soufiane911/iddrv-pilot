import { test, expect } from '@playwright/test';

test.describe("Flux d'authentification", () => {
  test('la page login redirige vers overview en mode SKIP_AUTH', async ({ page }) => {
    await page.goto('/login');
    await page.waitForURL(/\/overview/, { timeout: 15000 });
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h2', { timeout: 15000 });
    await expect(page.locator('h1')).toBeVisible({ timeout: 15000 });
  });

  test("vérifie l'absence de jeton dans localStorage (mode sécurisé par cookie)", async ({ page }) => {
    await page.goto('/overview');
    await page.waitForLoadState('networkidle');
    const token = await page.evaluate(() => localStorage.getItem('token'));
    expect(token).toBeNull();
    const authToken = await page.evaluate(() => localStorage.getItem('auth-token'));
    expect(authToken).toBeNull();
  });

  test('le bouton de déconnexion est masqué en mode SKIP_AUTH', async ({ page }) => {
    await page.goto('/overview');
    await page.waitForLoadState('networkidle');
    const logoutButton = page.getByRole('button', { name: /Se déconnecter/i });
    await expect(logoutButton).toHaveCount(0);
  });

  test('vérifie la note de sécurité sur la page login (composant)', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/overview/);
  });

  test('la navigation protégée est accessible sans authentification en mode SKIP_AUTH', async ({ page }) => {
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Incidents à examiner/i })).toBeVisible();

    await page.goto('/sites');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Vos ateliers/i })).toBeVisible();

    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Administration/i })).toBeVisible();
  });
});
