import { expect, test, type Page } from "@playwright/test";

const lessons = [
  { id: "linear-search", label: "Linear Search" },
  { id: "binary-search", label: "Binary Search" },
  { id: "bubble-sort", label: "Bubble Sort" },
];
const modes = [
  { id: "static", label: "Static lesson" },
  { id: "rule_based", label: "Rule-based adaptive" },
  { id: "personalized", label: "Personalized adaptive" },
];

async function start(page: Page, lesson: string, mode: string) {
  await page.goto("/");
  await page.getByRole("combobox", { name: "Lesson" }).selectOption(lesson);
  await page.getByRole("button", { name: modes.find((item) => item.id === mode)!.label }).click();
  await page.getByRole("button", { name: /Open lesson/ }).click();
  await expect(page.getByRole("button", { name: /Try a checkpoint/ })).toBeVisible();
}

async function dismissSupport(page: Page) {
  const dialog = page.getByRole("dialog");
  if (await dialog.isVisible()) {
    await dialog.getByRole("button", { name: "Dismiss" }).click();
    await expect(dialog).toBeHidden();
  }
}

async function answerCurrent(page: Page) {
  await dismissSupport(page);
  const card = page.locator(".question-card");
  await expect(card).toBeVisible();
  const previousPrompt = await card.locator("h2").textContent();
  await card.locator(".option-list button").first().click();
  await card.getByRole("button", { name: /Submit answer|Finish question/ }).click();
  await expect.poll(async () => {
    const heading = page.locator(".question-card h2");
    return (await heading.count()) ? heading.textContent() : null;
  }).not.toBe(previousPrompt);
  await dismissSupport(page);
}

for (const lesson of lessons) {
  for (const mode of modes) {
    test(`${mode.id} · ${lesson.id} completes and reconciles`, async ({ page }) => {
      await start(page, lesson.id, mode.id);
      await page.getByRole("button", { name: /Try a checkpoint/ }).click();
      for (let index = 0; index < 9; index++) await answerCurrent(page);
      await expect(page.locator(".results-main h1")).toContainText(lesson.label);
      await expect(page.getByText("checkpoint correct")).toBeVisible();
      await expect(page.getByText("post-test correct")).toBeVisible();
      const session = await page.evaluate(() => JSON.parse(localStorage.getItem("idp.session") || "null"));
      expect(session?.lesson_id).toBe(lesson.id);
      const apiBase = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8093";
      const detail = await page.request.get(`${apiBase}/api/sessions/${session.session_id}`, { headers: { "X-Session-Token": session.access_token } });
      expect(detail.ok()).toBeTruthy();
      const body = await detail.json();
      expect(body.answers.filter((answer: { phase: string }) => answer.phase === "checkpoint")).toHaveLength(6);
      expect(body.answers.filter((answer: { phase: string }) => answer.phase === "post")).toHaveLength(3);
    });
  }
}

test("reload keeps question position and the first completed follow-up", async ({ page }) => {
  await start(page, "binary-search", "personalized");
  await page.getByRole("button", { name: /Try a checkpoint/ }).click();
  await answerCurrent(page);
  const nextPrompt = await page.locator(".question-card h2").textContent();
  await page.reload();
  await expect(page.locator(".question-card h2")).toHaveText(nextPrompt || "");
  await page.getByRole("button", { name: /Need help with this idea/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: /Use this support/ }).click();
  await expect(dialog.getByRole("heading", { name: "One quick check" })).toBeVisible();
  const firstPrompt = await dialog.locator("p").first().textContent();
  await dialog.locator(".option-list button").first().click();
  await expect(dialog.locator("p").first()).not.toHaveText(firstPrompt || "");
  const secondPrompt = await dialog.locator("p").first().textContent();
  await page.reload();
  await expect(page.getByRole("dialog").locator("p").first()).toHaveText(secondPrompt || "");
});
