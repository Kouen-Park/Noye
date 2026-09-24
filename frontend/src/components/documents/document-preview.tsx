import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * The rendered document.
 *
 * `react-markdown` rather than a string-to-HTML renderer, per the plan's §13.2.
 * The content is model-generated, then user-edited, and derived from the user's own
 * files — so something that looks like a script tag could reach here by way of an
 * ingested PDF and the model. A `marked`-style renderer produces HTML that has to
 * go through `dangerouslySetInnerHTML`, which makes sanitisation a thing someone
 * must remember; this builds a React element tree and renders no raw HTML at all,
 * so the safe behaviour is the default.
 *
 * `data-print="document"` is what the print stylesheet keeps. Everything without
 * it is hidden when printing, so the PDF is the document rather than the
 * application around it — and a control added later is hidden by default rather
 * than silently appearing in someone's export.
 *
 * Styles are applied per element rather than through a typography plugin, so the
 * document uses the same tokens as the rest of Noye and needs no extra dependency.
 */

export function DocumentPreview({ content }: { content: string }) {
  if (!content.trim()) {
    return (
      <p className="text-[13.5px] text-ink-soft">
        Nothing to preview yet. What you write appears here.
      </p>
    );
  }

  return (
    <div data-print="document" className="max-w-[72ch] text-[14.5px] leading-relaxed">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (props) => (
            <h1 className="mb-3 mt-5 font-display text-[22px] first:mt-0" {...props} />
          ),
          h2: (props) => (
            <h2 className="mb-2 mt-5 font-display text-[18px] first:mt-0" {...props} />
          ),
          h3: (props) => (
            <h3 className="mb-1.5 mt-4 text-[15px] font-semibold text-ink" {...props} />
          ),
          p: (props) => <p className="mb-3" {...props} />,
          ul: (props) => <ul className="mb-3 ml-5 list-disc space-y-1" {...props} />,
          ol: (props) => <ol className="mb-3 ml-5 list-decimal space-y-1" {...props} />,
          li: (props) => <li className="pl-0.5" {...props} />,
          strong: (props) => <strong className="font-semibold" {...props} />,
          blockquote: (props) => (
            <blockquote
              className="mb-3 border-l-2 border-accent pl-3 text-ink-soft"
              {...props}
            />
          ),
          code: (props) => (
            <code
              className="rounded-sm bg-sunken px-1 py-0.5 font-mono text-[13px]"
              {...props}
            />
          ),
          pre: (props) => (
            <pre
              className="mb-3 overflow-x-auto rounded-md border border-edge bg-sunken p-3 font-mono text-[12.5px]"
              {...props}
            />
          ),
          a: (props) => (
            <a
              className="text-accent-ink underline"
              target="_blank"
              rel="noopener noreferrer"
              {...props}
            />
          ),
          hr: () => <hr className="my-5 border-edge" />,
          table: (props) => (
            <div className="mb-3 overflow-x-auto">
              <table className="w-full border-collapse text-[13.5px]" {...props} />
            </div>
          ),
          th: (props) => (
            <th
              className="border border-edge-strong bg-sunken px-2 py-1 text-left font-semibold"
              {...props}
            />
          ),
          td: (props) => <td className="border border-edge px-2 py-1" {...props} />,
        }}
      >
        {content}
      </Markdown>
    </div>
  );
}
