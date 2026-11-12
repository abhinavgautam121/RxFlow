import { test, expect } from "@playwright/test";

test("executive values match the API and global filters update the cohort", async ({
  page,
  request,
}) => {
  const response = await request.get("/api/v1/overview");
  const overview = await response.json();
  await page.goto("/overview");
  await expect(
    page.getByRole("heading", { name: "Executive overview", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".stat").first()).toContainText(
    overview.kpis.total_orders.toLocaleString("en-IN"),
  );
  await page.getByLabel("City", { exact: true }).selectOption("Bengaluru");
  const filtered = await (
    await request.get("/api/v1/overview?city=Bengaluru")
  ).json();
  await expect(page.locator(".stat").first()).toContainText(
    filtered.kpis.total_orders.toLocaleString("en-IN"),
  );
  await page.screenshot({
    path: "../docs/screenshots/executive.png",
    fullPage: true,
  });
});

test("all nine pages load without uncaught errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const route of [
    "overview",
    "delivery",
    "zones",
    "partners",
    "inventory",
    "predictive",
    "simulation",
    "quality",
    "methodology",
  ]) {
    await page.goto("/" + route);
    await expect(page.locator("main h1")).toBeVisible();
    await expect(page.locator(".loading")).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
  }
  expect(errors).toEqual([]);
});

test("simulation saves a measured baseline and projected result", async ({
  page,
}) => {
  await page.goto("/simulation");
  await page
    .getByLabel("Scenario name", { exact: true })
    .fill("Recruiter walkthrough");
  await page.getByRole("button", { name: "Run & save scenario" }).click();
  await expect(page.getByText("Assumptions & provenance")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Recruiter walkthrough" }),
  ).toBeVisible();
  await expect(
    page.getByText("Historical delay rate (%)", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/simulation.png",
    fullPage: true,
  });
});

test("prediction workbench estimates probability and exports quality evidence", async ({
  page,
}) => {
  await page.goto("/predictive");
  await page.getByRole("button", { name: "Estimate delay risk" }).click();
  await expect(page.getByText("Estimated delay probability")).toBeVisible();
  await page.goto("/quality");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Export CSV" }).first().click(),
  ]);
  expect(download.suggestedFilename()).toBe("rxflow-quality.csv");
});

test("navigation and filter layout works on a phone viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/overview");
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page
    .getByRole("link", { name: "Inventory intelligence", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Inventory intelligence", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
