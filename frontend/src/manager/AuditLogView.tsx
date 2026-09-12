import { ClipboardList, Filter, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel } from "../components/ui";
import { apiRequest, type AuditLog, type Branch, type User } from "../services/api";

type Props = {
  context: AppContext;
  token: string;
  branches: Branch[];
};

const ACTION_OPTIONS = [
  "CASH_PAYMENT_CONFIRMED",
  "MOBILE_TRANSFER_PAYMENT_CONFIRMED",
  "MOBILE_TRANSFER_PROOF_REJECTED",
  "ORDER_COLLECTED",
  "ORDER_CANCELLED",
  "ORDER_MARKED_UNCOLLECTED",
  "ORDER_STOCK_CONSUMED",
  "STOCK_MOVEMENT_CREATED",
  "PAYMENT_INITIATED",
  "BRANCH_CREATED",
  "BRANCH_UPDATED",
  "STAFF_CREATED",
  "STAFF_INVITED",
  "STAFF_UPDATED",
  "PASSWORD_SETUP_LINK_CREATED",
  "PAYMENT_WEBHOOK_PROCESSED",
];

const ENTITY_OPTIONS = ["order", "payment", "stock_movement", "branch", "user"];

function formatAction(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTimestamp(value: string | null) {
  if (!value) {
    return "Unknown time";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function summarizeValues(values: Record<string, unknown> | null) {
  if (!values) {
    return "None";
  }
  return Object.entries(values)
    .slice(0, 6)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.length : String(value)}`)
    .join(" | ");
}

export function AuditLogView({ context, token, branches }: Props) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [userId, setUserId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const actorOptions = useMemo(
    () => users.filter((user) => user.role_name !== "ADMIN"),
    [users],
  );

  const loadUsers = useCallback(async () => {
    try {
      const nextUsers = await apiRequest<User[]>("/api/v1/auth/users", {
        token,
        params: { restaurant_id: context.restaurant.id },
      });
      setUsers(nextUsers);
    } catch {
      setUsers([]);
    }
  }, [context.restaurant.id, token]);

  const loadLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextLogs = await apiRequest<AuditLog[]>(
        `/api/v1/restaurants/${context.restaurant.id}/audit-logs/`,
        {
          token,
          params: {
            action,
            entity_type: entityType,
            user_id: userId,
            branch_id: branchId,
            date_from: dateFrom,
            date_to: dateTo,
            limit: 100,
          },
        },
      );
      setLogs(nextLogs);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load audit logs");
    } finally {
      setIsLoading(false);
    }
  }, [
    action,
    branchId,
    context.restaurant.id,
    dateFrom,
    dateTo,
    entityType,
    token,
    userId,
  ]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  return (
    <div className="view-stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {isLoading ? <Notice>Loading audit logs</Notice> : null}

      <Panel
        title="Audit"
        action={
          <button className="secondary-action" type="button" onClick={loadLogs}>
            <RefreshCw size={17} />
            Refresh
          </button>
        }
      >
        <div className="audit-filter-grid">
          <Field label="From">
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </Field>
          <Field label="To">
            <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
          </Field>
          <Field label="Branch">
            <select value={branchId} onChange={(event) => setBranchId(event.target.value)}>
              <option value="">All branches</option>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Action">
            <select value={action} onChange={(event) => setAction(event.target.value)}>
              <option value="">All actions</option>
              {ACTION_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {formatAction(option)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Entity">
            <select value={entityType} onChange={(event) => setEntityType(event.target.value)}>
              <option value="">All entities</option>
              {ENTITY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </Field>
          <Field label="User">
            <select value={userId} onChange={(event) => setUserId(event.target.value)}>
              <option value="">All users</option>
              {actorOptions.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.first_name} {user.last_name} ({user.email})
                </option>
              ))}
            </select>
          </Field>
        </div>
        <div className="toolbar-line">
          <span className="status-pill">
            <Filter size={14} />
            {logs.length} events
          </span>
        </div>
      </Panel>

      <div className="audit-list">
        {logs.map((log) => (
          <article
            className="audit-row"
            data-testid={`audit-log-${log.action}`}
            key={log.id}
          >
            <header className="audit-row-header">
              <ClipboardList size={18} />
              <div>
                <strong data-testid={`audit-action-${log.action}`}>
                  {formatAction(log.action)}
                </strong>
                <span>
                  {log.user_name ?? log.user_email ?? "System"} | {formatTimestamp(log.created_at)}
                </span>
              </div>
              <span className="status-pill">{log.entity_type}</span>
            </header>
            <div className="audit-change-grid">
              <div>
                <span>Before</span>
                <p>{summarizeValues(log.old_values)}</p>
              </div>
              <div>
                <span>After</span>
                <p>{summarizeValues(log.new_values)}</p>
              </div>
            </div>
          </article>
        ))}
        {!logs.length ? <EmptyState>No audit events for the selected filters</EmptyState> : null}
      </div>
    </div>
  );
}
