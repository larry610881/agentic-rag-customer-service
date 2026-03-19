declare const __CSS_PREFIX__: string;

export const CSS_PREFIX =
  typeof __CSS_PREFIX__ !== "undefined" ? __CSS_PREFIX__ : "aw";

export function cls(name: string): string {
  return `${CSS_PREFIX}-${name}`;
}
