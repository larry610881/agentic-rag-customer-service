import { Check, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";

export type CircularProgressStatus = "uploading" | "success" | "error";

export type CircularProgressProps = {
  value: number;
  size?: number;
  strokeWidth?: number;
  status?: CircularProgressStatus;
  ariaLabel?: string;
  className?: string;
};

const STATUS_COLOR: Record<CircularProgressStatus, string> = {
  uploading: "text-primary",
  success: "text-emerald-500",
  error: "text-destructive",
};

export function CircularProgress({
  value,
  size = 64,
  strokeWidth = 6,
  status = "uploading",
  ariaLabel,
  className,
}: CircularProgressProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);
  const colorClass = STATUS_COLOR[status];

  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={ariaLabel}
      data-status={status}
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="absolute inset-0"
      >
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          className="text-muted/30"
          fill="none"
          strokeWidth={strokeWidth}
        />
        {/* Progress arc */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          className={colorClass}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          strokeDasharray={circumference}
          initial={false}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.3, ease: [0, 0, 0.2, 1] }}
        />
      </svg>
      <span
        className={cn(
          "relative flex items-center justify-center text-xs font-medium",
          colorClass,
        )}
      >
        {status === "success" ? (
          <Check aria-label="上傳成功" className="size-4" />
        ) : status === "error" ? (
          <AlertCircle aria-label="上傳失敗" className="size-4" />
        ) : (
          <span>{clamped}%</span>
        )}
      </span>
    </div>
  );
}
