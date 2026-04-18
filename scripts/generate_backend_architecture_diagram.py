from __future__ import annotations

from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data_agent_backend_architecture_v2.svg"


def tspan_lines(lines: list[str], x: int, y: int, size: int = 13, weight: str = "400", fill: str = "#334155") -> list[str]:
    result = []
    for index, line in enumerate(lines):
        if index == 0:
            result.append(
                f'<tspan x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(line)}</tspan>'
            )
        else:
            result.append(
                f'<tspan x="{x}" dy="{size + 4}" font-size="{size}" font-weight="{weight}" fill="{fill}">{escape(line)}</tspan>'
            )
    return result


def node(
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    lines: list[str],
    fill: str,
    stroke: str,
    icon: str = "",
) -> list[str]:
    cx = x + w // 2
    result = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1.4" filter="url(#softShadow)"/>'
    ]
    if icon:
        result.append(f'<text x="{x + 16}" y="{y + 29}" font-size="19" fill="{stroke}">{escape(icon)}</text>')
        title_x = x + 43
        anchor = "start"
    else:
        title_x = cx
        anchor = "middle"
    result.append(
        f'<text x="{title_x}" y="{y + 28}" text-anchor="{anchor}" font-size="15" font-weight="700" fill="#0f172a">{escape(title)}</text>'
    )
    if lines:
        text_y = y + 53
        result.append(f'<text text-anchor="middle" font-family="Inter, Arial, sans-serif">')
        result.extend(tspan_lines(lines, cx, text_y, 12, "400", "#475569"))
        result.append("</text>")
    return result


def container(x: int, y: int, w: int, h: int, title: str, subtitle: str, fill: str, stroke: str) -> list[str]:
    return [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="{fill}" stroke="{stroke}" stroke-width="1.3" stroke-dasharray="8 6"/>',
        f'<text x="{x + 18}" y="{y + 26}" font-size="16" font-weight="800" fill="#0f172a">{escape(title)}</text>',
        f'<text x="{x + 18}" y="{y + 47}" font-size="12" fill="#64748b">{escape(subtitle)}</text>',
    ]


def arrow(path: str, color: str = "#2563eb", dash: str = "", width: float = 2.0) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}"{dash_attr} marker-end="url(#arrow-{color[1:]})"/>'


def label(x: int, y: int, text: str, color: str = "#2563eb") -> list[str]:
    text_width = max(46, len(text) * 10 + 14)
    return [
        f'<rect x="{x - text_width // 2}" y="{y - 14}" width="{text_width}" height="22" rx="6" fill="#ffffff" opacity="0.96" stroke="#e2e8f0"/>',
        f'<text x="{x}" y="{y + 1}" text-anchor="middle" font-size="11" font-weight="700" fill="{color}">{escape(text)}</text>',
    ]


def main() -> None:
    lines: list[str] = []
    lines.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" width="1200" height="760">')
    lines.append("<defs>")
    lines.append(
        """<filter id="softShadow" x="-10%" y="-10%" width="120%" height="130%">
  <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#0f172a" flood-opacity="0.10"/>
</filter>"""
    )
    for color in ["2563eb", "ea580c", "059669", "7c3aed", "64748b"]:
        lines.append(
            f"""<marker id="arrow-{color}" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
  <path d="M 0 0 L 10 4 L 0 8 z" fill="#{color}"/>
</marker>"""
        )
    lines.append("</defs>")
    lines.append('<rect width="1200" height="760" fill="#f8fafc"/>')
    lines.append('<rect x="24" y="24" width="1152" height="712" rx="28" fill="#ffffff" stroke="#e2e8f0"/>')
    lines.append('<text x="600" y="58" text-anchor="middle" font-size="24" font-weight="850" fill="#0f172a">Data Analyst Agent 后端架构</text>')
    lines.append('<text x="600" y="84" text-anchor="middle" font-size="13" fill="#64748b">自然语言问数 · Schema 理解 · Join 推理 · SQL 自修复 · 流式洞察</text>')

    lines.extend(container(48, 110, 250, 190, "前端工作台", "Next.js / React / ECharts", "#eff6ff", "#93c5fd"))
    lines.extend(node(72, 170, 202, 72, "分析任务 UI", ["对话、时间线", "SQL、图表、洞察"], "#ffffff", "#2563eb", "▣"))

    lines.extend(container(358, 110, 260, 190, "FastAPI 服务层", "任务接口 + SSE 流式推送", "#fff7ed", "#fdba74"))
    lines.extend(node(380, 165, 100, 72, "Task API", ["创建任务", "AI 标题"], "#ffffff", "#ea580c"))
    lines.extend(node(498, 165, 96, 72, "SSE", ["step/token", "result/done"], "#ffffff", "#ea580c"))
    lines.extend(node(430, 246, 118, 42, "任务状态", [], "#fffaf0", "#ea580c"))

    lines.extend(container(682, 110, 210, 190, "模型服务", "OpenAI-compatible API", "#f5f3ff", "#c4b5fd"))
    lines.extend(node(708, 172, 158, 76, "LLM Provider", ["OpenAI / DeepSeek", "通义 / OpenRouter"], "#ffffff", "#7c3aed", "✦"))

    lines.extend(container(48, 340, 250, 270, "数据源层", "SQLAlchemy URL / Docker MySQL", "#ecfdf5", "#86efac"))
    lines.extend(node(72, 405, 202, 66, "业务数据库", ["MySQL 5 张表", "用户、商品、行为"], "#ffffff", "#059669", "▤"))
    lines.extend(node(72, 502, 202, 66, "运行时查询库", ["加载为 SQLite", "统一只读执行"], "#ffffff", "#059669", "◎"))

    lines.extend(container(358, 340, 534, 270, "LangChain Data Agent", "工具化编排 + 安全边界", "#f8fafc", "#94a3b8"))
    lines.extend(node(382, 402, 138, 72, "Schema 理解", ["字段画像", "样例与缺失率"], "#ffffff", "#64748b"))
    lines.extend(node(542, 402, 138, 72, "关联推理", ["customer_id", "product_id"], "#ffffff", "#64748b"))
    lines.extend(node(702, 402, 138, 72, "SQL 生成", ["只读 SELECT", "缺字段拦截"], "#ffffff", "#64748b"))
    lines.extend(node(382, 510, 138, 72, "安全执行", ["LIMIT 保护", "禁止写操作"], "#ffffff", "#64748b"))
    lines.extend(node(542, 510, 138, 72, "SQL 自修复", ["错误捕获", "最多重试 2 次"], "#ffffff", "#64748b"))
    lines.extend(node(702, 510, 138, 72, "洞察输出", ["图表建议", "流式分析"], "#ffffff", "#64748b"))

    lines.extend(container(930, 340, 210, 270, "可信输出", "可解释、可复盘、可分享", "#f0f9ff", "#7dd3fc"))
    lines.extend(node(956, 404, 158, 70, "结构化结果", ["SQL、表格", "图表配置"], "#ffffff", "#0284c7", "▦"))
    lines.extend(node(956, 504, 158, 70, "分析结论", ["证据、建议", "追问分支"], "#ffffff", "#0284c7", "✓"))

    lines.append(arrow("M 274 206 L 358 206", "#2563eb"))
    lines.extend(label(316, 196, "创建任务", "#2563eb"))
    lines.append(arrow("M 594 206 L 682 206", "#7c3aed"))
    lines.extend(label(638, 196, "模型调用", "#7c3aed"))
    lines.append(arrow("M 498 237 L 498 322 L 520 322 L 520 340", "#ea580c"))
    lines.extend(label(522, 316, "启动链路", "#ea580c"))

    lines.append(arrow("M 274 535 L 358 535", "#059669"))
    lines.extend(label(316, 525, "查询连接", "#059669"))
    lines.append(arrow("M 274 438 L 382 438", "#059669"))
    lines.extend(label(328, 428, "Schema", "#059669"))
    lines.append(arrow("M 520 438 L 542 438", "#64748b"))
    lines.append(arrow("M 680 438 L 702 438", "#64748b"))
    lines.append(arrow("M 771 474 L 771 492 L 451 492 L 451 510", "#2563eb"))
    lines.extend(label(642, 482, "SQL", "#2563eb"))
    lines.append(arrow("M 520 546 L 542 546", "#ea580c"))
    lines.extend(label(532, 536, "失败", "#ea580c"))
    lines.append(arrow("M 680 546 L 702 546", "#2563eb"))
    lines.extend(label(692, 536, "成功", "#2563eb"))
    lines.append(arrow("M 840 546 L 930 546", "#2563eb"))
    lines.extend(label(886, 536, "result", "#2563eb"))
    lines.append(arrow("M 866 210 L 918 210 L 918 434 L 956 434", "#7c3aed", "5 4", 1.8))
    lines.extend(label(918, 322, "token", "#7c3aed"))
    lines.append(arrow("M 956 538 L 906 538 L 906 252 L 594 252", "#64748b", "5 4", 1.6))
    lines.extend(label(906, 392, "SSE 回传", "#64748b"))

    lines.append('<rect x="394" y="646" width="412" height="48" rx="14" fill="#ffffff" stroke="#e2e8f0"/>')
    legend = [
        ("#2563eb", "主请求/结果"),
        ("#ea580c", "控制/重试"),
        ("#059669", "数据读取"),
        ("#7c3aed", "模型调用"),
        ("#64748b", "异步事件"),
    ]
    lx = 416
    for color, text in legend:
        lines.append(f'<line x1="{lx}" y1="670" x2="{lx + 26}" y2="670" stroke="{color}" stroke-width="2" marker-end="url(#arrow-{color[1:]})"/>')
        lines.append(f'<text x="{lx + 34}" y="674" font-size="12" fill="#475569">{escape(text)}</text>')
        lx += 78 if len(text) <= 4 else 92

    lines.append('<text x="600" y="716" text-anchor="middle" font-size="11" fill="#94a3b8">生成文件：docs/data_agent_backend_architecture_v2.svg · 文字已按节点宽度拆行</text>')
    lines.append("</svg>")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
