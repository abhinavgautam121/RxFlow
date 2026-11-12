import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Package,
  Target,
  TrendingUp,
  X,
} from "lucide-react";
import { useData, type PageProps } from "../App";
import {
  Badge,
  Bars,
  Empty,
  ErrorBox,
  Loading,
  Panel,
  Rate,
  Stat,
  Table,
  Trend,
} from "../components/common";
import { Button } from "../components/ui/button";
import { fmt, localTime, money, pct } from "../lib";

const cohortColumns = [
  { key: "id", label: "Cohort" },
  { key: "orders", label: "Orders", render: (r: any) => fmt(r.orders) },
  {
    key: "on_time_rate",
    label: "On time",
    render: (r: any) => (
      <Rate value={r.on_time_rate} n={r.eligible - r.delayed} d={r.eligible} />
    ),
  },
  {
    key: "avg_hours",
    label: "Avg. fulfilment",
    render: (r: any) => `${fmt(r.avg_hours, 1)} h`,
  },
  {
    key: "cost_per_shipment",
    label: "Cost / shipment",
    render: (r: any) => money(r.cost_per_shipment),
  },
];
function KPIs({ k }: { k: any }) {
  return (
    <div className="stats-grid">
      <Stat
        label="Total orders"
        value={fmt(k.total_orders)}
        note={`${fmt(k.delivered_orders)} delivered`}
      />
      <Stat
        label="On-time delivery"
        value={pct(k.on_time.value)}
        note={`${fmt(k.on_time.numerator)} / ${fmt(k.on_time.denominator)} eligible deliveries`}
      />
      <Stat
        label="Avg. fulfilment time"
        value={
          <>
            {fmt(k.avg_fulfilment_hours, 1)}
            <em>hours</em>
          </>
        }
        note="Creation → delivery · valid delivered"
        tone="blue"
      />
      <Stat
        label="Currently overdue"
        value={fmt(k.currently_overdue)}
        note={`${fmt(k.pending_orders)} active · ${fmt(k.not_yet_due)} not yet due`}
        tone="amber"
      />
    </div>
  );
}

export function Executive({ filters }: PageProps) {
  const query = useData("overview", filters);
  if (query.isPending) return <Loading />;
  if (query.error)
    return <ErrorBox error={query.error} retry={() => query.refetch()} />;
  const d = query.data,
    k = d.kpis;
  return (
    <>
      <div className="insight-strip">
        <div className="insight-icon">
          <Target size={21} />
        </div>
        <div>
          <strong>Every promise is an operational decision.</strong>
          <span>
            {fmt(k.delayed_delivered_orders)} delivered orders missed their
            promise. {fmt(k.currently_overdue)} active shipments are currently
            overdue.
          </span>
        </div>
        <Badge tone="teal">MEASURED · SYNTHETIC</Badge>
      </div>
      <KPIs k={k} />
      <div className="grid-main">
        <Panel
          title="Order volume"
          subtitle="Order creation cohorts · daily · Asia/Kolkata"
          action={<Badge>180-day demonstration</Badge>}
        >
          <Trend data={d.trends} />
        </Panel>
        <Panel title="Delivery health" subtitle="Eligible completed deliveries">
          <div
            className="health-ring"
            style={{
              background: `conic-gradient(#168f88 ${(k.on_time.value ?? 0) * 3.6}deg,#edf1f4 0deg)`,
            }}
          >
            <div>
              <strong>{pct(k.on_time.value)}</strong>
              <span>on time</span>
            </div>
          </div>
          <div className="health-legend">
            <span>
              <i className="dot teal" />
              On time <strong>{fmt(k.on_time.numerator)}</strong>
            </span>
            <span>
              <i className="dot amber" />
              Delivered late <strong>{fmt(k.delayed_delivered_orders)}</strong>
            </span>
            <span>
              <i className="dot gray" />
              Excluded delivered <strong>{fmt(k.excluded_delivered)}</strong>
            </span>
          </div>
        </Panel>
      </div>
      <div className="mini-stats">
        <div>
          <CheckCircle2 size={18} />
          <span>
            First-attempt success
            <strong>
              {pct(k.first_attempt_success.value)}{" "}
              <small>
                {fmt(k.first_attempt_success.numerator)} /{" "}
                {fmt(k.first_attempt_success.denominator)}
              </small>
            </strong>
          </span>
        </div>
        <div>
          <Package size={18} />
          <span>
            SDD / NDD mix
            <strong>
              {pct(k.sla_mix.SDD.value)} / {pct(k.sla_mix.NDD.value)}
            </strong>
          </span>
        </div>
        <div>
          <TrendingUp size={18} />
          <span>
            Cost per successful delivery
            <strong>{money(k.cost_per_successful_delivery)}</strong>
          </span>
        </div>
        <div>
          <Clock3 size={18} />
          <span>
            90th percentile fulfilment
            <strong>{fmt(k.p90_delivery_hours, 1)} h</strong>
          </span>
        </div>
      </div>
      <div className="grid-equal">
        <Panel
          title="SLA performance trend"
          subtitle="On-time share of eligible delivered orders (%)"
        >
          <Trend
            data={d.trends}
            metric="on_time_rate"
            color="#4e7dda"
            height={220}
          />
        </Panel>
        <Panel
          title="Priority investigations"
          subtitle="Evidence-backed rules · no automatic actions"
          action={
            <Link className="text-link" to="/quality">
              Data quality <ArrowRight size={13} />
            </Link>
          }
        >
          <div className="investigations">
            {d.recommendations.length ? (
              d.recommendations.slice(0, 3).map((r: any, i: number) => (
                <div className="investigation" key={i}>
                  <span className="alert-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <strong>{r.problem}</strong>
                    <p>{r.evidence}</p>
                    <small>{r.action}</small>
                  </div>
                  <Badge tone="amber">{r.priority}</Badge>
                </div>
              ))
            ) : (
              <Empty text="No rule-based alerts meet the evidence threshold." />
            )}
          </div>
        </Panel>
      </div>
      <Panel
        title="City performance"
        subtitle="Raw operating mix differs by city; investigate before attributing cause"
      >
        <Table rows={d.cities} columns={cohortColumns} pageSize={8} />
      </Panel>
      <Panel
        title="Fulfilment-centre performance"
        subtitle="All centre comparisons use the same selected order window"
      >
        <Table
          rows={d.centers.map((r: any) => ({ ...r, id: r.center_name }))}
          columns={cohortColumns}
        />
      </Panel>
    </>
  );
}

export function Delivery({ filters }: PageProps) {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const q = useData("delivery/analysis", filters);
  const list = useData("shipments", {
    ...filters,
    status,
    page,
    page_size: 20,
  });
  const detail = useData(selected ? `shipments/${selected}` : "shipments", {
    page_size: 1,
  });
  if (q.isPending) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data;
  return (
    <>
      <KPIs k={d.kpis} />
      <div className="grid-equal">
        <Panel
          title="Order lifecycle decomposition"
          subtitle="Mean duration in hours; each stage reports its own eligible sample"
        >
          <Bars data={d.lifecycle} x="stage" y="hours" />
          {d.lifecycle.map((r: any) => (
            <span className="sample" key={r.stage}>
              {r.stage}: n={fmt(r.sample_size)}
            </span>
          ))}
        </Panel>
        <Panel
          title="Shipment status"
          subtitle="Mutually exclusive operational statuses"
        >
          <Bars data={d.status} x="status" y="orders" color="#6089d6" />
        </Panel>
      </div>
      <div className="grid-equal">
        <Panel
          title="Delivery-time distribution"
          subtitle="Creation to delivery · hours · eligible completions"
        >
          <Bars data={d.distribution} x="band" y="orders" />
        </Panel>
        <Panel
          title="Backlog association"
          subtitle="Dispatch backlog cohorts; association does not establish causation"
        >
          <Table
            rows={d.by_backlog}
            columns={cohortColumns.slice(0, 4)}
            searchable={false}
          />
        </Panel>
      </div>
      <Panel
        title="Shipment explorer"
        subtitle="Open a shipment to inspect its recorded event history"
        action={
          <select
            aria-label="Shipment status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {[
              "OVERDUE",
              "DELIVERED",
              "IN_TRANSIT",
              "PENDING",
              "FAILED",
              "CANCELLED",
              "RETURNED",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        }
      >
        {list.isPending ? (
          <Loading />
        ) : list.error ? (
          <ErrorBox error={list.error} />
        ) : (
          <>
            <Table
              rows={list.data.rows}
              pageSize={20}
              columns={[
                { key: "shipment_id", label: "Shipment" },
                { key: "city", label: "City" },
                { key: "partner_name", label: "Partner" },
                {
                  key: "shipment_status",
                  label: "Status",
                  render: (r: any) => (
                    <Badge tone={r.late ? "amber" : "neutral"}>
                      {r.shipment_status}
                    </Badge>
                  ),
                },
                {
                  key: "promised_delivery_at",
                  label: "Promise · IST",
                  render: (r: any) =>
                    r.promised_delivery_at
                      ? localTime(r.promised_delivery_at)
                      : "—",
                },
              ]}
              onRow={(r) => setSelected(r.shipment_id)}
            />
            <div className="pagination">
              <span>
                API page {page} · {fmt(list.data.total)} total shipments
              </span>
              <div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page * 20 >= list.data.total}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Panel>
      <div className="grid-equal">
        <Panel
          title="Day-of-week cohorts"
          subtitle="Order creation in Asia/Kolkata"
        >
          <Table rows={d.by_day} columns={cohortColumns.slice(0, 4)} />
        </Panel>
        <Panel
          title="Distance cohorts"
          subtitle="Different route distances limit raw partner comparisons"
        >
          <Table rows={d.by_distance} columns={cohortColumns.slice(0, 4)} />
        </Panel>
      </div>
      <p className="footnote">{d.note}</p>
      {selected && (
        <div className="modal-backdrop" onClick={() => setSelected(null)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-label="Shipment history"
            className="modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-head">
              <h2>{selected} · Event history</h2>
              <Button
                variant="ghost"
                onClick={() => setSelected(null)}
                aria-label="Close shipment history"
              >
                <X size={19} />
              </Button>
            </div>
            {detail.isPending ? (
              <Loading />
            ) : detail.error ? (
              <ErrorBox error={detail.error} />
            ) : (
              <div className="timeline">
                {detail.data.events?.map((e: any) => (
                  <div key={e.event_id}>
                    <span />
                    <strong>{e.event_type.replaceAll("_", " ")}</strong>
                    <small>{localTime(e.event_timestamp)} IST</small>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}

export function Zones({ filters, meta }: PageProps) {
  const [weights, setWeights] = useState([0.2, 0.3, 0.2, 0.2, 0.1]);
  const [selected, setSelected] = useState("");
  const q = useData("zones", {
    ...filters,
    ...Object.fromEntries(
      ["volume", "delay", "impact", "gap", "feasibility"].map((k, i) => [
        k,
        weights[i],
      ]),
    ),
  });
  const detail = useData(
    selected ? `zones/${selected}/performance` : "delivery/trends",
    filters,
  );
  if (q.isPending) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const rows = q.data.rows;
  return (
    <>
      <div className="grid-main">
        <Panel
          title="Service footprint"
          subtitle="Illustrative zone-point map · fictional identifiers · not pincode boundaries"
        >
          <div className="zone-map">
            <div className="map-grid" />
            {rows.map((r: any) => (
              <button
                key={r.id}
                title={`${r.zone_code} · ${r.city} · ${pct(r.on_time_rate)} on time`}
                onClick={() => setSelected(r.id)}
                aria-label={`Select ${r.zone_code}`}
                className={`map-point ${(r.on_time_rate ?? 100) < 80 ? "warning" : ""} ${selected === r.id ? "selected" : ""}`}
                style={{
                  left: `${8 + ((r.longitude - 72) / 18) * 80}%`,
                  top: `${90 - ((r.latitude - 12) / 18) * 78}%`,
                  width: Math.max(8, Math.min(22, Math.sqrt(r.orders))),
                }}
              />
            ))}
            <span className="map-label" style={{ top: "15%", left: "35%" }}>
              NORTH
            </span>
            <span className="map-label" style={{ top: "49%", left: "9%" }}>
              WEST
            </span>
            <span className="map-label" style={{ top: "46%", left: "77%" }}>
              EAST
            </span>
            <span className="map-label" style={{ top: "88%", left: "39%" }}>
              SOUTH
            </span>
            <span className="map-note">
              Circle size = order volume · amber = on time &lt;80%
            </span>
          </div>
        </Panel>
        <Panel
          title="Opportunity score"
          subtitle="Configurable investigation priorities"
        >
          {[
            "Volume",
            "Delay rate",
            "Late-order impact",
            "SLA gap",
            "Feasibility",
          ].map((name, i) => (
            <label className="slider-label" key={name}>
              {name}
              <strong>{weights[i].toFixed(2)}</strong>
              <input
                type="range"
                min="0"
                max="1"
                step=".05"
                value={weights[i]}
                onChange={(e) =>
                  setWeights((w) => {
                    const next = w.map((v, j) =>
                      i === j ? Number(e.target.value) : v,
                    );
                    return next.some((v) => v > 0) ? next : w;
                  })
                }
              />
            </label>
          ))}
          <p className="footnote">{q.data.note}</p>
        </Panel>
      </div>
      <Panel
        title="Zone comparison"
        subtitle="Select a row or map point to inspect the zone"
      >
        <Table
          rows={rows}
          columns={[
            { key: "zone_code", label: "Fictional zone" },
            { key: "city", label: "City" },
            ...cohortColumns.slice(1),
            {
              key: "score",
              label: "Opportunity score",
              render: (r: any) => (
                <strong className="text-teal">{fmt(r.score, 1)}</strong>
              ),
            },
          ]}
          onRow={(r) => setSelected(r.id)}
        />
      </Panel>
      {selected && (
        <Panel
          title={`${meta.zones.find((z: any) => z.zone_id === selected)?.zone_code} · Zone profile`}
          subtitle="Selected order cohort"
        >
          <div className="score-components">
            {Object.entries(
              rows.find((r: any) => r.id === selected)?.score_components ?? {},
            ).map(([key, value]) => (
              <span key={key}>
                {key}
                <strong>{fmt(Number(value), 1)}</strong>
              </span>
            ))}
          </div>
          {detail.isPending ? (
            <Loading />
          ) : detail.error ? (
            <ErrorBox error={detail.error} />
          ) : (
            <>
              <Trend data={detail.data.trends ?? []} />
              <Table
                rows={detail.data.partners ?? []}
                columns={cohortColumns}
              />
            </>
          )}
        </Panel>
      )}
    </>
  );
}

export function Partners({ filters }: PageProps) {
  const [selected, setSelected] = useState<string[]>([]);
  const [weights, setWeights] = useState([0.45, 0.2, 0.2, 0.15]);
  const q = useData("partners", {
    ...filters,
    ...Object.fromEntries(
      ["reliability", "speed", "first", "cost"].map((k, i) => [k, weights[i]]),
    ),
  });
  if (q.isPending) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data;
  return (
    <>
      <div className="callout">
        <ShieldIcon />
        {d.warning}
      </div>
      <div className="weight-grid">
        {["Reliability", "Speed", "First attempt", "Cost efficiency"].map(
          (n, i) => (
            <label className="slider-label" key={n}>
              {n}
              <strong>{weights[i].toFixed(2)}</strong>
              <input
                type="range"
                min="0"
                max="1"
                step=".05"
                value={weights[i]}
                onChange={(e) =>
                  setWeights((w) => {
                    const next = w.map((v, j) =>
                      i === j ? Number(e.target.value) : v,
                    );
                    return next.some((v) => v > 0) ? next : w;
                  })
                }
              />
            </label>
          ),
        )}
      </div>
      <Panel
        title="Partner scorecards"
        subtitle={`${d.shared_cohorts} comparable cohorts · select up to four partners`}
      >
        <div className="partner-grid">
          {d.rows.map((r: any) => (
            <button
              className={`partner-card ${selected.includes(r.id) ? "selected" : ""}`}
              key={r.id}
              onClick={() =>
                setSelected((s) =>
                  s.includes(r.id)
                    ? s.filter((x) => x !== r.id)
                    : s.length < 4
                      ? [...s, r.id]
                      : s,
                )
              }
              aria-pressed={selected.includes(r.id)}
            >
              <div className="partner-header">
                <span className="partner-logo">{r.id}</span>
                <Badge tone="teal">
                  {r.score == null ? "NO MATCH" : `${fmt(r.score, 1)} / 100`}
                </Badge>
              </div>
              <h3>{r.partner_name}</h3>
              <p>
                {fmt(r.orders)} orders · {fmt(r.matched_share, 1)}% matched
                coverage
              </p>
              <div className="partner-metric">
                <span>Adjusted on time</span>
                <strong>{pct(r.adjusted_on_time)}</strong>
              </div>
              <div className="partner-metric">
                <span>Raw on time</span>
                <strong>{pct(r.on_time_rate)}</strong>
              </div>
              <div className="partner-metric">
                <span>Cost / shipment</span>
                <strong>{money(r.cost_per_shipment)}</strong>
              </div>
              <div className="progress-track">
                <i style={{ width: `${r.score ?? 0}%` }} />
              </div>
              <small>
                {selected.includes(r.id)
                  ? "Selected for comparison"
                  : "Select for comparison"}
              </small>
            </button>
          ))}
        </div>
      </Panel>
      {selected.length > 0 && (
        <Panel
          title="Selected partner comparison"
          subtitle="Raw metrics alongside cohort-standardised components"
        >
          <Table
            rows={d.rows
              .filter((r: any) => selected.includes(r.id))
              .map((r: any) => ({ ...r, ...r.components }))}
            columns={[
              { key: "partner_name", label: "Partner" },
              ...cohortColumns.slice(1),
              { key: "score", label: "Adjusted score" },
              {
                key: "reliability",
                label: "Reliability",
                render: (r: any) => fmt(r.reliability, 1),
              },
              {
                key: "speed",
                label: "Speed",
                render: (r: any) => fmt(r.speed, 1),
              },
              {
                key: "first_attempt",
                label: "First attempt",
                render: (r: any) => fmt(r.first_attempt, 1),
              },
              {
                key: "cost_efficiency",
                label: "Cost efficiency",
                render: (r: any) => fmt(r.cost_efficiency, 1),
              },
            ]}
            searchable={false}
          />
        </Panel>
      )}
      <Panel
        title="Operational performance"
        subtitle="Return and failure rates refer only to attributed shipment statuses"
      >
        <Table
          rows={d.rows}
          columns={[
            { key: "partner_name", label: "Partner" },
            ...cohortColumns.slice(1),
            {
              key: "p90_hours",
              label: "P90 (h)",
              render: (r: any) => fmt(r.p90_hours, 1),
            },
            {
              key: "failure_rate",
              label: "Failure",
              render: (r: any) => pct(r.failure_rate),
            },
            {
              key: "return_rate",
              label: "Return",
              render: (r: any) => pct(r.return_rate),
            },
            {
              key: "first_attempt_success",
              label: "First attempt",
              render: (r: any) => pct(r.first_attempt_success),
            },
          ]}
        />
      </Panel>
    </>
  );
}
function ShieldIcon() {
  return <CheckCircle2 size={18} />;
}

export function InventoryPage({ filters }: PageProps) {
  const [window, setWindow] = useState(30);
  const [safety, setSafety] = useState(20);
  const [target, setTarget] = useState(21);
  const [lead, setLead] = useState("");
  const [pack, setPack] = useState(10);
  const [minimum, setMinimum] = useState(10);
  const [sku, setSku] = useState("");
  const q = useData("inventory/overview", {
    city: filters.city,
    center: filters.center,
    window,
    safety_stock: safety,
    target_days: target,
    lead_time: lead,
    pack_size: pack,
    minimum,
  });
  if (q.isPending) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data,
    k = d.kpis;
  const shown = d.rows.filter((r: any) => !sku || r.sku_id === sku);
  return (
    <>
      <div className="stats-grid">
        <Stat
          label="Sellable inventory"
          value={fmt(k.available_inventory)}
          note="On hand − reserved − quarantined; eligible batches"
        />
        <Stat
          label="SKUs at stock-out risk"
          value={fmt(k.stockout_risk_skus)}
          note={`${fmt(k.risk_sku_center_pairs)} SKU–centre pairs below lead-time demand`}
          tone="amber"
        />
        <Stat
          label="Expiring within 30 days"
          value={fmt(k.near_expiry_units)}
          note={`${money(k.near_expiry_value)} recorded value at risk`}
          tone="amber"
        />
        <Stat
          label="Inventory holding value"
          value={money(k.inventory_value)}
          note={`${fmt(k.total_inventory_units)} on-hand units · all statuses`}
          tone="blue"
        />
      </div>
      <Panel
        title="Replenishment assumptions"
        subtitle="Illustrative; validate before procurement"
      >
        <div className="form-grid">
          {[
            ["Demand window", window, setWindow, 7, 90],
            ["Safety stock", safety, setSafety, 0, 10000],
            ["Target days", target, setTarget, 1, 180],
            ["Pack size", pack, setPack, 1, 1000],
            ["Minimum quantity", minimum, setMinimum, 1, 10000],
          ].map(([name, value, setter, min, max]) => (
            <label key={String(name)}>
              {String(name)}
              <input
                type="number"
                min={Number(min)}
                max={Number(max)}
                value={Number(value)}
                onChange={(e) =>
                  (setter as (n: number) => void)(
                    Math.max(
                      Number(min),
                      Math.min(Number(max), Number(e.target.value)),
                    ),
                  )
                }
              />
            </label>
          ))}
          <label>
            Lead time override
            <input
              aria-label="Lead time override"
              type="number"
              min="1"
              max="90"
              placeholder="Supplier default"
              value={lead}
              onChange={(e) => setLead(e.target.value)}
            />
          </label>
        </div>
      </Panel>
      <div className="grid-equal">
        <Panel
          title="Expiry exposure by centre"
          subtitle="Overlapping cumulative windows · units"
        >
          <Bars
            data={d.expiry}
            x="fulfillment_center_id"
            y="within_30"
            color="#d7a04a"
          />
        </Panel>
        <Panel
          title="Stock eligibility"
          subtitle="Snapshot units; reservations are subsets of on-hand stock"
        >
          <div className="eligibility">
            <div>
              <span>On hand</span>
              <strong>{fmt(k.total_inventory_units)}</strong>
            </div>
            <div>
              <span>Reserved</span>
              <strong>{fmt(k.reserved_inventory)}</strong>
            </div>
            <div>
              <span>Quarantined reservations</span>
              <strong>{fmt(k.quarantined_inventory)}</strong>
            </div>
            <div>
              <span>Expired</span>
              <strong>{fmt(k.expired_units)}</strong>
            </div>
            <div>
              <span>Expiring within 60 / 90 days</span>
              <strong>
                {fmt(k.units_expiring_60)} / {fmt(k.units_expiring_90)}
              </strong>
            </div>
            <div>
              <span>Demand / sellable-stock proxy</span>
              <strong>{fmt(k.inventory_turnover_proxy, 2)}×</strong>
            </div>
          </div>
        </Panel>
      </div>
      <Panel
        title="Inventory health & reorder queue"
        subtitle="Includes demand-active SKU–centre pairs with no recorded batches"
        action={
          <select
            aria-label="Select SKU"
            value={sku}
            onChange={(e) => setSku(e.target.value)}
          >
            <option value="">All SKUs</option>
            {Array.from(new Set<string>(d.rows.map((r: any) => r.sku_id)))
              .sort()
              .map((s) => (
                <option key={s}>{s}</option>
              ))}
          </select>
        }
      >
        <Table
          rows={shown}
          columns={[
            { key: "sku_id", label: "SKU" },
            { key: "product_name", label: "Fictional product" },
            { key: "fulfillment_center_id", label: "Centre" },
            {
              key: "available",
              label: "Sellable",
              render: (r: any) => fmt(r.available),
            },
            {
              key: "days_of_cover",
              label: "Days of cover",
              render: (r: any) =>
                r.days_of_cover == null ? (
                  <Badge>No demand</Badge>
                ) : (
                  <Badge tone={r.stockout_risk ? "amber" : "teal"}>
                    {fmt(r.days_of_cover, 1)} days
                  </Badge>
                ),
            },
            {
              key: "avg_daily_demand",
              label: "Daily demand",
              render: (r: any) => fmt(r.avg_daily_demand, 2),
            },
            {
              key: "reorder_point",
              label: "Reorder point",
              render: (r: any) => fmt(r.reorder_point, 1),
            },
            { key: "suggested_quantity", label: "Suggested qty." },
            { key: "demand_status", label: "Evidence" },
          ]}
        />
      </Panel>
      <Panel
        title="FEFO: first expiry, first out"
        subtitle="Eligible batches only · sort order is illustrative; no transfers are executed"
      >
        <Table
          rows={d.fefo.filter((r: any) => !sku || r.sku_id === sku)}
          columns={[
            { key: "batch_id", label: "Batch" },
            { key: "sku_id", label: "SKU" },
            { key: "fulfillment_center_id", label: "Centre" },
            {
              key: "days_to_expiry",
              label: "Days to expiry",
              render: (r: any) => fmt(r.days_to_expiry),
            },
            { key: "sellable_units", label: "Sellable units" },
            { key: "age_days", label: "Stock age (days)" },
          ]}
        />
      </Panel>
      <p className="footnote">{d.assumptions.note}</p>
    </>
  );
}
