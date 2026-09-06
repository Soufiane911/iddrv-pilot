import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const email = process.env.IDDRV_E2E_EMAIL;
const password = process.env.IDDRV_E2E_PASSWORD;
const siteId = process.env.IDDRV_E2E_SITE_ID ?? '1';
const machineId = process.env.IDDRV_E2E_MACHINE_ID ?? '1';
const fixtureUrl = process.env.IDDRV_FIXTURE_URL;
const fixtureToken = process.env.IDDRV_FIXTURE_CONTROL_TOKEN;
const sourceBaseUrl = process.env.IDDRV_SOURCE_BASE_URL ?? 'http://press-api:8090';
const trsFile = process.env.IDDRV_E2E_TRS_FILE;
const correctionFile = process.env.IDDRV_E2E_CORRECTION_FILE;
const to = process.env.IDDRV_E2E_TO ?? '2026-09-07T00:00:00Z';
const fixtureFrom = process.env.IDDRV_E2E_FROM ?? '2026-09-05T00:00:00Z';

async function loginApi(request: APIRequestContext) {
  const response = await request.post('/api/v1/auth/login', { data: { email, password } });
  expect(response.ok()).toBeTruthy();
  expect((await response.json()).user).toBeTruthy();
}

async function loginPage(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Adresse e-mail').fill(email!);
  await page.getByLabel('Mot de passe').fill(password!);
  await page.getByRole('button', { name: /ouvrir la supervision/i }).click();
  await expect(page).toHaveURL(/\/overview|\/sites/);
}

async function readCycles(request: APIRequestContext) {
  const response = await request.get(`/api/v1/machines/${machineId}/cycles?to=${encodeURIComponent(to)}&limit=100`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()).items as Array<Record<string, unknown>>;
}

async function resolvePreviewChoices(page: Page) {
  const createPresses = page.getByRole('checkbox', { name: /Créer la presse/ });
  for (let index = 0; index < await createPresses.count(); index += 1) await createPresses.nth(index).check();
  const identitySelectors = page.getByLabel(/Identité à vérifier/);
  for (let index = 0; index < await identitySelectors.count(); index += 1) {
    const options = identitySelectors.nth(index).locator('option');
    if (await options.count() > 1) await identitySelectors.nth(index).selectOption({ index: 1 });
  }
  const choiceGroups = page.getByRole('checkbox', { name: /Historique complet de l’OF|Confirmer les champs de contexte OF/ });
  for (let index = 0; index < await choiceGroups.count(); index += 1) await choiceGroups.nth(index).check();
}

async function uploadAndConfirm(page: Page, file: string) {
  await page.setInputFiles('input[type="file"]', file);
  await page.getByRole('button', { name: /téléverser et prévisualiser/i }).click();
  await expect(page.getByText(/Aperçu · version/i)).toBeVisible({ timeout: 30_000 });
  await resolvePreviewChoices(page);
  await page.getByRole('button', { name: /confirmer l’import/i }).click();
}

async function listImports(request: APIRequestContext) {
  const response = await request.get(`/api/v1/sites/${siteId}/erp-imports`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()).items as Array<{ id: string; state: string }>;
}

async function waitForNewImport(request: APIRequestContext, previousIds: Set<string>) {
  let createdId = '';
  await expect.poll(async () => {
    const items = await listImports(request);
    createdId = items.find(item => !previousIds.has(item.id))?.id ?? '';
    return createdId;
  }, { timeout: 30_000 }).not.toBe('');
  return createdId;
}

async function waitForCompletedImport(request: APIRequestContext, importId: string) {
  let observed: { id: string; state: string } | undefined;
  await expect.poll(async () => {
    observed = (await listImports(request)).find(item => item.id === importId);
    return observed?.state ?? 'missing';
  }, { timeout: 60_000 }).toBe('completed');
  expect(observed?.id).toBe(importId);
  expect(observed?.state).toBe('completed');
}

async function waitForNewCompletedImport(request: APIRequestContext, previousIds: Set<string>) {
  const importId = await waitForNewImport(request, previousIds);
  await waitForCompletedImport(request, importId);
  return importId;
}

async function controlFixture(request: APIRequestContext, payload: Record<string, unknown>) {
  const response = await request.post(`${fixtureUrl}/__test/control`, {
    headers: fixtureToken ? { 'x-test-control-token': fixtureToken } : undefined,
    data: payload,
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

type E2ePrediction = { id?: string; score?: number; anomaly_score?: number; status?: string; reason?: string | null };

function predictionItems(payload: unknown): E2ePrediction[] {
  if (Array.isArray(payload)) return payload as E2ePrediction[];
  if (payload && typeof payload === 'object' && Array.isArray((payload as { items?: unknown }).items)) {
    return (payload as { items: E2ePrediction[] }).items;
  }
  return [];
}

test.describe('flux réel connexion → import ERP → cycles → rapprochement → HDT', () => {
  test.skip(!email || !password || process.env.IDDRV_E2E_RUN !== '1', 'Recette activée uniquement avec une session synthétique dédiée.');

  test('collecte 100 événements, importe le bilan, score et vérifie la continuité', async ({ page, context, request }) => {
    test.skip(!fixtureUrl || !trsFile || !correctionFile, 'La recette complète nécessite la fixture et deux XLSX synthétiques.');
    await loginApi(request);

    const machineResponse = await request.get(`/api/v1/sites/${siteId}/machines`);
    expect(machineResponse.ok()).toBeTruthy();
    expect((await machineResponse.json()).items).toBeTruthy();

    await controlFixture(request, { emit: 100, retention_floor: 0, error: 0, profile: 'complete' });
    const sourceStatus = await request.get(`${fixtureUrl}/v1/machines/606/status`);
    expect(sourceStatus.ok()).toBeTruthy();
    const sourceBody = await sourceStatus.json();
    expect(sourceBody.oldest_available_sequence).toEqual(expect.any(Number));
    const previousSequence = sourceBody.last_cycle_sequence as number;
    expect(previousSequence).toBeGreaterThanOrEqual(100);
    const sourceCycles = await request.get(`${fixtureUrl}/v1/machines/606/cycles?limit=100`);
    expect(sourceCycles.ok()).toBeTruthy();
    const sourceItems = (await sourceCycles.json()).items as Array<{ event_id?: string; sequence?: number }>;
    expect(new Set(sourceItems.map(item => item.event_id ?? item.sequence)).size).toBe(100);

    const configured = await request.put(`/api/v1/machines/${machineId}/connection`, { data: { base_url: sourceBaseUrl, external_machine_id: '606', secret_ref: null, poll_interval_s: 1, enabled: true, mapping_profile: 'iddrv-cycle-v1' } });
    expect(configured.ok()).toBeTruthy();
    await expect.poll(async () => (await readCycles(request)).length, { timeout: 30_000 }).toBe(100);
    const cycles = await readCycles(request);
    const from = encodeURIComponent(fixtureFrom);
    expect(new Set(cycles.map(item => item.timestamp)).size).toBe(100);
    expect(cycles.every(item => typeof item.timestamp === 'string' && item.timestamp.length > 0)).toBeTruthy();

    const score = await request.post('/api/v1/process-drift', { data: { site_id: Number(siteId), cycles: cycles.slice(0, 20) } });
    expect(score.ok()).toBeTruthy();
    expect((await score.json()).anomaly_score).toEqual(expect.any(Number));

    const insufficient = await request.post('/api/v1/process-drift', { data: { site_id: Number(siteId), cycles: cycles.slice(0, 2) } });
    expect(insufficient.status()).toBe(422);
    const insufficientBody = await insufficient.json();
    expect(JSON.stringify(insufficientBody)).toMatch(/insufficient_history|three_cycles_required|validation_error|too_short/);
    expect(insufficientBody.score ?? insufficientBody.anomaly_score).toBeUndefined();

    // Move the synthetic source forward while retaining its SQLite history:
    // initial reads are filtered, a stale cursor gets HTTP 410, and recovery
    // must resume from the same stream's last verifiable position.
    const retentionFloor = previousSequence + 3;
    await controlFixture(request, { emit: 3, retention_floor: retentionFloor, error: 0, profile: 'partial' });
    const retainedInitial = await request.get(`${fixtureUrl}/v1/machines/606/cycles?limit=100`);
    expect(retainedInitial.ok()).toBeTruthy();
    const retainedItems = (await retainedInitial.json()).items as Array<{ sequence: number; measurements?: Record<string, unknown> }>;
    expect(retainedItems.every(item => item.sequence >= retentionFloor)).toBeTruthy();
    expect(retainedItems.some(item => !item.measurements?.cooling_time_s)).toBeTruthy();
    const retainedStatus = await request.get(`${fixtureUrl}/v1/machines/606/status`);
    expect((await retainedStatus.json()).oldest_available_sequence).toBe(retentionFloor);
    const expiredCursor = await request.get(`${fixtureUrl}/v1/machines/606/cycles?after=${sourceBody.stream_id}:${previousSequence}`);
    expect(expiredCursor.status()).toBe(410);
    await expect.poll(async () => {
      const response = await request.get(`/api/v1/machines/${machineId}/connection`);
      return response.ok() ? (await response.json()).state : 'unavailable';
    }, { timeout: 30_000 }).toBe('gap_detected');

    await loginPage(page);
    await page.goto(`/sites/${siteId}/workshop?mode=direct`);
    await expect(page.getByRole('heading', { name: /état des presses/i })).toBeVisible();
    await expect(page.getByText(/Source joignable|Collecte interrompue|Non connectée/).first()).toBeVisible();
    await expect(page.getByText(/Mesures visibles|En attente de cycles|Cycles inconnus/).first()).toBeVisible();
    await expect(page.getByText('Ajouter une presse manuellement')).toBeVisible();

    await page.goto(`/imports?siteId=${siteId}`);
    const importsBefore = new Set((await listImports(request)).map(item => item.id));
    await uploadAndConfirm(page, trsFile);
    await expect(page.getByRole('status')).toContainText(/Import en attente|Import terminé/, { timeout: 30_000 });
    await waitForNewCompletedImport(request, importsBefore);

    // The second workbook represents a late ERP correction/reopening. It must
    // be confirmed with the same explicit preview choices and processed fully.
    const importsAfterFirst = new Set((await listImports(request)).map(item => item.id));
    await uploadAndConfirm(page, correctionFile);
    await waitForNewCompletedImport(request, importsAfterFirst);

    const contextResponse = await request.get(`/api/v1/machines/${machineId}/production-context?from=${from}&known_at=${encodeURIComponent(to)}&limit=100`);
    expect(contextResponse.ok()).toBeTruthy();
    const productionContext = await contextResponse.json();
    expect(productionContext.orders ?? []).toBeTruthy();
    expect(productionContext.declarations ?? []).toBeTruthy();
    expect(productionContext.coverage).toBeDefined();
    const declarations = productionContext.declarations ?? [];
    expect(declarations).toHaveLength(2);
    expect(new Set(declarations.map((item: { production_order_id?: string; order_ref?: string }) => item.production_order_id ?? item.order_ref)).size).toBe(1);
    const revisions = declarations.map((item: { revision_number?: number }) => Number(item.revision_number));
    expect(new Set(revisions).size).toBe(2);
    expect(revisions.some((revision) => revision >= 2)).toBeTruthy();
    expect(productionContext.coverage?.declarations).toBe(2);

    const predictionsResponse = await request.get(`/api/v1/machines/${machineId}/hdt-predictions?from=${from}&known_at=${encodeURIComponent(to)}&limit=20`);
    expect(predictionsResponse.ok()).toBeTruthy();
    const predictionsPayload = await predictionsResponse.json();
    const predictions = predictionItems(predictionsPayload);
    expect(Array.isArray(predictions)).toBe(true);
    expect(predictions.length).toBeGreaterThanOrEqual(1);
    expect(predictions.every((item) => item.status === 'scored'
      ? typeof (item.score ?? item.anomaly_score) === 'number'
      : Boolean(item.status) && Boolean(item.reason))).toBe(true);
    const scoredPredictions = predictions.filter((item) => item.status === 'scored' && typeof (item.score ?? item.anomaly_score) === 'number');
    expect(scoredPredictions.length).toBeGreaterThanOrEqual(1);
    const scoreBeforeCorrection = scoredPredictions.map((item) => [item.id, item.score ?? item.anomaly_score]);

    const reviewResponse = await request.get(`/api/v1/machines/${machineId}/connection/continuity`);
    expect(reviewResponse.ok()).toBeTruthy();
    const review = await reviewResponse.json();
    expect(review.automatic_latest_jump).toBe(false);
    expect(review.available_history).toBeDefined();
    if (review.state === 'gap_detected' && review.last_validated?.stream_id) {
      const stale = await request.post(`/api/v1/machines/${machineId}/connection/continuity/recover`, { data: { decision: 'resume_available', expected_stream_id: review.last_validated.stream_id, expected_cursor: 'stale:cursor', new_stream_id: review.last_validated.stream_id, available_from_sequence: review.available_history.from_sequence, resume_cursor: `${review.last_validated.stream_id}:0`, confirmation: 'I understand the gap and retained history' } });
      expect(stale.status()).toBe(409);
      const available = review.available_history.from_sequence as number;
      const sameStream = await request.post(`/api/v1/machines/${machineId}/connection/continuity/recover`, { data: { decision: 'resume_available', expected_stream_id: review.last_validated.stream_id, expected_cursor: review.last_validated.cursor, new_stream_id: review.last_validated.stream_id, available_from_sequence: available, resume_cursor: `${review.last_validated.stream_id}:${available - 1}`, confirmation: 'I understand the gap and retained history' } });
      expect(sameStream.ok()).toBeTruthy();
      expect((await sameStream.json()).history_gap_preserved).toBe(true);
      await expect.poll(async () => (await readCycles(request)).length, { timeout: 30_000 }).toBeGreaterThan(0);
      const resumed = await readCycles(request);
      expect(new Set(resumed.map(item => item.timestamp)).size).toBe(resumed.length);
      const progressedStatus = await request.get(`${fixtureUrl}/v1/machines/606/status`);
      expect((await progressedStatus.json()).last_cycle_sequence).toBeGreaterThan(previousSequence);

      const reset = await controlFixture(request, { reset_stream: true, emit: 1, retention_floor: 0, profile: 'complete' });
      const newSourceStatus = await request.get(`${fixtureUrl}/v1/machines/606/status`);
      const newStream = (await newSourceStatus.json()).stream_id as string;
      expect(newStream).not.toBe(review.last_validated.stream_id);
      await expect.poll(async () => {
        const response = await request.get(`/api/v1/machines/${machineId}/connection`);
        return response.ok() ? (await response.json()).state : 'unavailable';
      }, { timeout: 30_000 }).toBe('gap_detected');
      const newReview = await (await request.get(`/api/v1/machines/${machineId}/connection/continuity`)).json();
      const newStreamRecovery = await request.post(`/api/v1/machines/${machineId}/connection/continuity/recover`, { data: { decision: 'initialize_new_stream', expected_stream_id: newReview.last_validated.stream_id, expected_cursor: newReview.last_validated.cursor, new_stream_id: newStream, available_from_sequence: null, resume_cursor: null, confirmation: 'I understand the gap and retained history' } });
      expect(newStreamRecovery.ok()).toBeTruthy();
      expect((await newStreamRecovery.json()).history_gap_preserved).toBe(true);
      await expect.poll(async () => (await readCycles(request)).length, { timeout: 30_000 }).toBeGreaterThan(0);
      expect((await readCycles(request)).length).toBeGreaterThan(0);
      expect(reset).toBeTruthy();
    }

    const predictionsAfterCorrection = await request.get(`/api/v1/machines/${machineId}/hdt-predictions?from=${from}&known_at=${encodeURIComponent(to)}&limit=20`);
    expect(predictionsAfterCorrection.ok()).toBeTruthy();
    const predictionsAfter = predictionItems(await predictionsAfterCorrection.json());
    expect(predictionsAfter.filter((item) => item.status === 'scored').map((item) => [item.id, item.score ?? item.anomaly_score])).toEqual(expect.arrayContaining(scoreBeforeCorrection));

    await page.close();
    const isolatedPage = await context.newPage();
    await isolatedPage.goto('/login');
    await expect(isolatedPage.getByLabel('Adresse e-mail')).toBeVisible();
    await isolatedPage.close();
  });

  test('la session authentifiée conserve le rapprochement tardif et les corrections', async ({ request }) => {
    await loginApi(request);
    const imports = await request.get(`/api/v1/sites/${siteId}/erp-imports`);
    expect(imports.ok()).toBeTruthy();
    expect((await imports.json()).items).toBeTruthy();
    const context = await request.get(`/api/v1/machines/${machineId}/production-context?from=${encodeURIComponent(fixtureFrom)}&known_at=${encodeURIComponent(to)}&limit=100`);
    expect(context.ok()).toBeTruthy();
    const body = await context.json();
    const declarations = body.declarations ?? [];
    expect(declarations).toHaveLength(2);
    expect(new Set(declarations.map((item: { production_order_id?: string; order_ref?: string }) => item.production_order_id ?? item.order_ref)).size).toBe(1);
    const revisions = declarations.map((item: { revision_number?: number }) => Number(item.revision_number));
    expect(new Set(revisions).size).toBe(2);
    expect(revisions.some((revision) => revision >= 2)).toBeTruthy();
    expect(body.coverage?.declarations).toBe(2);
  });
});
