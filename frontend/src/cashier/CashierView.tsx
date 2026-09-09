import {
  Banknote,
  CheckCircle2,
  ChefHat,
  Clock3,
  CreditCard,
  Link2,
  PackageCheck,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel } from "../components/ui";
import {
  apiRequest,
  realtimeUrl,
  type MenuItem,
  type Order,
  type OrderStatusToken,
  type Payment,
} from "../services/api";
import { formatMoney } from "../services/format";

type CartLine = {
  menuItemId: string;
  quantity: number;
};

type Props = {
  context: AppContext;
  token: string;
};

type CustomerStatusLink = {
  orderId: string;
  url: string;
  expiresInSeconds: number;
};

const ACTIVE_CUSTOMER_ORDER_STATUSES = ["PENDING_PAYMENT", "QUEUED", "PREPARING"] as const;
const CUSTOMER_CHANNELS = new Set(["QR", "WHATSAPP"]);

function currentBusinessDate() {
  return new Date().toISOString().slice(0, 10);
}

function orderStatusLabel(order: Order) {
  if (order.payment_status !== "PAID") {
    return "Waiting for payment";
  }
  if (order.order_status === "QUEUED") {
    return "Paid, waiting for kitchen";
  }
  if (order.order_status === "PREPARING") {
    return "In kitchen";
  }
  return order.order_status.replaceAll("_", " ");
}

export function CashierView({ context, token }: Props) {
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [customerOrders, setCustomerOrders] = useState<Order[]>([]);
  const [readyOrders, setReadyOrders] = useState<Order[]>([]);
  const [uncollectedOrders, setUncollectedOrders] = useState<Order[]>([]);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [lastOrder, setLastOrder] = useState<Order | null>(null);
  const [remotePayment, setRemotePayment] = useState<Payment | null>(null);
  const [customerStatusLink, setCustomerStatusLink] = useState<CustomerStatusLink | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const loadMenu = useCallback(async () => {
    setError(null);
    try {
      const items = await apiRequest<MenuItem[]>(
        `/api/v1/restaurants/${context.restaurant.id}/menu/items`,
        { token },
      );
      setMenuItems(items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load menu");
    }
  }, [context.restaurant.id, token]);

  useEffect(() => {
    void loadMenu();
  }, [loadMenu]);

  const loadOrderDesk = useCallback(async () => {
    setError(null);
    try {
      const orderPath = `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/orders/`;
      const orderParams = { business_date: currentBusinessDate() };
      const [pendingPayment, queued, preparing, ready, uncollected] = await Promise.all([
        ...ACTIVE_CUSTOMER_ORDER_STATUSES.map((status) =>
          apiRequest<Order[]>(orderPath, {
            token,
            params: { ...orderParams, status },
          }),
        ),
        apiRequest<Order[]>(orderPath, {
          token,
          params: { ...orderParams, status: "READY" },
        }),
        apiRequest<Order[]>(orderPath, {
          token,
          params: { ...orderParams, status: "UNCOLLECTED" },
        }),
      ]);
      setCustomerOrders(
        [...pendingPayment, ...queued, ...preparing].filter((order) =>
          CUSTOMER_CHANNELS.has(order.channel),
        ),
      );
      setReadyOrders(ready);
      setUncollectedOrders(uncollected);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load order desk");
    }
  }, [context.restaurant.id, context.branch.id, token]);

  useEffect(() => {
    void loadOrderDesk();
  }, [loadOrderDesk]);

  useEffect(() => {
    const socket = new WebSocket(
      realtimeUrl(
        `/ws/restaurants/${context.restaurant.id}/branches/${context.branch.id}/cashier`,
        token,
      ),
    );
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type: string };
      if (event.type !== "CONNECTED") {
        void loadOrderDesk();
      }
    };
    return () => socket.close();
  }, [context.restaurant.id, context.branch.id, loadOrderDesk, token]);

  const cartTotal = useMemo(() => {
    return cart.reduce((total, line) => {
      const item = menuItems.find((candidate) => candidate.id === line.menuItemId);
      return total + Number(item?.price ?? 0) * line.quantity;
    }, 0);
  }, [cart, menuItems]);

  function addToCart(menuItemId: string) {
    setCart((current) => {
      const existing = current.find((line) => line.menuItemId === menuItemId);
      if (existing) {
        return current.map((line) =>
          line.menuItemId === menuItemId ? { ...line, quantity: line.quantity + 1 } : line,
        );
      }
      return [...current, { menuItemId, quantity: 1 }];
    });
  }

  function updateQuantity(menuItemId: string, quantity: number) {
    setCart((current) =>
      current
        .map((line) => (line.menuItemId === menuItemId ? { ...line, quantity } : line))
        .filter((line) => line.quantity > 0),
    );
  }

  async function createOrder() {
    if (!cart.length) {
      setError("Add at least one item");
      return;
    }
    setIsBusy(true);
    setError(null);
    setNotice(null);
    try {
      const order = await apiRequest<Order>(
        `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/orders/cashier`,
        {
          method: "POST",
          token,
          body: {
            customer_id: null,
            items: cart.map((line) => ({
              menu_item_id: line.menuItemId,
              quantity: line.quantity,
            })),
            payment_method: "CASH",
          },
        },
      );
      setLastOrder(order);
      setRemotePayment(null);
      void createCustomerStatusLink(order);
      setCart([]);
      setNotice(`Created ${order.display_number}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create order");
    } finally {
      setIsBusy(false);
    }
  }

  async function createCustomerStatusLink(order: Order) {
    try {
      const statusToken = await apiRequest<OrderStatusToken>(
        `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/orders/${order.id}/status-token`,
        { token },
      );
      setCustomerStatusLink({
        orderId: order.id,
        expiresInSeconds: statusToken.expires_in_seconds,
        url: `${window.location.origin}/customer/restaurants/${context.restaurant.id}/branches/${context.branch.id}/orders/${order.id}/status?token=${encodeURIComponent(statusToken.access_token)}`,
      });
    } catch {
      setCustomerStatusLink(null);
    }
  }

  async function confirmCash() {
    if (!lastOrder) {
      return;
    }
    setIsBusy(true);
    setError(null);
    try {
      await apiRequest<Payment>(
        `/api/v1/restaurants/${context.restaurant.id}/orders/${lastOrder.id}/payments/cash/confirm`,
        {
          method: "POST",
          token,
          body: { amount_received: lastOrder.total },
        },
      );
      setLastOrder({ ...lastOrder, payment_status: "PAID", order_status: "QUEUED" });
      setNotice(`${lastOrder.display_number} paid and queued`);
      await loadOrderDesk();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not confirm cash");
    } finally {
      setIsBusy(false);
    }
  }

  async function initiateRemotePayment(provider: "ORANGE_MONEY" | "FNB") {
    if (!lastOrder) {
      return;
    }
    setIsBusy(true);
    setError(null);
    try {
      const payment = await apiRequest<Payment>(
        `/api/v1/restaurants/${context.restaurant.id}/orders/${lastOrder.id}/payments`,
        {
          method: "POST",
          token,
          body: { provider, customer_phone_number: "+26770000000" },
        },
      );
      setRemotePayment(payment);
      setNotice(`${provider} payment initiated`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not initiate payment");
    } finally {
      setIsBusy(false);
    }
  }

  async function updatePickup(order: Order, action: "collect" | "uncollected") {
    setIsBusy(true);
    setError(null);
    try {
      const updatedOrder = await apiRequest<Order>(
        `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/orders/${order.id}/${action}`,
        { method: "POST", token },
      );
      setNotice(`${updatedOrder.display_number} marked ${updatedOrder.order_status.toLowerCase()}`);
      if (lastOrder?.id === updatedOrder.id) {
        setLastOrder(updatedOrder);
      }
      await loadOrderDesk();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Could not mark order ${action}`);
    } finally {
      setIsBusy(false);
    }
  }

  async function copyCustomerLink() {
    if (!customerStatusLink) {
      return;
    }
    try {
      await navigator.clipboard.writeText(customerStatusLink.url);
      setNotice("Customer status link copied");
    } catch {
      setError("Could not copy the link automatically");
    }
  }

  return (
    <div className="view-stack">
      <div className="view-grid two-columns">
        <Panel
          title="Menu"
          action={
            <button className="icon-button" type="button" onClick={loadMenu} title="Refresh menu">
              <RefreshCw size={17} />
            </button>
          }
        >
          <div className="item-grid">
            {menuItems.map((item) => (
              <button
                key={item.id}
                className="menu-tile"
                data-testid={`menu-item-${item.id}`}
                type="button"
                onClick={() => addToCart(item.id)}
                disabled={!item.is_available}
              >
                <strong>{item.name}</strong>
                <span>{formatMoney(item.price)}</span>
              </button>
            ))}
            {!menuItems.length ? <EmptyState>No available menu items yet</EmptyState> : null}
          </div>
        </Panel>

        <Panel title="Current Order">
          {error ? <Notice tone="error">{error}</Notice> : null}
          {notice ? <Notice tone="success">{notice}</Notice> : null}
          <div className="cart-lines">
            {cart.map((line) => {
              const item = menuItems.find((candidate) => candidate.id === line.menuItemId);
              return (
                <div className="cart-line" key={line.menuItemId}>
                  <div>
                    <strong>{item?.name}</strong>
                    <span>{formatMoney(item?.price ?? 0)}</span>
                  </div>
                  <Field label="Qty">
                    <input
                      type="number"
                      min="0"
                      value={line.quantity}
                      onChange={(event) =>
                        updateQuantity(line.menuItemId, Number(event.target.value))
                      }
                    />
                  </Field>
                  <button
                    className="icon-button danger"
                    type="button"
                    onClick={() => updateQuantity(line.menuItemId, 0)}
                    title="Remove"
                  >
                    <Trash2 size={17} />
                  </button>
                </div>
              );
            })}
            {!cart.length ? <EmptyState>Select menu items to build an order</EmptyState> : null}
          </div>
          <div className="total-row">
            <span>Total</span>
            <strong data-testid="cart-total">{formatMoney(cartTotal)}</strong>
          </div>
          <button className="primary-action" type="button" onClick={createOrder} disabled={isBusy}>
            <Plus size={18} />
            Create order
          </button>

          {lastOrder ? (
            <div className="result-card" data-testid="last-order-card">
              <span className="status-pill">{lastOrder.order_status}</span>
              <h3 data-testid="last-order-number">{lastOrder.display_number}</h3>
              <p>{lastOrder.payment_reference}</p>
              <div className="button-row">
                <button
                  className="secondary-action"
                  type="button"
                  onClick={confirmCash}
                  disabled={isBusy || lastOrder.payment_status === "PAID"}
                >
                  <Banknote size={17} />
                  Cash paid
                </button>
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() => initiateRemotePayment("ORANGE_MONEY")}
                  disabled={isBusy || lastOrder.payment_status === "PAID"}
                >
                  <CreditCard size={17} />
                  Orange Money
                </button>
              </div>
              {customerStatusLink?.orderId === lastOrder.id ? (
                <div className="customer-link-row">
                  <a href={customerStatusLink.url} target="_blank" rel="noreferrer">
                    Customer status
                  </a>
                  <button className="icon-button" type="button" onClick={copyCustomerLink}>
                    <Link2 size={17} />
                  </button>
                </div>
              ) : null}
              {remotePayment ? (
                <Notice>Remote payment reference: {remotePayment.reference}</Notice>
              ) : null}
            </div>
          ) : null}
        </Panel>
      </div>

      <Panel
        title={`Customer Orders (${customerOrders.length})`}
        action={
          <button
            className="icon-button"
            type="button"
            onClick={loadOrderDesk}
            title="Refresh customer orders"
          >
            <RefreshCw size={17} />
          </button>
        }
      >
        <div className="order-grid">
          {customerOrders.map((order) => (
            <article
              className="order-card"
              data-testid={`customer-order-${order.id}`}
              key={order.id}
            >
              <div className="order-card-header">
                <span className="status-pill">
                  {order.payment_status === "PAID" ? (
                    <ChefHat size={14} />
                  ) : (
                    <Clock3 size={14} />
                  )}
                  {orderStatusLabel(order)}
                </span>
                <span className="channel-pill">{order.channel}</span>
              </div>
              <h3>{order.display_number}</h3>
              <p>{order.payment_reference}</p>
              <div className="order-meta">
                <span>{order.payment_status}</span>
                <strong>{formatMoney(order.total, order.currency)}</strong>
              </div>
            </article>
          ))}
          {!customerOrders.length ? (
            <EmptyState>No active QR or WhatsApp orders right now</EmptyState>
          ) : null}
        </div>
      </Panel>

      <Panel
        title={`Pickup Desk (${readyOrders.length})`}
        action={
          <button
            className="icon-button"
            type="button"
            onClick={loadOrderDesk}
            title="Refresh pickup desk"
          >
            <RefreshCw size={17} />
          </button>
        }
      >
        <div className="pickup-grid">
          <div className="order-stack">
            {readyOrders.map((order) => (
              <article className="order-card" data-testid={`pickup-order-${order.id}`} key={order.id}>
                <span className="status-pill">
                  <PackageCheck size={14} />
                  Ready
                </span>
                <h3>{order.display_number}</h3>
                <p>{order.payment_reference}</p>
                <strong>{formatMoney(order.total, order.currency)}</strong>
                <div className="button-row">
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => void updatePickup(order, "collect")}
                    disabled={isBusy}
                  >
                    <CheckCircle2 size={17} />
                    Collected
                  </button>
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => void updatePickup(order, "uncollected")}
                    disabled={isBusy}
                  >
                    <XCircle size={17} />
                    Not collected
                  </button>
                </div>
              </article>
            ))}
            {!readyOrders.length ? <EmptyState>No ready orders waiting for pickup</EmptyState> : null}
          </div>
          <div className="order-stack">
            <h3>Uncollected</h3>
            {uncollectedOrders.map((order) => (
              <article
                className="order-card"
                data-testid={`uncollected-order-${order.id}`}
                key={order.id}
              >
                <span className="status-pill">{order.order_status}</span>
                <h3>{order.display_number}</h3>
                <p>{order.payment_reference}</p>
              </article>
            ))}
            {!uncollectedOrders.length ? <EmptyState>No missed pickups today</EmptyState> : null}
          </div>
        </div>
      </Panel>
    </div>
  );
}
