import {
  BarChart3,
  Boxes,
  ChefHat,
  CreditCard,
  LogOut,
  RefreshCw,
  ShoppingCart,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CashierView } from "./cashier/CashierView";
import { Field, Notice } from "./components/ui";
import { CustomerOrderView } from "./customer/CustomerOrderView";
import { CustomerStatusView } from "./customer/CustomerStatusView";
import { InventoryView } from "./manager/InventoryView";
import { DashboardView } from "./manager/DashboardView";
import { KitchenView } from "./kitchen/KitchenView";
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

type ViewKey = "cashier" | "kitchen" | "inventory" | "dashboard";

const STORAGE_KEY = "cognivex.session";

const NAV_ITEMS: { key: ViewKey; label: string; icon: typeof ShoppingCart }[] = [
  { key: "cashier", label: "Cashier", icon: ShoppingCart },
  { key: "kitchen", label: "Kitchen", icon: ChefHat },
  { key: "inventory", label: "Inventory", icon: Boxes },
  { key: "dashboard", label: "Dashboard", icon: BarChart3 },
];

const ROLE_VIEWS: Partial<Record<RoleName, ViewKey[]>> = {
  OWNER: ["cashier", "kitchen", "inventory", "dashboard"],
  MANAGER: ["cashier", "kitchen", "inventory", "dashboard"],
  CASHIER: ["cashier"],
  KITCHEN: ["kitchen"],
};

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

  const loadContext = useCallback(async () => {
    if (!session) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      let restaurant: Restaurant;
      if (session.user.role_name === "ADMIN") {
        const restaurants = await apiRequest<Restaurant[]>("/api/v1/restaurants/", {
          token: session.token,
        });
        if (!restaurants.length) {
          throw new Error("No restaurants found");
        }
        restaurant = restaurants[0];
      } else if (session.user.restaurant_id) {
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
      setContext({ restaurant, branch: branches[0] });
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
    if (!context) {
      return "Operations Console";
    }
    return `${context.restaurant.name} / ${context.branch.name}`;
  }, [context]);

  if (!session) {
    return <LoginScreen onLogin={setSession} />;
  }

  function signOut() {
    localStorage.removeItem(STORAGE_KEY);
    setSession(null);
    setContext(null);
  }

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
          <button
            className="secondary-action"
            type="button"
            onClick={() => setRefreshKey((current) => current + 1)}
            title="Refresh"
          >
            <RefreshCw size={17} />
            Refresh
          </button>
        </header>

        {error ? <Notice tone="error">{error}</Notice> : null}
        {isLoading ? <Notice>Loading workspace data</Notice> : null}

        {context && token ? (
          <>
            {!visibleNavItems.length ? (
              <Notice tone="error">
                This account does not have an operational console role assigned.
              </Notice>
            ) : null}
            {view === "cashier" && visibleNavItems.some((item) => item.key === "cashier") ? (
              <CashierView context={context} token={token} />
            ) : null}
            {view === "kitchen" && visibleNavItems.some((item) => item.key === "kitchen") ? (
              <KitchenView context={context} token={token} />
            ) : null}
            {view === "inventory" && visibleNavItems.some((item) => item.key === "inventory") ? (
              <InventoryView context={context} token={token} />
            ) : null}
            {view === "dashboard" && visibleNavItems.some((item) => item.key === "dashboard") ? (
              <DashboardView context={context} token={token} />
            ) : null}
          </>
        ) : null}
      </section>
    </main>
  );
}

function App() {
  if (window.location.pathname.startsWith("/order/")) {
    return <CustomerOrderView />;
  }
  if (window.location.pathname.startsWith("/customer/")) {
    return <CustomerStatusView />;
  }
  return <OperationsApp />;
}

export default App;
