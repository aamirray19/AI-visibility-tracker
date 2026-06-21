import { expect, test } from "@playwright/test";

test("renders the baseline app shell", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", {
      name: "Campaign analytics for brand visibility in AI answers"
    })
  ).toBeVisible();
});
