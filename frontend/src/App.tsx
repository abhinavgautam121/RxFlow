import { useState } from "react";
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  Bell,
  Boxes,
  ChevronRight,
  CircleHelp,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  MapPinned,
  Menu,
  PackageCheck,
  ShieldCheck,
  Sparkles,
  Truck,
  X,
} from "lucide-react";
import { api, localTime, queryString, type Filters } from "./lib";
import { Badge, ErrorBox, ExportButton, Loading } from "./components/common";
import { Button } from "./components/ui/button";
import {
  Delivery,
  Executive,
  InventoryPage,
  Partners,
  Zones,
} from "./pages/Operations";
import { Methodology, Predictive } from "./pages/Models";
import { Quality, Simulation } from "./pages/Workbench";

export type PageProps = { filters: Filters; meta: any };
export function useData(path: string, filters: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: [path, filters],
    queryFn: () => api(`${path}?${queryString(filters)}`),
    placeholderData: (previous) => previous,
  });
}
const nav = [
  {
    path: "/overview",
    label: "Executive overview",
    icon: LayoutDashboard,
    group: "MONITOR",
  },
  { path: "/delivery", label: "Delivery control tower", icon: Truck },
  { path: "/zones", label: "Zone intelligence", icon: MapPinned },
  { path: "/partners", label: "Partner scorecards", icon: PackageCheck },
  { path: "/inventory", label: "Inventory intelligence", icon: Boxes },
  {
    path: "/predictive",
    label: "Predictive analytics",
    icon: Sparkles,
    group: "PLAN & IMPROVE",
  },
  { path: "/simulation", label: "Simulation lab", icon: FlaskConical },
  {
    path: "/quality",
    label: "Data quality centre",
    icon: ShieldCheck,
    group: "WORKSPACE",
  },
  { path: "/methodology", label: "Methodology", icon: CircleHelp },
];

export default function App() {
  const [filters, setFilters] = useState<Filters>({
    city: "",
    center: "",
    start: "",
    end: "",
  });
  const [mobile, setMobile] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const location = useLocation();
  const current = nav.find((x) => x.path === location.pathname) ?? nav[0];
  const meta = useData("meta");
  const overview = useData("overview", filters);
  const update = (key: keyof Filters, value: string) =>
    setFilters((s) => ({
      ...s,
      [key]: value,
      ...(key === "city" ? { center: "" } : {}),
    }));
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className={`sidebar ${mobile ? "is-open" : ""}`}>
        <a className="brand" href="/overview">
          <span className="brand-mark">
            <Activity size={23} />
          </span>
          <span>
            RxFlow<small>OPERATIONS INTELLIGENCE</small>
          </span>
        </a>
        <div className="workspace-chip">
          <span className="workspace-icon">Rx</span>
          <div>
            Demo workspace<small>Independent portfolio</small>
          </div>
          <Badge tone="teal">DEMO</Badge>
        </div>
        <nav aria-label="Main navigation">
          {nav.map(({ path, label, icon: Icon, group }) => (
            <div key={path}>
              {group && <p className="nav-group">{group}</p>}
              <NavLink
                to={path}
                onClick={() => setMobile(false)}
                className={({ isActive }) =>
                  isActive ? "nav-item active" : "nav-item"
                }
              >
                <Icon size={18} />
                <span>{label}</span>
                <ChevronRight size={13} className="nav-chevron" />
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="status-dot" />
          <div>
            Fictional operations<small>Reproducible data · seed 42</small>
          </div>
          <a
            href="https://github.com/abhinavgautam121/RxFlow"
            target="_blank"
            rel="noreferrer"
            aria-label="Open source repository"
          >
            <GitBranch size={18} />
          </a>
        </div>
      </aside>
      {mobile && (
        <button
          className="mobile-overlay"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <Button
              variant="ghost"
              className="mobile-menu"
              onClick={() => setMobile(!mobile)}
              aria-label="Toggle navigation"
            >
              <Menu size={20} />
            </Button>
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{current.label}</strong>
          </div>
          <div className="topbar-right">
            <span className="snapshot-pill">
              <span className="status-dot" />
              Synthetic snapshot
            </span>
            <Button
              variant="ghost"
              onClick={() => setNotifications(!notifications)}
              aria-label="View investigations"
            >
              <Bell size={18} />
              {overview.data?.recommendations?.length > 0 && (
                <span className="notification-dot" />
              )}
            </Button>
            <span className="avatar" title="Demo analyst profile">
              AG
            </span>
          </div>
        </header>
        {notifications && (
          <div className="notification-panel">
            <div className="panel-head">
              <h2>Recommended investigations</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setNotifications(false)}
                aria-label="Close investigations"
              >
                <X size={17} />
              </Button>
            </div>
            {overview.data?.recommendations?.length ? (
              overview.data.recommendations.map((r: any, i: number) => (
                <div key={i} className="notice">
                  <strong>{r.problem}</strong>
                  <p>{r.evidence}</p>
                </div>
              ))
            ) : (
              <p>No alerts in this cohort.</p>
            )}
          </div>
        )}
        <main id="main">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                RXFLOW /{" "}
                {current.path === "/simulation"
                  ? "DECISION WORKBENCH"
                  : "OPERATIONS WORKSPACE"}
              </div>
              <h1>{current.label}</h1>
              <p>{descriptions[current.path]}</p>
            </div>
            <div className="heading-actions">
              <ExportButton
                dataset={
                  location.pathname === "/inventory"
                    ? "inventory"
                    : location.pathname === "/quality"
                      ? "quality"
                      : location.pathname === "/simulation"
                        ? "scenarios"
                        : "shipments"
                }
                filters={filters}
              />
            </div>
          </div>
          <div className="filter-bar">
            <div className="filter-caption">
              <span className="filter-dot" />
              Cohort filters
            </div>
            <label>
              City
              <select
                value={filters.city}
                aria-label="City"
                onChange={(e) => update("city", e.target.value)}
              >
                <option value="">All cities</option>
                {meta.data?.cities.map((c: string) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              Fulfilment centre
              <select
                value={filters.center}
                aria-label="Fulfilment centre"
                onChange={(e) => update("center", e.target.value)}
              >
                <option value="">All centres</option>
                {meta.data?.centers
                  .filter((c: any) => !filters.city || c.city === filters.city)
                  .map((c: any) => (
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
              From
              <input
                type="date"
                value={filters.start}
                onChange={(e) => update("start", e.target.value)}
              />
            </label>
            <label>
              Through
              <input
                type="date"
                value={filters.end}
                onChange={(e) => update("end", e.target.value)}
              />
            </label>
            {Object.values(filters).some(Boolean) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setFilters({ city: "", center: "", start: "", end: "" })
                }
              >
                Reset
              </Button>
            )}
          </div>
          <div className="scope-note">
            {meta.data && <>Snapshot: {localTime(meta.data.as_of)} IST · </>}All
            entities are fictional.
            {[
              "/inventory",
              "/quality",
              "/methodology",
              "/predictive",
              "/simulation",
            ].includes(location.pathname) &&
              " Inventory and quality use the full snapshot; model evaluation is global; scenarios save their cohort."}
          </div>
          {meta.isPending ? (
            <Loading />
          ) : meta.error ? (
            <ErrorBox error={meta.error} retry={() => meta.refetch()} />
          ) : (
            <Routes>
              <Route
                path="/overview"
                element={<Executive filters={filters} meta={meta.data} />}
              />
              <Route
                path="/delivery"
                element={<Delivery filters={filters} meta={meta.data} />}
              />
              <Route
                path="/zones"
                element={<Zones filters={filters} meta={meta.data} />}
              />
              <Route
                path="/partners"
                element={<Partners filters={filters} meta={meta.data} />}
              />
              <Route
                path="/inventory"
                element={<InventoryPage filters={filters} meta={meta.data} />}
              />
              <Route
                path="/predictive"
                element={<Predictive filters={filters} meta={meta.data} />}
              />
              <Route
                path="/simulation"
                element={<Simulation filters={filters} meta={meta.data} />}
              />
              <Route
                path="/quality"
                element={<Quality filters={filters} meta={meta.data} />}
              />
              <Route path="/methodology" element={<Methodology />} />
              <Route path="*" element={<Navigate to="/overview" replace />} />
            </Routes>
          )}
          <footer>
            <span>
              RxFlow · From operational data to smarter medicine fulfilment.
            </span>
            <a
              href="https://github.com/abhinavgautam121/RxFlow"
              target="_blank"
              rel="noreferrer"
            >
              Explore the source <ArrowUpRight size={13} />
            </a>
          </footer>
        </main>
      </div>
    </div>
  );
}
const descriptions: Record<string, string> = {
  "/overview":
    "A clear view of delivery performance, inventory exposure and what needs attention.",
  "/delivery":
    "Follow the order lifecycle. Separate late deliveries from shipments still at risk.",
  "/zones":
    "Understand where demand meets service gaps, one illustrative zone at a time.",
  "/partners":
    "Compare reliability, speed and cost within shared operating cohorts.",
  "/inventory":
    "See stock availability, replenishment exposure and batch expiry in one place.",
  "/predictive":
    "Estimate dispatch-time delay risk and explore transparent demand forecasts.",
  "/simulation":
    "Turn an operational idea into a measurable, assumption-led scenario.",
  "/quality":
    "Validate the inputs behind every decision. Stage, inspect and audit your imports.",
  "/methodology":
    "Transparent definitions, explicit assumptions and the limits of the demonstration.",
};
