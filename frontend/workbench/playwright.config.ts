import { defineConfig } from "@playwright/test";
import { createServer } from "node:net";

let port = Number(process.env.WORKBENCH_BROWSER_PORT || 0);
if (!port) {
  const probe = createServer();
  await new Promise<void>(resolve => probe.listen(0, "127.0.0.1", resolve));
  const address = probe.address();
  if (!address || typeof address === "string") throw new Error("Cannot reserve browser test port.");
  port = address.port;
  await new Promise<void>(resolve => probe.close(() => resolve()));
  process.env.WORKBENCH_BROWSER_PORT = String(port);
}

export default defineConfig({
  testDir: "./tests/browser",
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `../../.venv/bin/python tests/server.py ${port}`,
    url: `http://127.0.0.1:${port}/admin/login/`,
    timeout: 120000,
    reuseExistingServer: false,
    gracefulShutdown: { signal: "SIGTERM", timeout: 5000 },
  },
});
