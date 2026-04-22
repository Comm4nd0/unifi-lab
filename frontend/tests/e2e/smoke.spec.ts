import { expect, test } from "@playwright/test";

/**
 * End-to-end smoke test: log in with the seeded admin account, add a
 * controller target, create a virtual device against it, and verify the
 * device row renders.
 *
 * Prereqs the runner must satisfy (not enforced here to keep the suite
 * portable):
 *   - Daphne on :8003 with the config from seed_example_data.
 *   - Vite dev server on :5173 (or UVL_WEB_BASE_URL pointing elsewhere).
 *   - UVL_ADMIN_EMAIL / UVL_ADMIN_PASSWORD match the seed.
 *
 * Run: `npm run test:e2e` from frontend/.
 */

const ADMIN_EMAIL = process.env.UVL_ADMIN_EMAIL ?? "admin@uvl.local";
const ADMIN_PASSWORD = process.env.UVL_ADMIN_PASSWORD ?? "devpassword";

test.beforeEach(async ({ context }) => {
  await context.clearCookies();
  await context.addInitScript(() => window.localStorage.clear());
});

test("login -> add controller -> create device", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);

  await page.locator('input[type="email"]').fill(ADMIN_EMAIL);
  await page.locator('input[type="password"]').fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // Add a uniquely named controller so the test is idempotent.
  const controllerName = `E2E Controller ${Date.now()}`;
  await page.getByRole("link", { name: "Controllers" }).click();
  await expect(page.getByRole("heading", { name: "Controllers" })).toBeVisible();
  await page.getByRole("button", { name: /add controller/i }).click();

  // Form fields, in document order: Name, Inform URL, API URL, API username, API password, [verify TLS checkbox].
  const formInputs = page.locator("form input:not([type='checkbox'])");
  await formInputs.nth(0).fill(controllerName);
  await formInputs.nth(1).fill("https://e2e.invalid:443");
  await formInputs.nth(2).fill("https://e2e.invalid:443/api");
  await formInputs.nth(3).fill("e2e-user");
  await formInputs.nth(4).fill("e2e-password");
  await page.getByRole("button", { name: /^create$/i }).click();

  await expect(page.getByRole("cell", { name: controllerName })).toBeVisible();

  // Now create a device against it.
  await page.getByRole("link", { name: "Devices" }).click();
  await expect(page.getByRole("heading", { name: "Devices" })).toBeVisible();
  await page.getByRole("button", { name: /add device/i }).click();

  // The controller select is the second select on the form (model, controller).
  const selects = page.locator("form select");
  await selects.nth(1).selectOption({ label: controllerName });
  await page.getByPlaceholder("8.3.42").fill("8.3.42");
  await page.getByRole("button", { name: /^create$/i }).click();

  // Verify the device row renders, linked to our controller.
  await expect(page.getByRole("cell", { name: controllerName })).toBeVisible();
  await expect(page.getByText("pending").first()).toBeVisible();
});
