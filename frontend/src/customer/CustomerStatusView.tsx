import { CheckCircle2, ChefHat, Clock3, PackageCheck, ReceiptText } from "lucide-react";
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
    /^\/customer\/restaurants\/([^/]+)\/branches\/([^/]+)\/orders\/([^/]+)\/status$/,
  );
  const token = new URLSearchParams(window.location.search).get("token");
  return {
    restaurantId: match?.[1] ?? null,
    branchId: match?.[2] ?? null,
    orderId: match?.[3] ?? null,
    token,
  };
}

function statusCopy(status: string) {
  if (status === "PENDING_PAYMENT") {
    return "Payment is being confirmed";
  }
  if (status === "QUEUED") {
    return "Your order is in the kitchen queue";
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
      setStatus({
        order_id: orderEvent.order_id,
        display_number: orderEvent.display_number,
        payment_status: orderEvent.payment_status,
        order_status: orderEvent.order_status,
        updated_at: orderEvent.occurred_at,
      });
    };
    return () => socket.close();
  }, [route.orderId, route.token]);

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
            <p>{statusCopy(status.order_status)}</p>
            <div className="status-steps" aria-label="Order progress">
              {[
                { key: "QUEUED", label: "Queued", icon: Clock3 },
                { key: "PREPARING", label: "Preparing", icon: ChefHat },
                { key: "READY", label: "Ready", icon: PackageCheck },
                { key: "COLLECTED", label: "Collected", icon: CheckCircle2 },
              ].map((step) => {
                const Icon = step.icon;
                const active = step.key === status.order_status;
                return (
                  <span className={active ? "status-step active" : "status-step"} key={step.key}>
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
              <span>{statusCopy(event.order_status)}</span>
            </div>
          ))}
          {!events.length ? <EmptyState>Updates will appear here automatically</EmptyState> : null}
        </div>
      </Panel>
    </main>
  );
}
