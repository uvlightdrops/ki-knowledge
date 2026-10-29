import type { Bootstrap } from "./types";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
  }
}

export function apiClient(config: Bootstrap) {
  return async function api<T>(path: string, method = "GET", data?: object, etag?: string): Promise<T> {
    const url = new URL(config.apiBase + path, window.location.origin);
    url.searchParams.set("domain", config.domain);
    const csrf = document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")?.value;
    const response = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(data ? { "Content-Type": "application/json" } : {}),
        ...(method !== "GET" && csrf ? { "X-CSRFToken": csrf } : {}),
        ...(etag ? { "If-Match": etag } : {}),
      },
      body: data ? JSON.stringify(data) : undefined,
    });
    if (!response.headers.get("content-type")?.includes("application/json")) {
      throw new ApiError(`Serverantwort ${response.status}: Sitzung oder CSRF-Schutz prüfen.`, response.status);
    }
    const payload = await response.json();
    if (!response.ok) {
      const fields = payload.error?.fields;
      const details = fields && typeof fields === "object"
        ? Object.entries(fields).map(([field, message]) => `${field}: ${message}`).join("\n")
        : "";
      throw new ApiError(
        [payload.error?.message || `Anfrage fehlgeschlagen (${response.status}).`, details].filter(Boolean).join("\n"),
        response.status,
      );
    }
    return payload;
  };
}
