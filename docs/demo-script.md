# Five-minute recruiter walkthrough

## 0:00–0:40 — Frame the problem

“I built RxFlow to connect operational evidence to reviewable decisions. This is an independent project with entirely fictional data. It combines React, FastAPI, PostgreSQL, Python analytics and Power BI exports.”

Open Executive overview. Show total orders and on-time numerator/denominator. Explain why 9,271 delivered-late orders and 23 currently-overdue active shipments are different populations.

## 0:40–1:30 — Investigate a cohort

Filter to Bengaluru, then open Delivery control tower. Inspect lifecycle samples and a shipment event history. Explain that incomplete event pairs are excluded visibly, and an association with backlog does not establish cause. Reset filters.

## 1:30–2:15 — Compare service and stock

Open Partner scorecards. Select two partners. Explain common city × distance × SLA standardisation, minimum cohort samples and coverage. Open Inventory intelligence; inspect a stock-out-risk SKU–centre pair, then the FEFO list. Expired and quarantined stock cannot contribute to sellable inventory.

## 2:15–3:10 — Demonstrate responsible modelling

Open Predictive analytics. Compare logistic regression, random forest and the rule baseline. Show test PR-AUC and calibration. Explain label availability at train/validation boundaries and the feature allowlist. Run the prediction workbench; describe the output as a synthetic-data estimate, not a clinical or causal recommendation.

## 3:10–4:15 — Make a scenario concrete

Open Simulation lab. Name a dispatch pilot, affect 20% of eligible orders and remove two processing hours. Run and save it. Compare baseline and projected results. State the one-for-one arrival-shift assumption and that no real improvement has been measured. Reopen the saved run and export the scenario CSV.

## 4:15–5:00 — Show engineering evidence

Open Data quality centre. Review intentionally missing delivery events. Download a template and Power BI ZIP. In GitHub, show SQL reconciliation tests, the chronological leakage test, migrations and CI evidence.

Close with: “The contribution is the complete chain from a business question to a validated metric, a working analytical system and an explicit decision assumption.”

## Interview discussion prompts

- Why use PR-AUC alongside ROC-AUC? Compare it with the positive-class prevalence and a rule baseline.
- Why does a model with lower complexity win? The validation result selects it; complexity is not itself a benefit.
- Why are scenario gains not causal estimates? Historical cohorts differ, and service/capacity assumptions are unvalidated.
- What changes first at scale? Incremental aggregates, asynchronous imports, access control and separately scheduled model retraining.
