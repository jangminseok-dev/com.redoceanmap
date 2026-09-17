"use client";

import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// 접힌 채로 시작하는 단락의 머리(백엔드가 코드로 쓰는 표기와 같아야 한다 — chat compare·stock_report).
// 결론·한눈에 판단·고지·등급 안내는 항상 보이고, 근거 표·세부 수치·못 쓴 데이터만 접는다.
// 2026-09-17 실사용: 답이 2천~1만 자로 깊어지자 결론이 표에 묻혔다.
const COLLAPSIBLE = [
  "**세부 근거**",
  "**전체 지표**",
  "**이번 비교에 못 쓴 데이터**",
  "**이 리포트에 못 쓴 데이터**",
  "**상권 성격·추이·진단·기사**",
];

// 본문의 [n] 인용 마커를 근거 번호 배지로 — 뉴스 근거 목록의 번호와 같다
export function withCitations(text: string): ReactNode {
  return text.split(/(\[\d+\])/g).map((part, i) => {
    const marker = /^\[(\d+)\]$/.exec(part);
    if (!marker) return part;
    return (
      <sup key={i} title={`근거 ${marker[1]}번`} className="ml-0.5 text-[10px] font-semibold text-brand tabular-nums">
        [{marker[1]}]
      </sup>
    );
  });
}

const cite = (children: ReactNode): ReactNode =>
  Array.isArray(children)
    ? children.map((c, i) => (typeof c === "string" ? <span key={i}>{withCitations(c)}</span> : c))
    : typeof children === "string"
      ? withCitations(children)
      : children;

function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // 줄바꿈 하나도 줄로 보이게(목록이 아닌 "1. …" 행·※ 안내가 한 줄로 뭉치지 않게)
        p: ({ children }) => <p className="whitespace-pre-wrap [&:not(:first-child)]:mt-2">{cite(children)}</p>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        ul: ({ children }) => <ul className="mt-1.5 list-disc pl-5 flex flex-col gap-1">{children}</ul>,
        ol: ({ children }) => <ol className="mt-1.5 list-decimal pl-5 flex flex-col gap-1">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{cite(children)}</li>,
        table: ({ children }) => (
          <div className="mt-2 overflow-x-auto rounded-lg border border-border">
            <table className="min-w-full text-xs tabular-nums">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="px-2 py-1.5 text-left font-medium bg-accent whitespace-nowrap border-b border-border">{children}</th>
        ),
        td: ({ children }) => <td className="px-2 py-1.5 align-top border-b border-border">{cite(children)}</td>,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand underline">
            {children}
          </a>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

export default function AnswerBody({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="mt-3 text-sm text-foreground leading-relaxed flex flex-col gap-2">
      {blocks.map((block, i) => {
        const head = COLLAPSIBLE.find((h) => block.startsWith(h));
        if (!head) return <Markdown key={i} text={block} />;
        // 머리 줄 전체(예: "**전체 지표** — 커피-음료, 2026년 2분기 기준")를 요약으로, 나머지를 접힌 본문으로
        const [first, ...rest] = block.split("\n");
        return (
          <details key={i} className="rounded-lg border border-border bg-background">
            <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-foreground-muted">
              {first.replaceAll("**", "")} <span className="font-normal">(눌러서 펼치기)</span>
            </summary>
            <div className="px-3 pb-2.5">
              <Markdown text={rest.join("\n")} />
            </div>
          </details>
        );
      })}
    </div>
  );
}
