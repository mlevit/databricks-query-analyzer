import { test, expect } from "@playwright/test";

test.describe("Navigation", () => {
  test("loads the home page with analyze form", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=Databricks Query Analyzer")).toBeVisible();
    await expect(page.locator("text=Analyze")).toBeVisible();
  });

  test("navigates to SQL Analyzer page", async ({ page }) => {
    await page.goto("/");
    await page.click("text=SQL Analyzer");
    await expect(page.locator("text=Paste SQL")).toBeVisible();
  });

  test("navigates to Workload Scan page", async ({ page }) => {
    await page.goto("/");
    await page.click("text=Workload Scan");
    await expect(page.locator("text=Workload Scanner")).toBeVisible();
    await expect(page.locator("text=Scan Workload")).toBeVisible();
  });

  test("navigates to Trends page", async ({ page }) => {
    await page.goto("/");
    await page.click("text=Trends");
    await expect(page.locator("text=Trends & History")).toBeVisible();
  });

  test("navigates to Tables page", async ({ page }) => {
    await page.goto("/");
    await page.click("text=Tables");
    await expect(page.locator("text=Table Health")).toBeVisible();
  });

  test("navigates to Warehouses page", async ({ page }) => {
    await page.goto("/");
    await page.click("text=Warehouses");
    await expect(page.locator("text=Warehouse Fleet")).toBeVisible();
  });
});

test.describe("SQL Analyzer", () => {
  test("shows textarea for SQL input", async ({ page }) => {
    await page.goto("/sql");
    const textarea = page.locator("textarea");
    await expect(textarea).toBeVisible();
    await expect(page.locator("text=Analyze SQL")).toBeVisible();
  });

  test("shows error for empty SQL", async ({ page }) => {
    await page.goto("/sql");
    await page.click("text=Analyze SQL");
    await expect(page.locator("text=Please enter SQL")).toBeVisible();
  });
});

test.describe("Dark Mode", () => {
  test("toggles dark mode", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    const hasDark = await html.evaluate((el) => el.classList.contains("dark"));

    await page.click("[aria-label='Toggle dark mode']");

    const hasDarkAfter = await html.evaluate((el) => el.classList.contains("dark"));
    expect(hasDarkAfter).not.toBe(hasDark);
  });
});
