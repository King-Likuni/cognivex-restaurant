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

type RemotePaymentProvider = "ORANGE_MONEY" | "PAY2CELL";
type CashierPaymentMethod = "CASH" | RemotePaymentProvider;

type MobileTransferConfirmation = {
  orderId: string;
  amountReceived: string;
  paymentReferenceUsed: string;
};

const CASHIER_PAYMENT_METHODS: {
  value: CashierPaymentMethod;
  label: string;
  icon: typeof Banknote;
}[] = [
  { value: "CASH", label: "Cash", icon: Banknote },
  { value: "ORANGE_MONEY", label: "Orange Money", icon: CreditCard },
  { value: "PAY2CELL", label: "Pay2Cell", icon: CreditCard },
];

const CLOSED_ORDER_STATUSES = new Set([
  "COLLECTED",
  "UNCOLLECTED",
  "CANCELLED",
  "PAYMENT_EXPIRED",
]);

function orderStatusLabel(order: Order) {
  if (
    order.order_status === "READY" &&
    order.payment_status === "PAID" &&
    isMobileTransferProvider(order.payment_provider) &&
    !order.mobile_transfer_proof_confirmed
  ) {
    return "Ready, proof required";
  }
  if (order.payment_status !== "PAID") {
    if (order.order_status === "READY") {
      return "Ready, awaiting payment";
    }
    if (order.order_status === "PREPARING") {
      return "Preparing, payment pending";
    }
    if (order.order_status === "QUEUED") {
      return "Queued, payment pending";
    }
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

function isMobileTransferProvider(provider: string | null) {
  return provider === "ORANGE_MONEY" || provider === "PAY2CELL";
}

function cashierErrorMessage(caught: unknown, fallback: string) {
  const message = caught instanceof Error ? caught.message : fallback;
  if (message.toLowerCase() === "not found") {
    return `${fallback}. Refresh the page, confirm the branch is Main Mall, and try again.`;
  }
  return message;
}

function formatProvider(provider: string | null) {
  if (provider === "PAY2CELL") {
    return "Pay2Cell";
  }
  if (provider === "ORANGE_MONEY") {
    return "Orange Money";
  }
  return provider ?? "No transfer method";
}

export function CashierView({ context, token }: Props) {
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [customerOrders, setCustomerOrders] = useState<Order[]>([]);
  const [readyOrders, setReadyOrders] = useState<Order[]>([]);
  const [uncollectedOrders, setUncollectedOrders] = useState<Order[]>([]);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [paymentMethod, setPaymentMethod] = useState<CashierPaymentMethod>("CASH");
  const [lastOrder, setLastOrder] = useState<Order | null>(null);
  const [customerStatusLink, setCustomerStatusLink] = useState<CustomerStatusLink | null>(null);
  const [mobileTransferConfirmation, setMobileTransferConfirmation] =
    useState<MobileTransferConfirmation | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const loadMenu = useCallback(async () => {
    setError(null);
    try {
      const items = await apiRequest<MenuItem[]>(
        `/api/v1/restaurants/${context.restaurant.id}/menu/branches/${context.branch.id}/items`,
        { token, params: { include_unavailable: true } },
      );
      setMenuItems(items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load menu");
    }
  }, [context.branch.id, context.restaurant.id, token]);

  useEffect(() => {
    void loadMenu();
  }, [loadMenu]);

  useEffect(() => {
    setCart([]);
    setPaymentMethod("CASH");
    setLastOrder(null);
    setCustomerStatusLink(null);
    setMobileTransferConfirmation(null);
  }, [context.restaurant.id, context.branch.id]);

  const loadOrderDesk = useCallback(async () => {
    setError(null);
    try {
      const orderPath = `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/orders/`;
      const orders = await apiRequest<Order[]>(orderPath, {
        token,
      });
      setCustomerOrders(
        orders.filter(
          (order) =>
            !CLOSED_ORDER_STATUSES.has(order.order_status) &&
            (order.payment_status !== "PAID" ||
              (order.order_status === "READY" &&
                isMobileTransferProvider(order.payment_provider) &&
                !order.mobile_transfer_proof_confirmed)),
        ),
      );
      setReadyOrders(
        orders.filter(
          (order) =>
            order.order_status === "READY" &&
            order.payment_status === "PAID" &&
            (!isMobileTransferProvider(order.payment_provider) ||
              order.mobile_transfer_proof_confirmed),
        ),
      );
      setUncollectedOrders(orders.filter((order) => order.order_status === "UNCOLLECTED"));
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
    const item = menuItems.find((candidate) => candidate.id === menuItemId);
    if (!item?.is_available_for_sale) {
      setError(item?.stock_message ?? "This menu item is not available for sale");
      return;
    }
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
            payment_method: paymentMethod,
          },
        },
      );
      setLastOrder(order);
      void createCustomerStatusLink(order);
      setCart([]);
      setNotice(
        paymentMethod === "CASH"
          ? `Created ${order.display_number}. Confirm cash before kitchen starts.`
          : `Created ${order.display_number}. ${formatProvider(paymentMethod)} reference is ready for customer payment.`,
      );
      await loadOrderDesk();
    } catch (caught) {
      setError(cashierErrorMessage(caught, "Could not create order"));
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

  async function confirmCashPayment(order: Order) {
    setIsBusy(true);
    setError(null);
    try {
      await apiRequest<Payment>(
        `/api/v1/restaurants/${context.restaurant.id}/orders/${order.id}/payments/cash/confirm`,
        {
          method: "POST",
          token,
          body: { amount_received: order.total },
        },
      );
      if (lastOrder?.id === order.id) {
        setLastOrder({ ...order, payment_status: "PAID", order_status: "QUEUED" });
      }
      setNotice(`${order.display_number} paid and queued`);
      await loadOrderDesk();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not confirm cash");
    } finally {
      setIsBusy(false);
    }
  }

  async function confirmCash() {
    if (!lastOrder) {
      return;
    }
    await confirmCashPayment(lastOrder);
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

  async function cancelOrder(order: Order) {
    setIsBusy(true);
    setError(null);
    try {
      const updatedOrder = await apiRequest<Order>(
        `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/orders/${order.id}/cancel`,
        { method: "POST", token },
      );
      setNotice(`${updatedOrder.display_number} cancelled`);
      if (lastOrder?.id === updatedOrder.id) {
        setLastOrder(updatedOrder);
      }
      await loadOrderDesk();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not cancel order");
    } finally {
      setIsBusy(false);
    }
  }

  function canCancelOrder(order: Order) {
    return order.payment_status !== "PAID" && order.order_status !== "CANCELLED";
  }

  function startMobileTransferConfirmation(order: Order) {
    setMobileTransferConfirmation({
      orderId: order.id,
      amountReceived: order.total,
      paymentReferenceUsed: "",
    });
    setError(null);
    setNotice(null);
  }

  async function confirmMobileTransfer(order: Order) {
    if (!mobileTransferConfirmation || mobileTransferConfirmation.orderId !== order.id) {
      return;
    }
    setIsBusy(true);
    setError(null);
    setNotice(null);
    try {
      await apiRequest<Payment>(
        `/api/v1/restaurants/${context.restaurant.id}/orders/${order.id}/payments/mobile-transfer/confirm`,
        {
          method: "POST",
          token,
          body: {
            amount_received: mobileTransferConfirmation.amountReceived,
            payment_reference_used: mobileTransferConfirmation.paymentReferenceUsed,
          },
        },
      );
      setMobileTransferConfirmation(null);
      setNotice(`${order.display_number} mobile transfer confirmed`);
      await loadOrderDesk();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not confirm mobile transfer");
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
                className={item.is_available_for_sale ? "menu-tile" : "menu-tile unavailable"}
                data-testid={`menu-item-${item.id}`}
                type="button"
                onClick={() => addToCart(item.id)}
                disabled={!item.is_available_for_sale}
              >
                <strong>{item.name}</strong>
                <span>{formatMoney(item.price)}</span>
                {item.stock_message ? <small>{item.stock_message}</small> : null}
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
          <div className="payment-method-grid" role="group" aria-label="Payment method">
            {CASHIER_PAYMENT_METHODS.map((method) => {
              const Icon = method.icon;
              return (
                <button
                  className={
                    method.value === paymentMethod
                      ? "payment-method-option active"
                      : "payment-method-option"
                  }
                  key={method.value}
                  type="button"
                  onClick={() => setPaymentMethod(method.value)}
                  aria-pressed={method.value === paymentMethod}
                >
                  <Icon size={17} />
                  {method.label}
                </button>
              );
            })}
          </div>
          <button className="primary-action" type="button" onClick={createOrder} disabled={isBusy}>
            <Plus size={18} />
            Create order
          </button>

          {lastOrder ? (
            <div className="result-card" data-testid="last-order-card">
              <span className="status-pill">{lastOrder.order_status}</span>
              <h3 data-testid="last-order-number">{lastOrder.display_number}</h3>
              <p>Reference is hidden. Enter it only from the customer proof of payment.</p>
              {canCancelOrder(lastOrder) ? (
                <div className="button-row">
                  {lastOrder.payment_provider ? (
                    <button className="secondary-action" type="button" disabled>
                      <Clock3 size={17} />
                      Waiting for proof
                    </button>
                  ) : (
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={confirmCash}
                      disabled={isBusy}
                    >
                      <Banknote size={17} />
                      Cash paid
                    </button>
                  )}
                  <button
                    className="secondary-action danger-action"
                    type="button"
                    onClick={() => void cancelOrder(lastOrder)}
                    disabled={isBusy}
                  >
                    <XCircle size={17} />
                    Cancel order
                  </button>
                </div>
              ) : null}
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
              {lastOrder.payment_provider ? (
                <Notice>
                  {formatProvider(lastOrder.payment_provider)} proof can be confirmed only after
                  the kitchen marks this order ready.
                </Notice>
              ) : null}
            </div>
          ) : null}
        </Panel>
      </div>

      <Panel
        title={`Payment Queue (${customerOrders.length})`}
        action={
          <button
            className="icon-button"
            type="button"
            onClick={loadOrderDesk}
            title="Refresh payment queue"
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
              {mobileTransferConfirmation?.orderId === order.id ? (
                <form
                  className="transfer-confirmation"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void confirmMobileTransfer(order);
                  }}
                >
                  <Field label="Amount received">
                    <input
                      value={mobileTransferConfirmation.amountReceived}
                      onChange={(event) =>
                        setMobileTransferConfirmation({
                          ...mobileTransferConfirmation,
                          amountReceived: event.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field label="Payment reference used">
                    <input
                      value={mobileTransferConfirmation.paymentReferenceUsed}
                      onChange={(event) =>
                        setMobileTransferConfirmation({
                          ...mobileTransferConfirmation,
                          paymentReferenceUsed: event.target.value,
                        })
                      }
                      placeholder="Enter reference from customer proof"
                      autoComplete="off"
                    />
                  </Field>
                  <div className="button-row">
                    <button className="secondary-action" type="submit" disabled={isBusy}>
                      <CheckCircle2 size={17} />
                      Confirm
                    </button>
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => setMobileTransferConfirmation(null)}
                      disabled={isBusy}
                    >
                      <XCircle size={17} />
                      Cancel
                    </button>
                  </div>
                </form>
              ) : null}
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
              <p>Reference hidden until the customer provides proof of payment.</p>
              <div className="order-meta">
                <span>{formatProvider(order.payment_provider)}</span>
                <span>{order.payment_status}</span>
                <strong>{formatMoney(order.total, order.currency)}</strong>
              </div>
              <div className="button-row">
                {order.payment_provider ? (
                  order.order_status === "READY" ? (
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => startMobileTransferConfirmation(order)}
                      disabled={isBusy}
                    >
                      <Banknote size={17} />
                      Confirm transfer
                    </button>
                  ) : (
                    <button className="secondary-action" type="button" disabled>
                      <Clock3 size={17} />
                      In progress
                    </button>
                  )
                ) : (
                  <>
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => void confirmCashPayment(order)}
                      disabled={isBusy}
                    >
                      <Banknote size={17} />
                      Cash paid
                    </button>
                  </>
                )}
                <button
                  className="secondary-action danger-action"
                  type="button"
                  onClick={() => void cancelOrder(order)}
                  disabled={isBusy}
                >
                  <XCircle size={17} />
                  Cancel order
                </button>
              </div>
            </article>
          ))}
          {!customerOrders.length ? (
            <EmptyState>No orders waiting for payment right now</EmptyState>
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
                <p>Paid and ready for pickup</p>
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
                <p>Not collected during this service window</p>
              </article>
            ))}
            {!uncollectedOrders.length ? <EmptyState>No missed pickups today</EmptyState> : null}
          </div>
        </div>
      </Panel>
    </div>
  );
}
