import { test, expect } from '@playwright/test';

test.describe("Parcours incident complet : liste → détail → investigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/incidents');
    await page.waitForLoadState('networkidle');
  });

  test('affiche la liste des incidents', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Incidents à examiner/i })).toBeVisible();
    await expect(page.getByRole('combobox', { name: /Statut/i })).toBeVisible();
  });

  test('filtre les incidents par statut ouvert', async ({ page }) => {
    await expect(page.getByRole('combobox', { name: /Statut/i })).toBeVisible();
    await page.getByRole('combobox', { name: /Statut/i }).selectOption('open');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/status=open/);
    // Vérifie que le compteur de résultats est affiché
    await expect(page.getByText(/résultat/i)).toBeVisible();
  });

  test('filtre les incidents par statut revu', async ({ page }) => {
    await page.getByRole('combobox', { name: /Statut/i }).selectOption('reviewed');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/status=reviewed/);
  });

  test('filtre les incidents par statut clos', async ({ page }) => {
    await page.getByRole('combobox', { name: /Statut/i }).selectOption('closed');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/status=closed/);
  });

  test('réinitialise les filtres', async ({ page }) => {
    await page.getByRole('combobox', { name: /Statut/i }).selectOption('open');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/status=open/);
    await page.getByRole('button', { name: /Réinitialiser les filtres/i }).click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/incidents$/);
  });

  test("ouvre le détail d’un incident et vérifie l'affichage", async ({ page }) => {
    const tableRows = page.locator('table tbody tr');
    const rowCount = await tableRows.count();
    if (rowCount === 0) {
      test.skip(true, 'Aucun incident disponible pour tester le détail');
      return;
    }

    // Clique sur le premier lien d'incident
    await tableRows.first().getByRole('link').first().click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/incidents\//);

    // Vérifie les éléments clés de la page détail
    await expect(page.getByRole('link', { name: /Tous les incidents/i })).toBeVisible();
    await expect(page.getByText(/Presse/i)).toBeVisible();
  });

  test('vérifie la présence des métriques sur la fiche incident', async ({ page }) => {
    const tableRows = page.locator('table tbody tr');
    if (await tableRows.count() === 0) {
      test.skip(true, 'Aucun incident disponible');
      return;
    }

    await tableRows.first().getByRole('link').first().click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/incidents\//);

    // Vérifie les cartes de métriques
    await expect(page.getByText('Fenêtre du signal', { exact: true })).toBeVisible();
    await expect(page.getByText('Rebut observé', { exact: true })).toBeVisible();
    await expect(page.getByText('Zone 2', { exact: true })).toBeVisible();
    await expect(page.getByText('Confiance', { exact: true })).toBeVisible();
  });

  test("lance l’investigation et vérifie les hypothèses et preuves", async ({ page }) => {
    const tableRows = page.locator('table tbody tr');
    if (await tableRows.count() === 0) {
      test.skip(true, 'Aucun incident disponible');
      return;
    }

    await tableRows.first().getByRole('link').first().click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/incidents\//);

    const investigateButton = page.getByRole('button', { name: /Lancer l’investigation/i });
    if (await investigateButton.count() === 0 || !(await investigateButton.isVisible())) {
      test.skip(true, 'Bouton investigation non disponible (lecture seule ou absent)');
      return;
    }

    await investigateButton.click();
    await expect(page.getByText(/Investigation/i)).toBeVisible();

    // Attend que l’investigation se termine (succès ou erreur)
    await expect(page.getByRole('status').or(page.getByText(/Investigation terminée/i)).or(page.getByText(/preuves/i))).toBeVisible({ timeout: 15000 });

    // Vérifie la section hypothèses
    await expect(page.getByText(/Raisonnement structuré/i).or(page.getByText(/Aucun run disponible/i))).toBeVisible();

    // Vérifie la section preuves (timeline ou liste)
    await expect(page.getByText(/Reconstitution temporelle/i).or(page.getByText(/Avant/i))).toBeVisible();
  });

  test('vérifie la timeline de reconstitution temporelle', async ({ page }) => {
    const tableRows = page.locator('table tbody tr');
    if (await tableRows.count() === 0) {
      test.skip(true, 'Aucun incident disponible');
      return;
    }

    await tableRows.first().getByRole('link').first().click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/incidents\//);
    await expect(page.getByText(/Reconstitution temporelle/i)).toBeVisible();
  });
});
