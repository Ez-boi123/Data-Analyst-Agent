"use client";

import { useMemo } from "react";
import ReactFlow, { Background, Controls, type Edge, type Node } from "reactflow";
import "reactflow/dist/style.css";
import type { SchemaEvidence } from "@/lib/types";

export function SchemaGraph({ schema }: { schema: SchemaEvidence }) {
  const nodes: Node[] = useMemo(
    () =>
      schema.tables.map((table, index) => ({
        id: table.id,
        position: { x: (index % 2) * 360, y: Math.floor(index / 2) * 150 },
        data: {
          label: (
            <div>
              <strong>{table.name}</strong>
              <br />
              <small>
                {table.domain} · {table.confidence == null ? "置信度未评估" : `${Math.round(table.confidence * 100)}%`}
              </small>
            </div>
          )
        },
        style: {
          border: "1px solid #bacefd",
          borderRadius: 8,
          padding: 10,
          width: 220,
          background: "#ffffff",
          color: "#1f2329",
          boxShadow: "0 1px 2px rgba(31, 35, 41, 0.06)"
        }
      })),
    [schema.tables]
  );

  const edges: Edge[] = useMemo(
    () =>
      schema.joinPaths.map((path, index) => ({
        id: `edge-${index}`,
        source: schema.tables.find((table) => path.from.includes(table.id.replace("s", "")))?.id ?? schema.tables[0].id,
        target: schema.tables.find((table) => path.to.includes(table.id.replace("s", "")))?.id ?? schema.tables[1].id,
        label: path.confidence == null ? "候选关联" : `${Math.round(path.confidence * 100)}%`,
        animated: true,
        style: { stroke: "#3370ff", strokeWidth: 1.6 },
        labelStyle: { fill: "#245bdb", fontWeight: 600 },
        labelBgStyle: { fill: "#e8f0ff" }
      })),
    [schema.joinPaths, schema.tables]
  );

  return (
    <div className="detail-grid">
      <div className="schema-graph" aria-label="Schema Join Path">
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background color="#dee0e3" gap={18} />
          <Controls />
        </ReactFlow>
      </div>
      <div>
        {schema.assessment && (
          <section aria-label="Schema 评分依据">
            <h3>Schema 评分依据</h3>
            <p>{schema.assessment.scope}</p>
            <p>{schema.assessment.method}</p>
            <ul className="evidence-list">
              {Object.entries(schema.assessment.components).map(([name, score]) => (
                <li key={name}>{name}：{Math.round(score * 100)}%</li>
              ))}
              {schema.assessment.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
            </ul>
          </section>
        )}
        <h3 style={{ marginTop: 0 }}>关联路径 Join Path</h3>
        <ul className="evidence-list">
          {schema.joinPaths.map((path) => (
            <li key={`${path.from}-${path.to}`}>
              {path.condition} · 置信度 {path.confidence == null ? "未评估" : `${Math.round(path.confidence * 100)}%`}
              {path.assessment && <p>{path.assessment.method}。{Object.entries(path.assessment.components).map(([key, value]) => `${key} ${Math.round(value * 100)}%`).join("；")}</p>}
            </li>
          ))}
        </ul>
        <h3>相关表</h3>
        <ul className="evidence-list">
          {schema.tables.map((table) => (
            <li key={table.id}>
              {table.name}：{table.reason}
              {table.assessment && <p>{table.assessment.method}。{Object.entries(table.assessment.components).map(([key, value]) => `${key} ${Math.round(value * 100)}%`).join("；")}</p>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
