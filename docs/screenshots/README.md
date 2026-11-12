# Actual application screenshots

The Playwright acceptance suite captures `executive.png` and `simulation.png` from the working application, rather than generating UI mockups.

After starting Docker Compose:

```bash
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
```

In GitHub Actions, download the **rxflow-evidence** artifact from a successful **Validate RxFlow** workflow. It contains screenshots, a Playwright HTML report and the generated model report. Screenshots included in this directory must come from an actual browser run; see [validation status](../validation.md).

**Verified capture:** [successful run 43320614304](https://github.com/abhinavgautam121/RxFlow/actions/runs/43320614304). The `rxflow-evidence` artifact includes `executive.png` (Bengaluru cohort), `simulation.png`, the HTML test report and structured results. All five browser flows passed. Screenshots are stored as workflow artifacts; no mock image is substituted in the source tree. GitHub artifact retention applies, so download the files if you need a permanent copy for applications or presentations.
