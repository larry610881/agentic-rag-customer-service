import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

const eslintConfig = defineConfig([
  globalIgnores(["dist/**", "node_modules/**", "e2e/.features-gen/**"]),
  {
    files: ["src/**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      // 以下兩條是 React Compiler 導向的規則，本專案未啟用 React Compiler（vite.config 僅 plugin-react）：
      // - set-state-in-effect：全站 33 處皆為「server data → 本地草稿 state」同步的慣用寫法，
      //   改寫成 key remount / render 期推導屬大範圍行為風險重構，無對應缺陷價值
      // - incompatible-library：僅提示 react-hook-form 的 watch() 無法被 Compiler memoize，未啟用 Compiler 時無意義
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/incompatible-library": "off",
    },
  },
  {
    // shadcn/ui 生成元件依上游慣例同檔匯出 cva variants（buttonVariants 等），由 CLI 覆寫維護；
    // 測試工具檔不參與 HMR。兩者皆與 Fast Refresh 無關
    files: ["src/components/ui/**/*.tsx", "src/test/**/*.{ts,tsx}"],
    rules: {
      "react-refresh/only-export-components": "off",
    },
  },
]);

export default eslintConfig;
