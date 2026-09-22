import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 blocks cross-origin access to its dev-only resources by default,
  // and it treats `127.0.0.1` as a different origin from the `localhost` the
  // dev server advertises. Loading the page on the numeric address therefore
  // got `/_next/hmr` refused — the dev server logs "Blocked cross-origin
  // request to Next.js dev resource" — which broke hot reload and left the
  // page served but never hydrated: the markup rendered, no handler ran, and
  // picking a file in the upload dialog did nothing.
  //
  // Both spellings of loopback are the same machine here, and this setting
  // applies to `next dev` only, so `next start` is unaffected.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
