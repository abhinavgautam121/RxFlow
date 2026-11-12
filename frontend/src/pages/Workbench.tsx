import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, FlaskConical, Play, Upload } from "lucide-react";
import { useData, type PageProps } from "../App";
import {
  Badge,
  ErrorBox,
  ExportButton,
  Loading,
  Panel,
  Stat,
  Table,
} from "../components/common";
import { Button } from "../components/ui/button";
import { api, fmt, localTime, queryString } from "../lib";

const kinds = [
  ["partner_allocation", "Delivery partner allocation"],
  ["dispatch_improvement", "Dispatch-time improvement"],
  ["zone_pilot", "Zone intervention pilot"],
  ["inventory_replenishment", "Inventory replenishment"],
  ["center_capacity", "Fulfilment-centre capacity"],
];
const labels: Record<string, string> = {
  on_time_rate: "On-time delivery (%)",
  average_hours: "Avg. fulfilment (h)",
  delay_rate: "Historical delay rate (%)",
  shipping_cost: "Eligible shipping cost (₹)",
  orders_affected: "Orders affected",
  stockout_sku_center_pairs: "Stock-out exposure (SKU–centre)",
  sellable_units: "Sellable inventory (units)",
  inventory_holding_value: "Inventory holding value (₹)",
  daily_capacity: "Daily capacity (orders)",
  daily_load: "Mean daily workload",
  daily_overflow: "Daily overflow (orders)",
  target_coverage_gap_units: "Target coverage gap (units)",
};
export function Simulation({ filters, meta }: PageProps) {
  const client = useQueryClient();
  const history = useData("scenarios");
  const [active, setActive] = useState<any>(null);
  const [compare, setCompare] = useState<string[]>([]);
  const [params, setParams] = useState<Record<string, string | number>>({
    scenario_name: "Dispatch improvement pilot",
    scenario_type: "dispatch_improvement",
    percentage: 20,
    hours_reduced: 2,
    source_partner: "LP4",
    target_partner: "LP1",
    zone_id: "Z000",
    center_id: "FC1",
    stock_multiplier: 1.2,
    capacity_multiplier: 1.2,
    lead_time_days: 7,
    safety_stock: 20,
    target_days: 21,
  });
  const run = useMutation({
    mutationFn: () =>
      api(`scenarios?${queryString(filters)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      }),
    onSuccess: (result) => {
      setActive(result);
      client.invalidateQueries({ queryKey: ["scenarios"] });
    },
  });
  const kind = String(params.scenario_type);
  const numeric = (
    key: string,
    label: string,
    min: number,
    max: number,
    step = 1,
  ) => (
    <label>
      {label}
      <input
        required
        type="number"
        min={min}
        max={max}
        step={step}
        value={params[key]}
        onChange={(e) =>
          setParams({ ...params, [key]: Number(e.target.value) })
        }
      />
    </label>
  );
  const rows = active
    ? Object.entries(active.simulated_metrics).map(([key, value]) => ({
        key,
        label: labels[key] ?? key,
        baseline: active.baseline_metrics[key] ?? null,
        simulated: value,
        change:
          active.baseline_metrics[key] != null
            ? Number(value) - active.baseline_metrics[key]
            : null,
      }))
    : [];
  return (
    <>
      <div className="callout">
        <FlaskConical size={20} />
        <span>
          Historical baseline + explicit assumptions = an illustrative
          projection. Scenario results are saved, reproducible and never
          presented as realised improvements.
        </span>
      </div>
      <div className="simulation-layout">
        <Panel
          title="Configure your scenario"
          subtitle="Choose an intervention and its operating assumptions"
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run.mutate();
            }}
          >
            <div className="form-stack">
              <label>
                Scenario name
                <input
                  required
                  maxLength={100}
                  value={params.scenario_name}
                  onChange={(e) =>
                    setParams({ ...params, scenario_name: e.target.value })
                  }
                />
              </label>
              <label>
                Intervention type
                <select
                  value={kind}
                  onChange={(e) =>
                    setParams({ ...params, scenario_type: e.target.value })
                  }
                >
                  {kinds.map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              {[
                "partner_allocation",
                "dispatch_improvement",
                "zone_pilot",
              ].includes(kind) &&
                numeric("percentage", "Eligible orders affected (%)", 0, 100)}
              {kind === "partner_allocation" && (
                <>
                  {["source_partner", "target_partner"].map((key) => (
                    <label key={key}>
                      {key === "source_partner" ? "From partner" : "To partner"}
                      <select
                        value={params[key]}
                        onChange={(e) =>
                          setParams({ ...params, [key]: e.target.value })
                        }
                      >
                        {meta.partners.map((p: any) => (
                          <option
                            key={p.delivery_partner_id}
                            value={p.delivery_partner_id}
                          >
                            {p.partner_name}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </>
              )}
              {["dispatch_improvement", "zone_pilot"].includes(kind) &&
                numeric(
                  "hours_reduced",
                  "Pre-dispatch hours removed",
                  0,
                  24,
                  0.25,
                )}
              {kind === "zone_pilot" && (
                <label>
                  Pilot zone
                  <select
                    value={params.zone_id}
                    onChange={(e) =>
                      setParams({ ...params, zone_id: e.target.value })
                    }
                  >
                    {meta.zones.map((z: any) => (
                      <option key={z.zone_id} value={z.zone_id}>
                        {z.zone_code} · {z.city}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {kind === "inventory_replenishment" && (
                <>
                  {numeric("stock_multiplier", "Stock multiplier", 0, 5, 0.1)}
                  {numeric("lead_time_days", "Lead time (days)", 1, 90)}
                  {numeric("safety_stock", "Safety stock (units)", 0, 10000)}
                  {numeric("target_days", "Target coverage (days)", 1, 180)}
                </>
              )}
              {kind === "center_capacity" && (
                <>
                  <label>
                    Fulfilment centre
                    <select
                      value={params.center_id}
                      onChange={(e) =>
                        setParams({ ...params, center_id: e.target.value })
                      }
                    >
                      {meta.centers.map((c: any) => (
                        <option
                          key={c.fulfillment_center_id}
                          value={c.fulfillment_center_id}
                        >
                          {c.center_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {numeric(
                    "capacity_multiplier",
                    "Daily capacity multiplier",
                    0.1,
                    5,
                    0.1,
                  )}
                </>
              )}
            </div>
            <Button type="submit" disabled={run.isPending}>
              <Play size={15} />
              {run.isPending ? "Running scenario…" : "Run & save scenario"}
            </Button>
          </form>
          {run.error && <ErrorBox error={run.error} />}
        </Panel>
        <Panel
          title={
            active?.scenario_name ?? "Your decision starts with a baseline"
          }
          subtitle={
            active
              ? `Saved ${localTime(active.created_at)} IST`
              : "Run a scenario to compare measured history with an illustrative intervention"
          }
          action={
            active && (
              <Badge tone="teal">
                <Check size={12} />
                SAVED
              </Badge>
            )
          }
        >
          {active ? (
            <>
              <Table
                rows={rows}
                columns={[
                  { key: "label", label: "KPI" },
                  {
                    key: "baseline",
                    label: "Baseline",
                    render: (r: any) => fmt(r.baseline, 2),
                  },
                  {
                    key: "simulated",
                    label: "Scenario",
                    render: (r: any) => <strong>{fmt(r.simulated, 2)}</strong>,
                  },
                  {
                    key: "change",
                    label: "Change",
                    render: (r: any) =>
                      r.change == null
                        ? "—"
                        : `${r.change > 0 ? "+" : ""}${fmt(r.change, 2)}`,
                  },
                ]}
                pageSize={20}
                searchable={false}
              />
              <div className="assumptions">
                <h3>Assumptions & provenance</h3>
                {Object.entries(active.assumptions)
                  .filter(([key]) => !["parameters", "filters"].includes(key))
                  .map(([key, value]) => (
                    <p key={key}>
                      <strong>{key.replaceAll("_", " ")}: </strong>
                      {typeof value === "object"
                        ? JSON.stringify(value)
                        : String(value)}
                    </p>
                  ))}
                <details>
                  <summary>Saved parameters and cohort</summary>
                  <pre>
                    {JSON.stringify(
                      {
                        parameters: active.assumptions.parameters,
                        filters: active.assumptions.filters,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </div>
            </>
          ) : (
            <div className="scenario-empty">
              <FlaskConical size={48} />
              <h3>Test an idea. Keep the assumptions visible.</h3>
              <p>
                Explore all five operational interventions. Delivery, inventory
                and capacity metrics change only where the model supports a
                projection.
              </p>
            </div>
          )}
        </Panel>
      </div>
      <Panel
        title="Saved scenario library"
        subtitle="Revisit a run or select up to three scenarios to compare"
        action={<ExportButton dataset="scenarios" />}
      >
        {history.isPending ? (
          <Loading />
        ) : history.error ? (
          <ErrorBox error={history.error} />
        ) : (
          <>
            <Table
              rows={history.data.rows}
              columns={[
                { key: "scenario_name", label: "Scenario" },
                { key: "scenario_type", label: "Intervention" },
                {
                  key: "created_at",
                  label: "Saved · IST",
                  render: (r: any) => localTime(r.created_at),
                },
                {
                  key: "compare",
                  label: "Compare",
                  render: (r: any) => (
                    <input
                      aria-label={`Compare ${r.scenario_name}`}
                      type="checkbox"
                      checked={compare.includes(r.scenario_id)}
                      onChange={() =>
                        setCompare((s) =>
                          s.includes(r.scenario_id)
                            ? s.filter((x) => x !== r.scenario_id)
                            : s.length < 3
                              ? [...s, r.scenario_id]
                              : s,
                        )
                      }
                    />
                  ),
                },
              ]}
              onRow={(r) => setActive(r)}
            />
            {compare.length > 0 && (
              <Table
                rows={history.data.rows
                  .filter((r: any) => compare.includes(r.scenario_id))
                  .map((r: any) => ({
                    name: r.scenario_name,
                    ...r.simulated_metrics,
                  }))}
                columns={[
                  { key: "name", label: "Scenario" },
                  {
                    key: "on_time_rate",
                    label: "Projected on time (%)",
                    render: (r: any) => fmt(r.on_time_rate, 2),
                  },
                  {
                    key: "average_hours",
                    label: "Projected hours",
                    render: (r: any) => fmt(r.average_hours, 2),
                  },
                  {
                    key: "shipping_cost",
                    label: "Projected shipping (₹)",
                    render: (r: any) => fmt(r.shipping_cost, 2),
                  },
                  { key: "orders_affected", label: "Affected" },
                ]}
                searchable={false}
              />
            )}
          </>
        )}
      </Panel>
    </>
  );
}

export function Quality({ meta }: PageProps) {
  const q = useData("data-quality");
  const history = useData("imports");
  const client = useQueryClient();
  const [table, setTable] = useState("orders");
  const [key, setKey] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<any>(null);
  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a CSV file");
      const form = new FormData();
      form.append("file", file);
      return api(`imports?table=${encodeURIComponent(table)}`, {
        method: "POST",
        headers: { "X-Admin-Key": key },
        body: form,
      });
    },
    onSuccess: (result) => {
      setSelected(result);
      client.invalidateQueries();
    },
  });
  if (q.isPending) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  return (
    <>
      <div className="stats-grid">
        <Stat
          label="Records scanned"
          value={fmt(d.total_records_scanned)}
          note="Orders, shipments, events and inventory batches"
        />
        <Stat
          label="Issue occurrences"
          value={fmt(d.issue_occurrences)}
          note="Checks can overlap; this is not distinct rejected rows"
          tone="amber"
        />
        <Stat
          label="Validation checks"
          value={fmt(d.checks.length)}
          note="Database constraints also enforce record integrity"
          tone="blue"
        />
        <Stat
          label="Checks with findings"
          value={d.checks.filter((r: any) => r.affected_records > 0).length}
          note="Intentional synthetic defects remain visible"
          tone="amber"
        />
      </div>
      <Panel
        title="Data-quality findings"
        subtitle="Downloadable evidence rather than silent exclusions"
        action={<ExportButton dataset="quality" />}
      >
        <Table
          rows={d.checks}
          columns={[
            { key: "code", label: "Check" },
            { key: "description", label: "Validation rule" },
            {
              key: "affected_records",
              label: "Affected records",
              render: (r: any) => (
                <strong
                  className={r.affected_records ? "text-amber" : "text-teal"}
                >
                  {fmt(r.affected_records)}
                </strong>
              ),
            },
            {
              key: "severity",
              label: "Severity",
              render: (r: any) => (
                <Badge tone={r.affected_records ? "amber" : "teal"}>
                  {r.affected_records ? r.severity : "Pass"}
                </Badge>
              ),
            },
            {
              key: "sample",
              label: "Example IDs",
              render: (r: any) => r.sample.join(", "),
            },
          ]}
        />
        <p className="footnote">{d.note}</p>
      </Panel>
      <Panel
        title="Staged CSV import"
        subtitle="Authenticated · insert-only · all-or-nothing validation"
      >
        <div className="callout">
          Use fictional operational data only. Unknown columns are rejected.
          Existing rows are never overwritten. A rejected staged batch inserts
          no operational records and writes an audit entry.
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <div className="form-grid">
            <label>
              Dataset
              <select value={table} onChange={(e) => setTable(e.target.value)}>
                {meta.import_tables.map((s: string) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label>
              Administrator API key
              <input
                type="password"
                autoComplete="off"
                required
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="Configured ADMIN_API_KEY"
              />
            </label>
            <label>
              UTF-8 CSV · max 5 MiB
              <input
                type="file"
                accept=".csv,text/csv"
                required
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>
          <div className="form-actions">
            <Button type="submit" disabled={mutation.isPending}>
              <Upload size={15} />
              {mutation.isPending ? "Validating…" : "Validate & import"}
            </Button>
            <Button variant="outline" asChild>
              <a href={`/api/v1/templates/${table}`} download>
                Download CSV template
              </a>
            </Button>
            <ExportButton dataset="powerbi" />
          </div>
        </form>
        {mutation.error && <ErrorBox error={mutation.error} />}{" "}
        {selected && (
          <div className="import-result" role="status">
            <Badge
              tone={selected.import_status === "COMPLETED" ? "teal" : "amber"}
            >
              {selected.import_status}
            </Badge>
            <p>
              {fmt(selected.records_processed)} processed ·{" "}
              {fmt(selected.records_accepted)} accepted ·{" "}
              {fmt(selected.records_rejected)} rejected
            </p>
            {selected.error_details?.length > 0 && (
              <pre>{JSON.stringify(selected.error_details, null, 2)}</pre>
            )}
          </div>
        )}
      </Panel>
      <Panel
        title="Import audit trail"
        subtitle="Every staged batch records its filename, source, row counts and validation outcome"
      >
        {history.isPending ? (
          <Loading />
        ) : history.error ? (
          <ErrorBox error={history.error} />
        ) : (
          <Table
            rows={history.data.rows}
            columns={[
              { key: "filename", label: "Filename" },
              { key: "source", label: "Source / policy" },
              {
                key: "import_date",
                label: "Imported · IST",
                render: (r: any) => localTime(r.import_date),
              },
              { key: "records_processed", label: "Processed" },
              { key: "records_accepted", label: "Accepted" },
              { key: "records_rejected", label: "Rejected" },
              {
                key: "import_status",
                label: "Status",
                render: (r: any) => (
                  <Badge
                    tone={r.import_status === "COMPLETED" ? "teal" : "amber"}
                  >
                    {r.import_status}
                  </Badge>
                ),
              },
            ]}
            onRow={(r) => setSelected(r)}
          />
        )}
      </Panel>
    </>
  );
}
