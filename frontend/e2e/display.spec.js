import { test, expect } from "@playwright/test";
import { atRule } from "postcss";

/**
 * Test the display screen.
 */
test("Checks if the page is display", async ({ page }) => {
  await page.goto("/display");
  expect(await page.title()).toBe("Display");
});

/**
 * Test the checkbox for display PDF when.
 */
test("Check if show document checkbox can be enabled", async ({ page }) => {
  await page.goto("/display");
  await page.check("#output-show-document");
  expect(await page.isChecked("#output-show-document")).toBeTruthy();
});

/**
 * Test the checkbox for display PDF when disabled.
 */
test("Check if show document checkbox can be disabled", async ({ page }) => {
  await page.goto("/display");
  await page.uncheck("#output-show-document");
  expect(await page.isChecked("#output-show-document")).toBeFalsy();
});

/**
 * Test to see if renderer is visible when checkbox is ticked.
 */
test("Check visibility of pdf render", async ({ page }) => {
  await page.goto("/display");
  await page.check("#output-show-document");
  expect(await page.isVisible("#pdf-renderer")).toBeTruthy();
});

/**
 * Test to see if renderer is invisible when checkbox is unticked.
 */
test("Check if pdf render is invisible", async ({ page }) => {
  await page.goto("/display");
  await page.uncheck("#output-show-document");
  expect(await page.isHidden("#pdf-renderer")).toBeTruthy();
});
