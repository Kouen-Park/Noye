import { Passages } from "@/components/chat/passages";
import type { ChatMessage } from "@/lib/api";

/**
 * One turn in a conversation.
 *
 * A question sits right-aligned on the brand colour; an answer is a card on the
 * left, so the two are distinguishable without reading. A failed turn is neither:
 * it is a bordered notice carrying the reason, because the user's question is
 * still there above it and what they need to know is why it went unanswered.
 */

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <li className="mb-3 flex justify-end">
        <div className="max-w-[46ch] rounded-lg rounded-br-sm bg-brand px-3.5 py-2.5 text-[14.5px] text-ink-inverse">
          <p className="whitespace-pre-wrap">{message.content}</p>
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
    <li className="mb-3">
      <div className="max-w-[68ch] rounded-lg rounded-bl-sm border border-edge-strong bg-card px-3.5 py-2.5">
        <p className="whitespace-pre-wrap text-[14.5px] leading-relaxed">{message.content}</p>
        <Passages citations={message.citations} />
      </div>
    </li>
  );
}
