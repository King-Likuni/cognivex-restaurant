import { CheckCircle2, ChefHat, Play, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Notice, Panel } from "../components/ui";
import {
  apiRequest,
  realtimeUrl,
  type KitchenBoard,
  type Order,
  type RealtimeEvent,
} from "../services/api";

type Props = {
  context: AppContext;
  token: string;
};

type BoardColumn = {
  title: string;
  orders: Order[];
  action?: (order: Order) => Promise<void>;
  actionLabel?: string;
  icon?: typeof Play;
  testIdPrefix?: string;
};

const EMPTY_BOARD: KitchenBoard = { new: [], preparing: [], ready: [], collected: [] };

export function KitchenView({ context, token }: Props) {
  const [board, setBoard] = useState<KitchenBoard>(EMPTY_BOARD);
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const loadBoard = useCallback(async () => {
    setError(null);
    try {
      const nextBoard = await apiRequest<KitchenBoard>(
        `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/kitchen/board`,
        { token },
      );
      setBoard(nextBoard);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load kitchen board");
    }
  }, [context.restaurant.id, context.branch.id, token]);

  async function startPreparing(order: Order) {
    const updated = await apiRequest<Order>(
      `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/kitchen/orders/${order.id}/start`,
      { method: "POST", token },
    );
    setEvents((current) => [
      {
        type: "ORDER_STATUS_CHANGED",
        restaurant_id: updated.restaurant_id,
        branch_id: updated.branch_id,
        order_id: updated.id,
        display_number: updated.display_number,
        order_status: updated.order_status,
        payment_status: updated.payment_status,
        channel: updated.channel,
        occurred_at: new Date().toISOString(),
      },
      ...current,
    ]);
    await loadBoard();
  }

  async function markReady(order: Order) {
    await apiRequest<Order>(
      `/api/v1/restaurants/${context.restaurant.id}/branches/${context.branch.id}/kitchen/orders/${order.id}/ready`,
      { method: "POST", token },
    );
    await loadBoard();
  }

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);

  useEffect(() => {
    const socket = new WebSocket(
      realtimeUrl(
        `/ws/restaurants/${context.restaurant.id}/branches/${context.branch.id}/kitchen`,
        token,
      ),
    );
    socket.onopen = () => setIsConnected(true);
    socket.onclose = () => setIsConnected(false);
    socket.onerror = () => setIsConnected(false);
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as RealtimeEvent | { type: string };
      if (event.type === "CONNECTED") {
        return;
      }
      setEvents((current) => [event as RealtimeEvent, ...current].slice(0, 8));
      void loadBoard();
    };
    return () => socket.close();
  }, [context.restaurant.id, context.branch.id, loadBoard, token]);

  const columns: BoardColumn[] = [
    { title: "New", orders: board.new, action: startPreparing, actionLabel: "Start", icon: Play },
    {
      title: "Preparing",
      orders: board.preparing,
      action: markReady,
      actionLabel: "Ready",
      icon: CheckCircle2,
    },
    { title: "Ready", orders: board.ready },
    { title: "Collected Today", orders: board.collected, testIdPrefix: "collected-order" },
  ];

  return (
    <div className="view-stack">
      <div className="toolbar-line">
        <span className={isConnected ? "socket-state online" : "socket-state"}>
          <ChefHat size={16} />
          {isConnected ? "Realtime connected" : "Realtime offline"}
        </span>
        <button className="secondary-action" type="button" onClick={loadBoard}>
          <RefreshCw size={17} />
          Refresh board
        </button>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <div className="board-grid">
        {columns.map((column) => (
          <Panel key={column.title} title={`${column.title} (${column.orders.length})`}>
            <div className="order-stack">
              {column.orders.map((order) => {
                const Icon = column.icon;
                return (
                  <article
                    className="order-card"
                    data-testid={`${column.testIdPrefix ?? "kitchen-order"}-${order.id}`}
                    key={order.id}
                  >
                    <span className="status-pill">{order.order_status}</span>
                    <h3>{order.display_number}</h3>
                    <p>{order.payment_reference}</p>
                    <strong>{order.currency} {order.total}</strong>
                    {column.action && Icon ? (
                      <button
                        className="secondary-action"
                        type="button"
                        onClick={() => void column.action?.(order)}
                      >
                        <Icon size={17} />
                        {column.actionLabel}
                      </button>
                    ) : null}
                  </article>
                );
              })}
              {!column.orders.length ? <EmptyState>No orders</EmptyState> : null}
            </div>
          </Panel>
        ))}
      </div>
      <Panel title="Recent Realtime Events">
        <div className="event-list">
          {events.map((event) => (
            <div className="event-row" key={`${event.type}-${event.order_id}-${event.occurred_at}`}>
              <strong>{event.type}</strong>
              <span>{event.display_number}</span>
              <span>{event.order_status}</span>
            </div>
          ))}
          {!events.length ? <EmptyState>Events will appear as orders change</EmptyState> : null}
        </div>
      </Panel>
    </div>
  );
}
