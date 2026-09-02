/** Issue #60 — config hash 色塊：同 hash 同色、顯示前 12 碼、hover 看全文、可複製 */

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { hashChipStyle, shortHash } from "@/features/admin/lib/config-hash";

interface ConfigHashChipProps {
  hash: string;
  /** 顯示複製按鈕 */
  copyable?: boolean;
  className?: string;
}

export function ConfigHashChip({
  hash,
  copyable = false,
  className,
}: ConfigHashChipProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      toast.success("已複製設定 hash");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("複製失敗");
    }
  };

  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span
        data-testid="config-hash-chip"
        title={hash}
        style={hashChipStyle(hash)}
        className="inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-xs"
      >
        {shortHash(hash)}
      </span>
      {copyable && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          aria-label="複製 hash"
          onClick={handleCopy}
        >
          {copied ? (
            <Check className="h-3 w-3 text-green-600" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
        </Button>
      )}
    </span>
  );
}
