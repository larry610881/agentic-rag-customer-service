import { defineConfig, globalIgnores } from "eslint/config";

const eslintConfig = defineConfig([
  globalIgnores(["dist/**", "node_modules/**", "e2e/.features-gen/**"]),
]);

export default eslintConfig;
