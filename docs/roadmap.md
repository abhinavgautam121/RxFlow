# Limitations and next steps

## Deliberate demonstration boundaries

- Synthetic data are coherent but simplified. Generator relationships can make model results optimistic. There is no evidence about actual company operations.
- PostgreSQL is the supported runtime. SQLite is not silently substituted in tests or development.
- One shipment per order simplifies the SLA grain. Split shipments and partial-order SLA definitions need separate product decisions.
- Inventory is a batch snapshot. Receipt movements demonstrate the schema but do not reconstruct historical stock. Reservations do not model customer-level allocation.
- Inventory-balance CSV ingestion is represented by new batch-level snapshots. Updating existing balance rows is unsupported because imports are strictly insert-only.
- Forecasts are order-volume baselines; category counts are orders containing that category. SKU-unit probabilistic forecasts are outside the current implementation.
- Partner capacity is not known. Allocation projections explicitly request operational validation. Centre-capacity scenarios constrain mean daily workload but do not estimate causal delivery gains or queueing dynamics.
- Scores have transparent demonstration scales/weights and are not calibrated business utility functions.
- Global permutation importance does not provide individual causal explanations. Model probabilities are evaluated but not explicitly recalibrated.
- Raw event data do not include customer names, addresses, phone numbers or prescriptions. Unknown CSV columns are rejected, but this is not a certified privacy gateway.
- Public analytics have no user identity. Imports require an admin key; scenario saving is a demo workspace feature. Wider deployment needs real authentication and role-based access.
- Inventory arrays are bounded by the demo dataset rather than fully server-paginated. CSV exports are built in memory. Larger workloads need streaming and query aggregation.
- Power BI schema and DAX are provided; a native `.pbix` report and DAX-engine validation are separate Power BI Desktop work.
- Browser testing and screenshot evidence are reported separately in [validation.md](validation.md), with no mock screenshots or unverified claims.

## Priority roadmap

1. Privacy-safe real-data reconciliation with operational owners, versioned import policies and dedicated staging tables for large asynchronous imports.
2. RBAC, rate limits, background jobs, model registry and feature-schema validation for changes in input distribution.
3. Incremental SQL aggregates, cached analytical queries, streamed exports and inventory pagination.
4. Calibrated probabilities with temporal backtesting, drift monitoring and cohort-level evaluation.
5. Independently held-out forecast selection/evaluation and unit-demand forecasts with inventory-aware censoring.
6. Operational capacity/eligibility matrices, stock-transfer constraints and prospective intervention evaluation.
7. Native Power BI report authoring and validation against the exported semantic model.
