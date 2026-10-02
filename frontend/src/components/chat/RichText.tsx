import { Check } from "@phosphor-icons/react/ssr";
import type { ReactNode } from "react";

/**
 * Renders Domi's short structured answers:
 *   a lead line, then "- " bullets ("+ " for a plus point), "1. " lines as small headings.
 * Anything else is a paragraph. Plain text only: no HTML is ever injected.
 */
type Block =
  | { kind: "p"; text: string }
  | { kind: "heading"; text: string }
  | { kind: "list"; items: { marker: "dot" | "plus"; text: string }[] };

function parse(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const bullet = line.match(/^([-+•])\s+(.*)$/);
    if (bullet) {
      const item = { marker: bullet[1] === "+" ? ("plus" as const) : ("dot" as const), text: bullet[2] };
      const last = blocks.at(-1);
      if (last?.kind === "list") last.items.push(item);
      else blocks.push({ kind: "list", items: [item] });
    } else if (/^\d+\.\s+/.test(line)) {
      blocks.push({ kind: "heading", text: line });
    } else {
      blocks.push({ kind: "p", text: line });
    }
  }
  return blocks;
}

const isFinePrint = (t: string) => /loan offer|^Monthly payment assumes|^\(I assumed/.test(t);

export function RichText({ text }: { text: string }) {
  const blocks = parse(text);
  const leadIdx = blocks.findIndex((b) => b.kind === "p" && !isFinePrint(b.text));
  const out: ReactNode[] = blocks.map((b, i) => {
    if (b.kind === "heading")
      return (
        <p key={i} className="pt-1 text-[14px] font-semibold text-ink">
          {b.text}
        </p>
      );
    if (b.kind === "list")
      return (
        <ul key={i} className="space-y-1.5">
          {b.items.map((it, j) => (
            <li key={j} className="flex gap-2.5 text-[14px] leading-snug text-ink-soft">
              {it.marker === "plus" ? (
                <Check size={15} weight="bold" className="mt-0.5 shrink-0 text-sage-ink" aria-hidden />
              ) : (
                <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-sage-strong" aria-hidden />
              )}
              <span>{it.text}</span>
            </li>
          ))}
        </ul>
      );
    if (isFinePrint(b.text))
      return (
        <p key={i} className="text-xs leading-snug text-muted">
          {b.text}
        </p>
      );
    const lead = i === leadIdx;
    return (
      <p key={i} className={`text-[14px] leading-relaxed ${lead ? "font-medium text-ink" : "text-ink-soft"}`}>
        {b.text}
      </p>
    );
  });
  return <div className="space-y-2.5">{out}</div>;
}
