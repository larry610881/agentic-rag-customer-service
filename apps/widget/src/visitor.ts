const LS_KEY = "aw-visitor-id";

function uuidv4(): string {
  return crypto.randomUUID();
}

/** Persist the server-issued (signed) visitor id returned by /config. */
export function setVisitorId(id: string): void {
  try {
    localStorage.setItem(LS_KEY, id);
  } catch {
    /* localStorage unavailable */
  }
}

/** Get or create a persistent visitor ID stored in localStorage. */
export function getVisitorId(): string {
  try {
    let id = localStorage.getItem(LS_KEY);
    if (!id) {
      id = uuidv4();
      localStorage.setItem(LS_KEY, id);
    }
    return id;
  } catch {
    // localStorage unavailable (e.g. iframe sandbox) — ephemeral ID
    return uuidv4();
  }
}
