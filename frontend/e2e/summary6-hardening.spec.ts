import { expect, test } from '@playwright/test';

test.skip(process.env.SUMMARY6_UI_INTERCEPT !== 'true', 'Requires the dedicated intercepted API configuration.');

// Explicit interception: UI contract regression, not live backend certification.
for (const mode of ['summary6_replay', 'disabled']) {
  test(`atelier conservé en ${mode} (API interceptée)`, async ({ page }) => {
    const posts: string[] = [];
    await page.route('**/api/**', async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (request.method() === 'POST') posts.push(path);
      let body: unknown = [];
      if (path.endsWith('/auth/me')) body = { id: 'u', email: 's@test', role: 'supervisor', site_ids: [7], site_roles: { 7: 'supervisor' } };
      else if (path.endsWith('/summary6/current')) body = { selected_package_id: 'summary6-test', loaded_package_id: mode === 'disabled' ? null : 'summary6-test', active_mode: mode, readiness: mode === 'disabled' ? 'not_ready' : 'ready', replay_enabled: mode !== 'disabled', live_enabled: false, reasons: [] };
      else if (path.endsWith('/summary6/demo-datasets')) {
        expect(new URL(request.url()).searchParams.get('site_id')).toBe('7');
        body = { dataset_id: 'contract-demo', synthetic: true, lots: [{ lot_id: 'M1-R1-L15', count: 400 }] };
      } else if (path.endsWith('/summary6/replay')) {
        expect(request.postDataJSON()).toEqual({ site_id: 7, expected_package_id: 'summary6-test', source: { kind: 'demo_dataset', dataset_id: 'contract-demo', lot_id: 'M1-R1-L15', through_cycle: 84 } });
        body = { package_id: 'summary6-test', site_id: 7, through_cycle: 84, input_count: 85, latest: { status: 'abstained', reason: 'numerical_failure', instant_score: null, decision_score: null, alert: null } };
      } else if (path.endsWith('/sites')) body = [{ id: 7, name: 'Atelier sept', timezone: 'UTC' }];
      else if (path.endsWith('/sites/7')) body = { id: 7, name: 'Atelier sept', timezone: 'UTC' };
      else if (path.endsWith('/sites/7/machines')) body = [{ id: 8, site_id: 7, name: 'Presse sept', workshop_code: 'P7', lifecycle_status: 'active' }];
      else if (path.endsWith('/connection')) body = null;
      else if (path.endsWith('/status')) body = { machine_id: 8, as_of: new URL(request.url()).searchParams.get('as_of'), status: 'offline', last_cycle_at: null };
      await route.fulfill({ json: body });
    });
    await page.goto('/sites/7/workshop');
    await expect(page.getByRole('heading', { name: 'Catalogue des presses' })).toBeVisible();
    await expect(page.getByText('Plan 2D', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Configurer passerelle et mapping' })).toBeVisible();
    if (mode === 'summary6_replay') {
      await expect(page.getByText(/SYNTHÉTIQUE REPLAY PAS LIVE/)).toBeVisible();
      await page.getByLabel('Lot synthétique').selectOption('M1-R1-L15');
      await page.getByRole('button', { name: 'Calculer le replay' }).click();
      await expect(page.getByText(/Abstention : numerical_failure/)).toBeVisible();
      expect(posts).toEqual(['/api/v1/process-drift/summary6/replay']);
    } else {
      await expect(page.getByRole('alert').filter({ hasText: 'Scoring indisponible' })).toBeVisible();
      expect(posts).toEqual([]);
    }
    await page.getByRole('link', { name: 'Ouvrir le planning hebdomadaire' }).click();
    await expect(page).toHaveURL(/\/sites\/7\/planning/);
  });
}
