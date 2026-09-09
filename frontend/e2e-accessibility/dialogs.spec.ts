import { test, expect } from '@playwright/test';

for (const kind of ['presse', 'planning']) {
  test(`${kind}: extérieur, glisser, attente, inertie, Tab et restauration (composant réel)`, async ({ page }) => {
    let release!: () => void;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/a11y-save', async route => { await pending; await route.fulfill({ status: 409, body: '{}' }); });
    await page.goto('/e2e-accessibility/dialogs.html');
    const trigger = page.getByRole('button', { name: `Ouvrir ${kind}`, exact: true });
    const dialog = page.getByRole('dialog');
    const field = page.getByLabel(kind === 'presse' ? 'Nom de la presse' : 'Numéro OF', { exact: true });
    await trigger.click();
    await expect(field).toBeFocused();
    expect(await dialog.evaluate(el => el.matches(':modal'))).toBe(true);
    await trigger.evaluate(el => (el as HTMLElement).focus());
    await expect(field).toBeFocused();
    const buttons = dialog.getByRole('button');
    await buttons.last().focus(); await page.keyboard.press('Tab'); await expect(buttons.first()).toBeFocused();
    await page.keyboard.press('Shift+Tab'); await expect(buttons.last()).toBeFocused();
    await field.click(); await expect(dialog).toBeVisible();
    const box = (await field.boundingBox())!;
    await page.mouse.move(box.x + 5, box.y + 5); await page.mouse.down();
    await page.mouse.move(10, 100); await page.mouse.up();
    await expect(dialog).toBeVisible();
    await page.mouse.click(10, 100);
    await expect(dialog).toHaveCount(0); await expect(trigger).toBeFocused();
    await trigger.click(); await expect(field).toBeFocused();
    await field.fill(kind === 'presse' ? 'Presse audit' : '000123');
    if (kind === 'presse') await page.getByLabel('Code atelier', { exact: true }).fill('P-606');
    else {
      await page.getByLabel('Début prévu').fill('2026-06-01T08:00');
      await page.getByLabel('Fin prévue').fill('2026-06-01T09:00');
    }
    await dialog.getByRole('button', { name: kind === 'presse' ? 'Ajouter la presse' : 'Planifier l’OF', exact: true }).click();
    await expect(dialog.getByRole('status')).toBeVisible();
    await page.mouse.click(10, 100); await expect(dialog).toBeVisible();
    await page.keyboard.press('Escape'); await expect(dialog).toBeVisible();
    expect(await dialog.evaluate(el => el.matches(':modal'))).toBe(true);
    release();
    await expect(dialog.getByRole('alert')).toContainText('Refus simulé');
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0); await expect(trigger).toBeFocused();
  });
}
