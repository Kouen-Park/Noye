import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { DesktopSetup } from "@/lib/api";
import { RuntimeReadiness } from "./runtime-readiness";

it("distinguishes installation from configuration and cloud access", () => {
  render(<RuntimeReadiness setup={{
    configured_generation_model: "missing-model",
    readiness: { indexing_available: false, local_generation_available: false,
      cloud_configuration: { openai: true, anthropic: false, gemini: false },
      cloud_access_verified: false, reasons: ["Start Qdrant in Services."],
      context_tokens: 16384, output_tokens: 2048, input_byte_limit: 13824 },
  } as DesktopSetup} />);
  expect(screen.getByText(/Configured local model: missing-model/)).toBeInTheDocument();
  expect(screen.getByText(/Saved keys do not confirm API access/)).toBeInTheDocument();
  expect(screen.getByText("Start Qdrant in Services.")).toBeInTheDocument();
  expect(screen.getByText(/conservative input limit 13824/)).toBeInTheDocument();
});
