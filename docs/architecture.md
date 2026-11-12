# Architecture and data model

React renders nine route workspaces. TanStack Query manages request state and cohort filters. The frontend accesses FastAPI only; it never connects to PostgreSQL. Nginx serves the production assets and proxies `/api/`. FastAPI validates requests and uses SQLAlchemy 2. Alembic creates constrained operational tables and PostgreSQL reporting views. The generator and classifiers run on first startup and preserve existing data on restart.

```mermaid
flowchart TB
  Browser[React / TypeScript browser] --> Nginx[Nginx static assets + API proxy]
  Nginx --> API[FastAPI / Pydantic]
  API --> DB[(PostgreSQL)]
  API --> Analytics[Delivery and inventory Python functions]
  API --> Quality[Authenticated CSV staging + audit]
  API --> Scenario[Historical scenario projection engine]
  API --> Prediction[Dispatch-time sklearn pipeline]
  Generator[Fixed-seed NumPy generator] --> DB
  DB --> Train[Embargoed chronological training]
  Train --> Artifact[Versioned joblib + JSON evaluation]
  Artifact --> Prediction
  DB --> Views[Reporting SQL views]
  Views --> Export[Fact / dimension CSV exports]
  Export --> PowerBI[Power BI Desktop semantic model]
```

## Entity relationships

```mermaid
erDiagram
  zones ||--o{ orders : contains
  zones ||--o{ fulfilment_centres : locates
  fulfilment_centres ||--o{ orders : fulfils
  orders ||--o{ order_items : contains
  orders ||--o| shipments : ships
  delivery_partners ||--o{ shipments : delivers
  shipments ||--o{ shipment_events : records
  shipments ||--o{ risk_predictions : scores
  suppliers ||--o{ products : supplies
  products ||--o{ order_items : ordered
  products ||--o{ inventory_batches : stocked
  fulfilment_centres ||--o{ inventory_batches : holds
  inventory_batches ||--o{ inventory_movements : tracks
  fulfilment_centres ||--o{ inventory_movements : source_or_destination
  orders {
    string order_id PK
    datetime order_created_at
    datetime promised_delivery_at
    string fulfillment_center_id FK
    string zone_id FK
  }
  shipments {
    string shipment_id PK
    string order_id FK,UK
    string delivery_partner_id FK
    datetime dispatch_at
    datetime delivered_at
  }
  inventory_batches {
    string batch_id PK
    string sku_id FK
    string fulfillment_center_id FK
    int quantity_available
    int reserved_quantity
    int quarantined_quantity
    datetime expiry_date
  }
  risk_predictions {
    string prediction_id PK
    string shipment_id FK
    float delay_probability
    string model_version
    json feature_snapshot
  }
  scenario_runs {
    string scenario_id PK
    string scenario_type
    json baseline_metrics
    json simulated_metrics
    json assumptions
  }
  import_logs {
    string import_id PK
    string source
    int records_accepted
    int records_rejected
    json error_details
  }
```

`scenario_runs`, `import_logs` and `dataset_meta` are independent audit/configuration tables. One shipment per order is enforced; split shipments would require relaxing that constraint and revising order-level SLA denominators.

## Integrity and indexes

- Primary keys and unique references reject duplicates. Foreign keys protect zone, centre, supplier, SKU, order, shipment and batch relationships.
- Quantity constraints prevent negative stock, over-fulfilment, reservations above on-hand and invalid prediction probabilities.
- Indexes support creation date, centre, zone, partner, shipment status, batch expiry and shipment-event time lookups.
- Timestamp columns are timezone-aware PostgreSQL timestamps. Date filters use inclusive Asia/Kolkata calendar dates converted to a UTC half-open interval.
- API query values use SQLAlchemy-bound parameters. Import table/column names come from a fixed allowlist, never user-provided SQL.

## Performance and deployment boundaries

The 30,000-order demonstration uses database joins followed by reusable pandas functions. This keeps formula logic visible and testable. It is not a claim of production-scale query performance. A larger deployment should move stable aggregates into SQL/materialised views, add incremental ingestion, implement server-side inventory pagination and separate model retraining from web-server startup.

The specified Python/PostgreSQL service runs in Docker. A static site host or Cloudflare Worker alone cannot run this architecture; no reduced static dashboard is substituted for the backend.
