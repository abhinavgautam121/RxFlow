# Metric and modelling methodology

## Data provenance and time

The default generator uses NumPy seed 42 and a fixed UTC snapshot of `2026-11-12T00:00:00Z` (05:30 IST). It generates a configurable 180-day history. All business entities, identifiers and coordinates are fictional. Synthetic order-date probabilities vary by weekday and season; transit varies with route distance, zone, partner, retry and noise; processing varies with the centre's recorded dispatch backlog.

The UI interprets inclusive local calendar dates in Asia/Kolkata. The backend converts them to UTC `[start, end + 1 local day)`. A selected order cohort retains its subsequent shipment outcomes. Inventory/quality are snapshots, and global model evaluation does not change with dashboard filters.

## Delivery populations and formulas

An **eligible delivered shipment** has status DELIVERED, non-null creation, dispatch, delivery and promise, promise ≥ creation and creation ≤ dispatch ≤ delivery. Status alone is insufficient. Excluded delivered rows are reported separately.

| KPI | Calculation | Source / denominator |
|---|---|---|
| Total orders | Count selected order IDs | orders, left joined to shipments |
| Confirmed orders | Non-null confirmation timestamp | all selected orders |
| Dispatched orders | Non-null dispatch timestamp | selected shipments |
| Delivered orders | DELIVERED status | selected shipments; eligibility reported separately |
| Pending orders | PENDING or IN_TRANSIT | active selected shipments |
| Cancelled orders / cancellation rate | CANCELLED count / total orders | order_status |
| Delivered late | Eligible delivered with delivered_at > promise | completed eligible population |
| Currently overdue | Active + valid promise + promise < fixed snapshot | excludes delivered/cancelled/failed/returned |
| Not yet due | Active + valid promise + promise ≥ snapshot | invalid active promises reported separately |
| On-time rate | Eligible delivered_at ≤ promise / eligible delivered | numerator and denominator are returned |
| First-attempt success | first_attempt_success=True / attempt_count > 0 | unattempted shipments excluded |
| Delivery failure | FAILED / dispatched | return rate is separate |
| Order-to-dispatch time | Mean(dispatch − creation) / 3600 | non-null dispatch pairs |
| Transit time | Mean(delivery − dispatch) / 3600 | eligible delivered |
| Fulfilment time | Mean(delivery − creation) / 3600 | eligible delivered |
| Median / P90 | Quantile 0.5 / 0.9 of fulfilment time | eligible delivered |
| SDD / NDD / OTHER share | Count service-level label / selected orders | all selected orders |
| Cost / shipment | Mean recorded shipping cost | dispatched |
| Cost / successful delivery | Total cohort shipping spend / eligible delivered | includes failure/return spend in numerator |

Stage decomposition uses observed event pairs for confirmation, picking, packing, dispatch queue and last mile. Negative or >720-hour stage durations are excluded and counted. Each stage has a distinct sample size; stage averages need not sum to mean end-to-end time. Missing event histories remain visible in the quality report.

## Partner score

Construct city × distance band × promised-service-level cohorts. Retain cohorts with at least three eligible delivered records for every compared partner in the current population. Weight each cohort by its pooled delivered volume. Average each partner's cohort-level metrics against those common weights.

Components, each bounded to 0–100:

- Reliability: standardised on-time share.
- Speed: `clip(100 − standardised fulfilment_hours × 1.5, 0, 100)`.
- First attempt: standardised first-attempt-success share among eligible completed deliveries.
- Cost efficiency: `clip(100 − standardised mean shipping_cost_INR, 0, 100)`.

Default weights: 0.45, 0.20, 0.20, 0.15. A weighted average normalises non-unit weight sums. If no shared observations exist, score is null. The UI shows matched coverage and warns about operating mix. Scaling constants are illustrative policy choices, not universal benchmarks. Raw operational KPIs are also shown, with their separate populations.

## Zone opportunity score

Components: relative order volume (20%), delay share (30%), relative late-order impact (20%), gap to 95% on-time service (20%), and inverse-distance feasibility (10%). Relative components use the maximum in the current filtered population; weights are configurable. Feasibility is `100 × (1 − distance_band_km / 100)` for the demonstration's ≤70 km zones. This heuristic prioritises investigation and does not imply that a centre should be built or that a factor caused delays.

## Inventory

`quantity_available` represents recorded on-hand units **before** reservations, despite its operational column name. Sellable units are `max(0, on_hand − reserved − quarantined)` for ACTIVE batches received by snapshot and expiring after snapshot. All other batches contribute zero. Inventory holding value includes recorded stock at unit cost, including restricted/expired stock; it is not a sellable-stock valuation.

Average daily demand is non-cancelled order-item quantity over a configurable 7–90 day window ending at the snapshot, divided by calendar days. Demand is measured at SKU × centre; zero stock pairs with demand are retained. Cover is sellable units / daily demand. Zero demand gives null, with a separate low-sample warning below ten observed units.

Stock-out exposure means sellable units are below lead-time demand. Reorder point adds configurable safety stock. If stock is below the reorder point, order suggestion covers target days plus safety stock, with minimum quantity and pack-size rounding. It does not execute a purchase.

Expiry windows `(snapshot, snapshot + 30/60/90 days]` are cumulative. Expired stock is shown separately. FEFO sorts only eligible positive-sellable batches by expiry. Period demand / snapshot sellable inventory is labelled a turnover **proxy**, not accounting turnover or COGS.

## Prediction

Target is `delivered_at > promised_delivery_at` among eligible completed shipments. Sort by dispatch time and identify 60/20/20 boundaries. Remove training labels not observed before validation begins and validation labels not observed before test begins. This prevents a shipment dispatched just before a boundary but delivered after it from leaking an unavailable outcome into the earlier fit/selection.

The feature allowlist uses distance, elapsed processing/picking/packing, dispatch backlog, local placement hour/weekday, remaining promise, zone, centre, partner and service level. It excludes delivered_at, final attempt counts, future events and all target/outcome columns. No historically aggregated delivery features are used.

Numerical features are median-imputed and scaled; categoricals are imputed and one-hot encoded with unknown categories ignored. Logistic regression and seeded random forest are compared with a simple rule. Validation PR-AUC selects the model, then validation F1 selects its decision threshold. Test metrics are evaluated once. The model ID fingerprints training feature content and labels, and joblib persists the preprocessing pipeline with its report.

Report ROC-AUC, PR-AUC, class prevalence, precision, recall, F1, a fixed-order [on-time, late] confusion matrix, Brier score and quantile-bin calibration. Global permutation importance uses validation PR-AUC. Default risk tiers <0.30, 0.30–<0.60, ≥0.60 are separate illustrative triage thresholds and may differ from the classifier's validation-selected threshold.

Active queue predictions use only dispatched, in-transit records and retain model version. Persisted bootstrap predictions record actual computation time, not a fabricated historical execution time. The feature point remains dispatch. No claims of production calibration, causality or real-world performance are made.

## Demand forecasting

Aggregate local calendar days, filling absent dates with zero. Require at least 60 days and 100 orders. Hold out up to 28 days. Moving average (28 days), day-of-week average (56 days) and simple exponential smoothing (alpha=0.2) make fixed-origin predictions from the training prefix only. Holdout actuals never become forecast features. MAE and WAPE are reported for every baseline.

The lowest holdout MAE selects the exploratory forward method, so its holdout score is a selection estimate, not an independent second test. Forward forecasts refit on all observed history. Bands use the 90th percentile of absolute holdout errors; coverage is not guaranteed. Weekly reporting aggregates order volume, and category forecasts represent orders containing a category, not SKU-unit forecasts.

## Simulation

Every result saves creation cohort filters, snapshot, request parameters, measured baseline and projected metrics. Deterministic shipment-ID selection makes reruns reproducible. No operational action is executed.

| Intervention | Assumption and constraint |
|---|---|
| Partner allocation | Shift a floored share within matched zone × distance × SLA groups with target n≥5. Apply historical target on-time/time/cost means. Unmatched groups are not shifted. Partner capacity is unknown and explicitly unvalidated. |
| Dispatch improvement | For a deterministic fraction of eligible delivered records, subtract min(requested hours, elapsed processing) from arrival. Last-mile time and shipping cost remain fixed. |
| Zone pilot | Apply the same replay to one selected zone. The projected gain is conditional on the one-for-one arrival assumption. |
| Replenishment | Uniformly scale recorded sellable stock/value and compare lead-time demand + safety stock. Report target coverage gap. Demand and average unit cost stay constant; delivery effects are unidentified. |
| Centre capacity | Compare mean historical daily order load with recorded capacity × multiplier. Report overflow exposure. Do not infer delivery-time improvement from capacity alone. |

The delivery scenario's `delay_rate` is a historical replay rate, not an ML probability. Financial values are calculated exposure/cost projections, never realised savings.

## Data quality and import policy

Database constraints enforce keys and stock/probability ranges. Quality checks expose missing shipments/events, invalid promises/timestamps, impossible durations, backward transitions, missing metadata and expired stock. Issue occurrences can overlap and are not distinct invalid-row counts.

Import allowlist: orders, items, shipments, events, partners, centres, zones, suppliers, products and inventory batches. Templates use exact operational schemas. Files are UTF-8, ≤5 MiB and ≤10,000 rows. Unknown columns are rejected to reduce accidental ingestion of personal/health fields. Timezones are required. Numeric values must be finite. Keys, foreign keys, chronology and semantic ranges are validated before insertion.

All imports are INSERT_ONLY and atomic. If any staged record fails, no operational row is inserted and the audit log marks the whole batch rejected. Header/encoding/size failures create a schema-rejected audit entry with zero parsed records. Error detail is bounded to 100 entries. There is no balance overwrite or automatic deletion policy.
