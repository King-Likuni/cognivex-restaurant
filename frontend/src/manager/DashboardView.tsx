import { BarChart3, CalendarDays, Download, RefreshCw, TrendingUp, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel, Stat } from "../components/ui";
import { apiRequest, type DailySalesReport } from "../services/api";
import { formatMoney } from "../services/format";

type Props = {
  context: AppContext;
  token: string;
};

function csvValue(value: string | number | null) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function csvRow(values: (string | number | null)[]) {
  return values.map(csvValue).join(",");
}

function reportCsv(report: DailySalesReport, branchName: string) {
  const rows = [
    csvRow(["Cognivex Owner Report"]),
    csvRow(["Business date", report.business_date]),
    csvRow(["Branch", branchName]),
    "",
    csvRow(["Summary"]),
    csvRow(["Revenue", report.revenue]),
    csvRow(["Orders", report.orders]),
    csvRow(["Collected", report.collected_orders]),
    csvRow(["Ready", report.ready_orders]),
    csvRow(["Uncollected", report.uncollected_orders]),
    csvRow(["Cancelled", report.cancelled_orders]),
    csvRow(["Average order value", report.average_order_value]),
    "",
    csvRow(["Sold products"]),
    csvRow(["Product", "Quantity", "Revenue"]),
    ...report.top_items.map((item) => csvRow([item.name, item.quantity, item.revenue])),
    "",
    csvRow(["Payment methods"]),
    csvRow(["Provider", "Payments", "Revenue"]),
    ...report.sales_by_payment.map((payment) =>
      csvRow([payment.provider, payment.payments, payment.revenue]),
    ),
    "",
    csvRow(["Channels"]),
    csvRow(["Channel", "Orders", "Revenue"]),
    ...report.sales_by_channel.map((channel) =>
      csvRow([channel.channel, channel.orders, channel.revenue]),
    ),
    "",
    csvRow(["Cashier activity"]),
    csvRow([
      "Name",
      "Email",
      "Orders created",
      "Payments confirmed",
      "Orders collected",
      "Revenue collected",
    ]),
    ...report.cashier_activity.map((cashier) =>
      csvRow([
        cashier.name,
        cashier.email,
        cashier.orders_created,
        cashier.payments_confirmed,
        cashier.orders_collected,
        cashier.revenue_collected,
      ]),
    ),
  ];
  return rows.join("\n");
}

export function DashboardView({ context, token }: Props) {
  const [businessDate, setBusinessDate] = useState("");
  const [report, setReport] = useState<DailySalesReport | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  function downloadReport() {
    if (!report) {
      return;
    }
    const blob = new Blob([reportCsv(report, context.branch.name)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `cognivex-owner-report-${report.business_date}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="view-stack">
      <Panel
        title="Owner Report"
        action={
          <div className="button-row">
            <button className="secondary-action" type="button" onClick={loadReport}>
              <RefreshCw size={17} />
              Refresh
            </button>
            <button
              className="secondary-action"
              type="button"
              onClick={downloadReport}
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
