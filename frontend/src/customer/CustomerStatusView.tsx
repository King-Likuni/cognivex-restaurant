import {
  CheckCircle2,
  ChefHat,
  Clock3,
  CreditCard,
  PackageCheck,
  ReceiptText,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState, Notice, Panel } from "../components/ui";
import {
  apiRequest,
  realtimeUrl,
  type CustomerOrderStatus,
  type RealtimeEvent,
} from "../services/api";

function readCustomerRoute() {
  const match = window.location.pathname.match(
    /^\/customer\/restaurants\/([^/]+)\/branches\/([^/]+)\/orders\/([^/]+)\/status\/?$/,
  );
  const token = new URLSearchParams(window.location.search).get("token");
  return {
    restaurantId: match?.[1] ?? null,
    branchId: match?.[2] ?? null,
    orderId: match?.[3] ?? null,
    token,
  };
}

function fallbackStatusCopy(status: string) {
  if (status === "PENDING_PAYMENT") {
    return "Your order was received and will continue through the kitchen.";
  }
  if (status === "QUEUED") {
    return "Your order is moving through the kitchen. Keep your payment proof ready for collection.";
  }
  if (status === "PREPARING") {
    return "The kitchen is preparing your order";
  }
  if (status === "READY") {
    return "Your order is ready for pickup";
  }
  if (status === "COLLECTED") {
    return "Your order has been collected";
  }
  if (status === "UNCOLLECTED") {
    return "Your order was marked uncollected";
  }
  return "Waiting for the latest order update";
}

function stageIndex(orderStatus: string) {
  const order = ["QUEUED", "PREPARING", "READY", "COLLECTED"];
  const index = order.indexOf(orderStatus);
  return index === -1 ? 0 : index;
}

export function CustomerStatusView() {
  const route = useMemo(() => readCustomerRoute(), []);
  const [status, setStatus] = useState<CustomerOrderStatus | null>(null);
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const loadStatus = useCallback(async () => {
    if (!route.restaurantId || !route.branchId || !route.orderId || !route.token) {
      setError("Order status link is missing required details");
      return;
    }
    setError(null);
    try {
      const nextStatus = await apiRequest<CustomerOrderStatus>(
        `/api/v1/restaurants/${route.restaurantId}/branches/${route.branchId}/orders/${route.orderId}/customer-status`,
        { params: { token: route.token } },
      );
      setStatus(nextStatus);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load order status");
    }
  }, [route.restaurantId, route.branchId, route.orderId, route.token]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (!route.orderId || !route.token) {
      return;
    }
    const socket = new WebSocket(realtimeUrl(`/ws/orders/${route.orderId}/status`, route.token));
    socket.onopen = () => setIsConnected(true);
    socket.onclose = () => setIsConnected(false);
    socket.onerror = () => setIsConnected(false);
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as RealtimeEvent | { type: string };
      if (event.type === "CONNECTED") {
        return;
      }
      const orderEvent = event as RealtimeEvent;
      setEvents((current) => [orderEvent, ...current].slice(0, 5));
      void loadStatus();
    };
    return () => socket.close();
  }, [loadStatus, route.orderId, route.token]);

  return (
    <main className="customer-status-page">
      <Panel title="Order Status">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {status ? (
          <div className="customer-status-card">
            <span className={isConnected ? "socket-state online" : "socket-state"}>
              <Clock3 size={16} />
              {isConnected ? "Live updates on" : "Live updates offline"}
            </span>
            <ReceiptText size={40} />
            <h1>{status.display_number}</h1>
            <span className="customer-stage-label">{status.stage_label}</span>
            <p>{status.message}</p>
            <div className="customer-reference-panel">
              <CreditCard size={18} />
              <div>
                <span>Payment reference</span>
                <strong>{status.payment_reference}</strong>
              </div>
            </div>
            {status.payment_reference_required ? (
              <Notice tone="info">
                {status.collection_instruction ??
                  "Show your proof of payment with this reference at the counter."}
              </Notice>
            ) : null}
            <div className="status-steps" aria-label="Order progress">
              {[
                { key: "QUEUED", label: "Queued", icon: Clock3 },
                { key: "PREPARING", label: "Preparing", icon: ChefHat },
                { key: "READY", label: "Ready", icon: PackageCheck },
                { key: "COLLECTED", label: "Collected", icon: CheckCircle2 },
              ].map((step) => {
                const Icon = step.icon;
                const active = step.key === status.order_status;
                const completed = stageIndex(step.key) < stageIndex(status.order_status);
                return (
                  <span
                    className={[
                      "status-step",
                      active ? "active" : "",
                      completed ? "complete" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    key={step.key}
                  >
                    <Icon size={16} />
                    {step.label}
                  </span>
                );
              })}
            </div>
          </div>
        ) : (
          <EmptyState>Loading order status</EmptyState>
        )}
      </Panel>
      <Panel title="Recent Updates">
        <div className="event-list">
          {events.map((event) => (
            <div className="event-row" key={`${event.type}-${event.occurred_at}`}>
              <strong>{event.display_number}</strong>
              <span>{fallbackStatusCopy(event.order_status)}</span>
            </div>
          ))}
          {!events.length ? <EmptyState>Updates will appear here automatically</EmptyState> : null}
        </div>
      </Panel>
    </main>
  );
}
