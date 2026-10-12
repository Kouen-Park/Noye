/** Desktop URL is supplied by our own sidecar, never guessed from a fixed port. */
let desktopBaseUrl: string | undefined;

export function setDesktopBaseUrl(url: string): void {
  const parsed = new URL(url);
  if (parsed.protocol !== "http:" || parsed.hostname !== "127.0.0.1" ||
      !parsed.port || Number(parsed.port) === 0 || parsed.username || parsed.password ||
      parsed.pathname !== "/" || parsed.search || parsed.hash) {
    throw new Error("Noye returned an invalid backend address.");
  }
  desktopBaseUrl = parsed.origin;
}

export function apiBaseUrl(): string {
  return desktopBaseUrl ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
}

export function isDesktopRuntime(): boolean {
  return desktopBaseUrl !== undefined;
}
