/**
 * Agentic RAG Customer Service — Embeddable Chat Widget
 *
 * Usage:
 *   <script src="https://your-api.com/static/widget.js"
 *           data-bot="ab3Kx9">
 *   </script>
 */

import type { WidgetConfig } from "./types";
import { getVisitorId } from "./visitor";
import { Widget } from "./widget";

(function () {
  const script = document.currentScript as HTMLScriptElement | null;
  if (!script) return;

  const shortCode = script.getAttribute("data-bot");
  if (!shortCode) {
    console.error("[widget] data-bot attribute is required");
    return;
  }

  // Derive API base URL from the script's src
  const apiBase = script.src.replace(/\/static\/widget\.js.*$/, "");
  const configUrl = `${apiBase}/api/v1/widget/${shortCode}/config`;

  // Fetch bot config then initialize widget
  fetch(configUrl, {
    headers: { "X-Visitor-Id": getVisitorId() },
  })
    .then((res) => {
      if (!res.ok) throw new Error(`Config fetch failed: HTTP ${res.status}`);
      return res.json();
    })
    .then((data: WidgetConfig) => {
      // Apply defaults for fields that may not exist in the response yet
      const config: WidgetConfig = {
        name: data.name || "Chat",
        description: data.description || "",
        keep_history: data.keep_history !== false,
        avatar_type: data.avatar_type || "none",
        avatar_model_url: data.avatar_model_url || "",
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
