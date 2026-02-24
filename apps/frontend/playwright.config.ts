import { defineConfig } from "@playwright/test";
import { defineBddConfig } from "playwright-bdd";

const testDir = defineBddConfig({
  features: "e2e/features/**/*.feature",
  steps: ["e2e/steps/fixtures.ts", "e2e/steps/**/*.steps.ts"],
});

export default defineConfig({
  testDir,
  globalSetup: "e2e/global-setup.ts",
  timeout: 60000,
  retries: 1,
  workers: 1,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "on",
    video: "on",
  },
  projects: [
    {
      name: "auth",
      testMatch: "**/auth/*.feature.spec.js",
    },
    {
      name: "features",
      testMatch: /^(?!.*\/auth\/)(?!.*\/demo\/).*\.feature\.spec\.js$/,
      dependencies: ["auth"],
    },
    {
      name: "demo",
      testMatch: "**/demo/*.feature.spec.js",
      dependencies: ["features"],
      timeout: 120000,
    },
  ],
  webServer: {
    command: "npm run dev",
    port: 3000,
    reuseExistingServer: !process.env.CI,
  },
});
