import React from "react";

export function TableContainer({
  children,
  className = "",
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`w-full overflow-x-auto rounded-md border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm ${className}`}
    >
      {children}
    </div>
  );
}

export function Table({
  children,
  className = "",
  ...props
}: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <table
      className={`w-full text-left text-xs text-[var(--text-secondary)] divide-y divide-[var(--border-subtle)] ${className}`}
      {...props}
    >
      {children}
    </table>
  );
}

export function TableHeader({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={`bg-[var(--bg-subtle)] text-[11px] font-bold text-[var(--text-muted)] uppercase font-mono tracking-wider ${className}`}
      {...props}
    >
      {children}
    </thead>
  );
}

export function TableBody({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody
      className={`divide-y divide-[var(--border-subtle)] bg-transparent ${className}`}
      {...props}
    >
      {children}
    </tbody>
  );
}

export function TableRow({
  children,
  className = "",
  interactive = true,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement> & { interactive?: boolean }) {
  return (
    <tr
      className={`transition-colors duration-100 ${
        interactive ? "hover:bg-[var(--bg-hover)]" : ""
      } ${className}`}
      {...props}
    >
      {children}
    </tr>
  );
}

export function TableHead({
  children,
  className = "",
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={`px-4 py-3 font-semibold ${className}`} {...props}>
      {children}
    </th>
  );
}

export function TableCell({
  children,
  className = "",
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={`px-4 py-3 align-middle text-[var(--text-primary)] ${className}`} {...props}>
      {children}
    </td>
  );
}
