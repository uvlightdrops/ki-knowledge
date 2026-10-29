import { test, expect, Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/admin/login/?next=/knowledge/workbench/%3Fdomain%3Dbrowser-test");
  await page.locator("#id_username").fill("browser");
  await page.locator("#id_password").fill("browser-test-only");
  await page.locator('input[type="submit"]').click();
  await expect(page.locator("#workbench-root .wb")).toBeVisible();
  await expect(page.getByRole("link", { name: "Textwerkstatt", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("link", { name: "Textwerkstatt", exact: true })).toHaveCSS("background-color", "rgb(109, 40, 217)");
  await expect(page.getByRole("status")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Textwerkstatt", exact: true })).toHaveCount(0);
  await expect(page.getByText("Quellsnapshots bleiben unveränderlich.", { exact: false })).toHaveCount(0);
}

async function capture(page: Page, title: string) {
  const source = page.getByLabel("Markdown-Quelle aus Data Sources");
  const value = await source.locator("option").filter({ hasText: `${title} ·` }).getAttribute("value");
  await source.selectOption(value!);
  await page.getByRole("button", { name: "Snapshot ausdrücklich erfassen" }).click();
  await expect(page.getByRole("status")).toContainText("Unveränderlichen Snapshot");
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
}

test("general discovered Markdown and direct selection work without an InfoSite project", async ({ page }) => {
  await login(page);
  const inventory = await (await page.request.get("/knowledge/workbench/api/sources?domain=browser-test")).json();
  const discovered = inventory.sources.find((source: { title: string }) => source.title === "Unimportiert.md");
  expect(discovered.registered).toBe(false);
  expect(discovered.id).toMatch(/^src_[0-9a-f]{64}$/);
  await page.goto(`/knowledge/workbench/?domain=browser-test&source_id=${discovered.id}`);
  await expect(page.getByLabel("Markdown-Quelle aus Data Sources")).toHaveValue(discovered.id);
  await expect(page.getByRole("button", { name: "Snapshot ausdrücklich erfassen" })).toBeEnabled();
  await expect(page.getByText("Nicht erfassbare Quellen", { exact: false })).toBeVisible();
  await page.getByText("Nicht erfassbare Quellen", { exact: false }).click();
  await expect(page.getByText("Hinweis.pdf:", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Snapshot ausdrücklich erfassen" }).click();
  await expect(page.getByRole("heading", { name: "Unimportiert.md", exact: true })).toBeVisible();
  await expect(page.getByTestId("source-editor")).toContainText("Direkt erfassbar.");
});

async function mark(page: Page, title: string) {
  const editor = page.getByTestId("source-editor").getByRole("textbox");
  await editor.focus();
  await page.keyboard.press("Control+Home");
  await page.keyboard.press("Control+A");
  await expect(page.getByRole("button", { name: "Als Block markieren", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Als Block markieren", exact: true }).click();
  await page.getByLabel("Titel", { exact: true }).fill(title);
  await page.getByLabel("Tags (kommagetrennt)").fill("Versorgung, Test");
  await page.getByLabel("Eigene Notiz", { exact: true }).fill("Nach Browserneustart wiederfinden.");
  await page.getByRole("button", { name: "Metadaten speichern", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("serverseitig gespeichert");
}

test("Unicode selection, metadata, cross-document relation and reload use real Django persistence", async ({ page }) => {
  const errors: string[] = [];
  const external: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => {
    if (!request.url().startsWith("http://127.0.0.1:")) external.push(request.url());
  });
  await login(page);
  await capture(page, "Beeren");
  await mark(page, "Nahrungsversorgung");
  await capture(page, "Planung");
  await mark(page, "Vorratshaltung");
  await page.getByLabel("Beziehung (dieser Block → Ziel)").selectOption("supports");
  await page.getByLabel("Zielblock").selectOption({ label: "Nahrungsversorgung · Beeren" });
  await page.getByLabel("Begründung").fill("Beide sind für die Versorgung wichtig.");
  await page.getByRole("button", { name: "Relation speichern", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Relation serverseitig gespeichert");
  await page.reload();
  await page.getByRole("button", { name: "Planung", exact: true }).click();
  await page.getByRole("button", { name: "Vorratshaltung", exact: true }).click();
  await expect(page.getByLabel("Eigene Notiz", { exact: true })).toHaveValue("Nach Browserneustart wiederfinden.");
  await page.getByRole("button", { name: "Nahrungsversorgung · Beeren", exact: true }).click();
  await expect(page.getByLabel("Titel", { exact: true })).toHaveValue("Nahrungsversorgung");
  await expect(page.getByRole("button", { name: "Vorratshaltung · Planung", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.locator(".wb").evaluate(element => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("draft revisions keep historical anchors and reject parallel overwrites", async ({ page, context }) => {
  await login(page);
  await capture(page, "Beeren");
  const created = page.waitForResponse(response => response.url().includes("/drafts") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Eigene Arbeitskopie anlegen", exact: true }).click();
  const draft = await (await created).json();
  await expect(page.getByRole("status")).toContainText("Eigene Arbeitskopie angelegt");
  await mark(page, "Entwurfsmarkierung");
  const editor = page.getByTestId("source-editor").getByRole("textbox");
  await editor.focus();
  await page.keyboard.press("Control+A");
  await page.keyboard.insertText("# Neue Versorgung\n\nEin anderer Text 🍒.\n");
  await page.getByRole("button", { name: "Textrevision speichern", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Neue Textrevision serverseitig gespeichert");
  await expect(page.getByRole("heading", { name: "Historische Markierungen", exact: true })).toBeVisible();
  await editor.focus();
  await page.keyboard.press("Control+Home");
  await page.keyboard.press("Control+A");
  await page.getByRole("button", { name: "Dieser Auswahl zuordnen", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Neue Zuordnung ausdrücklich bestätigt");
  await expect(page.getByRole("heading", { name: "Historische Markierungen", exact: true })).not.toBeVisible();
  const other = await context.newPage();
  await other.goto("/knowledge/workbench/?domain=browser-test");
  await other.getByRole("button", { name: `${draft.title} · Arbeitskopie`, exact: true }).click();
  await expect(other.getByRole("heading", { name: draft.title, exact: true })).toBeVisible();
  await editor.focus();
  await page.keyboard.press("Control+A");
  await page.keyboard.insertText("# Serverstand\n\nErste Änderung.\n");
  await page.getByRole("button", { name: "Textrevision speichern", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Neue Textrevision serverseitig gespeichert");
  await other.getByTestId("source-editor").getByRole("textbox").focus();
  await other.keyboard.press("Control+A");
  await other.keyboard.insertText("# Eigene Fassung\n\nNicht verlieren.\n");
  await other.getByRole("button", { name: "Textrevision speichern", exact: true }).click();
  await expect(other.getByText("Konflikt: Deine Textänderung wurde nicht überschrieben.", { exact: true })).toBeVisible();
  await expect(other.getByTestId("source-editor")).toContainText("Nicht verlieren.");
  await expect(other.getByText("Aktueller Serverstand", { exact: false })).toBeVisible();
  await other.close();
});

test("own note and explicit unsaved chat context persist without changing text", async ({ page }) => {
  await login(page);
  await page.getByLabel("Neue eigene Notiz").fill("Gesprächsnotiz");
  await page.getByRole("button", { name: "Leere Notiz anlegen", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Eigene Notiz angelegt");
  await expect(page.getByText("browser-mock", { exact: true })).toBeVisible();
  const editor = page.getByTestId("source-editor").getByRole("textbox");
  await editor.focus();
  await page.keyboard.insertText("# Ungespeicherte Hypothese\n\nWildbeeren allein genügen nicht.\n");
  await page.getByRole("button", { name: "Neues Gespräch starten", exact: true }).click();
  await expect(page.getByText("Die nächste Anfrage überträgt und speichert", { exact: false })).toBeVisible();
  await page.getByLabel("Nachricht", { exact: true }).fill("Welche Unsicherheit bleibt?");
  const sent = page.waitForResponse(response => response.url().includes("/messages") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Fragen", exact: true }).click();
  const response = await sent;
  const turn = await response.json();
  expect(response.status(), JSON.stringify(turn)).toBe(201);
  expect(turn.context.unsaved).toBe(true);
  expect(turn.context.sources[0].text).toContain("Ungespeicherte Hypothese");
  await expect(page.getByText("Testantwort zur ausgewählten Quelle.", { exact: true })).toBeVisible();
  await expect(page.getByText("Text noch nicht gespeichert.", { exact: true })).toBeVisible();
  page.once("dialog", dialog => dialog.accept());
  await page.reload();
  await page.getByRole("button", { name: "Gesprächsnotiz · Arbeitskopie", exact: true }).click();
  await page.getByLabel("Gespeichertes Gespräch (diese Revision)").selectOption({ index: 1 });
  await expect(page.getByText("Testantwort zur ausgewählten Quelle.", { exact: true })).toBeVisible();
  await expect(page.getByTestId("source-editor")).not.toContainText("Ungespeicherte Hypothese");
  await page.getByText("Tatsächlich übermittelter Kontext", { exact: false }).click();
  await expect(page.locator(".wb-messages pre")).toContainText("Ungespeicherte Hypothese");
  await page.getByLabel("Nachricht", { exact: true }).fill("PROVIDER_FAILURE");
  const failed = page.waitForResponse(response => response.url().includes("/messages") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Fragen", exact: true }).click();
  expect((await failed).status()).toBe(502);
  await expect(page.locator(".wb-messages")).toContainText("failed");
  await expect(page.locator(".wb-messages")).toContainText("ProviderError");
  await page.getByRole("button", { name: "Anfrage freigeben, danach bewusst neu senden", exact: true }).click();
  await page.getByLabel("Nachricht", { exact: true }).fill("");
});
