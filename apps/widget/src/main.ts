/**
 * Agentic RAG Customer Service — Embeddable Chat Widget
 *
 * Usage:
 *   <script src="https://your-api.com/static/widget.js"
 *           data-bot="ab3Kx9"
 *           crossorigin="anonymous">
 *   </script>
 */

import type { WidgetConfig } from "./types";
import { fetchWidgetConfig, identify } from "./session";
import type { IdentifyPayload, IdentifyResult } from "./session";
import { Widget } from "./widget";

declare global {
  interface Window {
    AgenticRagWidget?: {
      identify: (payload: IdentifyPayload) => Promise<IdentifyResult>;
    };
  }
}

(function () {
  const script = document.currentScript as HTMLScriptElement | null;
  if (!script) return;

  // 宿主 SDK：window.AgenticRagWidget.identify({ userId, exp, hash })
  window.AgenticRagWidget = { identify };

  const shortCode = script.getAttribute("data-bot");
  if (!shortCode) {
    console.error("[widget] data-bot attribute is required");
    return;
  }

  // Derive API base URL from the script's src
  const apiBase = script.src.replace(/\/static\/widget\.js.*$/, "");
  // Fetch bot config (+ widget token) then initialize widget
  fetchWidgetConfig(apiBase, shortCode)
    .then((data: WidgetConfig) => {
      // Apply defaults for fields that may not exist in the response yet
      const config: WidgetConfig = {
        name: data.name || "Chat",
        description: data.description || "",
        keep_history: data.keep_history !== false,
        show_sources: data.show_sources !== false,
        welcome_message: data.welcome_message || "",
        placeholder_text: data.placeholder_text || "",
        greeting_messages: data.greeting_messages || [],
        greeting_animation: data.greeting_animation || "fade",
      };

      new Widget(config, apiBase, shortCode);
    })
    .catch((err) => {
      console.error("[widget] Failed to initialize:", err);
    });
})();
