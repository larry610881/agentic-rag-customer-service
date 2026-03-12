/** Cache of loaded script URLs to avoid duplicate loading */
const loaded = new Set<string>();

/**
 * Dynamically load a script from CDN. Deduplicates by URL.
 * @param url - Full URL to the script
 * @param timeout - Timeout in ms (default 15000)
 */
export function loadScript(url: string, timeout = 15000): Promise<void> {
  if (loaded.has(url)) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = true;

    const timer = setTimeout(() => {
      reject(new Error(`Script load timeout: ${url}`));
    }, timeout);

    script.onload = () => {
      clearTimeout(timer);
      loaded.add(url);
      resolve();
    };
    script.onerror = () => {
      clearTimeout(timer);
      reject(new Error(`Failed to load script: ${url}`));
    };

    document.head.appendChild(script);
  });
}
