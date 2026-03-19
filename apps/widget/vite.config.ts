import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  define: {
    __CSS_PREFIX__: JSON.stringify(process.env.WIDGET_CSS_PREFIX || "aw"),
  },
  build: {
    lib: {
      entry: resolve(__dirname, "src/main.ts"),
      name: "AgenticWidget",
      formats: ["iife"],
      fileName: () => "widget.js",
    },
    outDir: "dist",
    minify: "esbuild",
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
  plugins: [
    {
      name: "css-prefix-replace",
      generateBundle(_, bundle) {
        const prefix = process.env.WIDGET_CSS_PREFIX || "aw";
        for (const file of Object.values(bundle)) {
          if (file.type === "asset" && file.fileName.endsWith(".css")) {
            file.source = (file.source as string).replaceAll(
              "aw-",
              `${prefix}-`,
            );
          }
        }
      },
    },
  ],
});
