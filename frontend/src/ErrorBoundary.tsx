import { Component, type ErrorInfo, type ReactNode } from "react";

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
