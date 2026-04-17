import { expect, test } from "@playwright/test";

test("home page creates an analysis task from the prompt composer", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "数据分析Agent" })).toBeVisible();
  await expect(page.getByText("华东区 GMV 下滑归因")).toBeVisible();

  const promptInput = page.getByLabel("输入分析提示词");
  await expect(promptInput).toBeVisible();

  await promptInput.fill("为什么华东区最近 7 天 GMV 下滑？");
  await page.getByRole("button", { name: "发送并创建任务" }).click();

  await expect(page).toHaveURL(/\/tasks\/task-gmv-east-7d\?q=/);
  await expect(page.getByText("Agent 对话")).toBeVisible();
  await expect(page.getByText("证据时间线")).toBeVisible();
});

test("home prompt composer submits with Enter", async ({ page }) => {
  await page.goto("/");

  const promptInput = page.getByLabel("输入分析提示词");
  await promptInput.fill("按渠道拆解华东区最近 7 天 GMV 下滑原因");
  await promptInput.press("Enter");

  await expect(page).toHaveURL(/\/tasks\/task-gmv-east-7d\?q=/);
  await expect(page.getByText("Agent 对话")).toBeVisible();
});

test("workbench exposes SQL repair, result preview, and audit details", async ({ page }) => {
  await page.goto("/tasks/task-gmv-east-7d");

  await expect(page.getByText("SQL 错误自修复").first()).toBeVisible();
  await expect(page.getByText("字段不存在：fact_refunds.refund_amount。Schema 中可用字段为 refund_amt。")).toBeVisible();
  await expect(page.getByText("-  refund_amount")).toBeVisible();
  await expect(page.getByText("+  refund_amt")).toBeVisible();
  await expect(page.getByText("结果预览")).toBeVisible();

  await page.getByRole("button", { name: "审计", exact: true }).click();
  await expect(page.getByText("发起人：Lina Chen")).toBeVisible();
  await expect(page.getByText("追问分支：2 个")).toBeVisible();
});

test("share page supports review, comments, and analysis branches", async ({ page }) => {
  await page.goto("/share/tasks/task-gmv-east-7d");

  await expect(page.getByRole("heading", { name: /分享页/ })).toBeVisible();
  await expect(page.getByText("评论与追问")).toBeVisible();
  await expect(page.getByRole("heading", { name: "分析分支" })).toBeVisible();
  await expect(page.getByRole("button", { name: /继续追问/ })).toBeVisible();
  await expect(page.getByText("追问：广告渠道是否异常？")).toBeVisible();
});

test("supporting product pages render data source, glossary, and settings scope", async ({ page }) => {
  await page.goto("/data-sources");
  await expect(page.getByRole("heading", { name: "数据源 / Schema" })).toBeVisible();
  await expect(page.getByText("交易数仓")).toBeVisible();
  await expect(page.getByText("同步中", { exact: true })).toBeVisible();

  await page.goto("/glossary");
  await expect(page.getByRole("heading", { name: "业务词典 / 指标口径" })).toBeVisible();
  await expect(page.getByText("GMV", { exact: true })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "设置" })).toBeVisible();
  await expect(page.getByText("中文：分析任务 / 表结构 Schema")).toBeVisible();
});

test("mobile share review keeps the delivery flow readable", async ({ page, isMobile }) => {
  test.skip(!isMobile, "mobile review check runs only on the mobile project");

  await page.goto("/share/tasks/task-gmv-east-7d");

  await expect(page.getByRole("heading", { name: /分享页/ })).toBeVisible();
  await expect(page.getByText("华东区 GMV 下降主要由推荐和广告渠道转化率下滑驱动。")).toBeVisible();
  await expect(page.getByText("结果预览")).toBeVisible();
});
