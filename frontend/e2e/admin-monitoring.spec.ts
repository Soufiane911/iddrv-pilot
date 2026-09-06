import { test, expect } from '@playwright/test';

test.describe('Administration et Monitoring', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/overview');
    await page.waitForLoadState('networkidle');
  });

  test('accède à la page admin et affiche le profil de démonstration', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Administration/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Votre profil/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Permissions par site/i })).toBeVisible();
  });

  test('affiche la matrice des rôles', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Matrice des rôles/i })).toBeVisible();
    await expect(page.getByText(/Bonnes pratiques/i)).toBeVisible();
  });

  test('affiche les informations de sécurité documentées', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/HttpOnly/i).first()).toBeVisible();
    await expect(page.getByText(/Secure/i).first()).toBeVisible();
    await expect(page.getByText(/Argon2id/i).first()).toBeVisible();
  });

  test('accède à la page monitoring avec les métriques HDT', async ({ page }) => {
    await page.goto('/monitoring');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Monitoring du modèle HDT/i })).toBeVisible();
    await expect(page.getByText(/hdt-process-drift-iforest-v1/i)).toBeVisible();
    await expect(page.getByText(/Isolation Forest/i)).toBeVisible();
  });

  test('vérifie la section des métriques offline', async ({ page }) => {
    await page.goto('/monitoring');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Métriques de validation offline/i })).toBeVisible();
    // La carte des métriques est un role region avec aria-label
    await expect(page.getByRole('region', { name: /Métriques de validation offline/i })).toBeVisible();
    await expect(page.getByText(/Average Precision/i)).toBeVisible();
    await expect(page.getByText(/ROC-AUC/i)).toBeVisible();
  });

  test('vérifie le simulateur HDT', async ({ page }) => {
    await page.goto('/monitoring');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('button', { name: /Calculer le score HDT/i })).toBeVisible();
  });

  test('vérifie la section historique des prédictions', async ({ page }) => {
    await page.goto('/monitoring');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Historique des prédictions/i })).toBeVisible();
  });

  test('vérifie la section feedbacks humains', async ({ page }) => {
    await page.goto('/monitoring');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Feedbacks humains/i })).toBeVisible();
    await expect(page.getByText('Confirmés', { exact: true })).toBeVisible();
    await expect(page.getByText('Rejetés', { exact: true })).toBeVisible();
    await expect(page.getByText('Incertains', { exact: true })).toBeVisible();
  });

  test('vérifie le disclaimer méthodologique', async ({ page }) => {
    await page.goto('/monitoring');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('note', { name: /Avertissement méthodologique/i })).toBeVisible();
    // Utilise first() pour éviter le strict mode violation (2 éléments contiennent ce texte)
    await expect(page.getByText(/validation offline sur données synthétiques/i).first()).toBeVisible();
  });

  test('atteint les écrans administration et monitoring par leurs routes publiques', async ({ page }) => {
    // These screens are intentionally not presented as sidebar links: the
    // sidebar exposes service health, while monitoring/admin are dedicated
    // routes.  Assert the routes that actually exist instead of a stale link.
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Administration/i })).toBeVisible();

    await page.goto('/monitoring');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/monitoring/);
    await expect(page.getByRole('heading', { name: /Monitoring du modèle HDT/i })).toBeVisible();

    await page.goto('/health');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/health/);
    await expect(page.getByRole('heading', { name: /Santé des services/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Dépendances sondées/i })).toBeVisible();
    await expect(page.getByText('Chargeable', { exact: true })).toBeVisible();
  });
});
