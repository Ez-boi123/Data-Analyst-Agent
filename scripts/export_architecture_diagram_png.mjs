import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..");
const require = createRequire(import.meta.url);
const { chromium } = require("../node_modules/playwright");

const input = path.join(root, "docs", "data_agent_backend_architecture_v2.svg");
const output = path.join(root, "docs", "data_agent_backend_architecture_v2.png");
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await chromium.launch({
  executablePath: chromePath,
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1920, height: 1216 }, deviceScaleFactor: 1 });
await page.setContent(`<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <style>
      html, body { margin: 0; padding: 0; background: #ffffff; }
      img { display: block; width: 1920px; height: 1216px; }
    </style>
  </head>
  <body>
    <img src="file://${input}" alt="Data Analyst Agent backend architecture" />
  </body>
</html>`);
await page.screenshot({ path: output, fullPage: false });
await browser.close();
console.log(output);
