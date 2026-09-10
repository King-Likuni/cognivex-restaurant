import { Copy, CreditCard, Minus, Plus, ReceiptText, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState, Field, Notice, Panel } from "../components/ui";
import {
  apiRequest,
  type PublicCustomerOrderResponse,
  type PublicMenu,
  type PublicMenuItem,
} from "../services/api";
import { formatMoney } from "../services/format";

type CartLine = {
  menuItemId: string;
  quantity: number;
};

type RemotePaymentProvider = "ORANGE_MONEY" | "PAY2CELL";

const CHICKEN_SPOT_MAIN_MALL = {
  restaurantId:
    import.meta.env.VITE_PUBLIC_RESTAURANT_ID ?? "db74a923-21c7-442a-8937-71bde3d9aa9c",
  branchId: import.meta.env.VITE_PUBLIC_BRANCH_ID ?? "2eebe040-5ec7-48d4-b89a-db407aefb864",
};

function readOrderRoute() {
  const normalizedPath = window.location.pathname.replace(/\/$/, "");
  if (normalizedPath === "/chicken-spot") {
    return {
      restaurantId:
        localStorage.getItem("cognivex.publicRestaurantId") ??
        CHICKEN_SPOT_MAIN_MALL.restaurantId,
      branchId:
        localStorage.getItem("cognivex.publicBranchId") ?? CHICKEN_SPOT_MAIN_MALL.branchId,
      channel: "QR",
    };
  }

  const match = window.location.pathname.match(
    /^\/order\/restaurants\/([^/]+)\/branches\/([^/]+)\/?$/,
  );
  const channel = new URLSearchParams(window.location.search).get("channel");
  return {
    restaurantId: match?.[1] ?? null,
    branchId: match?.[2] ?? null,
    channel: channel === "WHATSAPP" ? "WHATSAPP" : "QR",
  };
}

function formatProvider(provider: string | null) {
  if (provider === "PAY2CELL") {
    return "Pay2Cell";
  }
  if (provider === "ORANGE_MONEY") {
    return "Orange Money";
  }
  return provider ?? "Transfer";
}

export function CustomerOrderView() {
  const route = useMemo(() => readOrderRoute(), []);
  const [menu, setMenu] = useState<PublicMenu | null>(null);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [customerName, setCustomerName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [paymentProvider, setPaymentProvider] =
    useState<RemotePaymentProvider>("ORANGE_MONEY");
  const [orderResult, setOrderResult] = useState<PublicCustomerOrderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copyNotice, setCopyNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const menuItems = useMemo(() => {
    return menu?.categories.flatMap((category) => category.items) ?? [];
  }, [menu]);

  const cartTotal = useMemo(() => {
    return cart.reduce((total, line) => {
      const item = menuItems.find((candidate) => candidate.id === line.menuItemId);
      return total + Number(item?.price ?? 0) * line.quantity;
    }, 0);
  }, [cart, menuItems]);

  const loadMenu = useCallback(async () => {
    if (!route.restaurantId || !route.branchId) {
      setError("Customer order link is missing required details");
      return;
    }
    setError(null);
    try {
      const nextMenu = await apiRequest<PublicMenu>(
        `/api/v1/public/restaurants/${route.restaurantId}/branches/${route.branchId}/menu`,
      );
      setMenu(nextMenu);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load menu");
    }
  }, [route.restaurantId, route.branchId]);

  useEffect(() => {
    void loadMenu();
  }, [loadMenu]);

  function updateQuantity(menuItemId: string, quantity: number) {
    setCart((current) => {
      const nextQuantity = Math.max(0, quantity);
      const existing = current.find((line) => line.menuItemId === menuItemId);
      if (!existing && nextQuantity > 0) {
        return [...current, { menuItemId, quantity: nextQuantity }];
      }
      return current
        .map((line) =>
          line.menuItemId === menuItemId ? { ...line, quantity: nextQuantity } : line,
        )
        .filter((line) => line.quantity > 0);
    });
  }

  function quantityFor(item: PublicMenuItem) {
    return cart.find((line) => line.menuItemId === item.id)?.quantity ?? 0;
  }

  async function submitOrder(event: React.FormEvent) {
    event.preventDefault();
    if (!route.restaurantId || !route.branchId) {
      setError("Customer order link is missing required details");
      return;
    }
    if (!cart.length) {
      setError("Select at least one item");
      return;
    }
    if (!phoneNumber.trim()) {
      setError("Enter a phone number for payment updates");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const result = await apiRequest<PublicCustomerOrderResponse>(
        `/api/v1/public/restaurants/${route.restaurantId}/branches/${route.branchId}/orders`,
        {
          method: "POST",
          body: {
            customer_name: customerName.trim() || null,
            customer_phone_number: phoneNumber.trim(),
            channel: route.channel,
            payment_provider: paymentProvider,
            items: cart.map((line) => ({
              menu_item_id: line.menuItemId,
              quantity: line.quantity,
            })),
          },
        },
      );
      setOrderResult(result);
      setCopyNotice(null);
      setCart([]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not place order");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function copyPaymentReference() {
    if (!orderResult) {
      return;
    }
    try {
      await navigator.clipboard.writeText(orderResult.payment.reference);
      setCopyNotice("Payment reference copied");
    } catch {
      setCopyNotice("Copy failed. Long-press or select the reference instead.");
    }
  }

  return (
    <main className="customer-order-page">
      <Panel
        title={menu ? `${menu.restaurant_name} / ${menu.branch_name}` : "Customer Order"}
        action={
          <button className="icon-button" type="button" onClick={loadMenu} title="Refresh menu">
            <RefreshCw size={17} />
          </button>
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {orderResult ? (
          <Notice tone="success">
            {orderResult.order.display_number} created. Use payment reference{" "}
            <strong>{orderResult.payment.reference}</strong> when you send the transfer.
          </Notice>
        ) : null}
        <form className="customer-order-grid" onSubmit={submitOrder}>
          <div className="customer-menu-stack">
            {menu?.categories.map((category) => (
              <section className="customer-menu-section" key={category.id}>
                <h2>{category.name}</h2>
                <div className="customer-menu-list">
                  {category.items.map((item) => {
                    const quantity = quantityFor(item);
                    return (
                      <div className="customer-menu-row" key={item.id}>
                        <div>
                          <strong>{item.name}</strong>
                          {item.description ? <span>{item.description}</span> : null}
                          <small>{formatMoney(item.price, menu.currency)}</small>
                        </div>
                        <div className="quantity-stepper">
                          <button
                            type="button"
                            className="icon-button"
                            onClick={() => updateQuantity(item.id, quantity - 1)}
                            disabled={quantity === 0}
                            title="Decrease quantity"
                          >
                            <Minus size={16} />
                          </button>
                          <strong data-testid={`customer-item-quantity-${item.id}`}>
                            {quantity}
                          </strong>
                          <button
                            type="button"
                            className="icon-button"
                            data-testid={`customer-add-${item.id}`}
                            onClick={() => updateQuantity(item.id, quantity + 1)}
                            title="Increase quantity"
                          >
                            <Plus size={16} />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}
            {menu && !menuItems.length ? <EmptyState>No available menu items yet</EmptyState> : null}
            {!menu ? <EmptyState>Loading menu</EmptyState> : null}
          </div>

          <div className="customer-checkout">
            {orderResult ? (
              <div className="payment-instructions" data-testid="customer-payment-instructions">
                <span className="status-pill">Payment reference created</span>
                <div className="payment-reference-block">
                  <small>Use this exact reference</small>
                  <strong data-testid="customer-payment-reference">
                    {orderResult.payment.reference}
                  </strong>
                </div>
                <div className="payment-detail-row">
                  <span>Order</span>
                  <strong>{orderResult.order.display_number}</strong>
                </div>
                <div className="payment-detail-row">
                  <span>Amount</span>
                  <strong>{formatMoney(orderResult.order.total, orderResult.order.currency)}</strong>
                </div>
                <div className="payment-detail-row">
                  <span>Method</span>
                  <strong>{formatProvider(orderResult.payment.provider)}</strong>
                </div>
                <button className="secondary-action" type="button" onClick={copyPaymentReference}>
                  <Copy size={17} />
                  Copy reference
                </button>
                {copyNotice ? <Notice tone="success">{copyNotice}</Notice> : null}
              </div>
            ) : null}
            <Field label="Name">
              <input
                value={customerName}
                onChange={(event) => setCustomerName(event.target.value)}
                placeholder="Optional"
              />
            </Field>
            <Field label="Phone number">
              <input
                value={phoneNumber}
                onChange={(event) => setPhoneNumber(event.target.value)}
                placeholder="+267..."
              />
            </Field>
            <Field label="Payment method">
              <select
                value={paymentProvider}
                onChange={(event) =>
                  setPaymentProvider(event.target.value as RemotePaymentProvider)
                }
              >
                <option value="ORANGE_MONEY">Orange Money</option>
                <option value="PAY2CELL">Pay2Cell</option>
              </select>
            </Field>
            <div className="total-row">
              <span>Total</span>
              <strong data-testid="customer-cart-total">
                {formatMoney(cartTotal, menu?.currency)}
              </strong>
            </div>
            <button
              className="primary-action"
              type="submit"
              disabled={isSubmitting || !cart.length}
            >
              <CreditCard size={18} />
              {isSubmitting ? "Creating reference" : "Create order and payment reference"}
            </button>
            {orderResult ? (
              <a
                className="secondary-action"
                href={orderResult.status_url_path}
                data-testid="customer-status-link"
              >
                <ReceiptText size={17} />
                Track order
              </a>
            ) : null}
          </div>
        </form>
      </Panel>
    </main>
  );
}
