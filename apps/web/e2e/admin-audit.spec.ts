import { expect, test } from "@playwright/test";
import { loginAsCfo } from "./helpers/auth";

test.describe("Admin audit log", () => {
  test("CFO can browse audit trail", async ({ page }) => {
    await loginAsCfo(page);
    await page.getByRole("link", { name: "Admin" }).click();
    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();

    await page.getByRole("button", { name: "Audit log" }).click();
    await expect(page.getByRole("heading", { name: "Audit log" })).toBeVisible();

    const table = page.locator("table").filter({ has: page.getByRole("columnheader", { name: "Action" }) });
    await expect(table.locator("tbody tr").first()).toBeVisible({ timeout: 15_000 });
    await expect(table.getByText("user.login").first()).toBeVisible();
  });
});
