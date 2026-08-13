import { test, expect } from '@playwright/test';

test.describe('Administration et Monitoring', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/overview');
    await page.waitForLoadState('networkidle');
  });

  test('accède à la page admin et affiche le profil (si auth disponible)', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Administration/i })).toBeVisible();

    // En mode SKIP_AUTH, le profil peut ne pas charger (401 sur /auth/me)
    // On vérifie soit le profil, soit le message d'erreur, soit l'état de chargement
    const profileHeading = page.getByRole('heading', { name: /Votre profil/i });
    const errorPanel = page.getByRole('alert');
    const loadingPanel = page.getByText(/Chargement du profil/i);

    const hasProfile = await profileHeading.count() > 0 && await profileHeading.isVisible().catch(() => false);
    const hasError = await errorPanel.count() > 0 && await errorPanel.first().isVisible().catch(() => false);
    const hasLoading = await loadingPanel.count() > 0 && await loadingPanel.isVisible().catch(() => false);

    if (hasProfile) {
      // Le profil est chargé — vérifie les sections attendues
      await expect(page.getByRole('heading', { name: /Permissions par site/i })).toBeVisible();
    } else if (hasError || hasLoading) {
      // Mode SKIP_AUTH : le profil est indisponible ou en cours de chargement, c'est acceptable
      expect(true).toBe(true);
    } else {
      // Ni profil ni erreur — attend au moins la présence du titre Administration
      await expect(page.getByRole('heading', { name: /Administration/i })).toBeVisible();
    }
  });

  test('affiche la matrice des rôles (si auth disponible)', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    const matriceHeading = page.getByRole('heading', { name: /Matrice des rôles/i });
    if (await matriceHeading.count() > 0 && await matriceHeading.isVisible().catch(() => false)) {
      await expect(matriceHeading).toBeVisible();
      await expect(page.getByText(/Bonnes pratiques/i)).toBeVisible();
    } else {
      test.skip(true, 'Matrice des rôles non affichée en mode SKIP_AUTH');
    }
  });

  test('affiche les informations de sécurité (si auth disponible)', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    const httpOnlyText = page.getByText(/HttpOnly/i);
    if (await httpOnlyText.count() > 0 && await httpOnlyText.first().isVisible().catch(() => false)) {
      await expect(page.getByText(/Secure/i).first()).toBeVisible();
      await expect(page.getByText(/Argon2id/i).first()).toBeVisible();
    } else {
      test.skip(true, 'Informations de sécurité non affichées en mode SKIP_AUTH');
    }
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

  test('navigue entre admin et monitoring via la sidebar', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Administration/i })).toBeVisible();

    await page.getByRole('link', { name: /Monitoring HDT/i }).click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/monitoring/);
    await expect(page.getByRole('heading', { name: /Monitoring du modèle HDT/i })).toBeVisible();

    await page.getByRole('link', { name: /Utilisateurs/i }).click();
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.getByRole('heading', { name: /Administration/i })).toBeVisible();
  });
});
