import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import DocumentsPage from '@/app/documents/page';
import * as docs from '@/lib/api';
import * as wiki from '@/lib/wiki';
import * as sourceDocs from '@/lib/source-documents';

const nav = vi.hoisted(() => ({ query: '', push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams(nav.query), useRouter: () => nav }));
vi.mock('@/components/app-shell', async () => {
  const { useState } = await import('react');
  return {
    AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
    useWorkspaceLayout: () => { const [readingFocus, setReadingFocus] = useState(false); return { readingFocus, setReadingFocus }; },
  };
});
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
it('repeated focus changes preserve a pending source save, draft owner and base', async () => {
  const pending = deferred<sourceDocs.SourceDocument>();
  vi.mocked(sourceDocs.readSourceDocument).mockResolvedValue(makeSourceDoc('a'));
  vi.mocked(sourceDocs.editSourceDocument).mockReturnValue(pending.promise);
  render(<DocumentsPage />);
  const content = await screen.findByLabelText(/Document content/);
  await userEvent.type(content, ' 한글 authored');
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  const retained = localStorage.getItem('noye-document-draft:a');
  const editor = screen.getByRole('region', { name: 'Document editor' });
  const loads = vi.mocked(sourceDocs.readSourceDocument).mock.calls.length;
  await userEvent.click(screen.getByRole('button', { name: 'Focus reading' }));
  expect(screen.queryByRole('complementary', { name: 'Document list' })).not.toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Document editor' })).toBe(editor);
  expect(screen.getByLabelText(/Document content/)).toBe(content);
  expect(content).toHaveValue('Body a-r2 한글 authored');
  expect(localStorage.getItem('noye-document-draft:a')).toBe(retained);
  await userEvent.click(screen.getByRole('button', { name: 'Focus reading' }));
  expect(screen.getByRole('complementary', { name: 'Document list' })).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Focus reading' }));
  await userEvent.click(screen.getByRole('button', { name: 'Focus reading' }));
  expect(screen.getByLabelText(/Document content/)).toBe(content);
  expect(localStorage.getItem('noye-document-draft:a')).toBe(retained);
  expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled();
  expect(sourceDocs.readSourceDocument).toHaveBeenCalledTimes(loads);
  expect(nav.query).toBe('d=a');
  expect(sourceDocs.editSourceDocument).toHaveBeenCalledWith('a', 'r2', { title: 'Document a', content: 'Body a-r2 한글 authored' });
  await userEvent.type(content, ' later');
  const saved = makeSourceDoc('a', 'r3');
  saved.content = saved.revision.content = 'Body a-r2 한글 authored';
  saved.revisions.unshift({ id: 'r3', origin: 'user', title: saved.title, created_at: '2026-10-08' });
  await act(async () => pending.resolve(saved));
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body a-r2 한글 authored later'));
  expect(JSON.parse(localStorage.getItem('noye-document-draft:a')!).expectedRevision).toBe('r3');
  expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
});
it('focus reading keeps the selected historical document revision read only', async () => {
  vi.mocked(sourceDocs.readSourceDocument).mockImplementation(async (_id, revision) => makeSourceDoc('a', revision ?? 'r2'));
  render(<DocumentsPage />);
  await screen.findByLabelText(/Document content/);
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Revision' }), 'r1');
  await waitFor(() => expect(screen.getByLabelText(/Document content/)).toHaveValue('Body a-r1'));
  const content = screen.getByLabelText(/Document content/);
  const loads = vi.mocked(sourceDocs.readSourceDocument).mock.calls.length;
  await userEvent.click(screen.getByRole('button', { name: 'Focus reading' }));
  await userEvent.click(screen.getByRole('button', { name: 'Focus reading' }));
  await userEvent.click(screen.getByRole('button', { name: 'Focus reading' }));
  await userEvent.click(screen.getByRole('button', { name: 'Focus reading' }));
  expect(screen.getByLabelText(/Document content/)).toBe(content);
  expect(content).toHaveAttribute('readonly');
  expect(screen.getByRole('combobox', { name: 'Revision' })).toHaveValue('r1');
  expect(sourceDocs.readSourceDocument).toHaveBeenCalledTimes(loads);
  expect(sourceDocs.editSourceDocument).not.toHaveBeenCalled();
});
it('uses one optional details row while preserving the source draft and visible partial status', async () => {
  const document = makeSourceDoc('a');
  document.source_instruction = 'Write retained notes';
  document.revision.metadata.coverage.partial = true;
  document.revision.metadata.coverage.presentation_limits = [{ code: 'language_limit', reason: 'Translation remains unresolved.' }];
  vi.mocked(sourceDocs.readSourceDocument).mockResolvedValue(document);
  const { container } = render(<DocumentsPage />);
  const content = await screen.findByLabelText(/Document content/);
  await userEvent.type(content, ' 한국어 retained');
  const editor = screen.getByRole('region', { name: 'Document editor' });
  const retained = localStorage.getItem('noye-document-draft:a');
  const summary = screen.getByText('Details · 0 evidence passages · review limits');
  const disclosure = summary.closest('details')!;
  expect(container.querySelectorAll('.noye-work-pane > .noye-work-details')).toHaveLength(1);
  expect(disclosure).not.toHaveAttribute('open');
  expect(screen.getAllByText('Partial document')[0].closest('details')).toBeNull();
  await userEvent.click(summary);
  await userEvent.click(screen.getByText(/Originals, coverage and saved evidence/));
  expect(screen.getByText('Translation remains unresolved.')).toBeInTheDocument();
  await userEvent.click(summary);
  expect(disclosure).not.toHaveAttribute('open');
  expect(screen.getByRole('region', { name: 'Document editor' })).toBe(editor);
  expect(screen.getByLabelText(/Document content/)).toBe(content);
  expect(content).toHaveValue('Body a-r2 한국어 retained');
  expect(localStorage.getItem('noye-document-draft:a')).toBe(retained);
  expect(sourceDocs.readSourceDocument).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('combobox', { name: 'Revision' })).toHaveValue('r2');
});
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
it.each([
  ['  Renamed  ', 'Renamed'],
  ['', 'Document a'],
])('settles the legacy saved baseline for title %j', async (draftTitle, savedTitle) => {
  render(<DocumentsPage />);
  await screen.findByLabelText(/Document content/);
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: draftTitle } });
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  await screen.findByRole('button', { name: 'Saved' });
  expect(docs.updateDocument).toHaveBeenCalledWith('a', { title: savedTitle, content: 'Body a' });
  expect(screen.getByLabelText('Title')).toHaveValue(savedTitle);
  expect(screen.queryByText('Unsaved changes')).not.toBeInTheDocument();
  expect(localStorage.getItem('noye-document-draft:a')).toBeNull();
});
it('keeps newer title and body typing while a trimmed legacy title save is pending', async () => {
  const pending = deferred<docs.NoyeDocument>();
  vi.mocked(docs.updateDocument).mockReturnValueOnce(pending.promise);
  render(<DocumentsPage />);
  await screen.findByLabelText(/Document content/);
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: '  Renamed  ' } });
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  await userEvent.type(screen.getByLabelText('Title'), ' later');
  await userEvent.type(screen.getByLabelText(/Document content/), ' later body');
  await act(async () => pending.resolve({ ...makeDoc('a'), title: 'Renamed' }));
  expect(screen.getByLabelText('Title')).toHaveValue('Renamed later');
  expect(screen.getByLabelText(/Document content/)).toHaveValue('Body a later body');
  expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
  expect(JSON.parse(localStorage.getItem('noye-document-draft:a')!)).toMatchObject({ title: 'Renamed later', content: 'Body a later body' });
});
it('keeps a normalized authored title dirty when its legacy save fails', async () => {
  vi.mocked(docs.updateDocument).mockRejectedValueOnce(new docs.ApiError(500, 'Save failed'));
  render(<DocumentsPage />);
  await screen.findByLabelText(/Document content/);
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: '  Renamed  ' } });
  await userEvent.click(screen.getByRole('button', { name: 'Save' }));
  await screen.findByText('Save failed');
  expect(screen.getByLabelText('Title')).toHaveValue('Renamed');
  expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled();
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

it('shows pending documents instead of an empty library while the first list is loading', async () => {
  nav.query = '';
  const pending = deferred<docs.DocumentSummary[]>();
  vi.mocked(docs.listDocuments).mockReturnValueOnce(pending.promise);
  render(<DocumentsPage />);
  expect(screen.getByText('Loading documents…')).toBeInTheDocument();
  expect(screen.queryByText('Nothing written yet.')).not.toBeInTheDocument();
  await act(async () => pending.resolve(summaries));
  expect(screen.getByRole('button', { name: 'Open Document a' })).toBeInTheDocument();
  expect(screen.queryByText('Loading documents…')).not.toBeInTheDocument();
});
it('retries a failed initial list without calling it an empty workspace', async () => {
  nav.query = '';
  vi.mocked(docs.listDocuments).mockRejectedValueOnce(new docs.ApiError(503, 'Library temporarily unavailable')).mockResolvedValueOnce([]);
  render(<DocumentsPage />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Library temporarily unavailable');
  expect(screen.queryByText('Nothing written yet.')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Retry documents' }));
  await screen.findByText('Nothing written yet.');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
it('creates only one document for repeated clicks while creation is pending', async () => {
  nav.query = '';
  const pending = deferred<docs.NoyeDocument>();
  vi.mocked(docs.createDocument).mockReturnValueOnce(pending.promise);
  render(<DocumentsPage />);
  const button = screen.getByRole('button', { name: 'New' });
  act(() => { fireEvent.click(button); fireEvent.click(button); });
  expect(docs.createDocument).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Creating…' })).toBeDisabled();
  await act(async () => pending.resolve(makeDoc('new')));
  await waitFor(() => expect(screen.getByRole('button', { name: 'New' })).toBeEnabled());
  expect(nav.push).toHaveBeenCalledExactlyOnceWith('/documents?d=new');
});
it('keeps the refreshed new document when an older initial list returns later', async () => {
  nav.query = '';
  const initial = deferred<docs.DocumentSummary[]>();
  const newSummary = { ...summaries[0], id: 'new', title: 'Document new' };
  vi.mocked(docs.listDocuments).mockReturnValueOnce(initial.promise).mockResolvedValueOnce([newSummary]);
  vi.mocked(docs.createDocument).mockResolvedValueOnce(makeDoc('new'));
  render(<DocumentsPage />);
  await userEvent.click(screen.getByRole('button', { name: 'New' }));
  await screen.findByRole('button', { name: 'Open Document new' });
  await act(async () => initial.resolve(summaries));
  expect(screen.getByRole('button', { name: 'Open Document new' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Open Document a' })).not.toBeInTheDocument();
});
it('reports an opening document while its known URL is still loading', async () => {
  const pending = deferred<docs.NoyeDocument>();
  vi.mocked(docs.readDocument).mockReturnValueOnce(pending.promise);
  render(<DocumentsPage />);
  expect(screen.getByText('Opening document…')).toBeInTheDocument();
  expect(screen.queryByText('Nothing open')).not.toBeInTheDocument();
  await act(async () => pending.resolve(makeDoc('a')));
  await screen.findByDisplayValue('Body a');
  expect(screen.queryByText('Opening document…')).not.toBeInTheDocument();
});
it('enables another explicit creation attempt after a failed request', async () => {
  nav.query = '';
  vi.mocked(docs.createDocument).mockRejectedValueOnce(new docs.ApiError(503, 'Creation unavailable')).mockResolvedValueOnce(makeDoc('retry'));
  render(<DocumentsPage />);
  await userEvent.click(screen.getByRole('button', { name: 'New' }));
  await screen.findByText('Creation unavailable');
  expect(screen.getByRole('button', { name: 'New' })).toBeEnabled();
  await userEvent.click(screen.getByRole('button', { name: 'New' }));
  await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/documents?d=retry'));
  expect(docs.createDocument).toHaveBeenCalledTimes(2);
});
