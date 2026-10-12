export interface DocumentDraft {
  title: string;
  content: string;
  expectedRevision?: string | null;
  owner?: string;
}

export const documentDraftKey = (id: string) => `noye-document-draft:${id}`;

// Only an acknowledged save of this draft's base may advance its revision.
// Typing that continued during the request stays in storage for the next editor.
export function acknowledgeDocumentDraft(id: string, expected: string, saved: string, owner?: string) {
  try {
    const key = documentDraftKey(id);
    const draft: DocumentDraft | null = JSON.parse(localStorage.getItem(key) ?? "null");
    if (owner && draft?.owner === owner && draft.expectedRevision === expected) {
      localStorage.setItem(key, JSON.stringify({ ...draft, expectedRevision: saved }));
    }
  } catch { /* The saved revision remains durable if draft storage is unavailable. */ }
}
