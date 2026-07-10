from playwright.sync_api import sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

    page.goto("http://127.0.0.1:5173/sites", wait_until="networkidle")
    page.get_by_role("heading", name="Vos ateliers, en un coup d’œil").wait_for()
    page.get_by_role("button", name="Ouvrir l’atelier").click()
    page.get_by_role("img", name="Plan 2D de l’atelier").wait_for()
    page.locator("g.machine-node").nth(2).click()
    page.get_by_label("Position dans la période historique").fill("75")
    page.locator("a[href^='/incidents/']").first.click()
    page.get_by_role("heading", name="short shot increase").wait_for()
    page.get_by_role("button", name="Lancer l’investigation").wait_for()
    page.screenshot(path="/tmp/iddrv-g3-smoke.png", full_page=True)
    assert not errors, errors
    browser.close()
