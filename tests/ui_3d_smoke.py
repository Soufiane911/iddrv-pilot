from playwright.sync_api import sync_playwright


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto("http://127.0.0.1:5173/sites/1/workshop", wait_until="networkidle")
    page.get_by_role("button", name="Vue 3D").click()
    page.locator(".three-canvas-wrap canvas").wait_for()
    assert page.locator(".three-canvas-wrap").count() == 1
    browser.close()
