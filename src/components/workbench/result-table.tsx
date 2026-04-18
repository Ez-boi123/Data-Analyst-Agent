"use client";

import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef
} from "@tanstack/react-table";
import type { ResultRow } from "@/lib/types";

export function ResultTable({ rows }: { rows: ResultRow[] }) {
  const columnKeys = Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).slice(0, 12);
  const columns: ColumnDef<ResultRow>[] = columnKeys.map((key) => ({
    accessorKey: key,
    header: key,
    cell: ({ getValue }) => formatCell(getValue())
  }));

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 5 } }
  });

  return (
    <section>
      <div className="panel-header" style={{ paddingLeft: 0, paddingRight: 0 }}>
        <div>
          <strong>结果预览</strong>
          <p className="subtitle" style={{ margin: "4px 0 0" }}>
            预览 {rows.length} 行，按 SQL 真实返回字段展示；大结果集由后端分页或采样。
          </p>
        </div>
        <button className="button" type="button">
          导出 CSV
        </button>
      </div>
      <div className="table-wrap">
        {columnKeys.length ? (
          <table>
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="subtitle">当前 SQL 没有返回可展示行。</p>
        )}
      </div>
      <div className="tabs">
        <span className="status-pill">行数限制 500</span>
        <span className="status-pill">字段来自 SQL 返回结果</span>
        <span className="status-pill">表内横向滚动</span>
      </div>
    </section>
  );
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return Number.isInteger(value) ? value : Number(value.toFixed(4));
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}
