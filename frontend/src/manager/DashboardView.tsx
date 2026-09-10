import { BarChart3, CalendarDays, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel, Stat } from "../components/ui";
import { apiRequest, type DailySalesReport } from "../services/api";
import { formatMoney } from "../services/format";

type Props = {
  context: AppContext;
  token: string;
};

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

  return (
    <div className="view-stack">
      <Panel
        title="Daily Sales"
        action={
          <button className="secondary-action" type="button" onClick={loadReport}>
            <RefreshCw size={17} />
            Refresh
          </button>
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
              <Panel title="Top Items">
                <div className="data-list">
                  {report.top_items.map((item) => (
                    <div className="data-row" key={item.menu_item_id}>
                      <div>
                        <strong>{item.name}</strong>
                        <span>{item.quantity} sold</span>
                      </div>
                      <strong>{formatMoney(item.revenue)}</strong>
                    </div>
                  ))}
                  {!report.top_items.length ? <EmptyState>No collected sales yet</EmptyState> : null}
                </div>
              </Panel>
              <Panel title="Payments">
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
              </Panel>
            </div>
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
