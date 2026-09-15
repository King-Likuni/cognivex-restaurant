import {
  AlertTriangle,
  Building2,
  CalendarDays,
  ClipboardList,
  Copy,
  CreditCard,
  KeyRound,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Store,
  UserPlus,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState, Field, Notice, Panel, Stat } from "../components/ui";
import {
  apiRequest,
  type AuditLog,
  type PasswordSetupToken,
  type PlatformRestaurantSummary,
  type PlatformUserInviteResponse,
  type RestaurantLifecycleStatus,
  type RestaurantOnboardingResponse,
  type RestaurantSubscriptionStatus,
  type RoleName,
  type User,
} from "../services/api";

export type PlatformAdminModule = "tenants" | "subscriptions" | "health" | "users" | "audit";

type Props = {
  token: string;
  module: PlatformAdminModule;
  roleName: RoleName | null;
};

type OnboardingForm = {
  restaurant_name: string;
  restaurant_code: string;
  branch_name: string;
  branch_code: string;
  branch_location: string;
  owner_email: string;
  owner_first_name: string;
  owner_last_name: string;
};

type SubscriptionDraft = {
  subscription_status: RestaurantSubscriptionStatus;
  subscription_started_at: string;
  subscription_renews_at: string;
};

type PlatformUserForm = {
  email: string;
  first_name: string;
  last_name: string;
  role_name: PlatformUserRole;
};

type PlatformUserRole = "ADMIN" | "SUPPORT" | "FINANCE";

const EMPTY_FORM: OnboardingForm = {
  restaurant_name: "",
  restaurant_code: "",
  branch_name: "",
  branch_code: "",
  branch_location: "",
  owner_email: "",
  owner_first_name: "",
  owner_last_name: "",
};

const EMPTY_PLATFORM_USER_FORM: PlatformUserForm = {
  email: "",
  first_name: "",
  last_name: "",
  role_name: "SUPPORT",
};

const PLATFORM_AUDIT_ACTIONS = [
  "RESTAURANT_ONBOARDED",
  "OWNER_INVITED",
  "PASSWORD_SETUP_LINK_CREATED",
  "RESTAURANT_LIFECYCLE_UPDATED",
  "RESTAURANT_SUBSCRIPTION_UPDATED",
  "PLATFORM_USER_INVITED",
  "PLATFORM_USER_UPDATED",
  "PLATFORM_PASSWORD_SETUP_LINK_CREATED",
  "BRANCH_CREATED",
  "BRANCH_UPDATED",
];

const PLATFORM_AUDIT_ENTITIES = ["restaurant", "branch", "user", "platform_user"];

function setupUrlFromInvite(invite: RestaurantOnboardingResponse["invite"]) {
  return `${window.location.origin}${invite.setup_url_path}`;
}

function formatAction(value: string | null | undefined) {
  return (value || "unknown")
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatMoney(value: string | number | null | undefined) {
  return `BWP ${Number(value || 0).toFixed(2)}`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Not set";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function toDateInputValue(value: string | null | undefined) {
  if (!value) {
    return "";
  }
  return value.slice(0, 10);
}

function dateInputToIso(value: string) {
  return value ? new Date(`${value}T00:00:00`).toISOString() : null;
}

function summarizeValues(values: Record<string, unknown> | null) {
  if (!values) {
    return "None";
  }
  return Object.entries(values)
    .slice(0, 6)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.length : String(value)}`)
    .join(" | ");
}

function statusPillClass(status: string | null | undefined) {
  return status === "SUSPENDED" ||
    status === "OVERDUE" ||
    status === "CANCELLED" ||
    status === "BLOCKED"
    ? "status-pill inactive"
    : "status-pill";
}

function auditTenantLabel(log: AuditLog, tenantNameById: Map<string, string>) {
  if (!log.restaurant_id) {
    return "Platform";
  }
  return tenantNameById.get(log.restaurant_id) ?? log.restaurant_id;
}

function orderAccessStatus(restaurant: PlatformRestaurantSummary) {
  return restaurant.order_access_status || "ACTIVE";
}

export function PlatformAdminView({ token, module, roleName }: Props) {
  const [restaurants, setRestaurants] = useState<PlatformRestaurantSummary[]>([]);
  const [platformUsers, setPlatformUsers] = useState<User[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [form, setForm] = useState<OnboardingForm>(EMPTY_FORM);
  const [platformUserForm, setPlatformUserForm] =
    useState<PlatformUserForm>(EMPTY_PLATFORM_USER_FORM);
  const [latestOnboarding, setLatestOnboarding] = useState<RestaurantOnboardingResponse | null>(
    null,
  );
  const [latestOwnerLink, setLatestOwnerLink] = useState<PasswordSetupToken | null>(null);
  const [latestPlatformUserLink, setLatestPlatformUserLink] =
    useState<PasswordSetupToken | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionRestaurantId, setActionRestaurantId] = useState<string | null>(null);
  const [suspendingRestaurantId, setSuspendingRestaurantId] = useState<string | null>(null);
  const [suspensionReason, setSuspensionReason] = useState("");
  const [subscriptionDrafts, setSubscriptionDrafts] = useState<Record<string, SubscriptionDraft>>(
    {},
  );
  const [auditAction, setAuditAction] = useState("");
  const [auditEntityType, setAuditEntityType] = useState("");
  const [auditDateFrom, setAuditDateFrom] = useState("");
  const [auditDateTo, setAuditDateTo] = useState("");

  const tenantNameById = useMemo(
    () => new Map(restaurants.map((restaurant) => [restaurant.id, restaurant.name])),
    [restaurants],
  );
  const activeRestaurantCount = useMemo(
    () => restaurants.filter((restaurant) => restaurant.status === "ACTIVE").length,
    [restaurants],
  );
  const setupPendingCount = useMemo(
    () => restaurants.filter((restaurant) => restaurant.status === "SETUP_PENDING").length,
    [restaurants],
  );
  const suspendedCount = useMemo(
    () => restaurants.filter((restaurant) => restaurant.status === "SUSPENDED").length,
    [restaurants],
  );
  const subscriptionCounts = useMemo(
    () => ({
      trial: restaurants.filter((restaurant) => restaurant.subscription_status === "TRIAL").length,
      active: restaurants.filter((restaurant) => restaurant.subscription_status === "ACTIVE")
        .length,
      overdue: restaurants.filter((restaurant) => restaurant.subscription_status === "OVERDUE")
        .length,
      cancelled: restaurants.filter(
        (restaurant) => restaurant.subscription_status === "CANCELLED",
      ).length,
    }),
    [restaurants],
  );
  const healthTotals = useMemo(
    () =>
      restaurants.reduce(
        (totals, restaurant) => ({
          orders: totals.orders + restaurant.today_order_count,
          revenue: totals.revenue + Number(restaurant.today_revenue || 0),
          paymentAttention:
            totals.paymentAttention +
            restaurant.pending_payment_count +
            restaurant.failed_payment_count,
          stockAlerts:
            totals.stockAlerts +
            restaurant.low_stock_alert_count +
            restaurant.critical_stock_alert_count,
        }),
        { orders: 0, revenue: 0, paymentAttention: 0, stockAlerts: 0 },
      ),
    [restaurants],
  );
  const activeAdminCount = useMemo(
    () =>
      platformUsers.filter((user) => user.role_name === "ADMIN" && user.is_active).length,
    [platformUsers],
  );
  const activeSupportCount = useMemo(
    () =>
      platformUsers.filter((user) => user.role_name === "SUPPORT" && user.is_active).length,
    [platformUsers],
  );
  const activeFinanceCount = useMemo(
    () =>
      platformUsers.filter((user) => user.role_name === "FINANCE" && user.is_active).length,
    [platformUsers],
  );
  const canManagePlatform = roleName === "ADMIN";

  const loadRestaurants = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextRestaurants = await apiRequest<PlatformRestaurantSummary[]>(
        "/api/v1/restaurants/platform",
        { token },
      );
      setRestaurants(nextRestaurants);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load restaurants");
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  const loadLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextLogs = await apiRequest<AuditLog[]>("/api/v1/platform/audit-logs/", {
        token,
        params: {
          action: auditAction,
          entity_type: auditEntityType,
          date_from: auditDateFrom,
          date_to: auditDateTo,
          limit: 100,
        },
      });
      setLogs(nextLogs);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load platform audit");
    } finally {
      setIsLoading(false);
    }
  }, [auditAction, auditDateFrom, auditDateTo, auditEntityType, token]);

  const loadPlatformUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextUsers = await apiRequest<User[]>("/api/v1/auth/platform-users", { token });
      setPlatformUsers(nextUsers);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load platform users");
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadRestaurants();
  }, [loadRestaurants]);

  useEffect(() => {
    if (module === "audit") {
      void loadLogs();
    }
    if (module === "users") {
      void loadPlatformUsers();
    }
  }, [loadLogs, loadPlatformUsers, module]);

  function updateField<K extends keyof OnboardingForm>(field: K, value: OnboardingForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updatePlatformUserField<K extends keyof PlatformUserForm>(
    field: K,
    value: PlatformUserForm[K],
  ) {
    setPlatformUserForm((current) => ({ ...current, [field]: value }));
  }

  async function onboardRestaurant(event: React.FormEvent) {
    event.preventDefault();
    setNotice(null);
    setError(null);
    setLatestOnboarding(null);
    setLatestOwnerLink(null);
    setIsSubmitting(true);
    try {
      const onboarding = await apiRequest<RestaurantOnboardingResponse>(
        "/api/v1/restaurants/onboard",
        {
          method: "POST",
          token,
          body: {
            restaurant_name: form.restaurant_name.trim(),
            restaurant_code: form.restaurant_code.trim() || null,
            branch_name: form.branch_name.trim(),
            branch_code: form.branch_code.trim() || null,
            branch_location: form.branch_location.trim() || null,
            owner_email: form.owner_email.trim(),
            owner_first_name: form.owner_first_name.trim(),
            owner_last_name: form.owner_last_name.trim(),
          },
        },
      );
      setLatestOnboarding(onboarding);
      setForm(EMPTY_FORM);
      setNotice(`${onboarding.restaurant.name} is ready. Share the owner setup link.`);
      await loadRestaurants();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not onboard restaurant");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function copySetupUrl() {
    const invite = latestOwnerLink ?? latestOnboarding?.invite;
    if (!invite) {
      return;
    }
    try {
      await navigator.clipboard.writeText(setupUrlFromInvite(invite));
      setNotice("Owner setup link copied");
    } catch {
      setError("Could not copy link. Select the link and copy it manually.");
    }
  }

  async function copyPlatformUserSetupUrl() {
    if (!latestPlatformUserLink) {
      return;
    }
    try {
      await navigator.clipboard.writeText(setupUrlFromInvite(latestPlatformUserLink));
      setNotice("Platform user setup link copied");
    } catch {
      setError("Could not copy link. Select the link and copy it manually.");
    }
  }

  async function updateLifecycle(
    restaurant: PlatformRestaurantSummary,
    status: RestaurantLifecycleStatus,
    reason: string | null = null,
  ) {
    setNotice(null);
    setError(null);
    setActionRestaurantId(restaurant.id);
    try {
      await apiRequest(`/api/v1/restaurants/${restaurant.id}/lifecycle`, {
        method: "PATCH",
        token,
        body: { status, suspension_reason: reason },
      });
      setNotice(`${restaurant.name} is now ${status.toLowerCase().replace("_", " ")}`);
      setSuspendingRestaurantId(null);
      setSuspensionReason("");
      await loadRestaurants();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update tenant status");
    } finally {
      setActionRestaurantId(null);
    }
  }

  async function updateSubscription(restaurant: PlatformRestaurantSummary) {
    const draft = subscriptionDrafts[restaurant.id] ?? {
      subscription_status: restaurant.subscription_status as RestaurantSubscriptionStatus,
      subscription_started_at: toDateInputValue(restaurant.subscription_started_at),
      subscription_renews_at: toDateInputValue(restaurant.subscription_renews_at),
    };
    setNotice(null);
    setError(null);
    setActionRestaurantId(restaurant.id);
    try {
      await apiRequest(`/api/v1/restaurants/${restaurant.id}/subscription`, {
        method: "PATCH",
        token,
        body: {
          subscription_status: draft.subscription_status,
          subscription_started_at: dateInputToIso(draft.subscription_started_at),
          subscription_renews_at: dateInputToIso(draft.subscription_renews_at),
        },
      });
      setNotice(`${restaurant.name} subscription updated`);
      await loadRestaurants();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update subscription");
    } finally {
      setActionRestaurantId(null);
    }
  }

  function updateSubscriptionDraft(
    restaurant: PlatformRestaurantSummary,
    patch: Partial<SubscriptionDraft>,
  ) {
    setSubscriptionDrafts((current) => ({
      ...current,
      [restaurant.id]: {
        subscription_status:
          current[restaurant.id]?.subscription_status ??
          (restaurant.subscription_status as RestaurantSubscriptionStatus),
        subscription_started_at:
          current[restaurant.id]?.subscription_started_at ??
          toDateInputValue(restaurant.subscription_started_at),
        subscription_renews_at:
          current[restaurant.id]?.subscription_renews_at ??
          toDateInputValue(restaurant.subscription_renews_at),
        ...patch,
      },
    }));
  }

  async function createOwnerSetupLink(restaurant: PlatformRestaurantSummary) {
    setNotice(null);
    setError(null);
    setLatestOnboarding(null);
    setActionRestaurantId(restaurant.id);
    try {
      const invite = await apiRequest<PasswordSetupToken>(
        `/api/v1/restaurants/${restaurant.id}/owner-setup-link`,
        {
          method: "POST",
          token,
        },
      );
      setLatestOwnerLink(invite);
      setNotice(`${restaurant.name} owner setup link created`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create owner setup link");
    } finally {
      setActionRestaurantId(null);
    }
  }

  async function invitePlatformUser(event: React.FormEvent) {
    event.preventDefault();
    setNotice(null);
    setError(null);
    setLatestPlatformUserLink(null);
    setIsSubmitting(true);
    try {
      const invite = await apiRequest<PlatformUserInviteResponse>(
        "/api/v1/auth/platform-users/invite",
        {
          method: "POST",
          token,
          body: {
            email: platformUserForm.email.trim(),
            first_name: platformUserForm.first_name.trim(),
            last_name: platformUserForm.last_name.trim(),
            role_name: platformUserForm.role_name,
          },
        },
      );
      setLatestPlatformUserLink(invite.invite);
      setPlatformUserForm(EMPTY_PLATFORM_USER_FORM);
      setNotice(`${invite.user.email} platform setup link created`);
      await loadPlatformUsers();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not invite platform user");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function updatePlatformUser(user: User, patch: Partial<User>) {
    setNotice(null);
    setError(null);
    setActionRestaurantId(user.id);
    try {
      await apiRequest(`/api/v1/auth/platform-users/${user.id}`, {
        method: "PATCH",
        token,
        body: patch,
      });
      setNotice(`${user.email} updated`);
      await loadPlatformUsers();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update platform user");
    } finally {
      setActionRestaurantId(null);
    }
  }

  async function createPlatformUserSetupLink(user: User) {
    setNotice(null);
    setError(null);
    setLatestPlatformUserLink(null);
    setActionRestaurantId(user.id);
    try {
      const invite = await apiRequest<PasswordSetupToken>(
        `/api/v1/auth/platform-users/${user.id}/password-reset`,
        {
          method: "POST",
          token,
        },
      );
      setLatestPlatformUserLink(invite);
      setNotice(`${user.email} setup link created`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create setup link");
    } finally {
      setActionRestaurantId(null);
    }
  }

  function renderOwnerSetupLink() {
    if (!latestOnboarding && !latestOwnerLink) {
      return null;
    }
    return (
      <Panel title="Owner Setup Link">
        <div className="invite-link-box">
          <input readOnly value={setupUrlFromInvite(latestOwnerLink ?? latestOnboarding!.invite)} />
          <button className="secondary-action" type="button" onClick={copySetupUrl}>
            <Copy size={17} />
            Copy
          </button>
        </div>
        {latestOnboarding ? (
          <div className="tenant-summary">
            <span>{latestOnboarding.restaurant.name}</span>
            <span>{latestOnboarding.branch.name}</span>
            <span>{latestOnboarding.owner.email}</span>
          </div>
        ) : null}
      </Panel>
    );
  }

  function renderPlatformUserSetupLink() {
    if (!latestPlatformUserLink) {
      return null;
    }
    return (
      <Panel title="Platform User Setup Link">
        <div className="invite-link-box">
          <input readOnly value={setupUrlFromInvite(latestPlatformUserLink)} />
          <button className="secondary-action" type="button" onClick={copyPlatformUserSetupUrl}>
            <Copy size={17} />
            Copy
          </button>
        </div>
      </Panel>
    );
  }

  function renderTenantActions(restaurant: PlatformRestaurantSummary) {
    return (
      <div className="tenant-card-actions">
        <button
          className="secondary-action"
          type="button"
          onClick={() => void createOwnerSetupLink(restaurant)}
          disabled={actionRestaurantId === restaurant.id}
        >
          <KeyRound size={17} />
          Owner link
        </button>
        {restaurant.status === "SUSPENDED" ? (
          <button
            className="secondary-action"
            type="button"
            onClick={() => void updateLifecycle(restaurant, "ACTIVE")}
            disabled={actionRestaurantId === restaurant.id}
          >
            <Power size={17} />
            Reactivate
          </button>
        ) : (
          <button
            className="secondary-action danger-action"
            type="button"
            onClick={() => {
              setSuspendingRestaurantId(restaurant.id);
              setSuspensionReason("");
            }}
            disabled={actionRestaurantId === restaurant.id}
          >
            <PowerOff size={17} />
            Suspend
          </button>
        )}
        {suspendingRestaurantId === restaurant.id ? (
          <div className="tenant-suspend-box">
            <label>
              <span>
                <AlertTriangle size={15} />
                Suspension reason
              </span>
              <textarea
                value={suspensionReason}
                onChange={(event) => setSuspensionReason(event.target.value)}
                rows={3}
                maxLength={300}
                required
              />
            </label>
            <div className="tenant-card-actions">
              <button
                className="secondary-action danger-action"
                type="button"
                onClick={() =>
                  void updateLifecycle(
                    restaurant,
                    "SUSPENDED",
                    suspensionReason.trim() || "Suspended by platform admin",
                  )
                }
                disabled={actionRestaurantId === restaurant.id}
              >
                <PowerOff size={17} />
                Confirm
              </button>
              <button
                className="secondary-action"
                type="button"
                onClick={() => {
                  setSuspendingRestaurantId(null);
                  setSuspensionReason("");
                }}
              >
                <CalendarDays size={17} />
                Cancel
              </button>
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  function renderTenantsModule() {
    return (
      <>
        <div className="stats-grid">
          <Stat label="Active restaurants" value={activeRestaurantCount} tone="good" />
          <Stat label="Setup pending" value={setupPendingCount} />
          <Stat label="Suspended" value={suspendedCount} tone="warn" />
          <Stat label="Tenants listed" value={restaurants.length} />
        </div>
        {canManagePlatform ? renderOwnerSetupLink() : null}
        <div className="view-grid two-columns">
          {canManagePlatform ? (
            <Panel title="Add Restaurant">
              <form className="tenant-onboarding-form" onSubmit={onboardRestaurant}>
                <div className="form-section-title">
                  <Store size={17} />
                  Restaurant
                </div>
                <Field label="Restaurant name">
                  <input
                    value={form.restaurant_name}
                    onChange={(event) => updateField("restaurant_name", event.target.value)}
                    placeholder="KFC"
                    required
                  />
                </Field>
                <Field label="Restaurant code">
                  <input
                    value={form.restaurant_code}
                    onChange={(event) => updateField("restaurant_code", event.target.value)}
                    placeholder="KFC"
                    maxLength={12}
                  />
                </Field>
                <div className="form-section-title">
                  <Building2 size={17} />
                  First branch
                </div>
                <Field label="Branch name">
                  <input
                    value={form.branch_name}
                    onChange={(event) => updateField("branch_name", event.target.value)}
                    placeholder="Main Mall"
                    required
                  />
                </Field>
                <Field label="Branch code">
                  <input
                    value={form.branch_code}
                    onChange={(event) => updateField("branch_code", event.target.value)}
                    placeholder="MM"
                    maxLength={12}
                  />
                </Field>
                <Field label="Branch location">
                  <input
                    value={form.branch_location}
                    onChange={(event) => updateField("branch_location", event.target.value)}
                    placeholder="Gaborone"
                  />
                </Field>
                <div className="form-section-title">
                  <UserPlus size={17} />
                  Owner
                </div>
                <Field label="Owner email">
                  <input
                    type="email"
                    value={form.owner_email}
                    onChange={(event) => updateField("owner_email", event.target.value)}
                    placeholder="owner@example.com"
                    required
                  />
                </Field>
                <Field label="First name">
                  <input
                    value={form.owner_first_name}
                    onChange={(event) => updateField("owner_first_name", event.target.value)}
                    required
                  />
                </Field>
                <Field label="Last name">
                  <input
                    value={form.owner_last_name}
                    onChange={(event) => updateField("owner_last_name", event.target.value)}
                    required
                  />
                </Field>
                <button className="primary-action" type="submit" disabled={isSubmitting}>
                  <Plus size={18} />
                  {isSubmitting ? "Creating tenant" : "Create tenant"}
                </button>
              </form>
            </Panel>
          ) : null}
          <Panel
            title="Tenants"
            action={
              <button className="icon-button" type="button" onClick={loadRestaurants}>
                <RefreshCw size={17} />
              </button>
            }
          >
            <div className="tenant-list">
              {restaurants.map((restaurant) => (
                <article className="tenant-card tenant-card-compact" key={restaurant.id}>
                  <div className="tenant-card-heading">
                    <span className={statusPillClass(restaurant.status)}>
                      {restaurant.status.replace("_", " ")}
                    </span>
                    <span className={statusPillClass(restaurant.subscription_status)}>
                      {restaurant.subscription_status}
                    </span>
                  </div>
                  <div className="tenant-card-body">
                    <h3>{restaurant.name}</h3>
                    <span>{restaurant.code}</span>
                    {restaurant.suspension_reason ? (
                      <p className="tenant-warning">{restaurant.suspension_reason}</p>
                    ) : null}
                    {restaurant.owner_setup_expires_at ? (
                      <p
                        className={
                          restaurant.owner_setup_expired ? "tenant-warning" : "tenant-helper-text"
                        }
                      >
                        Owner setup expires {formatDateTime(restaurant.owner_setup_expires_at)}
                      </p>
                    ) : null}
                    <div className="tenant-card-meta">
                      <span>{restaurant.branch_count} branches</span>
                      <span>{restaurant.active_user_count} users</span>
                      <span>{restaurant.owner_name ?? "No owner"}</span>
                      <span>{restaurant.owner_email ?? "No owner email"}</span>
                    </div>
                  </div>
                  {canManagePlatform ? renderTenantActions(restaurant) : null}
                </article>
              ))}
              {!restaurants.length ? <EmptyState>No restaurants onboarded yet</EmptyState> : null}
            </div>
          </Panel>
        </div>
      </>
    );
  }

  function renderSubscriptionsModule() {
    return (
      <>
        <div className="stats-grid">
          <Stat label="Trial" value={subscriptionCounts.trial} />
          <Stat label="Active" value={subscriptionCounts.active} tone="good" />
          <Stat label="Overdue" value={subscriptionCounts.overdue} tone="warn" />
          <Stat label="Cancelled" value={subscriptionCounts.cancelled} tone="warn" />
        </div>
        <Panel
          title="Subscriptions"
          action={
            <button className="icon-button" type="button" onClick={loadRestaurants}>
              <RefreshCw size={17} />
            </button>
          }
        >
          <div className="tenant-list">
            {restaurants.map((restaurant) => {
              const subscriptionDraft = subscriptionDrafts[restaurant.id] ?? {
                subscription_status:
                  restaurant.subscription_status as RestaurantSubscriptionStatus,
                subscription_started_at: toDateInputValue(restaurant.subscription_started_at),
                subscription_renews_at: toDateInputValue(restaurant.subscription_renews_at),
              };
              return (
                <article className="tenant-card tenant-card-subscription" key={restaurant.id}>
                  <div className="tenant-card-heading">
                    <span className={statusPillClass(restaurant.subscription_status)}>
                      {restaurant.subscription_status}
                    </span>
                    <span className={statusPillClass(restaurant.status)}>
                      {restaurant.status.replace("_", " ")}
                    </span>
                    <span className={statusPillClass(orderAccessStatus(restaurant))}>
                      Orders {formatAction(orderAccessStatus(restaurant))}
                    </span>
                  </div>
                  <div className="tenant-card-body">
                    <h3>{restaurant.name}</h3>
                    <span>{restaurant.code}</span>
                    {restaurant.order_access_message ? (
                      <p className="tenant-warning">{restaurant.order_access_message}</p>
                    ) : null}
                    <div className="tenant-subscription-grid">
                      <label>
                        <span>Subscription</span>
                        <select
                          value={subscriptionDraft.subscription_status}
                          disabled={!canManagePlatform}
                          onChange={(event) =>
                            updateSubscriptionDraft(restaurant, {
                              subscription_status: event.target
                                .value as RestaurantSubscriptionStatus,
                            })
                          }
                        >
                          <option value="TRIAL">Trial</option>
                          <option value="ACTIVE">Active</option>
                          <option value="OVERDUE">Overdue</option>
                          <option value="CANCELLED">Cancelled</option>
                        </select>
                      </label>
                      <label>
                        <span>Started</span>
                        <input
                          type="date"
                          value={subscriptionDraft.subscription_started_at}
                          disabled={!canManagePlatform}
                          onChange={(event) =>
                            updateSubscriptionDraft(restaurant, {
                              subscription_started_at: event.target.value,
                            })
                          }
                        />
                      </label>
                      <label>
                        <span>Renews</span>
                        <input
                          type="date"
                          value={subscriptionDraft.subscription_renews_at}
                          disabled={!canManagePlatform}
                          onChange={(event) =>
                            updateSubscriptionDraft(restaurant, {
                              subscription_renews_at: event.target.value,
                            })
                          }
                        />
                      </label>
                      {canManagePlatform ? (
                        <button
                          className="secondary-action"
                          type="button"
                          onClick={() => void updateSubscription(restaurant)}
                          disabled={actionRestaurantId === restaurant.id}
                        >
                          <CreditCard size={17} />
                          Save
                        </button>
                      ) : null}
                    </div>
                  </div>
                </article>
              );
            })}
            {!restaurants.length ? <EmptyState>No subscriptions available</EmptyState> : null}
          </div>
        </Panel>
      </>
    );
  }

  function renderHealthModule() {
    return (
      <>
        <div className="stats-grid">
          <Stat label="Orders today" value={healthTotals.orders} />
          <Stat label="Revenue today" value={formatMoney(healthTotals.revenue)} tone="good" />
          <Stat label="Payment attention" value={healthTotals.paymentAttention} tone="warn" />
          <Stat label="Stock alerts" value={healthTotals.stockAlerts} tone="warn" />
        </div>
        <Panel
          title="Tenant Health"
          action={
            <button className="icon-button" type="button" onClick={loadRestaurants}>
              <RefreshCw size={17} />
            </button>
          }
        >
          <div className="tenant-list">
            {restaurants.map((restaurant) => (
              <article className="tenant-card tenant-card-health" key={restaurant.id}>
                <div className="tenant-card-heading">
                  <span className={statusPillClass(restaurant.status)}>
                    {restaurant.status.replace("_", " ")}
                  </span>
                  <span className={statusPillClass(restaurant.subscription_status)}>
                    {restaurant.subscription_status}
                  </span>
                  <span className={statusPillClass(orderAccessStatus(restaurant))}>
                    Orders {formatAction(orderAccessStatus(restaurant))}
                  </span>
                </div>
                <div className="tenant-card-body">
                  <h3>{restaurant.name}</h3>
                  <span>{restaurant.code}</span>
                  <div className="tenant-health-grid">
                    <span>{restaurant.today_order_count} orders today</span>
                    <span>{formatMoney(restaurant.today_revenue)} today</span>
                    <span>{restaurant.pending_payment_count} pending payments</span>
                    <span>{restaurant.failed_payment_count} failed payments</span>
                    <span>{restaurant.critical_stock_alert_count} critical stock alerts</span>
                    <span>{restaurant.low_stock_alert_count} low stock alerts</span>
                    <span>{restaurant.branch_count} branches</span>
                    <span>{restaurant.active_user_count} users</span>
                    <span>{formatAction(orderAccessStatus(restaurant))} order access</span>
                  </div>
                  {restaurant.order_access_message ? (
                    <p className="tenant-warning">{restaurant.order_access_message}</p>
                  ) : null}
                  <div className="tenant-card-meta">
                    <span>Last order {formatDateTime(restaurant.last_order_at)}</span>
                    {restaurant.subscription_grace_ends_at ? (
                      <span>Grace ends {formatDateTime(restaurant.subscription_grace_ends_at)}</span>
                    ) : null}
                    <span>{restaurant.owner_name ?? "No owner"}</span>
                  </div>
                </div>
              </article>
            ))}
            {!restaurants.length ? <EmptyState>No tenant health data yet</EmptyState> : null}
          </div>
        </Panel>
      </>
    );
  }

  function renderPlatformUsersModule() {
    return (
      <>
        <div className="stats-grid">
          <Stat label="Active admins" value={activeAdminCount} tone="good" />
          <Stat label="Active support" value={activeSupportCount} />
          <Stat label="Active finance" value={activeFinanceCount} />
          <Stat label="Platform users" value={platformUsers.length} />
        </div>
        {renderPlatformUserSetupLink()}
        <div className="view-grid two-columns">
          <Panel title="Invite Platform User">
            <form className="tenant-onboarding-form" onSubmit={invitePlatformUser}>
              <div className="form-section-title">
                <Users size={17} />
                Platform access
              </div>
              <Field label="Email">
                <input
                  type="email"
                  value={platformUserForm.email}
                  onChange={(event) => updatePlatformUserField("email", event.target.value)}
                  placeholder="support@cognivex.com"
                  required
                />
              </Field>
              <Field label="First name">
                <input
                  value={platformUserForm.first_name}
                  onChange={(event) => updatePlatformUserField("first_name", event.target.value)}
                  required
                />
              </Field>
              <Field label="Last name">
                <input
                  value={platformUserForm.last_name}
                  onChange={(event) => updatePlatformUserField("last_name", event.target.value)}
                  required
                />
              </Field>
              <Field label="Role">
                <select
                  value={platformUserForm.role_name}
                  onChange={(event) =>
                    updatePlatformUserField("role_name", event.target.value as PlatformUserRole)
                  }
                >
                  <option value="SUPPORT">Support</option>
                  <option value="FINANCE">Finance</option>
                  <option value="ADMIN">Admin</option>
                </select>
              </Field>
              <button className="primary-action" type="submit" disabled={isSubmitting}>
                <UserPlus size={18} />
                {isSubmitting ? "Creating user" : "Invite platform user"}
              </button>
            </form>
          </Panel>

          <Panel
            title="Platform Users"
            action={
              <button className="icon-button" type="button" onClick={loadPlatformUsers}>
                <RefreshCw size={17} />
              </button>
            }
          >
            <div className="tenant-list">
              {platformUsers.map((user) => (
                <article className="tenant-card tenant-card-compact" key={user.id}>
                  <div className="tenant-card-heading">
                    <span className={statusPillClass(user.is_active ? "ACTIVE" : "SUSPENDED")}>
                      {user.is_active ? "ACTIVE" : "INACTIVE"}
                    </span>
                    <span className="status-pill">{user.role_name}</span>
                  </div>
                  <div className="tenant-card-body">
                    <h3>
                      {user.first_name} {user.last_name}
                    </h3>
                    <span>{user.email}</span>
                    <div className="tenant-card-meta">
                      <span>Created {formatDateTime(user.created_at)}</span>
                      <span>{user.restaurant_id ? "Tenant scoped" : "Platform scoped"}</span>
                    </div>
                  </div>
                  <div className="tenant-card-actions">
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => void createPlatformUserSetupLink(user)}
                      disabled={actionRestaurantId === user.id || !user.is_active}
                    >
                      <KeyRound size={17} />
                      Setup link
                    </button>
                    <select
                      value={user.role_name ?? "SUPPORT"}
                      onChange={(event) =>
                        void updatePlatformUser(user, {
                          role_name: event.target.value as User["role_name"],
                        })
                      }
                      disabled={actionRestaurantId === user.id}
                    >
                      <option value="ADMIN">Admin</option>
                      <option value="SUPPORT">Support</option>
                      <option value="FINANCE">Finance</option>
                    </select>
                    {user.is_active ? (
                      <button
                        className="secondary-action danger-action"
                        type="button"
                        onClick={() => void updatePlatformUser(user, { is_active: false })}
                        disabled={actionRestaurantId === user.id}
                      >
                        <PowerOff size={17} />
                        Deactivate
                      </button>
                    ) : (
                      <button
                        className="secondary-action"
                        type="button"
                        onClick={() => void updatePlatformUser(user, { is_active: true })}
                        disabled={actionRestaurantId === user.id}
                      >
                        <Power size={17} />
                        Reactivate
                      </button>
                    )}
                  </div>
                </article>
              ))}
              {!platformUsers.length ? <EmptyState>No platform users found</EmptyState> : null}
            </div>
          </Panel>
        </div>
      </>
    );
  }

  function renderAuditModule() {
    return (
      <>
        <div className="stats-grid">
          <Stat label="Audit events" value={logs.length} />
          <Stat label="Tenants" value={restaurants.length} />
          <Stat
            label="Lifecycle events"
            value={logs.filter((log) => log.action.includes("LIFECYCLE")).length}
          />
          <Stat
            label="Subscription events"
            value={logs.filter((log) => log.action.includes("SUBSCRIPTION")).length}
          />
        </div>
        <Panel
          title="Platform Audit"
          action={
            <button className="secondary-action" type="button" onClick={loadLogs}>
              <RefreshCw size={17} />
              Refresh
            </button>
          }
        >
          <div className="audit-filter-grid">
            <Field label="From">
              <input
                type="date"
                value={auditDateFrom}
                onChange={(event) => setAuditDateFrom(event.target.value)}
              />
            </Field>
            <Field label="To">
              <input
                type="date"
                value={auditDateTo}
                onChange={(event) => setAuditDateTo(event.target.value)}
              />
            </Field>
            <Field label="Action">
              <select value={auditAction} onChange={(event) => setAuditAction(event.target.value)}>
                <option value="">All actions</option>
                {PLATFORM_AUDIT_ACTIONS.map((option) => (
                  <option key={option} value={option}>
                    {formatAction(option)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Entity">
              <select
                value={auditEntityType}
                onChange={(event) => setAuditEntityType(event.target.value)}
              >
                <option value="">All entities</option>
                {PLATFORM_AUDIT_ENTITIES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </Panel>
        <div className="audit-list">
          {logs.map((log) => (
            <article className="audit-row" data-testid={`platform-audit-${log.action}`} key={log.id}>
              <header className="audit-row-header">
                <ClipboardList size={18} />
                <div>
                  <strong>{formatAction(log.action)}</strong>
                  <span>
                    {auditTenantLabel(log, tenantNameById)} |{" "}
                    {log.user_name ?? log.user_email ?? "System"} | {formatDateTime(log.created_at)}
                  </span>
                </div>
                <span className="status-pill">{log.entity_type}</span>
              </header>
              <div className="audit-change-grid">
                <div>
                  <span>Before</span>
                  <p>{summarizeValues(log.old_values)}</p>
                </div>
                <div>
                  <span>After</span>
                  <p>{summarizeValues(log.new_values)}</p>
                </div>
              </div>
            </article>
          ))}
          {!logs.length ? (
            <EmptyState>No platform audit events for the selected filters</EmptyState>
          ) : null}
        </div>
      </>
    );
  }

  return (
    <div className="view-stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      {isLoading ? <Notice>Loading platform data</Notice> : null}

      {module === "tenants" ? renderTenantsModule() : null}
      {module === "subscriptions" ? renderSubscriptionsModule() : null}
      {module === "health" ? renderHealthModule() : null}
      {module === "users" ? renderPlatformUsersModule() : null}
      {module === "audit" ? renderAuditModule() : null}
    </div>
  );
}
