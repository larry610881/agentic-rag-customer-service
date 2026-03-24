import { useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export type AssertionResultData = {
  passed: boolean;
  assertion_type: string;
  message: string;
};

export type CaseResultData = {
  case_id: string;
  question: string;
  priority: string;
  category: string;
  score: number;
  passed_count: number;
  total_count: number;
  p0_failed: boolean;
  answer_snippet: string;
  assertion_results: AssertionResultData[];
};

type CaseResultsTableProps = {
  caseResults: CaseResultData[] | undefined;
};

export function CaseResultsTable({ caseResults }: CaseResultsTableProps) {
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  if (!caseResults || caseResults.length === 0) return null;

  return (
    <div className="mt-4">
      <p className="mb-2 text-xs font-medium text-muted-foreground">
        測試案例結果
      </p>
      {(() => {
        const errorCount = caseResults.filter(
          (c) => !c.answer_snippet && c.score === 0
        ).length;
        return errorCount > 0 ? (
          <div className="mb-2 rounded border border-red-200 bg-red-50 px-3 py-1.5 text-xs text-red-600 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400">
            {errorCount}/{caseResults.length} 個案例 API 呼叫失敗（回答為空）
          </div>
        ) : null;
      })()}
      <div className="rounded border">
        {/* Header */}
        <div className="grid grid-cols-[1fr_60px_70px_70px_70px] gap-2 border-b bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
          <span>案例</span>
          <span>優先級</span>
          <span>分數</span>
          <span>通過</span>
          <span>狀態</span>
        </div>
        {/* Rows */}
        {caseResults.map((cr) => {
          const isExpanded = expandedCase === cr.case_id;
          const isApiError = !cr.answer_snippet && cr.score === 0;
          const statusLabel = isApiError
            ? "API 錯誤"
            : cr.p0_failed
              ? "P0 FAIL"
              : cr.score >= 1
                ? "PASS"
                : "FAIL";
          const statusColor = isApiError
            ? "text-red-500 font-medium"
            : cr.p0_failed
              ? "text-red-600 font-medium"
              : cr.score >= 1
                ? "text-green-600"
                : "text-orange-500";

          return (
            <div key={cr.case_id} className="border-b last:border-b-0">
              <button
                className={`grid w-full grid-cols-[1fr_60px_70px_70px_70px] gap-2 px-3 py-1.5 text-left text-xs hover:bg-muted/50 transition-colors ${isApiError ? "bg-red-50 dark:bg-red-950/20" : ""}`}
                onClick={() =>
                  setExpandedCase(isExpanded ? null : cr.case_id)
                }
              >
                <span className="flex items-center gap-1 truncate">
                  {isExpanded ? (
                    <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                  )}
                  {cr.case_id}
                </span>
                <Badge variant="outline" className="w-fit text-[10px]">
                  {cr.priority}
                </Badge>
                <span>{cr.score.toFixed(2)}</span>
                <span>
                  {cr.passed_count}/{cr.total_count}
                </span>
                <span className={statusColor}>{statusLabel}</span>
              </button>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="space-y-3 border-t bg-muted/10 px-4 py-3 text-xs">
                  <div>
                    <span className="font-medium text-muted-foreground">
                      問題：
                    </span>
                    <span>{cr.question}</span>
                  </div>
                  <div>
                    <span className="font-medium text-muted-foreground">
                      AI 回答：
                    </span>
                    <pre className="mt-1 max-h-[200px] overflow-auto whitespace-pre-wrap rounded bg-muted/20 p-2">
                      {cr.answer_snippet || "(空)"}
                    </pre>
                  </div>
                  {cr.assertion_results.length > 0 && (
                    <div className="space-y-1">
                      <span className="font-medium text-muted-foreground">
                        斷言結果：
                      </span>
                      {cr.assertion_results.map((ar, j) => (
                        <div key={j} className="flex items-center gap-2 pl-1">
                          {ar.passed ? (
                            <CheckCircle2 className="h-3 w-3 shrink-0 text-green-500" />
                          ) : (
                            <XCircle className="h-3 w-3 shrink-0 text-red-400" />
                          )}
                          <span className="font-medium">
                            {ar.assertion_type}
                          </span>
                          <span className="text-muted-foreground">
                            {ar.message}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
