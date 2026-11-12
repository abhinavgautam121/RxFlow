import { useMemo, useState, type ReactNode } from "react";
import {
  ArrowDownUp,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Download,
  Search,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "./ui/button";
import { download, fmt, pct } from "../lib";

export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Stat({
  label,
  value,
  note,
  tone = "teal",
}: {
  label: string;
  value: ReactNode;
  note?: string;
  tone?: string;
}) {
  return (
    <div className={`stat ${tone}`}>
      <span className="stat-label">{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
      <span className="stat-line" />
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <div className="spinner" />
      Calculating from operational records…
    </div>
  );
}
export function ErrorBox({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="error" role="alert">
      <strong>We couldn’t load this view.</strong>
      <p>{error instanceof Error ? error.message : String(error)}</p>
      {retry && (
        <Button variant="outline" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
export function Empty({
  text = "No records match these filters.",
}: {
  text?: string;
}) {
  return <div className="empty">{text}</div>;
}
export function ExportButton({
  dataset,
  filters = {},
}: {
  dataset: string;
  filters?: Record<string, unknown>;
}) {
  return (
    <Button variant="outline" asChild>
      <a href={download(dataset, filters)} download>
        <Download size={15} />
        Export {dataset === "powerbi" ? "Power BI ZIP" : "CSV"}
      </a>
    </Button>
  );
}
export function Rate({
  value,
  n,
  d,
}: {
  value: number | null;
  n?: number;
  d?: number;
}) {
  return (
    <span className="rate">
      <strong
        className={value != null && value < 80 ? "text-amber" : "text-teal"}
      >
        {pct(value)}
      </strong>
      {n != null && d != null && (
        <small>
          {fmt(n)} / {fmt(d)}
        </small>
      )}
    </span>
  );
}
export function Trend({
  data,
  metric = "orders",
  color = "#0f8c86",
  height = 250,
}: {
  data: any[];
  metric?: string;
  color?: string;
  height?: number;
}) {
  if (!data.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart
        data={data}
        margin={{ top: 10, right: 15, left: -15, bottom: 0 }}
      >
        <defs>
          <linearGradient id={`fill-${metric}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.23} />
            <stop offset="100%" stopColor={color} stopOpacity={0.01} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="#edf1f4" />
        <XAxis
          dataKey="date"
          tickFormatter={(v) => String(v).slice(5)}
          minTickGap={42}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 10, fill: "#7b8897" }}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 10, fill: "#7b8897" }}
        />
        <Tooltip
          contentStyle={{ borderRadius: 10, border: "1px solid #e6ebf0" }}
        />
        <Area
          name={
            metric === "orders"
              ? "Orders"
              : metric === "on_time_rate"
                ? "On time (%)"
                : metric
          }
          type="monotone"
          dataKey={metric}
          stroke={color}
          strokeWidth={2}
          fill={`url(#fill-${metric})`}
          connectNulls={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
export function Bars({
  data,
  x,
  y,
  color = "#239b95",
  height = 250,
}: {
  data: any[];
  x: string;
  y: string;
  color?: string;
  height?: number;
}) {
  if (!data.length) return <Empty />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        margin={{ top: 10, right: 10, left: -15, bottom: 0 }}
      >
        <CartesianGrid vertical={false} stroke="#edf1f4" />
        <XAxis
          dataKey={x}
          tick={{ fontSize: 10 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis tick={{ fontSize: 10 }} tickLine={false} axisLine={false} />
        <Tooltip />
        <Bar dataKey={y} fill={color} radius={[5, 5, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  );
}
export function ForecastChart({ data }: { data: any[] }) {
  return (
    <ResponsiveContainer width="100%" height={230}>
      <LineChart data={data}>
        <CartesianGrid vertical={false} stroke="#edf1f4" />
        <XAxis
          dataKey="date"
          tickFormatter={(v) => String(v).slice(5)}
          minTickGap={35}
          tick={{ fontSize: 10 }}
        />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip />
        <Line type="monotone" dataKey="actual" stroke="#98a5b4" dot={false} />
        <Line
          type="monotone"
          dataKey="predicted"
          stroke="#0f8c86"
          dot={false}
        />
        <Line
          dataKey="upper"
          stroke="#a8d8d5"
          strokeDasharray="3 4"
          dot={false}
        />
        <Line
          dataKey="lower"
          stroke="#a8d8d5"
          strokeDasharray="3 4"
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
export type Column = {
  key: string;
  label: string;
  render?: (r: any) => ReactNode;
};
export function Table({
  rows,
  columns,
  onRow,
  pageSize = 10,
  searchable = true,
}: {
  rows: any[];
  columns: Column[];
  onRow?: (r: any) => void;
  pageSize?: number;
  searchable?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<{ key: string; direction: number } | null>(
    null,
  );
  const filtered = useMemo(() => {
    const list = rows.filter(
      (r) =>
        !search ||
        Object.values(r).some((v) =>
          String(v).toLowerCase().includes(search.toLowerCase()),
        ),
    );
    if (sort)
      list.sort((a, b) => {
        const av = a[sort.key],
          bv = b[sort.key];
        return (
          (typeof av === "number"
            ? av - (bv ?? 0)
            : String(av ?? "").localeCompare(String(bv ?? ""))) * sort.direction
        );
      });
    return list;
  }, [rows, search, sort]);
  const max = Math.max(0, Math.ceil(filtered.length / pageSize) - 1);
  const current = Math.min(page, max);
  return (
    <>
      {searchable && (
        <div className="table-tools">
          <label className="search">
            <Search size={15} />
            <input
              aria-label="Search table"
              placeholder="Search records…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
            />
          </label>
          <span className="muted">{fmt(filtered.length)} records</span>
        </div>
      )}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key}>
                  <button
                    onClick={() =>
                      setSort({
                        key: c.key,
                        direction: sort?.key === c.key ? -sort.direction : 1,
                      })
                    }
                  >
                    {c.label}
                    <ArrowDownUp size={11} />
                  </button>
                </th>
              ))}
              {onRow && <th>Details</th>}
            </tr>
          </thead>
          <tbody>
            {filtered
              .slice(current * pageSize, (current + 1) * pageSize)
              .map((r, i) => (
                <tr key={r.id ?? r.shipment_id ?? r.batch_id ?? i}>
                  {columns.map((c) => (
                    <td key={c.key}>
                      {c.render ? c.render(r) : (r[c.key] ?? "—")}
                    </td>
                  ))}
                  {onRow && (
                    <td>
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`View ${r.id ?? r.shipment_id ?? "record"}`}
                        onClick={() => onRow(r)}
                      >
                        <ArrowRight size={15} />
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
          </tbody>
        </table>
        {!filtered.length && <Empty />}
      </div>
      <div className="pagination">
        <span>
          {filtered.length ? current * pageSize + 1 : 0}–
          {Math.min((current + 1) * pageSize, filtered.length)} of{" "}
          {fmt(filtered.length)}
        </span>
        <div>
          <Button
            variant="ghost"
            size="sm"
            disabled={current === 0}
            onClick={() => setPage(current - 1)}
            aria-label="Previous page"
          >
            <ChevronLeft size={15} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={current >= max}
            onClick={() => setPage(current + 1)}
            aria-label="Next page"
          >
            <ChevronRight size={15} />
          </Button>
        </div>
      </div>
    </>
  );
}
