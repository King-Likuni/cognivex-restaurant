import {
  CheckCircle2,
  ClipboardList,
  Copy,
  ExternalLink,
  RefreshCw,
  Rocket,
  Save,
  Store,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext, ViewKey } from "../App";
import { EmptyState, Field, Notice, Panel, Stat } from "../components/ui";
import {
  apiRequest,
  type Ingredient,
  type MenuCategory,
  type MenuItem,
  type RestaurantSetupStatus,
  type StockLocation,
} from "../services/api";

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
  const [categoryName, setCategoryName] = useState("Meals");
  const [itemName, setItemName] = useState("");
  const [itemDescription, setItemDescription] = useState("");
  const [itemPrice, setItemPrice] = useState("");
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [locations, setLocations] = useState<StockLocation[]>([]);
  const [inventoryMenuItemId, setInventoryMenuItemId] = useState("");
  const [ingredientName, setIngredientName] = useState("");
  const [ingredientUnit, setIngredientUnit] = useState("portion");
  const [locationName, setLocationName] = useState("Kitchen");
  const [startingQuantity, setStartingQuantity] = useState("10.000");
  const [recipeQuantity, setRecipeQuantity] = useState("1.000");
  const [warningQuantity, setWarningQuantity] = useState("5.000");
  const [criticalQuantity, setCriticalQuantity] = useState("2.000");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSavingMenu, setIsSavingMenu] = useState(false);
  const [isSavingInventory, setIsSavingInventory] = useState(false);

  const qrUrl = useMemo(() => setupUrl(status?.qr_order_url_path ?? null), [status]);

  const loadStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [nextStatus, nextMenuItems, nextIngredients, nextLocations] = await Promise.all([
        apiRequest<RestaurantSetupStatus>(
          `/api/v1/restaurants/${context.restaurant.id}/setup/status`,
          {
            token,
            params: { branch_id: context.branch.id },
          },
        ),
        apiRequest<MenuItem[]>(`/api/v1/restaurants/${context.restaurant.id}/menu/items`, {
          token,
        }),
        apiRequest<Ingredient[]>(
          `/api/v1/restaurants/${context.restaurant.id}/inventory/ingredients`,
          { token },
        ),
        apiRequest<StockLocation[]>(
          `/api/v1/restaurants/${context.restaurant.id}/inventory/branches/${context.branch.id}/locations`,
          { token },
        ),
      ]);
      setStatus(nextStatus);
      setMenuItems(nextMenuItems);
      setIngredients(nextIngredients);
      setLocations(nextLocations);
      setInventoryMenuItemId((current) =>
        current && nextMenuItems.some((item) => item.id === current)
          ? current
          : nextMenuItems[0]?.id ?? "",
      );
      setIngredientName((current) => current || nextIngredients[0]?.name || "");
      setIngredientUnit((current) => current || nextIngredients[0]?.unit || "portion");
      setLocationName((current) => current || nextLocations[0]?.name || "Kitchen");
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

  async function createFirstMenuItem(event: React.FormEvent) {
    event.preventDefault();
    setNotice(null);
    setError(null);
    setIsSavingMenu(true);
    try {
      const category = await apiRequest<MenuCategory>(
        `/api/v1/restaurants/${context.restaurant.id}/menu/categories`,
        {
          method: "POST",
          token,
          body: {
            name: categoryName.trim(),
            display_order: 1,
          },
        },
      );
      await apiRequest<MenuItem>(`/api/v1/restaurants/${context.restaurant.id}/menu/items`, {
        method: "POST",
        token,
        body: {
          category_id: category.id,
          name: itemName.trim(),
          description: itemDescription.trim() || null,
          price: itemPrice,
          image_url: null,
          is_available: true,
        },
      });
      setItemName("");
      setItemDescription("");
      setItemPrice("");
      setNotice("First menu item created");
      await loadStatus();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create menu item");
    } finally {
      setIsSavingMenu(false);
    }
  }

  function matchingIngredient() {
    const normalizedName = ingredientName.trim().toLowerCase();
    return ingredients.find((ingredient) => ingredient.name.trim().toLowerCase() === normalizedName);
  }

  function matchingLocation() {
    const normalizedName = locationName.trim().toLowerCase();
    return locations.find((location) => location.name.trim().toLowerCase() === normalizedName);
  }

  async function createFirstInventory(event: React.FormEvent) {
    event.preventDefault();
    setNotice(null);
    setError(null);
    if (!inventoryMenuItemId) {
      setError("Create a menu item before linking inventory");
      return;
    }
    setIsSavingInventory(true);
    try {
      const ingredient =
        matchingIngredient() ??
        (await apiRequest<Ingredient>(
          `/api/v1/restaurants/${context.restaurant.id}/inventory/ingredients`,
          {
            method: "POST",
            token,
            body: { name: ingredientName.trim(), unit: ingredientUnit.trim() },
          },
        ));
      const location =
        matchingLocation() ??
        (await apiRequest<StockLocation>(
          `/api/v1/restaurants/${context.restaurant.id}/inventory/branches/${context.branch.id}/locations`,
          {
            method: "POST",
            token,
            body: { name: locationName.trim() },
          },
        ));
      await apiRequest(
        `/api/v1/restaurants/${context.restaurant.id}/inventory/branches/${context.branch.id}/movements`,
        {
          method: "POST",
          token,
          body: {
            stock_location_id: location.id,
            ingredient_id: ingredient.id,
            movement_type: "RECEIVED",
            quantity: startingQuantity,
          },
        },
      );
      await apiRequest(
        `/api/v1/restaurants/${context.restaurant.id}/inventory/menu-items/${inventoryMenuItemId}/recipe-items`,
        {
          method: "PUT",
          token,
          body: { ingredient_id: ingredient.id, quantity: recipeQuantity },
        },
      );
      await apiRequest(
        `/api/v1/restaurants/${context.restaurant.id}/inventory/branches/${context.branch.id}/thresholds/${ingredient.id}`,
        {
          method: "PUT",
          token,
          body: {
            warning_quantity: warningQuantity,
            critical_quantity: criticalQuantity,
          },
        },
      );
      setNotice("First inventory setup saved");
      await loadStatus();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save inventory setup");
    } finally {
      setIsSavingInventory(false);
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
          <Panel title="First Menu Item">
            <form className="setup-menu-form" onSubmit={createFirstMenuItem}>
              <Field label="Category">
                <input
                  value={categoryName}
                  onChange={(event) => setCategoryName(event.target.value)}
                  placeholder="Meals"
                  required
                />
              </Field>
              <Field label="Item name">
                <input
                  value={itemName}
                  onChange={(event) => setItemName(event.target.value)}
                  placeholder="Quarter Chicken and Chips"
                  required
                />
              </Field>
              <Field label="Description">
                <textarea
                  value={itemDescription}
                  onChange={(event) => setItemDescription(event.target.value)}
                  placeholder="Short customer-facing description"
                  rows={3}
                />
              </Field>
              <Field label="Price">
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={itemPrice}
                  onChange={(event) => setItemPrice(event.target.value)}
                  placeholder="55.00"
                  required
                />
              </Field>
              <button className="primary-action" type="submit" disabled={isSavingMenu}>
                <Save size={18} />
                {isSavingMenu ? "Creating item" : "Create menu item"}
              </button>
            </form>
          </Panel>

          <Panel title="First Inventory Setup">
            <form className="setup-menu-form" onSubmit={createFirstInventory}>
              <Field label="Menu item">
                <select
                  value={inventoryMenuItemId}
                  onChange={(event) => setInventoryMenuItemId(event.target.value)}
                  required
                >
                  {!menuItems.length ? <option value="">Create a menu item first</option> : null}
                  {menuItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Ingredient">
                <input
                  value={ingredientName}
                  onChange={(event) => setIngredientName(event.target.value)}
                  placeholder="Chicken Quarter"
                  required
                />
              </Field>
              <Field label="Unit">
                <input
                  value={ingredientUnit}
                  onChange={(event) => setIngredientUnit(event.target.value)}
                  placeholder="portion"
                  required
                />
              </Field>
              <Field label="Stock location">
                <input
                  value={locationName}
                  onChange={(event) => setLocationName(event.target.value)}
                  placeholder="Kitchen"
                  required
                />
              </Field>
              <div className="setup-inline-grid">
                <Field label="Starting stock">
                  <input
                    type="number"
                    min="0.001"
                    step="0.001"
                    value={startingQuantity}
                    onChange={(event) => setStartingQuantity(event.target.value)}
                    required
                  />
                </Field>
                <Field label="Recipe qty">
                  <input
                    type="number"
                    min="0.001"
                    step="0.001"
                    value={recipeQuantity}
                    onChange={(event) => setRecipeQuantity(event.target.value)}
                    required
                  />
                </Field>
              </div>
              <div className="setup-inline-grid">
                <Field label="Warning level">
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={warningQuantity}
                    onChange={(event) => setWarningQuantity(event.target.value)}
                    required
                  />
                </Field>
                <Field label="Critical level">
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    value={criticalQuantity}
                    onChange={(event) => setCriticalQuantity(event.target.value)}
                    required
                  />
                </Field>
              </div>
              <button
                className="primary-action"
                type="submit"
                disabled={isSavingInventory || !menuItems.length}
              >
                <Save size={18} />
                {isSavingInventory ? "Saving inventory" : "Save inventory setup"}
              </button>
            </form>
          </Panel>

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
