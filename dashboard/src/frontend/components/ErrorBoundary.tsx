import React from "react";

interface State {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ReactNode },
  State
> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div
            style={{
              padding: 24,
              color: "#ef4444",
              fontFamily: "monospace",
              background: "#1a1a2e",
            }}
          >
            <strong>Runtime error:</strong> {this.state.error.message}
          </div>
        )
      );
    }
    return this.props.children;
  }
}
