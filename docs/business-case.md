# Business case: making fulfilment decisions reviewable

**Audience:** Data Analyst, Business Analyst, Operations Analytics and HealthTech hiring teams.  
**Context:** A hypothetical multi-centre Indian e-pharmacy. All evidence comes from generated data.

## Decision problem

Managers need to know which delivery promises are being missed, which operating segments warrant investigation, and what a proposed intervention would imply for cost, service and inventory exposure. A collection of disconnected charts does not establish consistent definitions or preserve the assumptions behind decisions.

## Proposed product

RxFlow unifies operational data, transparent metrics, dispatch-time risk estimates and saved what-if scenarios. An analyst can start at a portfolio-wide signal, inspect a city/zone/partner cohort, review shipment event evidence, test an intervention and export the analysis to Power BI.

## Demonstration evidence

The reproducible seed-42 dataset contains 30,000 orders. Of 27,706 eligible delivered shipments, 18,435 meet their promises (66.54%). Separately, 23 active shipments are overdue at the fixed snapshot. Mean end-to-end time is 24.56 hours. These patterns were deliberately generated and are not findings about PlatinumRx or any actual company.

The selected logistic classifier achieves test PR-AUC 0.896 against a rule baseline of 0.377 on 5,542 synthetic chronological holdout shipments. This demonstrates an evaluation workflow, not an operationally validated model.

## Decisions enabled

| Question | Evidence | Reviewable action |
|---|---|---|
| Where should we investigate delivery promises? | Eligible delivered denominator, zone trend, lifecycle samples | Select a zone pilot and document assumptions |
| Can another partner serve the same cohort? | Shared zone/distance/SLA observations and cost | Simulate eligible allocation; validate target capacity |
| Which stock needs attention? | Sellable stock, lead-time demand, expiry dates | Review FEFO/reorder queues with a planner |
| Which shipments merit attention? | Dispatch-time model probability, version and limitations | Prioritise human review; do not auto-intervene |

## Evaluation plan for a real pilot

First reconcile a privacy-safe operational extract, validate event and promise definitions, and review capacity/cost assumptions with domain owners. Use comparable pilot/control cohorts or random assignment where feasible. Predefine on-time delivery, first-attempt success, cost per successful delivery, inventory exposure and operational workload as outcomes. Avoid attributing a historical association to a cause.

No realised savings, patient outcomes or actual service improvements are claimed. The portfolio demonstrates analytical engineering and decision communication; a real pilot would establish business value.
