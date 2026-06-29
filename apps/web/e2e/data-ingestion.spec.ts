import path from "node:path";
import { expect, test } from "@playwright/test";
import { loginAsCfo } from "./helpers/auth";

test.describe("Data sources & ingestion", () => {
  test("register source and upload CSV completes job", async ({ page }) => {
    await loginAsCfo(page);
    await page.getByRole("link", { name: "Data Sources" }).click();
    await expect(page).toHaveURL(/\/data$/);
    await expect(page.getByRole("heading", { name: "Data Sources" })).toBeVisible();

    const sourceName = `E2E File Drop ${Date.now()}`;
    await page.getByPlaceholder("e.g. QuickBooks Production").fill(sourceName);
    await page.getByRole("button", { name: "Register source" }).click();
    await expect(page.getByRole("heading", { name: sourceName })).toBeVisible();

    const csvPath = path.join(__dirname, "fixtures", "customers.csv");
    await page.locator("#ingestion-file").setInputFiles(csvPath);
    await expect(page.getByText("customers.csv")).toBeVisible();
    await page.getByRole("button", { name: "Upload & ingest" }).click();

    await expect(page.getByText("completed", { exact: true }).first()).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByText("2 rows")).toBeVisible();
    await expect(page.getByText("Job detail")).toBeVisible();
  });
});
