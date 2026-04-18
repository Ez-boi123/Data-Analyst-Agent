"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { InsightView } from "@/lib/types";

export function InsightChart({ insight }: { insight: InsightView }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartType = normalizeEChartsType(insight.chartType);

  useEffect(() => {
    if (!ref.current || !chartType) return;

    const chart = echarts.init(ref.current);
    chart.setOption({
      color: ["#3370ff", "#00b42a", "#ff7d00"],
      title: { text: insight.chartConfig.title, left: 8, top: 8, textStyle: { color: "#1f2329", fontSize: 14, fontWeight: 600 } },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(31, 35, 41, 0.92)",
        borderWidth: 0,
        textStyle: { color: "#ffffff" }
      },
      legend: { top: 38, textStyle: { color: "#646a73" } },
      grid: { left: 44, right: 20, top: 82, bottom: 34 },
      xAxis: {
        type: "category",
        data: insight.chartConfig.categories,
        axisLine: { lineStyle: { color: "#dee0e3" } },
        axisLabel: { color: "#646a73" }
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "#eff0f1" } },
        axisLabel: { color: "#646a73" }
      },
      series: insight.chartConfig.series.map((series) => ({
        name: series.name,
        type: chartType,
        smooth: true,
        symbolSize: insight.chartType === "bubble" ? 12 : 7,
        lineStyle: { width: 2 },
        data: series.data
      }))
    });

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [insight, chartType]);

  if (!chartType) {
    return (
      <div className="chart chart-empty" aria-label={insight.chartConfig.title}>
        <strong>{insight.chartConfig.title || "查询结果更适合表格展示"}</strong>
        <p>当前结果不适合绘制图表，请在“结果”页查看 SQL 返回的真实字段。</p>
      </div>
    );
  }

  return <div ref={ref} className="chart" aria-label={insight.chartConfig.title} />;
}

function normalizeEChartsType(chartType: InsightView["chartType"]) {
  if (chartType === "table") return null;
  if (chartType === "bubble") return "scatter";
  return chartType;
}
