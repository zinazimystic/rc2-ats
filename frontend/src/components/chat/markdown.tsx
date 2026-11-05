"use client";
import { memo, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";
import { copyText } from "./clipboard";

/** Close dangling inline syntax in a partially streamed reply so it doesn't flicker. */
export function healMarkdown(src: string): string {
  let s = src;
  const fences = s.match(/^ {0,3}(```|~~~)/gm);
  if (fences && fences.length % 2 === 1) return s; // inside an open fence: renders as code until it closes
  s = s.replace(/\[([^\]\n]*)\]\([^)\n]*$/, "$1"); // half-typed link -> plain text
  s = s.replace(/\[[^\]\n]*$/, (m) => m.slice(1)); // dangling "[text"
  const lastLine = s.slice(s.lastIndexOf("\n") + 1);
  if ((lastLine.match(/`/g)?.length ?? 0) % 2 === 1) s += "`";
  if ((lastLine.match(/\*\*/g)?.length ?? 0) % 2 === 1) s += "**";
  return s;
}

function toText(n: ReactNode): string {
  if (typeof n === "string" || typeof n === "number") return String(n);
  if (Array.isArray(n)) return n.map(toText).join("");
  if (n && typeof n === "object" && "props" in n) return toText((n as { props: { children?: ReactNode } }).props.children);
  return "";
}

function CodeBlock({ children }: { children: ReactNode }) {
  const [done, setDone] = useState(false);
  const text = toText(children).replace(/\n$/, "");
  return (
    <div className="group/code relative my-2 overflow-hidden rounded-xl border bg-muted/60">
      <button
        type="button"
        aria-label={done ? "Copied" : "Copy code"}
        title={done ? "Copied" : "Copy code"}
        onClick={async () => {
          if (await copyText(text)) {
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          }
        }}
        className="absolute top-1.5 right-1.5 inline-flex size-7 items-center justify-center rounded-lg bg-card/90 text-muted-foreground opacity-70 shadow-sm transition hover:text-foreground focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-ring group-hover/code:opacity-100"
      >
        {done ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
      </button>
      <pre className="overflow-x-auto p-3 pr-10 font-mono text-[12.5px] leading-relaxed">{children}</pre>
    </div>
  );
}

const H3 = ({ children }: { children?: ReactNode }) => <h3 className="mt-3 mb-1 text-sm font-semibold">{children}</h3>;
const H4 = ({ children }: { children?: ReactNode }) => <h4 className="mt-3 mb-1 text-[13px] font-semibold">{children}</h4>;

function buildComponents(onNavigate: () => void): Components {
  return {
    h1: H3, h2: H3, h3: H3, h4: H4, h5: H4, h6: H4,
    p: ({ children }) => <p className="my-2 leading-relaxed">{children}</p>,
    ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
    ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
    li: ({ children }) => <li className="pl-0.5">{children}</li>,
    blockquote: ({ children }) => <blockquote className="my-2 border-l-2 border-primary/40 pl-3 text-muted-foreground">{children}</blockquote>,
    hr: () => <hr className="my-3 border-border" />,
    img: () => null,
    pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
    code: ({ className, children }) =>
      className ? (
        <code className={className}>{children}</code>
      ) : (
        <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.85em]">{children}</code>
      ),
    table: ({ children }) => (
      <div className="my-2 max-w-full overflow-x-auto rounded-xl border">
        <table className="w-full border-collapse text-left text-[13px]">{children}</table>
      </div>
    ),
    th: ({ children }) => <th className="border-b bg-muted/60 px-2.5 py-1.5 font-semibold whitespace-nowrap">{children}</th>,
    td: ({ children }) => <td className="border-b px-2.5 py-1.5 align-top">{children}</td>,
    a: ({ href, children }) => {
      const h = (href ?? "").trim();
      const cls = "font-medium text-primary underline underline-offset-2 hover:opacity-80 [overflow-wrap:anywhere]";
      if (h.startsWith("/") && !h.startsWith("//") && !h.includes("\\"))
        return (
          <Link href={h} onClick={onNavigate} className={cls}>
            {children}
          </Link>
        );
      if (/^https:\/\/\S+$/i.test(h))
        return (
          <a href={h} target="_blank" rel="noopener noreferrer" className={cls}>
            {children}
          </a>
        );
      return <span>{children}</span>;
    },
  };
}

function MarkdownImpl({ text, streaming, onNavigate }: { text: string; streaming: boolean; onNavigate: () => void }) {
  const components = useMemo(() => buildComponents(onNavigate), [onNavigate]);
  const src = streaming ? healMarkdown(text) : text;
  return (
    <div className={`rc-md text-sm ${streaming ? "rc-streaming" : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} skipHtml>
        {src}
      </ReactMarkdown>
    </div>
  );
}
export const Markdown = memo(MarkdownImpl);
