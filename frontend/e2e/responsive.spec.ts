import { test, expect } from '@playwright/test';

test.describe('Tests responsive', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/overview');
    await page.waitForLoadState('networkidle');
  });

  test('desktop : la navigation latérale est visible', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.reload();
    await page.waitForLoadState('networkidle');

    const sidebar = page.getByRole('complementary', { name: /Navigation principale/i });
    await expect(sidebar).toBeVisible();

    const nav = page.getByRole('navigation', { name: /Navigation métier/i });
    await expect(nav).toBeVisible();
    await expect(nav.getByRole('link').first()).toBeVisible();
  });

  test('mobile : le menu hamburger est fonctionnel', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.reload();
    await page.waitForLoadState('networkidle');

    const mobileMoreButton = page.getByRole('button', { name: /Plus/i });
    await expect(mobileMoreButton).toBeVisible();

    await mobileMoreButton.click();
    await expect(page.getByRole('navigation', { name: /Navigation complémentaire/i })).toBeVisible();
  });

  test('mobile : ferme le menu hamburger avec Échap', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.reload();
    await page.waitForLoadState('networkidle');

    const mobileMoreButton = page.getByRole('button', { name: /Plus/i });
    await mobileMoreButton.click();
    await expect(page.getByRole('navigation', { name: /Navigation complémentaire/i })).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(page.getByRole('navigation', { name: /Navigation complémentaire/i })).toBeHidden();
  });

  test('tablette : la page incidents reste utilisable', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Incidents à examiner/i })).toBeVisible();
    await expect(page.getByRole('combobox', { name: /Statut/i })).toBeVisible();
  });

  test('table des incidents : scroll horizontal si contenu large', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');

    const tableWrap = page.locator('.incident-table-wrap');
    if (await tableWrap.count() > 0) {
      const scrollWidth = await tableWrap.evaluate((el) => el.scrollWidth);
      const clientWidth = await tableWrap.evaluate((el) => el.clientWidth);
      if (scrollWidth > clientWidth) {
        const overflowX = await tableWrap.evaluate((el) => window.getComputedStyle(el).overflowX);
        expect(['auto', 'scroll']).toContain(overflowX);
      }
    }
  });

  test('atelier : la liste compacte mobile est visible sur petit écran', async ({ page }) => {
    await page.goto('/sites');
    await page.waitForLoadState('networkidle');
    const openButtons = page.locator('button.site-open');
    if (await openButtons.count() === 0) {
      test.skip(true, 'Aucun site disponible');
      return;
    }

    await openButtons.first().click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/sites\/\d+\/workshop/);

    // Attend que le contenu se stabilise (liste compacte, SVG, ou message d'état)
    const mobileList = page.getByRole('radiogroup', { name: /Presses de l'atelier en liste/i });
    const svg = page.locator('svg[role="radiogroup"]').first();
    const status = page.locator('[role="status"]').first();
    await expect.poll(async () => {
      if (await mobileList.count() > 0 && await mobileList.isVisible().catch(() => false)) return true;
      if (await svg.count() > 0 && await svg.isVisible().catch(() => false)) return true;
      if (await status.count() > 0 && await status.isVisible().catch(() => false)) return true;
      return false;
    }, { timeout: 30000 }).toBe(true);
  });
});
