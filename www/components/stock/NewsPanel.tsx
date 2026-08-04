"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { fetchStockNews } from "@/lib/api";

function sentimentChip(sentiment: number | null) {
  if (sentiment === null) return null;
  if (sentiment >= 0.15) {
    return { label: `호재 +${sentiment.toFixed(2)}`, className: "text-up bg-up-weak border-up/20" };
  }
  if (sentiment <= -0.15) {
    return { label: `악재 ${sentiment.toFixed(2)}`, className: "text-down bg-down-weak border-down/20" };
  }
  return { label: `중립 ${sentiment.toFixed(2)}`, className: "text-foreground-muted bg-surface border-border" };
}

function formatDate(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
}

export default function NewsPanel({ symbol }: { symbol: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["stock-news", symbol],
    queryFn: () => fetchStockNews(symbol),
    enabled: !!symbol,
  });

  if (isLoading) {
    return (
      <div className="p-4 flex flex-col gap-2">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="skeleton h-16 rounded-lg" />
        ))}
      </div>
    );
  }
  if (isError || !data || data.length === 0) {
    return (
      <p className="p-4 text-sm text-foreground-muted">
        수집된 뉴스가 없습니다. 워치리스트 종목의 뉴스가 주기적으로 쌓입니다.
      </p>
    );
  }

  return (
    <ul className="p-4 flex flex-col gap-2">
      {data.map((item) => {
        const chip = sentimentChip(item.sentiment);
        return (
          <li key={item.id}>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block bg-surface border border-border rounded-lg p-3 hover:border-brand/40 transition-colors"
            >
              <p className="text-sm leading-snug">{item.title}</p>
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-foreground-muted">
                <span>{item.source}</span>
                {item.publishedAt && <span>· {formatDate(item.publishedAt)}</span>}
                {chip && (
                  <span className={`inline-flex px-1.5 py-0.5 rounded-md border font-medium ${chip.className}`}>
                    {chip.label}
                  </span>
                )}
                {item.eventType && (
                  <span className="inline-flex px-1.5 py-0.5 rounded-md border border-border bg-background">
                    {item.eventType}
                  </span>
                )}
                <ExternalLink size={11} className="ml-auto shrink-0" />
              </div>
            </a>
          </li>
        );
      })}
    </ul>
  );
}
