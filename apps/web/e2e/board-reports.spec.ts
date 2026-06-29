import { expect, test } from "@playwright/test";
import { loginAsCfo } from "./helpers/auth";

test.describe("Board reports", () => {
  test("generate board pack shows status and download", async ({ page }) => {
    await loginAsCfo(page);
    await page.getByRole("link", { name: "Board Reports" }).click();
    await expect(page).toHaveURL(/\/reports$/);

    const title = `E2E Board Pack ${Date.now()}`;
    await page.getByLabel("Title").fill(title);
    await page.getByRole("button", { name: "Generate board pack" }).click();

    await expect(page.getByRole("button", { name: "Download PDF" })).toBeVisible({
      timeout: 90_000,
    });

    const reportRow = page.getByRole("button").filter({ hasText: title });
    await expect(reportRow).toBeVisible();
    await expect(reportRow.getByText(/in review|ready|approved/i)).toBeVisible();
  });
});
