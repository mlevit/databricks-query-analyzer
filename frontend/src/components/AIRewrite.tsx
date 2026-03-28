import { useCallback, useState } from "react";
import { rewriteQuery } from "../api";
import type { AIRewriteResult } from "../types";

interface Props {
  statementId: string;
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setCopyError(false);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError(true);
      setTimeout(() => setCopyError(false), 2000);
    }
  }, [text]);

  return (
    <button
      className="copy-btn"
      onClick={handleCopy}
      aria-label={`Copy ${label} to clipboard`}
    >
      {copied ? (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <rect x="5" y="5" width="8" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M3 11V3.5C3 2.67 3.67 2 4.5 2H10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      )}
      {copyError ? "Failed" : copied ? "Copied" : "Copy"}
    </button>
  );
}

// ---- Simple line-level diff (Myers-like LCS) ----

type DiffLine = { type: "equal" | "added" | "removed"; text: string };

function computeDiff(a: string, b: string): DiffLine[] {
  const aLines = a.split("\n");
  const bLines = b.split("\n");

  if (aLines.length > 500 || bLines.length > 500) {
    return [{ type: "equal", text: "(Query too large for inline diff)" }];
  }

  const lcs = buildLCS(aLines, bLines);
  const result: DiffLine[] = [];
  let ai = 0;
  let bi = 0;

  for (const [la, lb] of lcs) {
    while (ai < la) result.push({ type: "removed", text: aLines[ai++] });
    while (bi < lb) result.push({ type: "added", text: bLines[bi++] });
    result.push({ type: "equal", text: aLines[ai] });
    ai++;
    bi++;
  }
  while (ai < aLines.length) result.push({ type: "removed", text: aLines[ai++] });
  while (bi < bLines.length) result.push({ type: "added", text: bLines[bi++] });

  return result;
}

function buildLCS(a: string[], b: string[]): [number, number][] {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (a[i].trim() === b[j].trim()) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const pairs: [number, number][] = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (a[i].trim() === b[j].trim()) {
      pairs.push([i, j]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      i++;
    } else {
      j++;
    }
  }
  return pairs;
}

function DiffView({ original, suggested }: { original: string; suggested: string }) {
  const lines = computeDiff(original, suggested);

  if (lines.every((l) => l.type === "equal")) {
    return (
      <div className="diff-view">
        <p className="diff-view__identical">No differences — the suggested query is identical.</p>
      </div>
    );
  }

  return (
    <div className="diff-view">
      <pre className="diff-view__code">
        {lines.map((line, i) => (
          <div key={i} className={`diff-line diff-line--${line.type}`}>
            <span className="diff-line__marker">
              {line.type === "added" ? "+" : line.type === "removed" ? "−" : " "}
            </span>
            <span className="diff-line__text">{line.text || " "}</span>
          </div>
        ))}
      </pre>
    </div>
  );
}

// ---- Explanation formatting ----

function formatExplanation(text: string) {
  const lines = text.split("\n").filter((l) => l.trim());

  return lines.map((line, i) => {
    const rendered = inlineBold(line.trim());

    const numberedMatch = line.match(/^\s*(\d+)\.\s+(.*)/);
    if (numberedMatch) {
      return (
        <div key={i} className="ai-rewrite__point">
          <span className="ai-rewrite__point-num">{numberedMatch[1]}.</span>
          <span>{inlineBold(numberedMatch[2])}</span>
        </div>
      );
    }

    const bulletMatch = line.match(/^\s*[-•]\s+(.*)/);
    if (bulletMatch) {
      return (
        <div key={i} className="ai-rewrite__point">
          <span className="ai-rewrite__point-num">&bull;</span>
          <span>{inlineBold(bulletMatch[1])}</span>
        </div>
      );
    }

    return <p key={i}>{rendered}</p>;
  });
}

function inlineBold(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={i}>{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

// ---- Main component ----

export default function AIRewrite({ statementId }: Props) {
  const [result, setResult] = useState<AIRewriteResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRewrite = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await rewriteQuery(statementId);
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Rewrite failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel ai-rewrite">
      <h2>AI Query Rewrite</h2>
      <p className="ai-rewrite__desc">
        Use Claude to analyze the query and suggest an optimized version based on
        the identified issues.
      </p>

      {!result && (
        <button
          className="ai-rewrite__btn"
          onClick={handleRewrite}
          disabled={loading}
        >
          {loading ? "Generating..." : "Generate AI Rewrite"}
        </button>
      )}

      {error && <p className="ai-rewrite__error" role="alert">{error}</p>}

      {result && (
        <div className="ai-rewrite__result">
          <div className="ai-rewrite__explanation">
            <h3>Explanation</h3>
            <div className="ai-rewrite__explanation-body">
              {formatExplanation(result.explanation)}
            </div>
          </div>
          <div className="ai-rewrite__section">
            <h3>Diff</h3>
            <DiffView original={result.original_sql} suggested={result.suggested_sql} />
          </div>
          <div className="ai-rewrite__columns">
            <div className="ai-rewrite__col">
              <h3>Original</h3>
              <div className="ai-rewrite__code-wrap">
                <CopyButton text={result.original_sql} label="original query" />
                <pre><code>{result.original_sql}</code></pre>
              </div>
            </div>
            <div className="ai-rewrite__col">
              <h3>Suggested</h3>
              <div className="ai-rewrite__code-wrap">
                <CopyButton text={result.suggested_sql} label="suggested query" />
                <pre><code>{result.suggested_sql}</code></pre>
              </div>
            </div>
          </div>
          <button className="ai-rewrite__btn" onClick={handleRewrite} disabled={loading}>
            {loading ? "Regenerating..." : "Regenerate"}
          </button>
        </div>
      )}
    </div>
  );
}
