import {
  Building2,
  Copy,
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
  ) {
    setNotice(null);
    setError(null);
    setActionRestaurantId(restaurant.id);
    try {
      await apiRequest(`/api/v1/restaurants/${restaurant.id}/lifecycle`, {
        method: "PATCH",
        token,
        body: { status },
      });
      setNotice(`${restaurant.name} is now ${status.toLowerCase().replace("_", " ")}`);
      await loadRestaurants();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update tenant status");
    } finally {
      setActionRestaurantId(null);
    }
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
        <Stat label="Setup pending" value={setupPendingCount} />
        <Stat label="Suspended" value={suspendedCount} tone="warn" />
        <Stat label="Tenants listed" value={restaurants.length} />
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
            {restaurants.map((restaurant) => (
              <article className="tenant-card" key={restaurant.id}>
                <span
                  className={
                    restaurant.status === "SUSPENDED" ? "status-pill inactive" : "status-pill"
                  }
                >
                  {restaurant.status.replace("_", " ")}
                </span>
                <div>
                  <h3>{restaurant.name}</h3>
                  <span>{restaurant.code}</span>
                  <div className="tenant-card-meta">
                    <span>{restaurant.branch_count} branches</span>
                    <span>{restaurant.owner_name ?? "No owner"}</span>
                    <span>{restaurant.owner_email ?? "No owner email"}</span>
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
                      onClick={() => void updateLifecycle(restaurant, "SUSPENDED")}
                      disabled={actionRestaurantId === restaurant.id}
                    >
                      <PowerOff size={17} />
                      Suspend
                    </button>
                  )}
                </div>
              </article>
            ))}
            {!restaurants.length ? <EmptyState>No restaurants onboarded yet</EmptyState> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}
