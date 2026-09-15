import { Component, type ErrorInfo, type ReactNode } from "react";

import { API_BASE_URL } from "./services/api";

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Frontend error boundary caught an error", { error, errorInfo });
    void reportFrontendError(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="recovery-page">
          <section className="login-card">
            <p className="eyebrow">Cognivex</p>
            <h1>Something went wrong</h1>
            <p>The screen could not load cleanly. Refresh to restore the workspace.</p>
            <button
              className="primary-action"
              type="button"
              onClick={() => window.location.reload()}
            >
              Refresh
            </button>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}

function readSessionUser() {
  try {
    const raw = localStorage.getItem("cognivex.session");
    if (!raw) {
      return {};
    }
    const session = JSON.parse(raw) as {
      user?: { email?: string | null; role_name?: string | null };
    };
    return {
      user_email: session.user?.email ?? null,
      user_role: session.user?.role_name ?? null,
    };
  } catch {
    return {};
  }
}

async function reportFrontendError(error: Error, errorInfo: ErrorInfo) {
  try {
    await fetch(`${API_BASE_URL}/api/v1/platform/incidents/frontend-errors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: error.message || "Unknown frontend error",
        stack: error.stack ?? null,
        component_stack: errorInfo.componentStack,
        path: window.location.pathname,
        url: window.location.href,
        ...readSessionUser(),
      }),
    });
  } catch {
    // The recovery UI must remain usable even if incident reporting is unavailable.
  }
}
