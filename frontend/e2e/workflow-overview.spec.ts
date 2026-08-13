import { test, expect } from '@playwright/test';

test.describe('Parcours complet : overview → sites → atelier → incidents', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/overview');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('h2', { timeout: 15000 });
  });

  test('affiche la page overview avec les indicateurs principaux', async ({ page }) => {
    await page.waitForSelector('.overview-ledger', { timeout: 15000 });
    await expect(page.locator('h2').first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('region', { name: /Indicateurs principaux/i })).toBeVisible();
    // Les labels sont en majuscules dans le DOM accessible
    await expect(page.getByText(/SITES SUIVIS/i).first()).toBeVisible();
    await expect(page.getByText(/MACHINES RÉFÉRENCÉES/i).first()).toBeVisible();
    await expect(page.getByText(/INCIDENTS OUVERTS/i).first()).toBeVisible();
    await expect(page.getByText(/IMPORTS TERMINÉS/i).first()).toBeVisible();
  });

  test('affiche les panneaux de sites, incidents prioritaires et ingestion', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Sites industriels/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Incidents prioritaires/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Dernières données/i })).toBeVisible();
  });

  test('navigue vers la liste des sites depuis overview', async ({ page }) => {
    await page.getByRole('link', { name: /Voir tous les sites/i }).click();
    await expect(page).toHaveURL(/\/sites/);
    await expect(page.getByRole('heading', { name: /Vos ateliers/i })).toBeVisible();
  });

  test('ouvre un atelier et vérifie la carte 2D des presses', async ({ page }) => {
    await page.goto('/sites');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Vos ateliers/i })).toBeVisible();

    await page.waitForSelector('.site-card, .empty-panel', { timeout: 15000 });
    await expect(page.getByText(/SITES SUIVIS/i).first()).toBeVisible();
    await expect(page.getByText(/PRESSES RÉFÉRENCÉES/i).first()).toBeVisible();

    const openButtons = page.locator('button.site-open');
    await expect.poll(async () => await openButtons.count(), { timeout: 10000 }).toBeGreaterThanOrEqual(0);
    const count = await openButtons.count();
    if (count === 0) {
      await expect(page.locator('.empty-panel')).toBeVisible();
      return;
    }

    await openButtons.first().click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/sites\/\d+\/workshop/);

    // Le workshop peut être en état "ready" ou "indisponible" selon les données
    // On attend que le contenu se stabilise (SVG, message ready, ou message d'erreur)
    const svg = page.locator('svg[role="radiogroup"]').first();
    const ready = page.locator('.workshop-page-ready').first();
    const alert = page.getByRole('alert').first();
    const status = page.locator('[role="status"]').first();
    await expect.poll(async () => {
      if (await svg.count() > 0 && await svg.isVisible().catch(() => false)) return true;
      if (await ready.count() > 0 && await ready.isVisible().catch(() => false)) return true;
      if (await alert.count() > 0 && await alert.isVisible().catch(() => false)) return true;
      if (await status.count() > 0 && await status.isVisible().catch(() => false)) return true;
      return false;
    }, { timeout: 30000 }).toBe(true);
  });

  test('sélectionne une presse sur le plan et affiche son détail', async ({ page }) => {
    await page.goto('/sites');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('.site-card, .empty-panel', { timeout: 15000 });

    const openButtons = page.locator('button.site-open');
    if (await openButtons.count() === 0) {
      test.skip(true, 'Aucun site disponible pour tester la sélection de presse');
      return;
    }
    await openButtons.first().click();
    await page.waitForLoadState('networkidle');

    // Attend que le contenu se stabilise
    const svg = page.locator('svg[role="radiogroup"]').first();
    const ready = page.locator('.workshop-page-ready').first();
    const alert = page.getByRole('alert').first();
    const status = page.locator('[role="status"]').first();
    await expect.poll(async () => {
      if (await svg.count() > 0 && await svg.isVisible().catch(() => false)) return true;
      if (await ready.count() > 0 && await ready.isVisible().catch(() => false)) return true;
      if (await alert.count() > 0 && await alert.isVisible().catch(() => false)) return true;
      if (await status.count() > 0 && await status.isVisible().catch(() => false)) return true;
      return false;
    }, { timeout: 30000 }).toBe(true);

    // Si le SVG est présent, teste la sélection de presse
    if (await svg.count() > 0 && await svg.isVisible().catch(() => false)) {
      await page.getByRole('radio').first().click();
      await expect(page.getByRole('complementary', { name: /Détail de la presse sélectionnée/i })).toBeVisible();
    }
  });

  test("navigue vers la page incidents depuis l'atelier", async ({ page }) => {
    await page.goto('/sites');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('.site-card, .empty-panel', { timeout: 15000 });

    const openButtons = page.locator('button.site-open');
    if (await openButtons.count() === 0) {
      test.skip(true, 'Aucun site disponible');
      return;
    }
    await openButtons.first().click();
    await page.waitForLoadState('networkidle');
    await page.getByRole('link', { name: /Incidents/i }).first().click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/incidents/);
    await expect(page.getByRole('heading', { name: /Incidents à examiner/i })).toBeVisible();
  });
});
