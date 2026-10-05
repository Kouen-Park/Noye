import { Passages } from "@/components/chat/passages";
import { CreateDocumentAction } from "@/components/documents/create-document-action";
import { MarkdownContent } from "@/components/documents/document-preview";
import type { ChatMessage } from "@/lib/api";

/**
 * One turn in a conversation.
 *
 * Questions are compact bubbles; answers read as an unboxed column of prose.
 * The inspection callback moves retrieved metadata into the workspace panel;
 * the inline disclosure remains available to other consumers.
 */

export function MessageBubble({ message, onInspect, inspected = false, panelId }: {
  message: ChatMessage;
  onInspect?: (message: ChatMessage, button: HTMLButtonElement) => void;
  inspected?: boolean;
  panelId?: string;
}) {
  if (message.role === "user") {
    return (
      <li className="flex justify-end py-4">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm border border-edge-strong bg-card px-4 py-3 text-[15px] leading-relaxed">
          <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{message.content}</p>
        </div>
      </li>
    );
  }

  if (message.error !== null) {
    return (
      <li className="mb-3">
        <div className="max-w-[68ch] rounded-lg border border-fail bg-fail-wash px-3.5 py-2.5">
          <p className="text-[13px] font-semibold text-fail">This went unanswered</p>
          <p className="mt-1 text-[12.5px] text-fail">{message.error}</p>
          <p className="mt-1.5 text-[12.5px] text-ink-soft">
            Your question is still here. Ask again once it is working.
          </p>
        </div>
      </li>
    );
  }

  return (
    <li className="py-5">
      <div>
        <p className="mb-2 text-[12px] font-semibold tracking-wide text-brand">Noye</p>
        <div className="text-[15px] leading-7"><MarkdownContent content={message.content} allowImages={false} /></div>
        {onInspect ? message.citations.length > 0 && (
          <button type="button" onClick={(event) => onInspect(message, event.currentTarget)}
            aria-expanded={inspected} aria-controls={inspected ? panelId : undefined}
            className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-md border border-edge-strong px-3 text-xs font-semibold text-brand hover:bg-brand-wash">
            <span aria-hidden="true" className="grid h-5 min-w-5 place-items-center rounded-sm bg-brand px-1 font-mono text-[10px] text-ink-inverse">{message.citations.length}</span>
            {message.citations.length === 1 ? "Passage consulted" : "Passages consulted"}
          </button>
        ) : <Passages citations={message.citations} />}
        {/* Offered only on an answer with something in it — there is nothing to
            make a document from otherwise, and the API refuses it anyway. */}
        {message.content.trim() !== "" && <CreateDocumentAction messageId={message.id} />}
      </div>
    </li>
  );
}
