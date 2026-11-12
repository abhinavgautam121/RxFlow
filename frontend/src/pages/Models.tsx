import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { BrainCircuit, Play, Sparkles } from "lucide-react";
import { useData, type PageProps } from "../App";
import {
  Badge,
  Bars,
  ErrorBox,
  ForecastChart,
  Loading,
  Panel,
  Stat,
  Table,
} from "../components/common";
import { Button } from "../components/ui/button";
import { api, fmt, localTime, pct } from "../lib";

export function Predictive({ filters, meta }: PageProps) {
  const report = useData("models/performance");
  const risks = useData("predictions/high-risk", filters);
  const [category, setCategory] = useState("");
  const [zone, setZone] = useState("");
  const forecast = useData("forecast", { ...filters, zone, category });
  const [inputs, setInputs] = useState<Record<string, string | number>>({
    zone_id: "Z000",
    fulfillment_center_id: "FC1",
    delivery_partner_id: "LP1",
    promised_service_level: "NDD",
    distance_band_km: 25,
    order_to_dispatch_hours: 5,
    picking_hours: 2,
    packing_hours: 1,
    backlog_at_dispatch: 30,
    order_hour: 10,
    order_weekday: 1,
    remaining_promise_hours: 25,
    low_threshold: 0.3,
    high_threshold: 0.6,
  });
  const prediction = useMutation({
    mutationFn: () =>
      api("predictions/delay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(inputs),
      }),
  });
  if (report.isPending) return <Loading />;
  if (report.error)
    return <ErrorBox error={report.error} retry={() => report.refetch()} />;
  const d = report.data;
  const test = d.models[d.selected_model].test;
  const metrics = Object.entries(d.models).map(([model, r]) => ({
    model,
    ...(r as any).test,
  }));
  return (
    <>
      <div className="insight-strip">
        <div className="insight-icon">
          <BrainCircuit size={22} />
        </div>
        <div>
          <strong>Prediction point: dispatch.</strong>
          <span>
            Only information known when a shipment leaves the fulfilment centre
            is used.
          </span>
        </div>
        <Badge tone="blue">CHRONOLOGICAL HOLDOUT</Badge>
      </div>
      <div className="stats-grid">
        <Stat
          label="Test ROC-AUC"
          value={fmt(test.roc_auc, 3)}
          note={`${fmt(test.sample_size)} untouched test shipments`}
        />
        <Stat
          label="Test PR-AUC"
          value={fmt(test.pr_auc, 3)}
          note={`Positive class share ${pct(test.positive_share * 100)}`}
        />
        <Stat
          label="Precision / recall"
          value={`${fmt(test.precision, 2)} / ${fmt(test.recall, 2)}`}
          note={`Validation-selected threshold ${fmt(test.threshold, 2)}`}
          tone="blue"
        />
        <Stat
          label="Brier score"
          value={fmt(test.brier_score, 3)}
          note="Lower is better · inspect calibration"
          tone="blue"
        />
      </div>
      <div className="grid-equal">
        <Panel
          title="Model comparison"
          subtitle="Test metrics · model chosen on validation PR-AUC"
        >
          <Table
            rows={metrics}
            columns={[
              { key: "model", label: "Model" },
              {
                key: "roc_auc",
                label: "ROC-AUC",
                render: (r: any) => fmt(r.roc_auc, 3),
              },
              {
                key: "pr_auc",
                label: "PR-AUC",
                render: (r: any) => fmt(r.pr_auc, 3),
              },
              { key: "f1", label: "F1", render: (r: any) => fmt(r.f1, 3) },
              {
                key: "recall",
                label: "Recall",
                render: (r: any) => fmt(r.recall, 3),
              },
            ]}
            searchable={false}
          />
          <p className="footnote">{d.selection_reason}</p>
        </Panel>
        <Panel
          title="Global feature associations"
          subtitle="Permutation importance · validation PR-AUC decrease"
        >
          <Bars
            data={d.importance.slice(0, 6).map((r: any) => ({
              ...r,
              feature: r.feature.replaceAll("_", " "),
            }))}
            x="feature"
            y="importance"
            height={240}
          />
        </Panel>
      </div>
      <Panel title="Evaluation provenance" subtitle={d.version}>
        <div className="score-components">
          <span>
            Training rows<strong>{fmt(d.split.train)}</strong>
          </span>
          <span>
            Validation rows<strong>{fmt(d.split.validation)}</strong>
          </span>
          <span>
            Test rows<strong>{fmt(d.split.test)}</strong>
          </span>
          <span>
            Trained at · IST<strong>{localTime(d.trained_at)}</strong>
          </span>
        </div>
        <p className="footnote">
          Training labels were observed before{" "}
          {localTime(d.split.validation_dispatch_start)} IST. Validation labels
          were observed before {localTime(d.split.test_dispatch_start)} IST. No
          future outcomes, attempt counts or delivery events are input features.
        </p>
        <div className="grid-equal">
          <div>
            <h3>Calibration by probability bin</h3>
            <Table
              rows={test.calibration}
              columns={[
                {
                  key: "predicted",
                  label: "Mean predicted",
                  render: (r: any) => pct(r.predicted * 100),
                },
                {
                  key: "observed",
                  label: "Observed delay",
                  render: (r: any) => pct(r.observed * 100),
                },
              ]}
              pageSize={8}
              searchable={false}
            />
          </div>
          <div>
            <h3>Confusion matrix</h3>
            <table className="matrix">
              <thead>
                <tr>
                  <th>Actual / predicted</th>
                  <th>On time</th>
                  <th>Late</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>On time</th>
                  <td>{fmt(test.confusion_matrix[0][0])}</td>
                  <td>{fmt(test.confusion_matrix[0][1])}</td>
                </tr>
                <tr>
                  <th>Late</th>
                  <td>{fmt(test.confusion_matrix[1][0])}</td>
                  <td>{fmt(test.confusion_matrix[1][1])}</td>
                </tr>
              </tbody>
            </table>
            <div className="callout">{d.limitations.join(" ")}</div>
          </div>
        </div>
      </Panel>
      <Panel
        title="Dispatch-time prediction workbench"
        subtitle="Model estimate based on fictional operations; demonstration thresholds are configurable"
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            prediction.mutate();
          }}
        >
          <div className="form-grid">
            <label>
              Fulfilment centre
              <select
                value={inputs.fulfillment_center_id}
                onChange={(e) =>
                  setInputs({
                    ...inputs,
                    fulfillment_center_id: e.target.value,
                  })
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
            <label>
              Delivery partner
              <select
                value={inputs.delivery_partner_id}
                onChange={(e) =>
                  setInputs({ ...inputs, delivery_partner_id: e.target.value })
                }
              >
                {meta.partners.map((c: any) => (
                  <option
                    key={c.delivery_partner_id}
                    value={c.delivery_partner_id}
                  >
                    {c.partner_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Zone
              <select
                value={inputs.zone_id}
                onChange={(e) =>
                  setInputs({ ...inputs, zone_id: e.target.value })
                }
              >
                {meta.zones.map((c: any) => (
                  <option key={c.zone_id} value={c.zone_id}>
                    {c.zone_code} · {c.city}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Service promise
              <select
                value={inputs.promised_service_level}
                onChange={(e) =>
                  setInputs({
                    ...inputs,
                    promised_service_level: e.target.value,
                  })
                }
              >
                {["SDD", "NDD", "OTHER"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            {[
              ["distance_band_km", "Distance (km)", 0, 500, 1],
              ["order_to_dispatch_hours", "Processing (hours)", 0, 240, 0.1],
              ["picking_hours", "Picking (hours)", 0, 120, 0.1],
              ["packing_hours", "Packing (hours)", 0, 120, 0.1],
              ["backlog_at_dispatch", "Backlog at dispatch", 0, 10000, 1],
              [
                "remaining_promise_hours",
                "Promise remaining (hours)",
                -240,
                240,
                0.1,
              ],
              ["order_hour", "Order hour · IST", 0, 23, 1],
              ["order_weekday", "Weekday (Mon = 0)", 0, 6, 1],
              ["low_threshold", "Low-risk threshold", 0, 0.99, 0.05],
              ["high_threshold", "High-risk threshold", 0.01, 1, 0.01],
            ].map(([key, label, min, max, step]) => (
              <label key={String(key)}>
                {String(label)}
                <input
                  type="number"
                  required
                  min={Number(min)}
                  max={Number(max)}
                  step={Number(step)}
                  value={inputs[String(key)]}
                  onChange={(e) =>
                    setInputs({
                      ...inputs,
                      [String(key)]: Number(e.target.value),
                    })
                  }
                />
              </label>
            ))}
          </div>
          <Button type="submit" disabled={prediction.isPending}>
            <Sparkles size={15} />
            {prediction.isPending ? "Estimating…" : "Estimate delay risk"}
          </Button>
        </form>
        {prediction.error && <ErrorBox error={prediction.error} />}{" "}
        {prediction.data && (
          <div className="prediction-result" role="status">
            <div>
              <span>Estimated delay probability</span>
              <strong>{pct(prediction.data.delay_probability * 100)}</strong>
              <Badge
                tone={prediction.data.risk_level === "HIGH" ? "amber" : "teal"}
              >
                {prediction.data.risk_level} RISK
              </Badge>
            </div>
            <p>
              {prediction.data.explanation}
              <small>
                Version: {prediction.data.model_version} ·{" "}
                {localTime(prediction.data.prediction_timestamp)} IST
              </small>
            </p>
          </div>
        )}
      </Panel>
      <Panel
        title="Active shipment risk queue"
        subtitle="Dispatched, in-transit shipments · highest estimates first"
      >
        {risks.isPending ? (
          <Loading />
        ) : risks.error ? (
          <ErrorBox error={risks.error} />
        ) : (
          <>
            <Table
              rows={risks.data.rows}
              columns={[
                { key: "shipment_id", label: "Shipment" },
                { key: "city", label: "City" },
                { key: "partner_name", label: "Partner" },
                {
                  key: "delay_probability",
                  label: "Delay probability",
                  render: (r: any) => pct(r.delay_probability * 100),
                },
                {
                  key: "risk_level",
                  label: "Risk",
                  render: (r: any) => (
                    <Badge tone={r.risk_level === "HIGH" ? "amber" : "teal"}>
                      {r.risk_level}
                    </Badge>
                  ),
                },
              ]}
            />
            <p className="footnote">
              Showing the top 25 of {risks.data.total} eligible active
              shipments; paginated API supports the full queue.
            </p>
          </>
        )}
      </Panel>
      <Panel
        title="Demand planning"
        subtitle="Daily, weekly and optional zone/category cohorts · fixed-origin holdout"
      >
        <div className="form-grid">
          <label>
            Forecast zone
            <select value={zone} onChange={(e) => setZone(e.target.value)}>
              <option value="">All selected zones</option>
              {meta.zones.map((z: any) => (
                <option key={z.zone_id} value={z.zone_id}>
                  {z.zone_code} · {z.city}
                </option>
              ))}
            </select>
          </label>
          <label>
            Product category
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">All categories</option>
              {[
                "Wellness",
                "Chronic care",
                "Seasonal care",
                "Personal care",
                "Essentials",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
        {forecast.isPending ? (
          <Loading />
        ) : forecast.error ? (
          <ErrorBox error={forecast.error} />
        ) : forecast.data.sufficient ? (
          <>
            <ForecastChart
              data={[...forecast.data.history, ...forecast.data.forecast]}
            />
            <Table
              rows={Object.entries(forecast.data.evaluation).map(
                ([method, m]) => ({ method, ...(m as any) }),
              )}
              columns={[
                { key: "method", label: "Forecast baseline" },
                {
                  key: "mae",
                  label: "Holdout MAE",
                  render: (r: any) => fmt(r.mae, 2),
                },
                {
                  key: "wape",
                  label: "Holdout WAPE",
                  render: (r: any) => pct(r.wape * 100),
                },
              ]}
              searchable={false}
            />
            <div className="grid-equal">
              <div>
                <h3>
                  Forward planning range · {forecast.data.selected_method}
                </h3>
                <Table
                  rows={forecast.data.forecast}
                  columns={[
                    { key: "date", label: "Date" },
                    { key: "predicted", label: "Forecast orders" },
                    { key: "lower", label: "Lower" },
                    { key: "upper", label: "Upper" },
                  ]}
                  pageSize={7}
                  searchable={false}
                />
              </div>
              <div>
                <h3>Weekly order volume</h3>
                <Bars
                  data={forecast.data.weekly.map((r: any) => ({
                    ...r,
                    week: r.week.slice(5, 10),
                  }))}
                  x="week"
                  y="orders"
                  height={220}
                />
              </div>
            </div>
            <p className="footnote">{forecast.data.warning}</p>
          </>
        ) : (
          <p className="callout">{forecast.data.warning}</p>
        )}
      </Panel>
    </>
  );
}

export function Methodology() {
  return (
    <div className="methodology">
      <Panel
        title="A transparent operational intelligence product"
        subtitle="Independent portfolio · fictional Indian e-pharmacy operation"
      >
        <p>
          RxFlow follows five decisions: monitor performance, identify
          bottlenecks, investigate associations, estimate risk, and simulate
          interventions. The dataset and every company, SKU, supplier, zone
          identifier and coordinate are fictional. The project has no
          affiliation with PlatinumRx or another pharmacy.
        </p>
        <div className="method-steps">
          {["Monitor", "Identify", "Investigate", "Predict", "Simulate"].map(
            (s, i) => (
              <div key={s}>
                <span>0{i + 1}</span>
                <strong>{s}</strong>
              </div>
            ),
          )}
        </div>
      </Panel>
      <Panel
        title="Metric dictionary"
        subtitle="Source tables and population rules are also documented in docs/methodology.md"
      >
        <Table
          searchable={false}
          pageSize={20}
          rows={[
            {
              metric: "On-time delivery",
              formula:
                "Eligible delivered at or before promise / eligible delivered",
              source: "orders + shipments",
              population:
                "Valid promise ≥ creation; creation ≤ dispatch ≤ delivery. Equality at promise is on time.",
            },
            {
              metric: "Delivered late",
              formula: "Count eligible delivered with delivery > promise",
              source: "orders + shipments",
              population: "Completed shipments only.",
            },
            {
              metric: "Currently overdue",
              formula: "Active shipments with valid promise before snapshot",
              source: "orders + shipments",
              population:
                "PENDING and IN_TRANSIT; excludes cancelled, failed and returned.",
            },
            {
              metric: "Average / median / P90 fulfilment",
              formula: "Delivery timestamp − creation timestamp (hours)",
              source: "orders + shipments",
              population:
                "Eligible completed deliveries. P90 is the 90th percentile.",
            },
            {
              metric: "First-attempt success",
              formula:
                "True first-attempt successes / shipments with ≥1 attempt",
              source: "shipments",
              population:
                "Only attempted shipments; unattempted shipments excluded.",
            },
            {
              metric: "Cancellation rate",
              formula: "Cancelled orders / all orders",
              source: "orders",
              population: "Selected creation cohort.",
            },
            {
              metric: "Delivery failure rate",
              formula: "Failed shipments / dispatched shipments",
              source: "shipments",
              population:
                "Explicit failed terminal statuses; returns shown separately.",
            },
            {
              metric: "Cost per successful delivery",
              formula: "Total recorded shipping cost / eligible delivered",
              source: "shipments",
              population:
                "Includes spend on failed/returned shipments in the numerator.",
            },
            {
              metric: "Available to promise",
              formula: "On hand − reserved − quarantined, floored at zero",
              source: "inventory_batches",
              population: "Active, received and unexpired batches only.",
            },
            {
              metric: "Days of cover",
              formula: "Sellable units / average daily non-cancelled demand",
              source: "inventory_batches + order_items + orders",
              population:
                "Selected demand window ending at fixed snapshot; null means no demand.",
            },
            {
              metric: "Reorder point",
              formula: "Daily demand × supplier lead time + safety stock",
              source: "products + suppliers + inventory",
              population:
                "Order suggestion only when below reorder point; quantity rounded to pack size and minimum.",
            },
            {
              metric: "Near expiry",
              formula:
                "Recorded stock expiring in (snapshot, snapshot + window]",
              source: "inventory_batches",
              population:
                "30, 60 and 90 day windows are cumulative and overlap.",
            },
            {
              metric: "Partner score",
              formula:
                "Weighted reliability, speed, first-attempt success, cost efficiency",
              source: "eligible delivered cohorts",
              population:
                "Direct standardisation on shared city × distance × SLA; n≥3 per partner in each cohort.",
            },
            {
              metric: "Zone opportunity score",
              formula:
                "Weighted volume, delay, impact, SLA gap and feasibility",
              source: "orders + shipments",
              population:
                "Heuristic priorities only; no causal or new-facility conclusions.",
            },
          ]}
          columns={[
            { key: "metric", label: "Metric" },
            { key: "formula", label: "Definition" },
            { key: "source", label: "Source" },
            { key: "population", label: "Eligibility / limitation" },
          ]}
        />
      </Panel>
      <div className="grid-equal">
        <Panel title="Prediction methodology">
          <p>
            Only delivered historical shipments create a target: delivery later
            than promise. Data are sorted by dispatch time into chronological
            60/20/20 windows. Training outcomes must be observed before
            validation dispatch begins; validation outcomes must be observed
            before test dispatch begins.
          </p>
          <p>
            Logistic regression and random forest are compared against a simple
            rule baseline. Validation PR-AUC selects the model; validation F1
            selects its classification threshold. Reported test metrics include
            ROC-AUC, PR-AUC, precision, recall, F1, confusion matrix,
            calibration and Brier score.
          </p>
          <p>
            Features include only values available at dispatch. Global
            permutation importance shows associations and does not explain the
            cause of an individual delay. Synthetic performance does not
            establish deployment readiness.
          </p>
        </Panel>
        <Panel title="Simulation assumptions">
          <p>
            Partner allocation reweights observed performance within the same
            zone, distance and SLA. Target cohorts need five delivered
            shipments. Target capacity is unknown and must be validated before
            operational use.
          </p>
          <p>
            Dispatch and zone interventions assume every saved processing hour
            advances arrival by one hour, capped at actual processing time.
            Capacity scenarios expose average load and overflow; they do not
            infer delivery gains. Inventory scenarios hold demand and costs
            constant.
          </p>
          <p>
            All saved results distinguish baseline measurements from
            projections. RxFlow never executes procurement, stock transfers or
            partner allocation.
          </p>
        </Panel>
      </div>
      <Panel title="Data governance, timing & known limitations">
        <p>
          CSV imports are authenticated, staged and insert-only. Unknown fields
          are rejected. Do not upload personal identifiers, prescription
          information or health records. The public demonstration is designed
          for local exploration; production use needs user authentication,
          authorisation, retention rules, rate limits and a formal model review.
        </p>
        <p>
          Timestamps are stored in UTC and displayed in Asia/Kolkata. Date
          filters describe order creation cohorts with inclusive local calendar
          dates. Inventory and data quality are snapshots and do not follow the
          order-date filter. Geography uses illustrative zone points, without
          fabricated administrative boundaries.
        </p>
        <p>
          Event histories intentionally contain missing delivery events.
          Lifecycle metrics show their own sample sizes. Stock snapshots do not
          reconstruct historical balances. Forecast bands are empirical and do
          not guarantee a coverage rate. Power BI exports and DAX are provided;
          a native Power BI Desktop report is a separate authoring step.
        </p>
        <Button variant="outline" asChild>
          <a
            href="https://github.com/abhinavgautam121/RxFlow/tree/main/docs"
            target="_blank"
            rel="noreferrer"
          >
            Read the technical documentation <Play size={13} />
          </a>
        </Button>
      </Panel>
    </div>
  );
}
