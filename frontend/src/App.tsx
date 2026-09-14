import {
  BarChart3,
  Boxes,
  Building2,
  ChefHat,
  ClipboardList,
  CreditCard,
  LogOut,
  RefreshCw,
  ShoppingCart,
  Store,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PasswordSetupView } from "./auth/PasswordSetupView";
import { CashierView } from "./cashier/CashierView";
import { Field, Notice } from "./components/ui";
import { CustomerOrderView } from "./customer/CustomerOrderView";
import { CustomerStatusView } from "./customer/CustomerStatusView";
import { AuditLogView } from "./manager/AuditLogView";
import { BranchManagementView } from "./manager/BranchManagementView";
import { InventoryView } from "./manager/InventoryView";
import { DashboardView } from "./manager/DashboardView";
import { StaffManagementView } from "./manager/StaffManagementView";
import { KitchenView } from "./kitchen/KitchenView";
import { PlatformAdminView, type PlatformAdminModule } from "./platform/PlatformAdminView";
import {
  apiRequest,
  login,
  type Branch,
  type Restaurant,
  type RoleName,
  type User,
} from "./services/api";

type Session = {
  token: string;
  user: User;
};

export type AppContext = {
  restaurant: Restaurant;
  branch: Branch;
};

type ViewKey =
  | "platform-tenants"
  | "platform-subscriptions"
  | "platform-health"
  | "platform-audit"
  | "cashier"
  | "kitchen"
  | "inventory"
  | "dashboard"
  | "branches"
  | "staff"
  | "audit";

const STORAGE_KEY = "cognivex.session";
const BRANCH_STORAGE_KEY = "cognivex.branchId";

const NAV_ITEMS: { key: ViewKey; label: string; icon: typeof ShoppingCart }[] = [
  { key: "platform-tenants", label: "Tenants", icon: Store },
  { key: "platform-subscriptions", label: "Subscriptions", icon: CreditCard },
  { key: "platform-health", label: "Tenant Health", icon: BarChart3 },
  { key: "platform-audit", label: "Platform Audit", icon: ClipboardList },
  { key: "cashier", label: "Cashier", icon: ShoppingCart },
  { key: "kitchen", label: "Kitchen", icon: ChefHat },
  { key: "inventory", label: "Inventory", icon: Boxes },
  { key: "dashboard", label: "Dashboard", icon: BarChart3 },
  { key: "branches", label: "Branches", icon: Building2 },
  { key: "staff", label: "Staff", icon: Users },
  { key: "audit", label: "Audit", icon: ClipboardList },
];

const ROLE_VIEWS: Partial<Record<RoleName, ViewKey[]>> = {
  ADMIN: ["platform-tenants", "platform-subscriptions", "platform-health", "platform-audit"],
  OWNER: ["cashier", "kitchen", "inventory", "dashboard", "branches", "staff", "audit"],
  MANAGER: ["cashier", "kitchen", "inventory", "dashboard"],
  CASHIER: ["cashier", "kitchen", "inventory", "dashboard"],
  KITCHEN: ["cashier", "kitchen"],
  INVENTORY: ["inventory"],
};

const PLATFORM_MODULE_BY_VIEW: Partial<Record<ViewKey, PlatformAdminModule>> = {
  "platform-tenants": "tenants",
  "platform-subscriptions": "subscriptions",
  "platform-health": "health",
  "platform-audit": "audit",
};

function isPlaceholderBranch(branch: Branch) {
  return branch.name.trim().toLowerCase() === "string";
}

function chooseBranch(branches: Branch[], storedBranchId: string | null) {
  const storedBranch = branches.find((branch) => branch.id === storedBranchId);
  if (storedBranch && !isPlaceholderBranch(storedBranch)) {
    return storedBranch;
  }
  return branches.find((branch) => !isPlaceholderBranch(branch)) ?? storedBranch ?? branches[0];
}

function readStoredSession(): Session | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Session;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

function LoginScreen({ onLogin }: { onLogin: (session: Session) => void }) {
  const [email, setEmail] = useState("owner@chickenspot.com");
  const [password, setPassword] = useState("ownerpassword");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await login(email, password);
      const session = { token: result.access_token, user: result.user };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
      onLogin(session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div>
          <p className="eyebrow">Cognivex Restaurant</p>
          <h1>Operations Console</h1>
        </div>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Email">
          <input value={email} onChange={(event) => setEmail(event.target.value)} />
        </Field>
        <Field label="Password">
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <button className="primary-action" type="submit" disabled={isSubmitting}>
          <CreditCard size={18} />
          {isSubmitting ? "Signing in" : "Sign in"}
        </button>
      </form>
    </main>
  );
}

function OperationsApp() {
  const [session, setSession] = useState<Session | null>(() => readStoredSession());
  const [context, setContext] = useState<AppContext | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [view, setView] = useState<ViewKey>("cashier");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const token = session?.token ?? null;
  const visibleNavItems = useMemo(() => {
    if (!session) {
      return [];
    }
    const roleName = session.user.role_name;
    const allowedViews = roleName ? ROLE_VIEWS[roleName] ?? [] : [];
    return NAV_ITEMS.filter((item) => allowedViews.includes(item.key));
  }, [session]);
  const branchOptions = useMemo(() => {
    const operationalBranches = branches.filter((branch) => !isPlaceholderBranch(branch));
    return operationalBranches.length ? operationalBranches : branches;
  }, [branches]);

  const loadContext = useCallback(async () => {
    if (!session) {
      return;
    }
    if (session.user.role_name === "ADMIN") {
      setContext(null);
      setBranches([]);
      setError(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      let restaurant: Restaurant;
      if (session.user.restaurant_id) {
        restaurant = await apiRequest<Restaurant>(
          `/api/v1/restaurants/${session.user.restaurant_id}`,
          { token: session.token },
        );
      } else {
        throw new Error("User is not assigned to a restaurant");
      }

      const branches = await apiRequest<Branch[]>(`/api/v1/restaurants/${restaurant.id}/branches`, {
        token: session.token,
      });
      if (!branches.length) {
        throw new Error("No branches found");
      }
      setBranches(branches);
      const storedBranchId = localStorage.getItem(BRANCH_STORAGE_KEY);
      const selectedBranch = chooseBranch(branches, storedBranchId);
      localStorage.setItem(BRANCH_STORAGE_KEY, selectedBranch.id);
      setContext({ restaurant, branch: selectedBranch });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load workspace");
    } finally {
      setIsLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void loadContext();
  }, [loadContext, refreshKey]);

  useEffect(() => {
    if (visibleNavItems.length && !visibleNavItems.some((item) => item.key === view)) {
      setView(visibleNavItems[0].key);
    }
  }, [view, visibleNavItems]);

  const title = useMemo(() => {
    if (session?.user.role_name === "ADMIN") {
      if (view === "platform-tenants") {
        return "Platform / Tenants";
      }
      if (view === "platform-subscriptions") {
        return "Platform / Subscriptions";
      }
      if (view === "platform-health") {
        return "Platform / Tenant Health";
      }
      if (view === "platform-audit") {
        return "Platform / Audit";
      }
      return "Platform Admin Console";
    }
    if (!context) {
      return "Operations Console";
    }
    return `${context.restaurant.name} / ${context.branch.name}`;
  }, [context, session?.user.role_name, view]);

  if (!session) {
    return <LoginScreen onLogin={setSession} />;
  }

  function signOut() {
    localStorage.removeItem(STORAGE_KEY);
    setSession(null);
    setContext(null);
    setBranches([]);
  }

  function selectBranch(branchId: string) {
    const selectedBranch = branchOptions.find((branch) => branch.id === branchId);
    if (!selectedBranch || !context) {
      return;
    }
    localStorage.setItem(BRANCH_STORAGE_KEY, selectedBranch.id);
    setContext({ ...context, branch: selectedBranch });
  }

  const platformModule = PLATFORM_MODULE_BY_VIEW[view];

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark">CV</span>
          <div>
            <strong>Cognivex</strong>
            <small>{session.user.role_name}</small>
          </div>
        </div>
        <nav className="nav-stack" aria-label="Main navigation">
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                className={view === item.key ? "nav-item active" : "nav-item"}
                onClick={() => setView(item.key)}
                type="button"
                title={item.label}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <button className="nav-item" type="button" onClick={signOut} title="Sign out">
          <LogOut size={18} />
          <span>Sign out</span>
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Live backend</p>
            <h1 data-testid="workspace-title">{title}</h1>
          </div>
          <div className="topbar-actions">
            {context ? (
              <label className="branch-picker">
                <span>Branch</span>
                <select
                  value={context.branch.id}
                  onChange={(event) => selectBranch(event.target.value)}
                  data-testid="branch-picker"
                >
                  {branchOptions.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <button
              className="secondary-action"
              type="button"
              onClick={() => setRefreshKey((current) => current + 1)}
              title="Refresh"
            >
              <RefreshCw size={17} />
              Refresh
            </button>
          </div>
        </header>

        {error ? <Notice tone="error">{error}</Notice> : null}
        {isLoading ? <Notice>Loading workspace data</Notice> : null}

        {token ? (
          <>
            {!visibleNavItems.length ? (
              <Notice tone="error">
                This account does not have an operational console role assigned.
              </Notice>
            ) : null}
            {platformModule && visibleNavItems.some((item) => item.key === view) ? (
              <PlatformAdminView token={token} module={platformModule} />
            ) : null}
            {view === "cashier" && visibleNavItems.some((item) => item.key === "cashier") ? (
              context ? <CashierView context={context} token={token} /> : null
            ) : null}
            {view === "kitchen" && visibleNavItems.some((item) => item.key === "kitchen") ? (
              context ? <KitchenView context={context} token={token} /> : null
            ) : null}
            {view === "inventory" && visibleNavItems.some((item) => item.key === "inventory") ? (
              context ? (
                <InventoryView context={context} token={token} roleName={session.user.role_name} />
              ) : null
            ) : null}
            {view === "dashboard" && visibleNavItems.some((item) => item.key === "dashboard") ? (
              context ? (
                <DashboardView context={context} token={token} roleName={session.user.role_name} />
              ) : null
            ) : null}
            {view === "branches" && visibleNavItems.some((item) => item.key === "branches") ? (
              context ? (
                <BranchManagementView
                  context={context}
                  token={token}
                  onBranchesChanged={() => setRefreshKey((current) => current + 1)}
                />
              ) : null
            ) : null}
            {view === "staff" && visibleNavItems.some((item) => item.key === "staff") ? (
              context ? (
                <StaffManagementView context={context} token={token} branches={branchOptions} />
              ) : null
            ) : null}
            {view === "audit" && visibleNavItems.some((item) => item.key === "audit") ? (
              context ? (
                <AuditLogView context={context} token={token} branches={branchOptions} />
              ) : null
            ) : null}
          </>
        ) : null}
      </section>
    </main>
  );
}

function App() {
  const normalizedPath = window.location.pathname.replace(/\/$/, "");
  if (window.location.pathname.startsWith("/order/") || normalizedPath === "/chicken-spot") {
    return <CustomerOrderView />;
  }
  if (window.location.pathname.startsWith("/customer/")) {
    return <CustomerStatusView />;
  }
  if (normalizedPath === "/password-setup") {
    return <PasswordSetupView />;
  }
  return <OperationsApp />;
}

export default App;
