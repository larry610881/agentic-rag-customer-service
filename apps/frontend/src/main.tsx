import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Providers } from "@/components/providers";
import { App } from "@/App";
import { errorReporter } from "@/lib/error-reporter";
import { GlobalErrorBoundary } from "@/components/error-boundary";
import "./globals.css";

errorReporter.install();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <GlobalErrorBoundary>
      <BrowserRouter>
        <Providers>
          <App />
        </Providers>
      </BrowserRouter>
    </GlobalErrorBoundary>
  </StrictMode>,
);
