import { expect, request, test, type APIRequestContext } from "@playwright/test";

const API_BASE_URL = process.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const OWNER_EMAIL = process.env.E2E_OWNER_EMAIL ?? "owner@chickenspot.com";
const OWNER_PASSWORD = process.env.E2E_OWNER_PASSWORD ?? "ownerpassword";

type User = {
  restaurant_id: string;
};

type LoginResponse = {
  access_token: string;
  user: User;
};

type Branch = {
  id: string;
};

type MenuCategory = {
  id: string;
};

type MenuItem = {
  id: string;
  name: string;
};

type Order = {
  id: string;
  business_date: string;
  display_number: string;
  order_status: string;
  total: string;
};

type DailySalesReport = {
  collected_orders: number;
  revenue: string;
};

type StaffInviteResponse = {
  invite: {
    setup_url_path: string;
  };
};

type TestData = {
  token: string;
  restaurantId: string;
  branchId: string;
  menuItem: MenuItem;
};

async function getDailySalesReport(
  api: APIRequestContext,
  headers: { Authorization: string },
  data: TestData,
  businessDate?: string,
): Promise<DailySalesReport> {
  const response = await api.get(`/api/v1/restaurants/${data.restaurantId}/reports/daily-sales`, {
    headers,
    params: {
      business_date: businessDate,
      branch_id: data.branchId,
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()) as DailySalesReport;
}

async function apiSetup(): Promise<{ api: APIRequestContext; data: TestData }> {
  const api = await request.newContext({ baseURL: API_BASE_URL, timeout: 10_000 });
  const healthResponse = await api.get("/health");
  expect(healthResponse.ok(), await healthResponse.text()).toBeTruthy();

  const loginResponse = await api.post("/api/v1/auth/login", {
    form: {
      username: OWNER_EMAIL,
      password: OWNER_PASSWORD,
    },
  });
  expect(loginResponse.ok(), await loginResponse.text()).toBeTruthy();
  const login = (await loginResponse.json()) as LoginResponse;
  const headers = { Authorization: `Bearer ${login.access_token}` };

  const branchesResponse = await api.get(
    `/api/v1/restaurants/${login.user.restaurant_id}/branches`,
    { headers },
  );
  expect(branchesResponse.ok(), await branchesResponse.text()).toBeTruthy();
  const branches = (await branchesResponse.json()) as Branch[];
  expect(branches.length).toBeGreaterThan(0);

  const suffix = Date.now();
  const categoryResponse = await api.post(
    `/api/v1/restaurants/${login.user.restaurant_id}/menu/categories`,
    {
      headers,
      data: {
        name: `E2E Chicken ${suffix}`,
        display_order: 1,
      },
    },
  );
  expect(categoryResponse.ok(), await categoryResponse.text()).toBeTruthy();
  const category = (await categoryResponse.json()) as MenuCategory;

  const itemResponse = await api.post(`/api/v1/restaurants/${login.user.restaurant_id}/menu/items`, {
    headers,
    data: {
      category_id: category.id,
      name: `E2E Meal ${suffix}`,
      description: "Created by Playwright",
      price: "55.00",
      image_url: null,
      is_available: true,
    },
  });
  expect(itemResponse.ok(), await itemResponse.text()).toBeTruthy();
  const menuItem = (await itemResponse.json()) as MenuItem;

  return {
    api,
    data: {
      token: login.access_token,
      restaurantId: login.user.restaurant_id,
      branchId: branches[0].id,
      menuItem,
    },
  };
}

test("cashier, kitchen, pickup, and dashboard journey", async ({ page }) => {
  const { api, data } = await apiSetup();
  const headers = { Authorization: `Bearer ${data.token}` };

  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByLabel("Email").fill(OWNER_EMAIL);
  await page.getByLabel("Password").fill(OWNER_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByTestId("workspace-title")).toContainText("Chicken Spot");
  await expect(page.getByTestId("branch-picker")).toHaveValue(data.branchId);
  await page.getByTestId(`menu-item-${data.menuItem.id}`).click();
  await page.getByTestId(`menu-item-${data.menuItem.id}`).click();
  await expect(page.getByTestId("cart-total")).toHaveText("BWP 110.00");

  await page.getByRole("button", { name: "Create order" }).click();
  const orderNumber = await page.getByTestId("last-order-number").innerText();
  await page.getByRole("button", { name: "Cash paid" }).click();
  await expect(page.getByText(`${orderNumber} paid and queued`)).toBeVisible();

  const ordersResponse = await api.get(
    `/api/v1/restaurants/${data.restaurantId}/branches/${data.branchId}/orders/`,
    { headers, params: { status: "QUEUED" } },
  );
  expect(ordersResponse.ok(), await ordersResponse.text()).toBeTruthy();
  const queuedOrders = (await ordersResponse.json()) as Order[];
  const order = queuedOrders.find((candidate) => candidate.display_number === orderNumber);
  expect(order).toBeTruthy();
  const baselineReport = await getDailySalesReport(api, headers, data, order!.business_date);

  await page.getByRole("button", { name: "Kitchen" }).click();
  const kitchenOrder = page.getByTestId(`kitchen-order-${order!.id}`);
  await expect(kitchenOrder).toBeVisible();
  await kitchenOrder.getByRole("button", { name: "Start" }).click();
  await expect(page.getByTestId(`kitchen-order-${order!.id}`)).toContainText("PREPARING");
  await page.getByTestId(`kitchen-order-${order!.id}`).getByRole("button", { name: "Ready" }).click();

  await page.getByRole("button", { name: "Cashier" }).click();
  const pickupOrder = page.getByTestId(`pickup-order-${order!.id}`);
  await expect(pickupOrder).toBeVisible();
  await pickupOrder.getByRole("button", { name: "Collected", exact: true }).click();
  await expect(pickupOrder).toBeHidden();

  await page.getByRole("button", { name: "Kitchen" }).click();
  await expect(page.getByTestId(`collected-order-${order!.id}`)).toBeVisible();

  const finalReport = await getDailySalesReport(api, headers, data, order!.business_date);
  const expectedCollectedOrders = baselineReport.collected_orders + 1;
  const expectedRevenue = (Number(baselineReport.revenue) + 110).toFixed(2);
  expect(finalReport.collected_orders).toBe(expectedCollectedOrders);
  expect(finalReport.revenue).toBe(expectedRevenue);

  await page.getByRole("button", { name: "Dashboard" }).click();
  await expect(page.getByText("Revenue counts paid collected orders only.")).toBeVisible();
  await expect(page.getByTestId("stat-collected")).toContainText(String(expectedCollectedOrders));
  await expect(page.getByTestId("stat-revenue")).toContainText(`BWP ${expectedRevenue}`);

  await page.getByRole("button", { name: "Audit" }).click();
  await expect(page.getByTestId("audit-log-CASH_PAYMENT_CONFIRMED").first()).toBeVisible();
  await expect(page.getByTestId("audit-log-ORDER_COLLECTED").first()).toBeVisible();

  await api.dispose();
});

test("invited staff can set a password and sign in", async ({ page }) => {
  const { api, data } = await apiSetup();
  const headers = { Authorization: `Bearer ${data.token}` };
  const email = `invited-e2e-${Date.now()}@example.com`;
  const password = "newstaffpassword";

  const inviteResponse = await api.post("/api/v1/auth/users/invite", {
    headers,
    data: {
      email,
      first_name: "Invited",
      last_name: "Cashier",
      role_name: "CASHIER",
      restaurant_id: data.restaurantId,
      branch_ids: [data.branchId],
    },
  });
  expect(inviteResponse.ok(), await inviteResponse.text()).toBeTruthy();
  const invite = (await inviteResponse.json()) as StaffInviteResponse;

  await page.addInitScript(() => window.localStorage.clear());
  await page.goto(invite.invite.setup_url_path);
  await expect(page.getByText(email)).toBeVisible();
  await page.getByLabel("New password").fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Set password" }).click();
  await expect(page.getByText("Password updated")).toBeVisible();

  await page.getByRole("link", { name: "Sign in" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("workspace-title")).toContainText("Chicken Spot");
  await expect(page.getByRole("button", { name: "Cashier" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Staff" })).toBeHidden();

  await api.dispose();
});

test("customer can place a QR order and open the status page", async ({ page }) => {
  const { api, data } = await apiSetup();

  await page.addInitScript(({ restaurantId, branchId }) => {
    window.localStorage.clear();
    window.localStorage.setItem("cognivex.publicRestaurantId", restaurantId);
    window.localStorage.setItem("cognivex.publicBranchId", branchId);
  }, data);
  await page.goto("/chicken-spot/");

  await expect(page.getByRole("heading", { name: /Chicken Spot/i })).toBeVisible();
  await page.getByTestId(`customer-add-${data.menuItem.id}`).click();
  await page.getByTestId(`customer-add-${data.menuItem.id}`).click();
  await expect(page.getByTestId("customer-cart-total")).toHaveText("BWP 110.00");

  await page.getByLabel("Name").fill("QR Test Customer");
  await page.getByLabel("Phone number").fill("+26771112222");
  await page.getByRole("button", { name: "Create order and payment reference" }).click();

  await expect(page.getByText(/created\. Use payment reference/i)).toBeVisible();
  await expect(page.getByTestId("customer-payment-instructions")).toBeVisible();
  const customerPaymentReference = (
    await page.getByTestId("customer-payment-reference").innerText()
  ).trim();
  expect(customerPaymentReference).toMatch(/^[A-Z0-9]+-[A-Z0-9]+-\d{6}-\d{3}$/);
  const statusLink = page.getByTestId("customer-status-link");
  await expect(statusLink).toBeVisible();
  await expect(statusLink).toHaveAttribute("href", /\/customer\/restaurants\//);
  const statusHref = await statusLink.getAttribute("href");
  const orderId = statusHref?.match(/\/orders\/([^/]+)\/status/)?.[1];
  if (!orderId) {
    throw new Error(`Could not find order id in status link: ${statusHref}`);
  }

  await statusLink.click();
  await expect(page.getByText("Payment is being confirmed")).toBeVisible();

  await page.goto("/");
  await page.getByLabel("Email").fill(OWNER_EMAIL);
  await page.getByLabel("Password").fill(OWNER_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByTestId("branch-picker")).toHaveValue(data.branchId);
  await expect(page.getByTestId(`customer-order-${orderId}`)).toBeVisible();
  await expect(page.getByTestId(`customer-order-${orderId}`)).toContainText("Waiting for payment");
  await expect(page.getByTestId(`customer-order-${orderId}`)).toContainText("QR");

  const customerOrder = page.getByTestId(`customer-order-${orderId}`);
  await customerOrder.getByRole("button", { name: "Confirm transfer" }).click();
  await customerOrder.getByLabel("Payment reference used").fill(customerPaymentReference);
  await customerOrder.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(customerOrder).toContainText("Paid, waiting for kitchen");

  await api.dispose();
});
