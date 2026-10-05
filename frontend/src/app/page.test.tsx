import { render, screen, waitFor } from "@testing-library/react";
import { expect, it } from "vitest";
import Home from "@/app/page";
import { mockRouter } from "@/tests/setup";

it("opens the chat workspace on first launch, including static desktop builds", async () => {
  render(<Home />);
  expect(screen.getByRole("status")).toHaveTextContent("Opening your workspace");
  await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/chat/"));
});
