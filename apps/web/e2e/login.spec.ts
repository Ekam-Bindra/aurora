import { expect, test } from "@playwright/test";
import { loginAsCfo } from "./helpers/auth";

test.describe("Login & overview", () => {
  test("CFO login loads dashboard KPIs", async ({ page }) => {
    await loginAsCfo(page);

    await expect(page.getByText("Welcome,")).toBeVisible();
    await expect(page.getByText("Revenue (MTD)")).toBeVisible();
    await expect(page.getByText("Gross Margin")).toBeVisible();
    await expect(page.getByText("Operating Margin")).toBeVisible();

    const kpiValues = page.locator("section.grid").first().locator(".tabular-nums");
    await expect(kpiValues.first()).toBeVisible();
    await expect(kpiValues.first()).not.toHaveText("");
  });
});
