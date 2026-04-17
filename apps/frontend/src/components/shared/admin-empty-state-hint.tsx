import { Link } from "react-router-dom";
import { ArrowRight, Info } from "lucide-react";

import { useAuthStore } from "@/stores/use-auth-store";

type AdminResource = "bots" | "knowledge-bases" | "conversations" | "feedback" | "token-usage";

const RESOURCE_CONFIG: Record<
  AdminResource,
  { label: string; adminPath: string; cta: string }
> = {
  bots: {
    label: "機器人",
    adminPath: "/admin/bots",
    cta: "前往系統管理 → 所有機器人",
  },
  "knowledge-bases": {
    label: "知識庫",
    adminPath: "/admin/knowledge-bases",
    cta: "前往系統管理 → 所有知識庫",
  },
  conversations: {
    label: "對話",
    adminPath: "/admin/observability",
    cta: "前往系統管理 → 可觀測性",
  },
  feedback: {
    label: "回饋",
    adminPath: "/admin/observability",
    cta: "前往系統管理 → 可觀測性",
  },
  "token-usage": {
    label: "Token 用量",
    adminPath: "/admin/token-usage",
    cta: "前往系統管理 → Token 用量",
  },
};

type AdminEmptyStateHintProps = {
  resource: AdminResource;
  isEmpty: boolean;
};

/**
 * S-Gov.3: 系統管理員以 SYSTEM 租戶身份登入一般功能頁時，
 * 若列表空白則顯示指引，引導至「系統管理」區查跨租戶資料。
 * 非 admin 或列表非空時不顯示。
 */
export const AdminEmptyStateHint = ({
  resource,
  isEmpty,
}: AdminEmptyStateHintProps) => {
  const role = useAuthStore((s) => s.role);

  if (role !== "system_admin" || !isEmpty) return null;

  const { label, adminPath, cta } = RESOURCE_CONFIG[resource];

  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-border bg-muted/40 p-4 shadow-sm"
    >
      <Info className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden />
      <div className="flex flex-col gap-2 text-sm">
        <p className="text-foreground">
          您目前以 <strong>系統租戶</strong> 身份登入，此頁僅顯示系統租戶的{label}。
          如需查看或管理跨租戶資料，請使用系統管理區。
        </p>
        <Link
          to={adminPath}
          className="inline-flex items-center gap-1 font-medium text-primary hover:underline underline-offset-4"
        >
          {cta}
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>
    </div>
  );
};
