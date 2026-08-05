"use client";
import { cn } from "@/lib/utils";

export type DataTableColumn<T> = {
  id: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  className?: string;
};

type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  stickyHeader?: boolean;
  selectable?: boolean;
  selectedKeys?: Set<string>;
  onSelectionChange?: (keys: Set<string>) => void;
  empty?: React.ReactNode;
};

export default function DataTable<T>({
  columns,
  rows,
  getRowKey,
  onRowClick,
  stickyHeader = true,
  selectable,
  selectedKeys,
  onSelectionChange,
  empty,
}: DataTableProps<T>) {
  if (rows.length === 0 && empty) {
    return <>{empty}</>;
  }

  const allSelected = selectable && rows.length > 0 && rows.every((r) => selectedKeys?.has(getRowKey(r)));

  const toggleAll = () => {
    if (!onSelectionChange) return;
    if (allSelected) onSelectionChange(new Set());
    else onSelectionChange(new Set(rows.map(getRowKey)));
  };

  const toggleRow = (key: string) => {
    if (!onSelectionChange || !selectedKeys) return;
    const next = new Set(selectedKeys);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onSelectionChange(next);
  };

  return (
    <div className="overflow-auto rounded-xl border border-gray-200 bg-white shadow-card">
      <table className="w-full min-w-[720px] text-sm">
        <thead
          className={cn(
            "border-b bg-muted-50 text-start text-gray-600",
            stickyHeader && "sticky top-0 z-10 shadow-sm"
          )}
        >
          <tr>
            {selectable && (
              <th className="w-10 px-3 py-3">
                <input type="checkbox" checked={!!allSelected} onChange={toggleAll} aria-label="Select all" />
              </th>
            )}
            {columns.map((col) => (
              <th key={col.id} className={cn("data-cell px-4 py-3 font-semibold", col.className)}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const key = getRowKey(row);
            return (
              <tr
                key={key}
                className={cn(
                  "border-b last:border-0 hairline-b",
                  i % 2 === 1 && "bg-muted-50/40",
                  onRowClick && "cursor-pointer hover:bg-muted-50/80"
                )}
                onClick={() => onRowClick?.(row)}
              >
                {selectable && (
                  <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedKeys?.has(key) ?? false}
                      onChange={() => toggleRow(key)}
                      aria-label="Select row"
                    />
                  </td>
                )}
                {columns.map((col) => (
                  <td key={col.id} className={cn("data-cell px-4 py-3", col.className)}>
                    {col.cell(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
