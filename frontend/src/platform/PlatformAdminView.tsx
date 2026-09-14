import {
  AlertTriangle,
  Building2,
  CalendarDays,
  Copy,
  CreditCard,
  KeyRound,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Store,
  UserPlus,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState, Field, Notice, Panel, Stat } from "../components/ui";
import {
  apiRequest,
  type PasswordSetupToken,
  type PlatformRestaurantSummary,
  type RestaurantLifecycleStatus,
  type RestaurantOnboardingResponse,
  type RestaurantSubscriptionStatus,
} from "../services/api";

type Props = {
  token: string;
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

function setupUrlFromInvite(invite: RestaurantOnboardingResponse["invite"]) {
  return `${window.location.origin}${invite.setup_url_path}`;
}

function formatMoney(value: string | number) {
  return `BWP ${Number(value).toFixed(2)}`;
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "Not set";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function toDateInputValue(value: string | null) {
  if (!value) {
    return "";
  }
  return value.slice(0, 10);
}

function dateInputToIso(value: string) {
  return value ? new Date(`${value}T00:00:00`).toISOString() : null;
}

export function PlatformAdminView({ token }: Props) {
  const [restaurants, setRestaurants] = useState<PlatformRestaurantSummary[]>([]);
  const [form, setForm] = useState<OnboardingForm>(EMPTY_FORM);
  const [latestOnboarding, setLatestOnboarding] = useState<RestaurantOnboardingResponse | null>(
    null,
  );
  const [latestOwnerLink, setLatestOwnerLink] = useState<PasswordSetupToken | null>(null);
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
  const overdueCount = useMemo(
    () => restaurants.filter((restaurant) => restaurant.subscription_status === "OVERDUE").length,
    [restaurants],
  );
  const todayRevenue = useMemo(
    () =>
      restaurants.reduce(
        (total, restaurant) => total + Number(restaurant.today_revenue || 0),
        0,
      ),
    [restaurants],
  );
  const paymentIssueCount = useMemo(
    () =>
      restaurants.reduce(
        (total, restaurant) =>
          total + restaurant.pending_payment_count + restaurant.failed_payment_count,
        0,
      ),
    [restaurants],
  );

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

  useEffect(() => {
    void loadRestaurants();
  }, [loadRestaurants]);

  function updateField<K extends keyof OnboardingForm>(field: K, value: OnboardingForm[K]) {
    setForm((current) => ({ ...current, [field]: value }));
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

  return (
    <div className="view-stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      {isLoading ? <Notice>Loading platform tenants</Notice> : null}

      <div className="stats-grid">
        <Stat label="Active restaurants" value={activeRestaurantCount} tone="good" />
        <Stat label="Today revenue" value={formatMoney(todayRevenue)} tone="good" />
        <Stat label="Payment attention" value={paymentIssueCount} tone="warn" />
        <Stat label="Setup pending" value={setupPendingCount} />
        <Stat label="Overdue" value={overdueCount} tone="warn" />
        <Stat label="Suspended" value={suspendedCount} tone="warn" />
      </div>

      {latestOnboarding || latestOwnerLink ? (
        <Panel title="Owner Setup Link">
          <div className="invite-link-box">
            <input
              readOnly
              value={setupUrlFromInvite(latestOwnerLink ?? latestOnboarding!.invite)}
            />
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
      ) : null}

      <div className="view-grid two-columns">
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

        <Panel
          title="Restaurants"
          action={
            <button
              className="icon-button"
              type="button"
              onClick={loadRestaurants}
              title="Refresh restaurants"
            >
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
                <article className="tenant-card" key={restaurant.id}>
                  <div className="tenant-card-heading">
                    <span
                      className={
                        restaurant.status === "SUSPENDED" ? "status-pill inactive" : "status-pill"
                      }
                    >
                      {restaurant.status.replace("_", " ")}
                    </span>
                    <span
                      className={
                        restaurant.subscription_status === "OVERDUE" ||
                        restaurant.subscription_status === "CANCELLED"
                          ? "status-pill inactive"
                          : "status-pill"
                      }
                    >
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
                          restaurant.owner_setup_expired
                            ? "tenant-warning"
                            : "tenant-helper-text"
                        }
                      >
                        Owner setup expires {formatDateTime(restaurant.owner_setup_expires_at)}
                      </p>
                    ) : null}
                    <div className="tenant-health-grid">
                      <span>{restaurant.branch_count} branches</span>
                      <span>{restaurant.active_user_count} users</span>
                      <span>{restaurant.today_order_count} orders today</span>
                      <span>{formatMoney(restaurant.today_revenue)} today</span>
                      <span>{restaurant.pending_payment_count} pending payments</span>
                      <span>{restaurant.failed_payment_count} failed payments</span>
                      <span>
                        {restaurant.critical_stock_alert_count} critical stock alerts
                      </span>
                      <span>{restaurant.low_stock_alert_count} low stock alerts</span>
                    </div>
                    <div className="tenant-subscription-grid">
                      <label>
                        <span>Subscription</span>
                        <select
                          value={subscriptionDraft.subscription_status}
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
                          onChange={(event) =>
                            updateSubscriptionDraft(restaurant, {
                              subscription_renews_at: event.target.value,
                            })
                          }
                        />
                      </label>
                      <button
                        className="secondary-action"
                        type="button"
                        onClick={() => void updateSubscription(restaurant)}
                        disabled={actionRestaurantId === restaurant.id}
                      >
                        <CreditCard size={17} />
                        Save
                      </button>
                    </div>
                    <div className="tenant-card-meta">
                      <span>{restaurant.owner_name ?? "No owner"}</span>
                      <span>{restaurant.owner_email ?? "No owner email"}</span>
                      <span>Last order {formatDateTime(restaurant.last_order_at)}</span>
                    </div>
                  </div>
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
                </article>
              );
            })}
            {!restaurants.length ? <EmptyState>No restaurants onboarded yet</EmptyState> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}
