import { Component, type ErrorInfo, type ReactNode } from "react";
import { errorReporter } from "@/lib/error-reporter";

interface Props {
  children: ReactNode;
}
interface State {
  hasError: boolean;
  error: Error | null;
}

export class GlobalErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    errorReporter.report({
      source: "frontend",
      error_type: error.name,
      message: error.message,
      stack_trace: error.stack,
      path: window.location.pathname,
      user_agent: navigator.userAgent,
      extra: { componentStack: info.componentStack },
    });
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center">
          <div className="text-center space-y-4">
            <h2 className="text-xl font-semibold">發生未預期的錯誤</h2>
            <p className="text-muted-foreground">
              {this.state.error?.message}
            </p>
            <button
              className="rounded-md bg-primary px-4 py-2 text-primary-foreground"
              onClick={() => window.location.reload()}
            >
              重新載入
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
