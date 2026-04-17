"use client";

import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef
} from "@tanstack/react-table";
import type { ResultRow } from "@/lib/types";

const columns: ColumnDef<ResultRow>[] = [
  { accessorKey: "date", header: "日期" },
  { accessorKey: "region", header: "区域" },
  { accessorKey: "channel", header: "渠道" },
  { accessorKey: "gmv", header: "GMV(万)" },
  { accessorKey: "orders", header: "订单数" },
  { accessorKey: "conversionRate", header: "转化率(%)" },
  { accessorKey: "refundRate", header: "退款率(%)" }
];

export function ResultTable({ rows }: { rows: ResultRow[] }) {
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
            预览 {rows.length} 行，字段类型已标注；大结果集由后端分页或采样。
          </p>
        </div>
        <button className="button" type="button">
          导出 CSV
        </button>
      </div>
      <div className="table-wrap">
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
      </div>
      <div className="tabs">
        <span className="status-pill">行数限制 500</span>
        <span className="status-pill">字段类型：date / string / decimal / number</span>
        <span className="status-pill">表内横向滚动</span>
      </div>
    </section>
  );
}
