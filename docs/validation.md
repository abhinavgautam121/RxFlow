# Validation record

This record distinguishes implemented behaviour from checks actually executed. Dataset: seed 42, 30,000 orders, 180-day history, fixed 2026-11-12 UTC snapshot. Python 3.12, PostgreSQL 16, Node.js 22.

| Check | Status |
|---|---|
| Alembic initial schema + analytical views against PostgreSQL | Passed locally |
| Synthetic generator reproducibility and relational insertion | Passed locally |
| Backend formula, API, import, ML and integration tests | 46 passed locally |
| Frontend interaction/format/API-error component tests | 8 passed locally, including prediction-form validity and submission |
| TypeScript type check + Vite production build | Passed locally |
| Ruff lint and formatting | Passed locally |
| Database/API totals and stock reconcile to independent SQL views | Passed in pytest |
| Temporal train/validation/test and outcome availability | Passed in pytest |
| Future-outcome mutations do not change dispatch features | Passed in pytest |
| Joblib roundtrip, missing-value handling, probability bounds | Passed in pytest |
| CSV atomic insert-only policy, auth, integrity and exports | Passed in pytest |
| Five scenario types reproducible and bounded | Passed in pytest |
| Docker clean build and Compose startup | Passed locally; PostgreSQL, API and frontend healthy |
| Playwright five browser acceptance flows | Previous CI: 4 passed / 1 failed; prediction-form fix submitted for rerun |
| Actual browser screenshots | Captured in the CI artifact by the passing overview and simulation flows |
| Native Power BI Desktop / DAX execution | Not performed; guide and exports supplied |
| Public hosted application | Not deployed; localhost Docker application supplied |

Local browser-control tools were unavailable in the managed workspace. Browser acceptance and screenshot capture are therefore assigned to the repository's GitHub Actions workflow; they are not counted as locally verified.

The browser run exposed a default prediction threshold rejected by the HTML number input's step constraint. A component regression test reproduced the invalid form before the step was corrected, then verified valid defaults, request submission and displayed prediction output.

The first Docker build exceeded the workspace's disk quota. Build layers were simplified and temporary task build cache cleared before retrying. Both images then built successfully, and a fresh Compose database migrated, seeded, trained and launched all three healthy services. A host database-port override (5433) avoided the separate unit-test database during this check. Ordinary startup uses the documented defaults.

## Reproduce

See [deployment.md](deployment.md) for startup, then:

```bash
docker compose exec backend python -m pytest -q
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The CI workflow performs the same backend/frontend checks and uploads its browser/model evidence. A successful build badge describes CI's returned state, not a hardcoded success label.
