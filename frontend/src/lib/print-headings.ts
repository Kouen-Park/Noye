/** Keep a heading and its first content block together in WebKit printing.
 * Only the document preview opts in; every original node remains in order. */
type Node = {
  type: string;
  tagName?: string;
  value?: string;
  properties?: Record<string, unknown>;
  children?: Node[];
};

export function groupPrintHeadings() {
  return function transform(parent: Node) {
    if (!parent.children) return;
    for (const child of parent.children) transform(child);
    const children = parent.children;
    const grouped: Node[] = [];
    for (let i = 0; i < children.length; i++) {
      const heading = children[i];
      let next = i + 1;
      while (children[next]?.type === "text" && !children[next].value?.trim()) next++;
      const following = children[next];
      if (heading.type === "element" && /^h[123]$/.test(heading.tagName ?? "")
        && following?.type === "element" && /^(p|ul|ol|blockquote)$/.test(following.tagName ?? "")) {
        const imageOnly = following.tagName === "p"
          && following.children?.some(child => child.type === "element" && child.tagName === "img")
          && following.children.every(child => child.type === "text" ? !child.value?.trim() : child.tagName === "img");
        grouped.push({ type: "element", tagName: "div", properties: {
          className: ["noye-heading-block", ...(imageOnly ? ["noye-image-heading"] : [])],
        },
          children: children.slice(i, next + 1) });
        i = next;
      } else grouped.push(heading);
    }
    parent.children = grouped;
  };
}
