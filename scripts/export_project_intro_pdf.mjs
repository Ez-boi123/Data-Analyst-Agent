import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..");
const require = createRequire(import.meta.url);
const { chromium } = require("../node_modules/playwright");

const input = path.join(root, "docs", "project_introduction.md");
const output = path.join(root, "docs", "project_introduction.pdf");
const htmlOutput = path.join(root, "docs", "project_introduction.html");
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function inlineMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  return html;
}

function closeList(state, html) {
  if (state.list === "ul") html.push("</ul>");
  if (state.list === "ol") html.push("</ol>");
  state.list = "";
}

function renderTable(lines, start) {
  const rows = [];
  let index = start;
  while (index < lines.length && /^\s*\|.*\|\s*$/.test(lines[index])) {
    rows.push(lines[index]);
    index += 1;
  }

  const parseRow = (line) =>
    line
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((cell) => inlineMarkdown(cell.trim()));

  const headers = parseRow(rows[0]);
  const bodyRows = rows.slice(2).map(parseRow);
  const html = ["<table>", "<thead><tr>"];
  for (const header of headers) html.push(`<th>${header}</th>`);
  html.push("</tr></thead>", "<tbody>");
  for (const row of bodyRows) {
    html.push("<tr>");
    for (const cell of row) html.push(`<td>${cell}</td>`);
    html.push("</tr>");
  }
  html.push("</tbody></table>");
  return { html: html.join("\n"), next: index };
}

function markdownToHtml(markdown) {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  const state = { list: "", code: false, codeLines: [] };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];

    if (line.startsWith("```")) {
      if (state.code) {
        html.push(`<pre><code>${escapeHtml(state.codeLines.join("\n"))}</code></pre>`);
        state.code = false;
        state.codeLines = [];
      } else {
        closeList(state, html);
        state.code = true;
      }
      continue;
    }

    if (state.code) {
      state.codeLines.push(line);
      continue;
    }

    if (!line.trim()) {
      closeList(state, html);
      continue;
    }

    if (/^\s*\|.*\|\s*$/.test(line) && index + 1 < lines.length && /^\s*\|?[\s:-]+\|/.test(lines[index + 1])) {
      closeList(state, html);
      const table = renderTable(lines, index);
      html.push(table.html);
      index = table.next - 1;
      continue;
    }

    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      closeList(state, html);
      const level = heading[1].length;
      html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    const unordered = /^\s*-\s+(.+)$/.exec(line);
    if (unordered) {
      if (state.list !== "ul") {
        closeList(state, html);
        html.push("<ul>");
        state.list = "ul";
      }
      html.push(`<li>${inlineMarkdown(unordered[1])}</li>`);
      continue;
    }

    const ordered = /^\s*\d+\.\s+(.+)$/.exec(line);
    if (ordered) {
      if (state.list !== "ol") {
        closeList(state, html);
        html.push("<ol>");
        state.list = "ol";
      }
      html.push(`<li>${inlineMarkdown(ordered[1])}</li>`);
      continue;
    }

    closeList(state, html);
    html.push(`<p>${inlineMarkdown(line)}</p>`);
  }

  closeList(state, html);
  return html.join("\n");
}

function buildDocument(body) {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Data Analyst Agent 项目介绍</title>
  <style>
    @page {
      size: A4;
      margin: 18mm 16mm 18mm 16mm;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      color: #1f2329;
      font-family: "Arial Unicode MS", "Hiragino Sans GB", "STHeiti", "PingFang SC", Arial, sans-serif;
      font-size: 11pt;
      line-height: 1.62;
      background: #ffffff;
    }
    h1 {
      margin: 0 0 18px;
      padding-bottom: 10px;
      border-bottom: 2px solid #3370ff;
      color: #102a56;
      font-size: 25pt;
      line-height: 1.25;
      page-break-after: avoid;
    }
    h2 {
      margin: 24px 0 10px;
      color: #173b75;
      font-size: 17pt;
      line-height: 1.3;
      page-break-after: avoid;
    }
    h3 {
      margin: 16px 0 7px;
      color: #244b84;
      font-size: 13pt;
      line-height: 1.35;
      page-break-after: avoid;
    }
    p {
      margin: 7px 0;
      text-align: justify;
    }
    ul,
    ol {
      margin: 6px 0 10px 20px;
      padding: 0;
    }
    li {
      margin: 3px 0;
    }
    table {
      width: 100%;
      margin: 10px 0 14px;
      border-collapse: collapse;
      page-break-inside: avoid;
      font-size: 9.5pt;
    }
    th {
      background: #eef4ff;
      color: #173b75;
      font-weight: 700;
    }
    th,
    td {
      border: 1px solid #d9e1ef;
      padding: 7px 8px;
      vertical-align: top;
    }
    code {
      padding: 1px 4px;
      border-radius: 4px;
      background: #f3f6fa;
      color: #174a7c;
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 0.92em;
    }
    pre {
      margin: 10px 0 14px;
      padding: 10px 12px;
      border: 1px solid #d9e1ef;
      border-radius: 8px;
      background: #f7f9fc;
      white-space: pre-wrap;
      word-break: break-word;
      page-break-inside: avoid;
    }
    pre code {
      padding: 0;
      background: transparent;
      color: #1f2329;
      font-size: 9pt;
    }
    a {
      color: #245edb;
      text-decoration: none;
    }
  </style>
</head>
<body>
${body}
</body>
</html>`;
}

const markdown = fs.readFileSync(input, "utf8");
const html = buildDocument(markdownToHtml(markdown));
fs.writeFileSync(htmlOutput, html, "utf8");

const browser = await chromium.launch({
  executablePath: chromePath,
  headless: true,
});
const page = await browser.newPage();
await page.goto(`file://${htmlOutput}`, { waitUntil: "load" });
await page.pdf({
  path: output,
  format: "A4",
  printBackground: true,
  preferCSSPageSize: true,
});
await browser.close();

console.log(output);
