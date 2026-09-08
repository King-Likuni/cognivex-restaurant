import { Boxes, Plus, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel } from "../components/ui";
import {
  apiRequest,
  type Ingredient,
  type MenuItem,
  type RecipeItem,
  type StockBalance,
  type StockLocation,
} from "../services/api";

type Props = {
  context: AppContext;
  token: string;
};

export function InventoryView({ context, token }: Props) {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [locations, setLocations] = useState<StockLocation[]>([]);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [balances, setBalances] = useState<StockBalance[]>([]);
  const [recipeItems, setRecipeItems] = useState<RecipeItem[]>([]);
  const [selectedMenuItemId, setSelectedMenuItemId] = useState("");
  const [ingredientName, setIngredientName] = useState("");
  const [unit, setUnit] = useState("portion");
  const [locationName, setLocationName] = useState("Kitchen");
  const [stockQuantity, setStockQuantity] = useState("10.000");
  const [recipeIngredientId, setRecipeIngredientId] = useState("");
  const [recipeQuantity, setRecipeQuantity] = useState("1.000");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadInventory = useCallback(async () => {
    setError(null);
    try {
      const [nextIngredients, nextLocations, nextItems, nextBalances] = await Promise.all([
        apiRequest<Ingredient[]>(`/api/v1/restaurants/${context.restaurant.id}/inventory/ingredients`, {
          token,
        }),
        apiRequest<StockLocation[]>(
          `/api/v1/restaurants/${context.restaurant.id}/inventory/branches/${context.branch.id}/locations`,
          { token },
        ),
        apiRequest<MenuItem[]>(`/api/v1/restaurants/${context.restaurant.id}/menu/items`, { token }),
        apiRequest<StockBalance[]>(
          `/api/v1/restaurants/${context.restaurant.id}/inventory/branches/${context.branch.id}/balances`,
          { token },
        ),
      ]);
      setIngredients(nextIngredients);
      setLocations(nextLocations);
      setMenuItems(nextItems);
      setBalances(nextBalances);
      setRecipeIngredientId(nextIngredients[0]?.id ?? "");
      setSelectedMenuItemId((current) => current || nextItems[0]?.id || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load inventory");
    }
  }, [context.branch.id, context.restaurant.id, token]);

  const loadRecipe = useCallback(async (menuItemId: string) => {
    if (!menuItemId) {
      setRecipeItems([]);
      return;
    }
    const items = await apiRequest<RecipeItem[]>(
      `/api/v1/restaurants/${context.restaurant.id}/inventory/menu-items/${menuItemId}/recipe-items`,
      { token },
    );
    setRecipeItems(items);
  }, [context.restaurant.id, token]);

  useEffect(() => {
    void loadInventory();
  }, [loadInventory]);

  useEffect(() => {
    void loadRecipe(selectedMenuItemId);
  }, [loadRecipe, selectedMenuItemId]);

  async function createIngredient(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await apiRequest<Ingredient>(`/api/v1/restaurants/${context.restaurant.id}/inventory/ingredients`, {
        method: "POST",
        token,
        body: { name: ingredientName, unit },
      });
      setIngredientName("");
      setNotice("Ingredient created");
      await loadInventory();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create ingredient");
    }
  }

  async function createLocation(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await apiRequest<StockLocation>(
        `/api/v1/restaurants/${context.restaurant.id}/inventory/branches/${context.branch.id}/locations`,
        {
          method: "POST",
          token,
          body: { name: locationName },
        },
      );
      setNotice("Stock location created");
      await loadInventory();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create location");
    }
  }

  async function receiveStock(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const stockLocationId = locations[0]?.id;
    const ingredientId = recipeIngredientId || ingredients[0]?.id;
    if (!stockLocationId || !ingredientId) {
      setError("Create a stock location and ingredient first");
      return;
    }
    try {
      await apiRequest(
        `/api/v1/restaurants/${context.restaurant.id}/inventory/branches/${context.branch.id}/movements`,
        {
          method: "POST",
          token,
          body: {
            stock_location_id: stockLocationId,
            ingredient_id: ingredientId,
            movement_type: "RECEIVED",
            quantity: stockQuantity,
          },
        },
      );
      setNotice("Stock received");
      await loadInventory();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not receive stock");
    }
  }

  async function saveRecipe(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!selectedMenuItemId || !recipeIngredientId) {
      setError("Select a menu item and ingredient");
      return;
    }
    try {
      await apiRequest<RecipeItem>(
        `/api/v1/restaurants/${context.restaurant.id}/inventory/menu-items/${selectedMenuItemId}/recipe-items`,
        {
          method: "PUT",
          token,
          body: { ingredient_id: recipeIngredientId, quantity: recipeQuantity },
        },
      );
      setNotice("Recipe saved");
      await loadRecipe(selectedMenuItemId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save recipe");
    }
  }

  return (
    <div className="view-grid two-columns">
      <div className="view-stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}
        <Panel
          title="Ingredients"
          action={
            <button className="icon-button" type="button" onClick={loadInventory} title="Refresh">
              <RefreshCw size={17} />
            </button>
          }
        >
          <form className="compact-form" onSubmit={createIngredient}>
            <Field label="Name">
              <input
                value={ingredientName}
                onChange={(event) => setIngredientName(event.target.value)}
                placeholder="Chicken Portion"
              />
            </Field>
            <Field label="Unit">
              <input value={unit} onChange={(event) => setUnit(event.target.value)} />
            </Field>
            <button className="primary-action" type="submit">
              <Plus size={18} />
              Add ingredient
            </button>
          </form>
          <div className="data-list">
            {ingredients.map((ingredient) => (
              <div className="data-row" key={ingredient.id}>
                <strong>{ingredient.name}</strong>
                <span>{ingredient.unit}</span>
              </div>
            ))}
            {!ingredients.length ? <EmptyState>No ingredients yet</EmptyState> : null}
          </div>
        </Panel>

        <Panel title="Stock Locations">
          <form className="compact-form" onSubmit={createLocation}>
            <Field label="Location">
              <input value={locationName} onChange={(event) => setLocationName(event.target.value)} />
            </Field>
            <button className="primary-action" type="submit">
              <Boxes size={18} />
              Add location
            </button>
          </form>
          <div className="data-list">
            {locations.map((location) => (
              <div className="data-row" key={location.id}>
                <strong>{location.name}</strong>
                <span>{context.branch.name}</span>
              </div>
            ))}
            {!locations.length ? <EmptyState>No stock locations yet</EmptyState> : null}
          </div>
        </Panel>
      </div>

      <div className="view-stack">
        <Panel title="Receive Stock">
          <form className="compact-form" onSubmit={receiveStock}>
            <Field label="Ingredient">
              <select
                value={recipeIngredientId}
                onChange={(event) => setRecipeIngredientId(event.target.value)}
              >
                {ingredients.map((ingredient) => (
                  <option key={ingredient.id} value={ingredient.id}>
                    {ingredient.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Quantity">
              <input
                type="number"
                step="0.001"
                value={stockQuantity}
                onChange={(event) => setStockQuantity(event.target.value)}
              />
            </Field>
            <button className="primary-action" type="submit">
              <Plus size={18} />
              Receive
            </button>
          </form>
        </Panel>

        <Panel title="Recipes">
          <form className="compact-form" onSubmit={saveRecipe}>
            <Field label="Menu item">
              <select
                value={selectedMenuItemId}
                onChange={(event) => setSelectedMenuItemId(event.target.value)}
              >
                {menuItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Ingredient">
              <select
                value={recipeIngredientId}
                onChange={(event) => setRecipeIngredientId(event.target.value)}
              >
                {ingredients.map((ingredient) => (
                  <option key={ingredient.id} value={ingredient.id}>
                    {ingredient.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Per item">
              <input
                type="number"
                step="0.001"
                value={recipeQuantity}
                onChange={(event) => setRecipeQuantity(event.target.value)}
              />
            </Field>
            <button className="primary-action" type="submit">
              <Save size={18} />
              Save recipe
            </button>
          </form>
          <div className="data-list">
            {recipeItems.map((item) => (
              <div className="data-row" key={item.id}>
                <strong>{item.ingredient_name}</strong>
                <span>
                  {item.quantity} {item.unit}
                </span>
              </div>
            ))}
            {!recipeItems.length ? <EmptyState>No recipe items for this menu item</EmptyState> : null}
          </div>
        </Panel>

        <Panel title="Balances">
          <div className="data-list">
            {balances.map((balance) => (
              <div className="data-row" key={balance.ingredient_id}>
                <strong>{balance.ingredient_name}</strong>
                <span>
                  {Number(balance.quantity_on_hand).toFixed(3)} {balance.unit}
                </span>
              </div>
            ))}
            {!balances.length ? <EmptyState>No balances yet</EmptyState> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}
