import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface PromptDiffProps {
  before: string;
  after: string;
  title?: string;
}

interface DiffLine {
  type: "unchanged" | "added" | "removed";
  text: string;
}

function computeDiff(before: string, after: string): DiffLine[] {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  const result: DiffLine[] = [];

  const maxLen = Math.max(beforeLines.length, afterLines.length);
  let bi = 0;
  let ai = 0;

  while (bi < beforeLines.length || ai < afterLines.length) {
    if (bi < beforeLines.length && ai < afterLines.length) {
      if (beforeLines[bi] === afterLines[ai]) {
        result.push({ type: "unchanged", text: beforeLines[bi] });
        bi++;
        ai++;
      } else {
        // Look ahead to find if the before line appears later in after
        let foundInAfter = -1;
        let foundInBefore = -1;
        const lookAhead = Math.min(5, maxLen);

        for (let j = ai + 1; j < Math.min(ai + lookAhead, afterLines.length); j++) {
          if (beforeLines[bi] === afterLines[j]) {
            foundInAfter = j;
            break;
          }
        }
        for (let j = bi + 1; j < Math.min(bi + lookAhead, beforeLines.length); j++) {
          if (afterLines[ai] === beforeLines[j]) {
            foundInBefore = j;
            break;
          }
        }

        if (foundInAfter !== -1 && (foundInBefore === -1 || foundInAfter - ai <= foundInBefore - bi)) {
          // Lines were added
          while (ai < foundInAfter) {
            result.push({ type: "added", text: afterLines[ai] });
            ai++;
          }
        } else if (foundInBefore !== -1) {
          // Lines were removed
          while (bi < foundInBefore) {
            result.push({ type: "removed", text: beforeLines[bi] });
            bi++;
          }
        } else {
          result.push({ type: "removed", text: beforeLines[bi] });
          result.push({ type: "added", text: afterLines[ai] });
          bi++;
          ai++;
        }
      }
    } else if (bi < beforeLines.length) {
      result.push({ type: "removed", text: beforeLines[bi] });
      bi++;
    } else {
      result.push({ type: "added", text: afterLines[ai] });
      ai++;
    }
  }

  return result;
}

export function PromptDiff({ before, after, title }: PromptDiffProps) {
  const diffLines = useMemo(() => computeDiff(before, after), [before, after]);

  return (
    <Card>
      {title && (
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className={title ? "" : "pt-6"}>
        <div className="max-h-[400px] overflow-auto rounded-md border bg-muted/20 p-3 font-mono text-sm">
          {diffLines.map((line, i) => (
            <div
              key={i}
              className={
                line.type === "added"
                  ? "bg-green-500/15 text-green-400"
                  : line.type === "removed"
                    ? "bg-red-500/15 text-red-400"
                    : "text-muted-foreground"
              }
            >
              <span className="mr-2 inline-block w-4 select-none text-right opacity-60">
                {line.type === "added" ? "+" : line.type === "removed" ? "-" : " "}
              </span>
              {line.text || "\u00A0"}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
