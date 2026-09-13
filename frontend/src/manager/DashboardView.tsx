import { BarChart3, CalendarDays, Download, RefreshCw, TrendingUp, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel, Stat } from "../components/ui";
import { apiRequest, downloadApiFile, type DailySalesReport, type RoleName } from "../services/api";
import { formatMoney } from "../services/format";

type Props = {
  context: AppContext;
  token: string;
  roleName: RoleName | null;
};

export function DashboardView({ context, token, roleName }: Props) {
  const [businessDate, setBusinessDate] = useState("");
  const [report, setReport] = useState<DailySalesReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canExportAudit = roleName === "OWNER" || roleName === "MANAGER";

  const loadReport = useCallback(async () => {
    setError(null);
    try {
      const nextReport = await apiRequest<DailySalesReport>(
        `/api/v1/restaurants/${context.restaurant.id}/reports/daily-sales`,
        {
          token,
          params: {
            business_date: businessDate,
            branch_id: context.branch.id,
          },
        },
      );
      setReport(nextReport);
      if (!businessDate) {
        setBusinessDate(nextReport.business_date);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load report");
    }
  }, [businessDate, context.branch.id, context.restaurant.id, token]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  const collectionRate = useMemo(() => {
    if (!report || report.orders === 0) {
      return "0%";
    }
    return `${Math.round((report.collected_orders / report.orders) * 100)}%`;
  }, [report]);

  const maxTopItemQuantity = useMemo(
    () => Math.max(1, ...(report?.top_items.map((item) => item.quantity) ?? [])),
    [report],
  );
  const maxChannelOrders = useMemo(
    () => Math.max(1, ...(report?.sales_by_channel.map((channel) => channel.orders) ?? [])),
    [report],
  );
  const maxHourlyRevenue = useMemo(
    () => Math.max(1, ...(report?.hourly_sales.map((hour) => Number(hour.revenue)) ?? [])),
    [report],
  );

  async function downloadExport(path: string, filename: string, includeDate = true) {
    setError(null);
    try {
      const blob = await downloadApiFile(path, {
        token,
        params: {
          business_date: includeDate ? businessDate : undefined,
          branch_id: context.branch.id,
          date_from: includeDate ? businessDate : undefined,
          date_to: includeDate ? businessDate : undefined,
        },
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not download export");
    }
  }

  async function downloadReport() {
    setError(null);
    try {
      const exportDate = businessDate || report?.business_date || "today";
      const blob = await downloadApiFile(
        `/api/v1/restaurants/${context.restaurant.id}/reports/daily-sales.csv`,
        {
          token,
          params: {
            business_date: businessDate,
            branch_id: context.branch.id,
          },
        },
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `cognivex-owner-report-${exportDate}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not download report");
    }
  }

  return (
    <div className="view-stack">
      <Panel
        title={roleName === "CASHIER" ? "Branch Dashboard" : "Owner Report"}
        action={
          <div className="button-row">
            <button className="secondary-action" type="button" onClick={loadReport}>
              <RefreshCw size={17} />
              Refresh
            </button>
            <button
              className="secondary-action"
              type="button"
              onClick={() => void downloadReport()}
              disabled={!report}
            >
              <Download size={17} />
              CSV
            </button>
          </div>
        }
      >
        <div className="toolbar-line">
          <Field label="Business date">
            <input
              type="date"
              value={businessDate}
              onChange={(event) => setBusinessDate(event.target.value)}
            />
          </Field>
          <span className="socket-state online">
            <CalendarDays size={16} />
            {context.branch.name}
          </span>
        </div>
        {error ? <Notice tone="error">{error}</Notice> : null}
        {report ? (
          <>
            <div className="stats-grid">
              <Stat
                label="Revenue"
                value={formatMoney(report.revenue)}
                tone="good"
                testId="stat-revenue"
              />
              <Stat label="Orders" value={report.orders} />
              <Stat
                label="Collected"
                value={report.collected_orders}
                testId="stat-collected"
              />
              <Stat label="Ready" value={report.ready_orders} tone="warn" />
              <Stat label="Uncollected" value={report.uncollected_orders} tone="warn" />
              <Stat label="Average" value={formatMoney(report.average_order_value)} />
              <Stat label="Collection rate" value={collectionRate} />
            </div>
            <div className="view-grid two-columns">
              <section className="report-section">
                <h3>
                  <TrendingUp size={18} />
                  Sold Products
                </h3>
                <div className="data-list">
                  {report.top_items.map((item) => (
                    <div className="report-row" key={item.menu_item_id}>
                      <div className="report-row-header">
                        <div>
                          <strong>{item.name}</strong>
                          <span>{item.quantity} sold</span>
                        </div>
                        <strong>{formatMoney(item.revenue)}</strong>
                      </div>
                      <div className="bar-track">
                        <span
                          style={{
                            width: `${Math.max(6, (item.quantity / maxTopItemQuantity) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                  {!report.top_items.length ? <EmptyState>No collected sales yet</EmptyState> : null}
                </div>
              </section>
              <section className="report-section">
                <h3>
                  <BarChart3 size={18} />
                  Payments
                </h3>
                <div className="data-list">
                  {report.sales_by_payment.map((payment) => (
                    <div className="data-row" key={payment.provider}>
                      <div>
                        <strong>{payment.provider}</strong>
                        <span>{payment.payments} payments</span>
                      </div>
                      <strong>{formatMoney(payment.revenue)}</strong>
                    </div>
                  ))}
                  {!report.sales_by_payment.length ? <EmptyState>No payments collected yet</EmptyState> : null}
                </div>
              </section>
              <section className="report-section">
                <h3>
                  <BarChart3 size={18} />
                  Order Channels
                </h3>
                <div className="data-list">
                  {report.sales_by_channel.map((channel) => (
                    <div className="report-row" key={channel.channel}>
                      <div className="report-row-header">
                        <div>
                          <strong>{channel.channel}</strong>
                          <span>{channel.orders} orders</span>
                        </div>
                        <strong>{formatMoney(channel.revenue)}</strong>
                      </div>
                      <div className="bar-track">
                        <span
                          style={{
                            width: `${Math.max(6, (channel.orders / maxChannelOrders) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                  {!report.sales_by_channel.length ? <EmptyState>No orders yet</EmptyState> : null}
                </div>
              </section>
              <section className="report-section">
                <h3>
                  <TrendingUp size={18} />
                  Hourly Sales
                </h3>
                <div className="hour-chart">
                  {report.hourly_sales.map((hour) => (
                    <div className="hour-bar" key={hour.hour}>
                      <span
                        style={{
                          height: `${Math.max(8, (Number(hour.revenue) / maxHourlyRevenue) * 100)}%`,
                        }}
                        title={`${hour.orders} orders, ${formatMoney(hour.revenue)}`}
                      />
                      <strong>{String(hour.hour).padStart(2, "0")}</strong>
                    </div>
                  ))}
                  {!report.hourly_sales.length ? <EmptyState>No collected sales yet</EmptyState> : null}
                </div>
              </section>
            </div>
            <section className="report-section">
              <h3>
                <Users size={18} />
                Cashier Activity
              </h3>
              <div className="data-list">
                {report.cashier_activity.map((cashier) => (
                  <div className="data-row" key={cashier.user_id ?? cashier.name}>
                    <div>
                      <strong>{cashier.name}</strong>
                      <span>{cashier.email ?? "No email"}</span>
                    </div>
                    <div className="cashier-metrics">
                      <span>{cashier.orders_created} orders</span>
                      <span>{cashier.payments_confirmed} payments</span>
                      <span>{cashier.orders_collected} collections</span>
                      <strong>{formatMoney(cashier.revenue_collected)}</strong>
                    </div>
                  </div>
                ))}
                {!report.cashier_activity.length ? <EmptyState>No cashier activity yet</EmptyState> : null}
              </div>
            </section>
            <section className="report-section">
              <h3>
                <Download size={18} />
                Data Exports
              </h3>
              <div className="export-grid">
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() =>
                    void downloadExport(
                      `/api/v1/restaurants/${context.restaurant.id}/reports/exports/orders.csv`,
                      `cognivex-orders-${businessDate || report.business_date}.csv`,
                    )
                  }
                >
                  <Download size={17} />
                  Orders
                </button>
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() =>
                    void downloadExport(
                      `/api/v1/restaurants/${context.restaurant.id}/reports/exports/payments.csv`,
                      `cognivex-payments-${businessDate || report.business_date}.csv`,
                    )
                  }
                >
                  <Download size={17} />
                  Payments
                </button>
                {canExportAudit ? (
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() =>
                      void downloadExport(
                        `/api/v1/restaurants/${context.restaurant.id}/reports/exports/audit-logs.csv`,
                        `cognivex-audit-logs-${businessDate || report.business_date}.csv`,
                      )
                    }
                  >
                    <Download size={17} />
                    Audit Logs
                  </button>
                ) : null}
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() =>
                    void downloadExport(
                      `/api/v1/restaurants/${context.restaurant.id}/reports/exports/inventory-balances.csv`,
                      `cognivex-inventory-balances-${businessDate || report.business_date}.csv`,
                      false,
                    )
                  }
                >
                  <Download size={17} />
                  Inventory
                </button>
              </div>
            </section>
          </>
        ) : (
          <EmptyState>Load a report to see branch performance</EmptyState>
        )}
      </Panel>
      <Panel title="Operational Notes">
        <div className="event-row">
          <BarChart3 size={18} />
          <span>Revenue counts paid collected orders only.</span>
        </div>
      </Panel>
    </div>
  );
}
