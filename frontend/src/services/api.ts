export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type RoleName =
  | "ADMIN"
  | "SUPPORT"
  | "FINANCE"
  | "OWNER"
  | "MANAGER"
  | "CASHIER"
  | "KITCHEN"
  | "INVENTORY";

export type User = {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  is_active: boolean;
  role_name: RoleName | null;
  restaurant_id: string | null;
  branch_ids: string[];
  branch_assignments: { id: string; code: string; name: string }[];
  created_at: string | null;
};

export type PasswordSetupToken = {
  token: string;
  setup_url_path: string;
  expires_at: string;
};

export type StaffInviteResponse = {
  user: User;
  invite: PasswordSetupToken;
};

export type PlatformUserInviteResponse = {
  user: User;
  invite: PasswordSetupToken;
};

export type RestaurantOnboardingResponse = {
  restaurant: Restaurant;
  branch: Branch;
  owner: User;
  invite: PasswordSetupToken;
};

export type PasswordSetupPreview = {
  email: string;
  first_name: string | null;
  last_name: string | null;
  role_name: RoleName | null;
  expires_at: string;
};

export type Restaurant = {
  id: string;
  code: string;
  name: string;
  status: "SETUP_PENDING" | "ACTIVE" | "SUSPENDED" | string;
  subscription_status: "TRIAL" | "ACTIVE" | "OVERDUE" | "CANCELLED" | string;
  subscription_started_at: string | null;
  subscription_renews_at: string | null;
  suspension_reason: string | null;
  is_active: boolean;
  created_at: string | null;
};

export type RestaurantLifecycleStatus = "ACTIVE" | "SUSPENDED";
export type RestaurantSubscriptionStatus = "TRIAL" | "ACTIVE" | "OVERDUE" | "CANCELLED";

export type PlatformRestaurantSummary = Restaurant & {
  branch_count: number;
  active_user_count: number;
  owner_email: string | null;
  owner_name: string | null;
  owner_setup_expires_at: string | null;
  owner_setup_expired: boolean;
  today_order_count: number;
  today_revenue: string;
  pending_payment_count: number;
  failed_payment_count: number;
  low_stock_alert_count: number;
  critical_stock_alert_count: number;
  last_order_at: string | null;
  order_access_status: "ACTIVE" | "GRACE_PERIOD" | "BLOCKED" | string;
  order_access_message: string | null;
  order_access_blocked: boolean;
  subscription_grace_ends_at: string | null;
};

export type Branch = {
  id: string;
  restaurant_id: string;
  code: string;
  name: string;
  location: string | null;
  is_active: boolean;
};

export type BranchUpdate = {
  code?: string;
  name?: string;
  location?: string | null;
  is_active?: boolean;
};

export type MenuCategory = {
  id: string;
  restaurant_id: string;
  name: string;
  display_order: number;
  is_active: boolean;
};

export type MenuItem = {
  id: string;
  category_id: string;
  restaurant_id: string;
  name: string;
  description: string | null;
  price: string;
  image_url: string | null;
  is_available: boolean;
  is_available_for_sale: boolean;
  stock_status: string;
  stock_message: string | null;
};

export type PublicMenuItem = Omit<MenuItem, "restaurant_id">;

export type PublicMenuCategory = {
  id: string;
  name: string;
  display_order: number;
  items: PublicMenuItem[];
};

export type PublicMenu = {
  restaurant_id: string;
  restaurant_name: string;
  branch_id: string;
  branch_name: string;
  currency: string;
  categories: PublicMenuCategory[];
};

export type Order = {
  id: string;
  restaurant_id: string;
  branch_id: string;
  business_date: string;
  daily_sequence: number;
  display_number: string;
  payment_reference: string;
  customer_id: string | null;
  channel: string;
  subtotal: string;
  total: string;
  currency: string;
  payment_status: string;
  payment_provider: string | null;
  mobile_transfer_proof_confirmed: boolean;
  order_status: string;
  created_by: string | null;
  created_at: string | null;
  confirmed_at: string | null;
  preparing_at: string | null;
  ready_at: string | null;
  collected_at: string | null;
  items: OrderItem[];
};

export type OrderItem = {
  id: string;
  menu_item_id: string;
  quantity: number;
  unit_price: string;
  total_price: string;
};

export type Payment = {
  id: string;
  order_id: string;
  restaurant_id: string;
  provider: string;
  reference: string;
  provider_transaction_id: string | null;
  amount: string;
  currency: string;
  status: string;
  created_at: string | null;
  completed_at: string | null;
};

export type KitchenBoard = {
  new: Order[];
  preparing: Order[];
  ready: Order[];
  collected: Order[];
};

export type Ingredient = {
  id: string;
  restaurant_id: string;
  name: string;
  unit: string;
};

export type StockLocation = {
  id: string;
  restaurant_id: string;
  branch_id: string;
  name: string;
};

export type RecipeItem = {
  id: string;
  menu_item_id: string;
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  quantity: string;
};

export type StockBalance = {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  quantity_on_hand: string;
};

export type StockThreshold = {
  id: string;
  restaurant_id: string;
  branch_id: string;
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  warning_quantity: string;
  critical_quantity: string;
};

export type LowStockAlert = {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  quantity_on_hand: string;
  warning_quantity: string;
  critical_quantity: string;
  severity: "LOW" | "CRITICAL";
  message: string;
};

export type DailySalesReport = {
  restaurant_id: string;
  branch_id: string | null;
  business_date: string;
  orders: number;
  collected_orders: number;
  ready_orders: number;
  uncollected_orders: number;
  cancelled_orders: number;
  revenue: string;
  average_order_value: string;
  top_items: { menu_item_id: string; name: string; quantity: number; revenue: string }[];
  sales_by_payment: { provider: string; payments: number; revenue: string }[];
  sales_by_channel: { channel: string; orders: number; revenue: string }[];
  hourly_sales: { hour: number; orders: number; revenue: string }[];
  cashier_activity: {
    user_id: string | null;
    name: string;
    email: string | null;
    orders_created: number;
    payments_confirmed: number;
    orders_collected: number;
    revenue_collected: string;
  }[];
};

export type AuditLog = {
  id: string;
  restaurant_id: string | null;
  user_id: string | null;
  user_email: string | null;
  user_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  created_at: string | null;
};

export type OrderStatusToken = {
  order_id: string;
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
};

export type PublicCustomerOrderResponse = {
  order: Order;
  payment: Payment;
  status_token: OrderStatusToken;
  status_url_path: string;
};

export type CustomerOrderStatus = {
  order_id: string;
  display_number: string;
  payment_reference: string;
  payment_provider: string | null;
  payment_status: string;
  order_status: string;
  stage_label: string;
  message: string;
  collection_instruction: string | null;
  payment_reference_required: boolean;
  updated_at: string | null;
};

export type RealtimeEvent = {
  type: string;
  restaurant_id: string;
  branch_id: string;
  order_id: string;
  display_number: string;
  order_status: string;
  payment_status: string;
  channel: string;
  occurred_at: string;
};

type RequestOptions = {
  method?: string;
  token?: string | null;
  body?: unknown;
  params?: Record<string, string | number | boolean | null | undefined>;
};

function buildUrl(path: string, params?: RequestOptions["params"]) {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(buildUrl(path, options.params), {
    method: options.method ?? "GET",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Keep the HTTP status message when the body is not JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function downloadApiFile(path: string, options: RequestOptions = {}): Promise<Blob> {
  const response = await fetch(buildUrl(path, options.params), {
    method: options.method ?? "GET",
    headers: {
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Keep the HTTP status message when the body is not JSON.
    }
    throw new Error(message);
  }

  return response.blob();
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: "POST",
    body,
  });

  if (!response.ok) {
    throw new Error("Invalid email or password");
  }
  return (await response.json()) as { access_token: string; token_type: string; user: User };
}

export function realtimeUrl(path: string, token: string) {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  return `${wsBase}${path}?token=${encodeURIComponent(token)}`;
}
