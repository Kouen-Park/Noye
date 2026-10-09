import '@testing-library/jest-dom/vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import DocumentsPage from '@/app/documents/page';
import * as docs from '@/lib/api';
import * as wiki from '@/lib/wiki';
import * as sourceDocs from '@/lib/source-documents';

const nav = vi.hoisted(() => ({ query: '', push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(nav.query), useRouter: () => nav }));
vi.mock('@/components/app-shell', () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }));
vi.mock('@/lib/api', async get => ({ ...await get<typeof import('@/lib/api')>(), readDocument: vi.fn(), listDocuments: vi.fn(), updateDocument: vi.fn(), createDocument: vi.fn(), deleteDocument: vi.fn() }));
vi.mock('@/lib/source-documents', async get => ({ ...await get<typeof import('@/lib/source-documents')>(), readSourceDocument: vi.fn(), editSourceDocument: vi.fn() }));
const makeDoc = (id: string): docs.NoyeDocument => ({ id, title: `Document ${id}`, content: `Body ${id}`, source_conversation_id: null, source_message_id: null, source_instruction: null, citations: [], created_at: '', updated_at: '' });
const summaries = ['a','b'].map(id => ({ id, title: `Document ${id}`, excerpt: `Body ${id}`, is_generated: false, created_at: '', updated_at: '' }));
const makeSourceDoc = (id: string, rev = 'r2'): sourceDocs.SourceDocument => ({
  ...makeDoc(id), content: `Body ${id}-${rev}`,
  revision: { id: rev, origin: 'generated', title: `Document ${id}`, content: `Body ${id}-${rev}`, created_at: '2026-10-08', metadata: { coverage: { partial: false, inventory_mode: 'collection', inventory_count: 0, sources: [] }, model: 'local', prompt_version: 'test', processing_seconds: 1, citations: [], request_id: 'req', scope: wiki.ALL_WIKI_SOURCES } },
  revisions: ['r2', 'r1'].map(id => ({ id, origin: 'generated', title: 'Revision', created_at: '2026-10-08' })),
});
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r; }); return { promise, resolve }; }
beforeEach(() => {
  vi.clearAllMocks(); window.localStorage.clear(); nav.query = 'd=a';
  vi.mocked(docs.listDocuments).mockResolvedValue(summaries);
  vi.mocked(docs.readDocument).mockImplementation(async id => makeDoc(id));
  vi.mocked(docs.updateDocument).mockImplementation(async (id, patch) => ({ ...makeDoc(id), ...patch }));
  vi.mocked(sourceDocs.readSourceDocument).mockRejectedValue(new docs.ApiError(404, 'Not source driven'));
});
afterEach(cleanup);
it('Documents restores dirty draft after switching documents and returning', async () => {
  const view = render(<DocumentsPage />);
  await userEvent.type(await screen.findByLabelText(/Document content/), ' unsaved authored work');
  nav.query = 'd=b'; view.rerender(<DocumentsPage />);
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b'));
  nav.query = 'd=a'; view.rerender(<DocumentsPage />);
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body a unsaved authored work'));
  expect(window.localStorage.length).toBeGreaterThan(0);
});
it('late initial document read cannot replace the selected document', async () => {
  const pending = deferred<docs.NoyeDocument>();
  vi.mocked(docs.readDocument).mockImplementation(id => id === 'a' ? pending.promise : Promise.resolve(makeDoc(id)));
  const view = render(<DocumentsPage />);
  await waitFor(() => expect(docs.readDocument).toHaveBeenCalledWith('a', expect.any(AbortSignal)));
  nav.query = 'd=b'; view.rerender(<DocumentsPage />);
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b'));
  await act(async () => pending.resolve(makeDoc('a')));
  expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b');
});
it('late legacy Save cannot replace B or change its save target', async () => {
  const pending = deferred<docs.NoyeDocument>();
  vi.mocked(docs.updateDocument).mockReturnValueOnce(pending.promise);
  const view = render(<DocumentsPage />);
  await userEvent.type(await screen.findByLabelText(/Document content/), ' edited');
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  nav.query = 'd=b'; view.rerender(<DocumentsPage />);
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b'));
  await act(async () => pending.resolve({ ...makeDoc('a'), content: 'Body a edited' }));
  expect(screen.getByRole('button', { name: 'Open Document b' })).toHaveAttribute('aria-current', 'true');
  expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b');
  await userEvent.type(screen.getByLabelText(/Document content/), ' unintended');
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  expect(docs.updateDocument).toHaveBeenLastCalledWith('b', { title: 'Document b', content: 'Body b unintended' });
});
it('late source revision cannot replace a different document', async () => {
  const pending = deferred<sourceDocs.SourceDocument>();
  vi.mocked(sourceDocs.readSourceDocument).mockImplementation((id, rev) => id === 'a'
    ? rev === 'r1' ? pending.promise : Promise.resolve(makeSourceDoc('a'))
    : Promise.reject(new docs.ApiError(404, 'Not source driven')));
  const view = render(<DocumentsPage />);
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body a-r2'));
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Revision' }), 'r1');
  nav.query = 'd=b'; view.rerender(<DocumentsPage />);
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b'));
  await act(async () => pending.resolve(makeSourceDoc('a', 'r1')));
  expect(nav.query).toBe('d=b');
  expect(screen.getByRole('button', { name: 'Open Document b' })).toHaveAttribute('aria-current', 'true');
  expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b');
});
it('late source Save cannot replace a different document', async () => {
  const pending = deferred<sourceDocs.SourceDocument>();
  vi.mocked(sourceDocs.readSourceDocument).mockImplementation(id => id === 'a'
    ? Promise.resolve(makeSourceDoc('a')) : Promise.reject(new docs.ApiError(404, 'Not source driven')));
  vi.mocked(sourceDocs.editSourceDocument).mockReturnValue(pending.promise);
  const view = render(<DocumentsPage />);
  await userEvent.type(await screen.findByLabelText(/Document content/), ' edited');
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  nav.query = 'd=b'; view.rerender(<DocumentsPage />);
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b'));
  await act(async () => pending.resolve({ ...makeSourceDoc('a'), content: 'Body a-r2 edited' }));
  expect(nav.query).toBe('d=b');
  expect(screen.getByLabelText(/Document content/)).toHaveValue('Body b');
});
it('source revision remount retains additional typing during in-flight save', async () => {
  const pending = deferred<sourceDocs.SourceDocument>();
  vi.mocked(sourceDocs.readSourceDocument).mockResolvedValue(makeSourceDoc('a'));
  vi.mocked(sourceDocs.editSourceDocument).mockReturnValue(pending.promise);
  render(<DocumentsPage />);
  await userEvent.type(await screen.findByLabelText(/Document content/), ' edited');
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  await userEvent.type(screen.getByLabelText(/Document content/), ' later');
  const saved = makeSourceDoc('a', 'r3');
  saved.content = 'Body a-r2 edited'; saved.revision.content = saved.content;
  saved.revisions.unshift({ id: 'r3', origin: 'user', title: saved.title, created_at: '2026-10-08' });
  await act(async () => pending.resolve(saved));
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body a-r2 edited later'));
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
  expect(JSON.parse(localStorage.getItem('noye-document-draft:a')!).expectedRevision).toBe('r3');
});


it("keeps the base of an authored source draft across newer saved revisions", async () => {
  let current = makeSourceDoc("a", "r1");
  current.revisions = [current.revisions[1]];
  vi.mocked(sourceDocs.readSourceDocument).mockImplementation(async () => current);
  const first = render(<DocumentsPage />);
  await userEvent.type(await screen.findByLabelText(/Document content/), " retained authored work");
  first.unmount();
  current = makeSourceDoc("a", "r2");
  render(<DocumentsPage />);
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue("Body a-r1 retained authored work"));
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  await userEvent.click(screen.getByLabelText(/Document content/));
  await userEvent.keyboard("{Meta>}s{/Meta}");
  expect(sourceDocs.editSourceDocument).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Compare with latest revision" }));
  expect(await screen.findByLabelText("Latest saved Markdown")).toHaveValue("Body a-r2");
  await userEvent.click(screen.getByRole("button", { name: "Reapply my draft to this revision" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Save" })).toBeEnabled());
  vi.mocked(sourceDocs.editSourceDocument).mockRejectedValue(new docs.ApiError(409, "Revision changed again"));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(sourceDocs.editSourceDocument).toHaveBeenCalledWith("a", "r2", { title: "Document a", content: "Body a-r1 retained authored work" });
  expect(await screen.findByText("Revision changed again")).toBeInTheDocument();
  expect(screen.getByLabelText(/Document content/)).toHaveValue("Body a-r1 retained authored work");
});

it("requires comparison for a draft written before base revisions were retained", async () => {
  localStorage.setItem("noye-document-draft:a", JSON.stringify({ title: "Old draft", content: "Unknown base" }));
  vi.mocked(sourceDocs.readSourceDocument).mockResolvedValue(makeSourceDoc("a"));
  render(<DocumentsPage />);
  await screen.findByText(/older or unknown base revision/);
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Compare with latest revision" }));
  await screen.findByLabelText("Latest saved Markdown");
  await userEvent.click(screen.getByRole("button", { name: "Use latest saved content" }));
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue("Body a-r2"));
  expect(screen.getByRole("button", { name: "Saved" })).toBeDisabled();
  expect(localStorage.getItem("noye-document-draft:a")).toBeNull();
  expect(sourceDocs.editSourceDocument).not.toHaveBeenCalled();
});


it("a pending reload after conflict review cannot replace the next acknowledged save", async () => {
  const reload = deferred<sourceDocs.SourceDocument>();
  const old = makeSourceDoc("a");
  const saved = makeSourceDoc("a", "r3");
  saved.content = "Body a-r2 edited"; saved.revision.content = saved.content;
  saved.revisions.unshift({ id: "r3", origin: "user", title: saved.title, created_at: "2026-10-08" });
  vi.mocked(sourceDocs.readSourceDocument).mockResolvedValueOnce(old).mockResolvedValueOnce(old).mockReturnValueOnce(reload.promise);
  vi.mocked(sourceDocs.editSourceDocument).mockResolvedValue(saved);
  render(<DocumentsPage />);
  await userEvent.type(await screen.findByLabelText(/Document content/), " edited");
  await userEvent.click(screen.getByRole("button", { name: "Compare with latest revision" }));
  await screen.findByLabelText("Latest saved Markdown");
  await userEvent.click(screen.getByRole("button", { name: "Reapply my draft to this revision" }));
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByRole("button", { name: "Saved" });
  await act(async () => reload.resolve(old));
  expect(screen.getByRole("combobox", { name: "Revision" })).toHaveValue("r3");
  expect(screen.getByLabelText(/Document content/)).toHaveValue(saved.content);
});
