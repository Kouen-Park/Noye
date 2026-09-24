import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DocumentEditor } from "@/components/documents/document-editor";

function body(): HTMLTextAreaElement {
  return screen.getByLabelText(/document content/i) as HTMLTextAreaElement;
}

function titleField(): HTMLInputElement {
  return screen.getByLabelText("Title") as HTMLInputElement;
}

type EditorProps = Parameters<typeof DocumentEditor>[0];

/**
 * Renders the editor and hands back the save mock still typed as a mock, so a test
 * can read `.mock.calls`. Spreading a `Partial<EditorProps>` over it would widen
 * `onSave` back to the plain prop type.
 */
function editor(overrides: Partial<Omit<EditorProps, "onSave">> = {}) {
  const onSave = vi.fn<(patch: { title: string; content: string }) => Promise<void>>(
    () => Promise.resolve(),
  );
  render(
    <DocumentEditor title="Week 7" content="# Notes" saving={false} {...overrides} onSave={onSave} />,
  );
  return { onSave };
}

describe("DocumentEditor", () => {
  it("shows the document's title and body", () => {
    editor();
    expect(titleField()).toHaveValue("Week 7");
    expect(body()).toHaveValue("# Notes");
  });

  it("says Saved until something changes", async () => {
    editor();
    expect(screen.getByRole("button", { name: "Saved" })).toBeDisabled();

    await userEvent.type(body(), " more");

    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
  });

  it("saves the edited title and body together", async () => {
    const { onSave } = editor();

    await userEvent.type(body(), "\n\nAdded.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSave).toHaveBeenCalledWith({
      title: "Week 7",
      content: "# Notes\n\nAdded.",
    });
  });

  it("saves on the shortcut people already have in their fingers", async () => {
    const { onSave } = editor();

    await userEvent.type(body(), "x");
    await userEvent.keyboard("{Meta>}s{/Meta}");

    expect(onSave).toHaveBeenCalled();
  });

  it("keeps the stored title when the field is cleared rather than saving nothing", async () => {
    const { onSave } = editor();

    await userEvent.clear(titleField());
    await userEvent.type(body(), "x");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSave.mock.calls[0][0].title).toBe("Week 7");
  });

  it("cannot be saved twice while one save is in flight", async () => {
    const { onSave } = editor({ saving: true, content: "# Notes" });
    await userEvent.type(body(), "x");
    await userEvent.click(screen.getByRole("button", { name: "Saving…" }));
    expect(onSave).not.toHaveBeenCalled();
  });

  it("switches between writing and previewing", async () => {
    editor({ content: "# Rendered heading" });

    expect(screen.getByRole("tab", { name: "Write" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));

    expect(
      screen.getByRole("heading", { level: 1, name: "Rendered heading" }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/document content/i)).not.toBeInTheDocument();
  });

  it("previews the unsaved text, not the saved text", async () => {
    // Otherwise the preview would lie about what is being worked on.
    editor({ content: "# Old" });
    await userEvent.clear(body());
    await userEvent.type(body(), "# New");

    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));

    expect(screen.getByRole("heading", { name: "New" })).toBeInTheDocument();
  });

  it("reports which view is showing, because PDF export needs the preview", async () => {
    const onViewChange = vi.fn();
    editor({ onViewChange });

    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));

    expect(onViewChange).toHaveBeenCalledWith("preview");
  });
});
