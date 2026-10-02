"use client";

import React, { useState } from "react";
import { Copy, Check } from "lucide-react";

interface FormattedQuestionTextProps {
  text: string;
  className?: string;
}

// Decode HTML entities
function decodeHtmlEntities(str: string): string {
  if (!str) return "";
  return str
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&#x2F;/gi, "/")
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t");
}

// Transform LaTeX / Math symbols inside math tokens into clean readable typography
function formatMathSymbols(mathStr: string): string {
  return mathStr
    .replace(/\\times/g, " × ")
    .replace(/\\cdot/g, " · ")
    .replace(/\\le\b|\\leq\b/g, " ≤ ")
    .replace(/\\ge\b|\\geq\b/g, " ≥ ")
    .replace(/\\ne\b|\\neq\b/g, " ≠ ")
    .replace(/\\approx\b/g, " ≈ ")
    .replace(/\\to\b|\\rightarrow\b/g, " → ")
    .replace(/\\gets\b|\\leftarrow\b/g, " ← ")
    .replace(/\\dots\b|\\ldots\b|\\cdots\b/g, "...")
    .replace(/\\in\b/g, " ∈ ")
    .replace(/\\notin\b/g, " ∉ ")
    .replace(/\\subset\b/g, " ⊂ ")
    .replace(/\\subseteq\b/g, " ⊆ ")
    .replace(/\\cup\b/g, " ∪ ")
    .replace(/\\cap\b/g, " ∩ ")
    .replace(/\\infty\b/g, "∞")
    .replace(/\\pm\b/g, " ± ")
    .replace(/\\sum\b/g, "∑")
    .replace(/\\prod\b/g, "∏")
    .replace(/\\sqrt\{([^}]+)\}/g, "√($1)")
    .replace(/\\sqrt/g, "√")
    .replace(/\\alpha\b/g, "α")
    .replace(/\\beta\b/g, "β")
    .replace(/\\theta\b/g, "θ")
    .replace(/\\pi\b/g, "π")
    .replace(/\\lambda\b/g, "λ")
    .replace(/\\Delta\b/g, "Δ")
    .replace(/\\log\b/g, "log")
    .replace(/\\max\b/g, "max")
    .replace(/\\min\b/g, "min")
    .replace(/10\^([0-9]+)/g, (_, exp) => {
      const superscripts: Record<string, string> = {
        "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
        "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻"
      };
      return `10${exp.split("").map((c: string) => superscripts[c] || c).join("")}`;
    })
    .replace(/\^([0-9]+)/g, (_, exp) => {
      const superscripts: Record<string, string> = {
        "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
        "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"
      };
      return exp.split("").map((c: string) => superscripts[c] || c).join("");
    })
    .replace(/\\{/g, "{")
    .replace(/\\}/g, "}")
    .replace(/\\/g, "");
}

// Inline Formatter for text (handles $math$, `code`, **bold**, *italic*)
function renderInlineContent(content: string, keyPrefix: string): React.ReactNode[] {
  const tokenRegex = /(\$\$[\s\S]+?\$\$|\$[^\$\n]+?\$|`[^`\n]+?`|\*\*[^*]+?\*\*|__[^_]+?__|\*[^*\n]+?\*)/g;
  const parts = content.split(tokenRegex);

  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (!part) return null;

    // Double dollar math $$...$$
    if (part.startsWith("$$") && part.endsWith("$$") && part.length >= 4) {
      const raw = part.slice(2, -2).trim();
      const formatted = formatMathSymbols(raw);
      return (
        <span key={key} className="my-1 inline-block px-2 py-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--accent-text)] font-mono text-xs font-semibold">
          {formatted}
        </span>
      );
    }

    // Single dollar math $...$
    if (part.startsWith("$") && part.endsWith("$") && part.length >= 2) {
      const raw = part.slice(1, -1).trim();
      const formatted = formatMathSymbols(raw);
      return (
        <span key={key} className="inline-block px-1.5 py-0.2 mx-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--accent-text)] font-mono text-xs font-medium">
          {formatted}
        </span>
      );
    }

    // Inline code `...`
    if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
      const codeText = part.slice(1, -1);
      return (
        <code key={key} className="px-1.5 py-0.5 mx-0.5 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] text-[var(--accent-text)] font-mono text-[11px] font-semibold">
          {codeText}
        </code>
      );
    }

    // Bold **...**
    if ((part.startsWith("**") && part.endsWith("**") && part.length >= 4) ||
        (part.startsWith("__") && part.endsWith("__") && part.length >= 4)) {
      const boldText = part.slice(2, -2);
      return (
        <strong key={key} className="font-bold text-[var(--text-primary)]">
          {renderInlineContent(boldText, `${key}-b`)}
        </strong>
      );
    }

    // Italic *...*
    if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
      const italicText = part.slice(1, -1);
      return (
        <em key={key} className="italic text-[var(--text-secondary)]">
          {renderInlineContent(italicText, `${key}-i`)}
        </em>
      );
    }

    // Plain text
    return <span key={key}>{part}</span>;
  }).filter(Boolean);
}

function CodeBlockRenderer({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative my-2.5 rounded-md bg-[var(--bg-subtle)] border border-[var(--border-subtle)] overflow-hidden text-left">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[var(--bg-surface)] border-b border-[var(--border-subtle)] text-[11px] font-mono text-[var(--text-muted)]">
        <span className="uppercase tracking-wider">{language || "Code"}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-[var(--text-primary)] transition px-2 py-0.5 rounded bg-[var(--bg-subtle)] hover:bg-[var(--bg-hover)] focus-visible:outline-none"
          aria-label="Copy code block"
        >
          {copied ? <Check className="w-3 h-3 text-[var(--status-success-text)]" /> : <Copy className="w-3 h-3" />}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto font-mono text-xs text-[var(--text-primary)] leading-relaxed">
        {code}
      </pre>
    </div>
  );
}

export function FormattedQuestionText({ text, className = "" }: FormattedQuestionTextProps) {
  if (!text) return null;

  const decoded = decodeHtmlEntities(text);

  // Split text by code blocks ```lang ... ```
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(decoded)) !== null) {
    const beforeText = decoded.substring(lastIndex, match.index);
    if (beforeText) {
      elements.push(renderParagraphs(beforeText, `txt-${lastIndex}`));
    }
    const lang = match[1] || "";
    const code = match[2];
    elements.push(<CodeBlockRenderer key={`code-${match.index}`} code={code} language={lang} />);
    lastIndex = match.index + match[0].length;
  }

  const remainingText = decoded.substring(lastIndex);
  if (remainingText) {
    elements.push(renderParagraphs(remainingText, `txt-${lastIndex}`));
  }

  return (
    <div className={`space-y-2.5 font-sans text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed text-left ${className}`}>
      {elements}
    </div>
  );
}

function renderParagraphs(rawText: string, keyPrefix: string): React.ReactNode {
  const lines = rawText.split("\n");
  const blocks: React.ReactNode[] = [];
  let currentList: { type: "ul" | "ol"; items: string[] } | null = null;
  let currentParaLines: string[] = [];

  const flushParagraph = (idx: number) => {
    if (currentParaLines.length > 0) {
      const joined = currentParaLines.join("\n").trim();
      if (joined) {
        blocks.push(
          <p key={`${keyPrefix}-p-${idx}`} className="leading-relaxed whitespace-pre-line text-[var(--text-primary)]">
            {renderInlineContent(joined, `${keyPrefix}-p-${idx}`)}
          </p>
        );
      }
      currentParaLines = [];
    }
  };

  const flushList = (idx: number) => {
    if (currentList && currentList.items.length > 0) {
      if (currentList.type === "ul") {
        blocks.push(
          <ul key={`${keyPrefix}-ul-${idx}`} className="my-2 space-y-1 pl-4 list-none">
            {currentList.items.map((item, itemIdx) => (
              <li key={`${keyPrefix}-ul-${idx}-li-${itemIdx}`} className="flex items-start gap-2 text-[var(--text-secondary)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)] mt-2 shrink-0" />
                <span className="flex-1 leading-relaxed">
                  {renderInlineContent(item, `${keyPrefix}-ul-${idx}-${itemIdx}`)}
                </span>
              </li>
            ))}
          </ul>
        );
      } else {
        blocks.push(
          <ol key={`${keyPrefix}-ol-${idx}`} className="my-2 space-y-1 pl-2 list-none">
            {currentList.items.map((item, itemIdx) => (
              <li key={`${keyPrefix}-ol-${idx}-li-${itemIdx}`} className="flex items-start gap-2 text-[var(--text-secondary)]">
                <span className="text-[10px] font-mono font-bold text-[var(--accent-text)] px-1 py-0.2 rounded bg-[var(--bg-subtle)] border border-[var(--border-subtle)] mt-0.5 shrink-0">
                  {itemIdx + 1}
                </span>
                <span className="flex-1 leading-relaxed">
                  {renderInlineContent(item, `${keyPrefix}-ol-${idx}-${itemIdx}`)}
                </span>
              </li>
            ))}
          </ol>
        );
      }
      currentList = null;
    }
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    if (trimmed.startsWith("### ")) {
      flushList(idx);
      flushParagraph(idx);
      blocks.push(
        <h4 key={`${keyPrefix}-h4-${idx}`} className="font-bold text-xs sm:text-sm text-[var(--text-primary)] pt-1">
          {renderInlineContent(trimmed.substring(4), `${keyPrefix}-h4-${idx}`)}
        </h4>
      );
      return;
    }

    if (trimmed.startsWith("## ")) {
      flushList(idx);
      flushParagraph(idx);
      blocks.push(
        <h3 key={`${keyPrefix}-h3-${idx}`} className="font-bold text-sm sm:text-base text-[var(--text-primary)] pt-2">
          {renderInlineContent(trimmed.substring(3), `${keyPrefix}-h3-${idx}`)}
        </h3>
      );
      return;
    }

    if (trimmed.startsWith("# ")) {
      flushList(idx);
      flushParagraph(idx);
      blocks.push(
        <h2 key={`${keyPrefix}-h2-${idx}`} className="font-bold text-base sm:text-lg text-[var(--text-primary)] pt-3">
          {renderInlineContent(trimmed.substring(2), `${keyPrefix}-h2-${idx}`)}
        </h2>
      );
      return;
    }

    // Check for unordered bullet item
    const ulMatch = line.match(/^(\s*)([-*•])\s+(.+)$/);
    if (ulMatch) {
      flushParagraph(idx);
      if (!currentList || currentList.type !== "ul") {
        flushList(idx);
        currentList = { type: "ul", items: [] };
      }
      currentList.items.push(ulMatch[3]);
      return;
    }

    // Check for ordered list item
    const olMatch = line.match(/^(\s*)([0-9]+)\.\s+(.+)$/);
    if (olMatch) {
      flushParagraph(idx);
      if (!currentList || currentList.type !== "ol") {
        flushList(idx);
        currentList = { type: "ol", items: [] };
      }
      currentList.items.push(olMatch[3]);
      return;
    }

    if (trimmed === "") {
      flushList(idx);
      flushParagraph(idx);
      return;
    }

    flushList(idx);
    currentParaLines.push(line);
  });

  flushList(lines.length);
  flushParagraph(lines.length);

  return <React.Fragment key={keyPrefix}>{blocks}</React.Fragment>;
}

export default FormattedQuestionText;
