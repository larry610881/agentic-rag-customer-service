import { Fragment } from "react";
import { Link } from "react-router-dom";
import {
  Breadcrumb,
  BreadcrumbEllipsis,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { cn } from "@/lib/utils";

export type BreadcrumbEntry =
  | { label: string; to: string; onClick?: never }
  | { label: string; onClick: () => void; to?: never }
  | { label: string; to?: undefined; onClick?: undefined };

export interface PageBreadcrumbProps {
  items: BreadcrumbEntry[];
  /** 超過此長度的 label 會截斷並補 `...`，原文保留在 `title` attribute */
  maxLabelLength?: number;
  className?: string;
}

const DEFAULT_MAX_LABEL_LENGTH = 24;

interface RenderSegment {
  entry: BreadcrumbEntry;
  isCurrent: boolean;
  key: string;
}

function truncate(label: string, max: number): { display: string; truncated: boolean } {
  if (label.length <= max) return { display: label, truncated: false };
  return { display: label.slice(0, Math.max(0, max - 3)) + "...", truncated: true };
}

function renderSegment({ entry, isCurrent }: RenderSegment, maxLabelLength: number) {
  const { display, truncated } = truncate(entry.label, maxLabelLength);
  const titleAttr = truncated ? entry.label : undefined;

  if (isCurrent) {
    return (
      <BreadcrumbPage title={titleAttr}>{display}</BreadcrumbPage>
    );
  }

  if (entry.to) {
    return (
      <BreadcrumbLink asChild>
        <Link to={entry.to} title={titleAttr}>
          {display}
        </Link>
      </BreadcrumbLink>
    );
  }

  if (entry.onClick) {
    return (
      <BreadcrumbLink asChild>
        <button
          type="button"
          onClick={entry.onClick}
          title={titleAttr}
          className="cursor-pointer bg-transparent p-0 text-inherit underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 rounded-sm"
        >
          {display}
        </button>
      </BreadcrumbLink>
    );
  }

  return (
    <span className="text-muted-foreground" title={titleAttr}>
      {display}
    </span>
  );
}

export function PageBreadcrumb({
  items,
  maxLabelLength = DEFAULT_MAX_LABEL_LENGTH,
  className,
}: PageBreadcrumbProps) {
  if (items.length === 0) return null;

  const lastIndex = items.length - 1;
  // 在超過 3 層時，中段（索引 1 到 lastIndex-2）折疊為 ellipsis
  const shouldCollapse = items.length > 3;
  const visibleIndices: number[] = shouldCollapse
    ? [0, lastIndex - 1, lastIndex]
    : items.map((_, i) => i);

  return (
    <Breadcrumb className={className}>
      <BreadcrumbList>
        {visibleIndices.map((idx, visualIdx) => {
          const entry = items[idx];
          const isCurrent = idx === lastIndex;
          const segment = renderSegment(
            { entry, isCurrent, key: String(idx) },
            maxLabelLength,
          );

          // 在折疊模式下，於索引 0 與 lastIndex-1 之間插入 ellipsis
          const showEllipsisAfter =
            shouldCollapse && visualIdx === 0 && idx === 0;

          return (
            <Fragment key={idx}>
              <BreadcrumbItem className={cn(isCurrent && "text-foreground")}>
                {segment}
              </BreadcrumbItem>
              {showEllipsisAfter && (
                <>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbEllipsis />
                  </BreadcrumbItem>
                </>
              )}
              {visualIdx < visibleIndices.length - 1 && (
                <BreadcrumbSeparator />
              )}
            </Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
