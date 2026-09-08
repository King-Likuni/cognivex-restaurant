import type { ReactNode } from "react";

type PanelProps = {
  title: string;
  action?: ReactNode;
  children: ReactNode;
};

export function Panel({ title, action, children }: PanelProps) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

type StatProps = {
  label: string;
  value: string | number;
  tone?: "neutral" | "good" | "warn";
  testId?: string;
};

export function Stat({ label, value, tone = "neutral", testId }: StatProps) {
  return (
    <div className={`stat stat-${tone}`} data-testid={testId}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

type NoticeProps = {
  children: ReactNode;
  tone?: "info" | "error" | "success";
};

export function Notice({ children, tone = "info" }: NoticeProps) {
  return <div className={`notice notice-${tone}`}>{children}</div>;
}

type FieldProps = {
  label: string;
  children: ReactNode;
};

export function Field({ label, children }: FieldProps) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}
