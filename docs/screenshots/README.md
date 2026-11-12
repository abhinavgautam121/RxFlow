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
