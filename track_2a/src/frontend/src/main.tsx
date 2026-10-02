import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Component, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./auth";
import { ToastProvider } from "./components/Toast";
import { I18nProvider } from "./lib/i18n";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 15_000, refetchOnWindowFocus: false },
  },
});

// A browser left open during a release can request a retired page bundle.
// Refresh once to fetch the current manifest, then show a recovery screen.
window.addEventListener("vite:preloadError", (event) => {
  try {
    const last = Number(sessionStorage.getItem("zusage.bundle-reload") || 0);
    if (Date.now() - last > 30_000) {
      event.preventDefault();
      sessionStorage.setItem("zusage.bundle-reload", String(Date.now()));
      window.location.reload();
    }
  } catch { /* The recovery screen also works when storage is unavailable. */ }
});

class RecoveryBoundary extends Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center" role="alert">
      <h1 className="font-display text-xl font-bold">Let's get you back to Zusage</h1>
      <p>Your saved interviews are still there. Reload to open the latest app.</p>
      <button className="rounded-xl bg-ink px-6 py-3 font-bold text-white" onClick={() => window.location.reload()}>Reload app</button>
    </div>;
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RecoveryBoundary>
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <AuthProvider>
          <ToastProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </ToastProvider>
        </AuthProvider>
      </I18nProvider>
    </QueryClientProvider>
    </RecoveryBoundary>
  </StrictMode>,
);
