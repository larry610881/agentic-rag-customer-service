/** Streaming UX configuration */
export const STREAMING_CONFIG = {
  /**
   * Minimum display time (ms) for each status hint before it can be replaced.
   * Prevents fast tool transitions (executing → done → thinking) from flashing.
   * Set to 0 to disable throttling.
   */
  STATUS_MIN_DISPLAY_MS: 1500,
} as const;
