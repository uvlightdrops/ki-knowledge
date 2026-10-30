import { test, expect, Page } from "@playwright/test";

async function loginSettings(page: Page, compact = false) {
  await page.goto(`/admin/login/?next=/settings/config/${compact ? "c2/" : ""}`);
  await page.locator("#id_username").fill("browser");
  await page.locator("#id_password").fill("browser-test-only");
  await page.locator('input[type="submit"]').click();
  await expect(page.getByRole("heading", { name: compact ? "C2 · Konfiguration" : "Live-Konfiguration", exact: true })).toBeVisible();
}

function fieldForm(page: Page, path: string) {
  return page.locator(`[data-config-path="${path}"]`);
}

test("shared live settings persist typed values and reject stale edits without revealing credentials", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await loginSettings(page);
  await expect(page.locator("body")).not.toContainText("browser-secret-must-stay-hidden");

  const title = fieldForm(page, "infosite.title");
  const staleRevision = await page.locator('input[name="revision"]').inputValue();
  const csrf = await page.locator('input[name="csrfmiddlewaretoken"]').first().inputValue();
  await title.getByRole("checkbox", { name: "Neuen Wert übernehmen" }).check();
  await title.getByLabel("infosite.title", { exact: true }).fill("Browser settings title");
  await page.getByRole("button", { name: "Ausgewählte Änderungen speichern" }).click();
  await expect(page.getByRole("status")).toContainText(/gespeichert/i);
  await page.reload();
  await expect(page.locator("body")).toContainText("Browser settings title");

  const conflict = await page.request.post("/settings/config/", {
    form: {
      csrfmiddlewaretoken: csrf,
      revision: staleRevision,
      change: "infosite.title",
      "value:infosite.title": "Stale edit must never win",
    },
  });
  expect(conflict.status()).toBe(409);
  await page.reload();
  await expect(page.locator("body")).toContainText("Browser settings title");
  await expect(page.locator("body")).not.toContainText("Stale edit must never win");

  const hosts = fieldForm(page, "apps.ki_knowledge.django.allowed_hosts");
  await hosts.getByRole("checkbox", { name: "Neuen Wert übernehmen" }).check();
  await hosts.getByLabel("apps.ki_knowledge.django.allowed_hosts", { exact: true }).fill('["localhost", "browser.invalid"]');
  await page.getByRole("button", { name: "Ausgewählte Änderungen speichern" }).click();
  await expect(page.getByRole("status")).toContainText(/gespeichert/i);
  await page.reload();
  await expect(page.locator("body")).toContainText("browser.invalid");
  await expect(page.locator("body")).not.toContainText("browser-secret-must-stay-hidden");

  await fieldForm(page, "infosite.title").locator('input[name="remove"]').check();
  await page.getByRole("button", { name: "Ausgewählte Änderungen speichern" }).click();
  await expect(page.getByRole("status")).toContainText(/gespeichert/i);
  await page.reload();
  await expect(page.locator("body")).not.toContainText("Browser settings title");
  await expect(page.locator("body")).not.toContainText("Configuration changed");

  const provider = fieldForm(page, "llm.provider");
  await provider.getByRole("checkbox", { name: "Neuen Wert übernehmen" }).check();
  await provider.getByLabel("llm.provider", { exact: true }).selectOption({ label: "ollama" });
  const enabled = fieldForm(page, "infosite.enabled");
  await enabled.getByRole("checkbox", { name: "Neuen Wert übernehmen" }).check();
  await enabled.getByLabel("infosite.enabled", { exact: true }).selectOption("true");
  await page.getByRole("button", { name: "Ausgewählte Änderungen speichern" }).click();
  await expect(page.getByRole("status")).toContainText(/gespeichert/i);
  await page.reload();
  expect(JSON.parse(await fieldForm(page, "llm.provider").getByLabel("llm.provider", { exact: true }).inputValue())).toBe("ollama");
  await expect(fieldForm(page, "infosite.enabled").getByLabel("infosite.enabled", { exact: true })).toHaveValue("true");
  expect(errors).toEqual([]);
});

test("credentials are write-only, revision-protected and explicitly removable", async ({ page }) => {
  await loginSettings(page);
  const path = "llm.providers.openai.api_key";
  const secret = "synthetic-browser-only-credential";
  const secretForm = () => page.locator("form").filter({
    has: page.locator(`input[name="secret_path"][value="${path}"]`),
  }).filter({ has: page.locator('input[name="action"][value="save_secret"]') });
  const staleRevision = await secretForm().locator('input[name="creds_revision"]').inputValue();
  const csrf = await secretForm().locator('input[name="csrfmiddlewaretoken"]').inputValue();
  await secretForm().getByLabel(path, { exact: true }).fill(secret);
  await secretForm().getByRole("button", { name: "Zugangsdaten speichern" }).click();
  await expect(page.getByRole("status")).toContainText(/gespeichert/i);
  await page.reload();
  expect(await page.content()).not.toContain(secret);
  await expect(secretForm().getByLabel(path, { exact: true })).toHaveValue("");

  const conflict = await page.request.post("/settings/config/", {
    form: {
      csrfmiddlewaretoken: csrf,
      action: "save_secret",
      creds_revision: staleRevision,
      secret_path: path,
      secret_value: "synthetic-stale-credential",
    },
  });

  expect(conflict.status()).toBe(409);
  expect(await conflict.text()).not.toContain("synthetic-stale-credential");
  await page.reload();

  const removeForm = page.locator("form").filter({
    has: page.locator(`input[name="secret_path"][value="${path}"]`),
  }).filter({ has: page.locator('input[name="action"][value="remove_secret"]') });
  await removeForm.getByRole("checkbox").check();
  await removeForm.getByRole("button", { name: "Override entfernen" }).click();
  await expect(page.getByRole("status")).toContainText(/gespeichert/i);
  await page.reload();
  expect(await page.content()).not.toContain(secret);
  await expect(secretForm().getByLabel(path, { exact: true })).toHaveValue("");
});

test("C2 is compact, hierarchical and uses the same protected config store", async ({ page }) => {
    await loginSettings(page, true);
    await expect(page.getByRole("link", { name: "C2", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Ausführliche Ansicht" })).toHaveAttribute("href", "/settings/config/");
    const title = fieldForm(page, "infosite.title");
    const input = title.getByLabel("infosite.title", { exact: true });
    const bounds = await input.boundingBox();
    expect(bounds!.height).toBeLessThanOrEqual(28);
    expect(bounds!.width).toBeLessThanOrEqual(260);
    await expect(title.locator(".wk-c2-name")).toHaveCSS("padding-left", "14px");
    await expect(fieldForm(page, "llm.providers.ollama.model").locator(".wk-c2-name")).toHaveCSS("padding-left", "42px");
    const revision = await page.locator('input[name="revision"]').inputValue();
    const csrf = await page.locator('input[name="csrfmiddlewaretoken"]').first().inputValue();
    await input.fill("Compact C2 title");
    await title.getByRole("checkbox", { name: "Änderung übernehmen: infosite.title", exact: true }).check();
    const provider = fieldForm(page, "llm.provider");
    await provider.getByLabel("llm.provider", { exact: true }).selectOption({ label: "mock" });
    await provider.getByRole("checkbox", { name: "Änderung übernehmen: llm.provider", exact: true }).check();
    await page.getByRole("button", { name: "Ausgewählte Änderungen speichern" }).click();
    await expect(page.getByRole("status")).toContainText(/gespeichert/i);
    await page.reload();
    await expect(input).toHaveValue("Compact C2 title");
    const stale = await page.request.post("/settings/config/c2/", {
      form: {
        csrfmiddlewaretoken: csrf, revision, change: "infosite.title",
        "value:infosite.title": "Must not overwrite",
      },
    });
    expect(stale.status()).toBe(409);
    await page.goto("/settings/config/");
    await expect(page.getByLabel("infosite.title", { exact: true })).toHaveValue("Compact C2 title");
    await page.getByRole("link", { name: "C2", exact: true }).click();
    await expect(page.getByRole("heading", { name: "C2 · Konfiguration" })).toBeVisible();

    const secretRow = page.locator('[data-secret-path="llm.providers.openai.api_key"]');
    const secret = "synthetic-c2-write-only";
    await secretRow.getByLabel("llm.providers.openai.api_key", { exact: true }).fill(secret);
    await secretRow.getByRole("button", { name: "Speichern", exact: true }).click();
    await expect(page.getByRole("status")).toContainText(/gespeichert/i);
    expect(await page.content()).not.toContain(secret);
    await expect(secretRow.getByLabel("llm.providers.openai.api_key", { exact: true })).toHaveValue("");
    await secretRow.getByRole("checkbox").check();
    await secretRow.getByRole("button", { name: "−", exact: true }).click();
    await expect(page.getByRole("status")).toContainText(/gespeichert/i);
    await page.setViewportSize({ width: 390, height: 844 });
    const dimensions = await page.evaluate(() => ({
      width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width + 1);
});
