import "@testing-library/jest-dom/vitest";
import { server } from "./mocks/server";
import { afterAll, afterEach, beforeAll } from "vitest";

// jsdom does not implement scrollIntoView
Element.prototype.scrollIntoView = () => {};

// jsdom does not implement ResizeObserver (required by Radix UI)
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());
