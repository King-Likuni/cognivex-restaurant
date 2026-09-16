import {
  CheckCircle2,
  ClipboardList,
  Copy,
  ExternalLink,
  RefreshCw,
  Rocket,
  Store,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext, ViewKey } from "../App";
import { EmptyState, Notice, Panel, Stat } from "../components/ui";
import { apiRequest, type RestaurantSetupStatus } from "../services/api";

type Props = {
  context: AppContext;
  token: string;
  onNavigate: (view: ViewKey) => void;
};

function setupUrl(path: string | null) {
  return path ? `${window.location.origin}${path}` : "";
}

export function OwnerSetupWizard({ context, token, onNavigate }: Props) {
  const [status, setStatus] = useState<RestaurantSetupStatus | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const qrUrl = useMemo(() => setupUrl(status?.qr_order_url_path ?? null), [status]);

  const loadStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextStatus = await apiRequest<RestaurantSetupStatus>(
        `/api/v1/restaurants/${context.restaurant.id}/setup/status`,
        {
          token,
          params: { branch_id: context.branch.id },
        },
      );
      setStatus(nextStatus);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load setup status");
    } finally {
      setIsLoading(false);
    }
  }, [context.branch.id, context.restaurant.id, token]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  async function copyQrUrl() {
    if (!qrUrl) {
      return;
    }
    try {
      await navigator.clipboard.writeText(qrUrl);
      setNotice("Customer ordering link copied");
    } catch {
      setError("Could not copy link. Select the link and copy it manually.");
    }
  }

  function navigateTo(view: string) {
    if (
      view === "branches" ||
      view === "inventory" ||
      view === "staff" ||
      view === "dashboard" ||
      view === "cashier" ||
      view === "kitchen" ||
      view === "audit" ||
      view === "setup"
    ) {
      onNavigate(view);
    }
  }

  return (
    <div className="view-stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      {isLoading ? <Notice>Loading setup checklist</Notice> : null}

      <div className="stats-grid">
        <Stat
          label="Setup progress"
          value={status ? `${status.completed_steps}/${status.total_steps}` : "0/0"}
          tone={status?.is_ready ? "good" : "warn"}
        />
        <Stat label="Menu items" value={status?.counts.menu_items ?? 0} />
        <Stat label="Ingredients" value={status?.counts.ingredients ?? 0} />
        <Stat label="Staff users" value={status?.counts.staff_users ?? 0} />
      </div>

      <div className="view-grid two-columns">
        <Panel
          title="Owner Setup"
          action={
            <button className="icon-button" type="button" onClick={loadStatus} title="Refresh">
              <RefreshCw size={17} />
            </button>
          }
        >
          <div className="setup-hero">
            <span className={status?.is_ready ? "setup-icon ready" : "setup-icon"}>
              {status?.is_ready ? <CheckCircle2 size={28} /> : <Rocket size={28} />}
            </span>
            <div>
              <h3>{status?.restaurant_name ?? context.restaurant.name}</h3>
              <p>
                {status?.is_ready
                  ? "This restaurant is ready for live ordering and daily operations."
                  : "Complete these setup steps before pushing customer ordering heavily."}
              </p>
            </div>
          </div>

          <div className="setup-step-list">
            {status?.steps.map((step) => (
              <article
                className={step.is_complete ? "setup-step complete" : "setup-step"}
                key={step.key}
              >
                <span className="setup-step-status">
                  {step.is_complete ? <CheckCircle2 size={18} /> : <ClipboardList size={18} />}
                </span>
                <div>
                  <strong>{step.label}</strong>
                  <p>{step.description}</p>
                  <span>{step.count} configured</span>
                </div>
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() => navigateTo(step.action_view)}
                >
                  Open
                </button>
              </article>
            ))}
            {!status?.steps.length ? <EmptyState>No setup steps available</EmptyState> : null}
          </div>
        </Panel>

        <div className="view-stack">
          <Panel title="Customer QR Link">
            <div className="setup-link-card">
              <Store size={22} />
              <div>
                <strong>{status?.branch_name ?? context.branch.name}</strong>
                <span>{qrUrl || "Create a branch first"}</span>
              </div>
            </div>
            <div className="invite-link-box">
              <input readOnly value={qrUrl} placeholder="Customer ordering link unavailable" />
              <button
                className="secondary-action"
                type="button"
                onClick={copyQrUrl}
                disabled={!qrUrl}
              >
                <Copy size={17} />
                Copy
              </button>
            </div>
            {qrUrl ? (
              <a
                className="secondary-action setup-link-action"
                href={qrUrl}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={17} />
                Open customer order page
              </a>
            ) : null}
          </Panel>

          <Panel title="Setup Counts">
            {status ? (
              <div className="setup-count-grid">
                <span>Branches: {status.counts.active_branches}</span>
                <span>Categories: {status.counts.menu_categories}</span>
                <span>Menu items: {status.counts.menu_items}</span>
                <span>Ingredients: {status.counts.ingredients}</span>
                <span>Stock locations: {status.counts.stock_locations}</span>
                <span>Recipes: {status.counts.recipe_items}</span>
                <span>Thresholds: {status.counts.stock_thresholds}</span>
                <span>Staff: {status.counts.staff_users}</span>
              </div>
            ) : (
              <EmptyState>Setup counts will appear after loading</EmptyState>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
