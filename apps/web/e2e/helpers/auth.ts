import { expect, type Page } from "@playwright/test";

export const DEMO_EMAIL = "cfo@nimbus.test";
export const DEMO_PASSWORD = "aurora-demo-2026";

/** Sign in as the demo CFO and wait for the executive dashboard. */
export async function loginAsCfo(page: Page): Promise<void> {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "AURORA" })).toBeVisible();
  await page.locator('input[type="email"]').fill(DEMO_EMAIL);
  await page.locator('input[type="password"]').fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("heading", { name: "Executive Dashboard" })).toBeVisible();
}
