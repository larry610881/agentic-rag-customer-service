import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  MessageSquare,
  Bot,
  BookOpen,
  BarChart3,
  ScrollText,
  Coins,
  Puzzle,
  Users,
  ChevronsLeft,
  ChevronsRight,
  Shield,
  ChevronDown,
  ChevronRight,
  Layers,
  Building,
  Plug,
  FileText,
  Stethoscope,
  Gauge,
  Trash2,
  AlertTriangle,
  Bell,
  Wand2,
  Wrench,
  Package,
  DollarSign,
  Database,
  MessagesSquare,
  Wallet,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useSidebarStore } from "@/stores/use-sidebar-store";
import { useAuthStore } from "@/stores/use-auth-store";

const generalNavItems = [
  { href: "/chat", label: "對話", icon: MessageSquare },
  { href: "/bots", label: "機器人", icon: Bot },
  { href: "/knowledge", label: "知識庫", icon: BookOpen },
  { href: "/feedback", label: "回饋分析", icon: BarChart3 },
  { href: "/token-usage", label: "Token 用量", icon: Coins },
  { href: "/quota", label: "本月額度", icon: Wallet },
];

// S-ConvInsights.1 follow-up: 25 項 flat list → 5 大類 collapsible
interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}
interface NavGroup {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  items: NavItem[];
}

const systemAdminGroups: NavGroup[] = [
  {
    key: "billing",
    label: "租戶與計費",
    icon: Building,
    items: [
      { href: "/admin/tenants", label: "租戶管理", icon: Building },
      { href: "/admin/plans", label: "方案管理", icon: Package },
      { href: "/admin/pricing", label: "定價管理", icon: DollarSign },
      { href: "/admin/quota-overview", label: "額度總覽", icon: Wallet },
      { href: "/admin/quota-events", label: "額度事件", icon: Bell },
      { href: "/admin/billing", label: "收益儀表板", icon: TrendingUp },
      { href: "/admin/token-usage", label: "Token 用量", icon: Coins },
    ],
  },
  {
    key: "content",
    label: "內容資產",
    icon: BookOpen,
    items: [
      { href: "/admin/knowledge-bases", label: "所有知識庫", icon: BookOpen },
      { href: "/admin/bots", label: "所有機器人", icon: Bot },
      { href: "/admin/milvus", label: "Milvus 管理", icon: Database },
      { href: "/admin/conversations", label: "對話與追蹤", icon: MessagesSquare },
    ],
  },
  {
    key: "ai-config",
    label: "AI 設定",
    icon: Plug,
    items: [
      { href: "/settings/providers", label: "供應商設定", icon: Plug },
      { href: "/admin/prompts", label: "系統提示詞", icon: FileText },
      { href: "/admin/mcp-registry", label: "MCP 工具庫", icon: Puzzle },
      { href: "/admin/tools", label: "工具權限", icon: Wrench },
      { href: "/admin/prompt-optimizer", label: "Prompt 自動優化", icon: Wand2 },
    ],
  },
  {
    key: "security",
    label: "安全與治理",
    icon: Shield,
    items: [
      { href: "/admin/guard-rules", label: "安全規則", icon: Shield },
      { href: "/admin/diagnostic-rules", label: "診斷規則", icon: Stethoscope },
      { href: "/admin/rate-limits", label: "速率限制", icon: Gauge },
      { href: "/admin/error-events", label: "錯誤追蹤", icon: AlertTriangle },
    ],
  },
  {
    key: "ops",
    label: "平台運維",
    icon: Wrench,
    items: [
      { href: "/admin/users", label: "帳號管理", icon: Users },
      { href: "/admin/logs", label: "系統日誌", icon: ScrollText },
      { href: "/admin/log-retention", label: "日誌清理", icon: Trash2 },
      { href: "/admin/notification-channels", label: "通知渠道", icon: Bell },
    ],
  },
];

export function Sidebar() {
  const { pathname } = useLocation();
  const isCollapsed = useSidebarStore((s) => s.isCollapsed);
  const toggle = useSidebarStore((s) => s.toggle);
  const role = useAuthStore((s) => s.role);
  const tenants = useAuthStore((s) => s.tenants);
  const tenantId = useAuthStore((s) => s.tenantId);
  const [generalOpen, setGeneralOpen] = useState(true);

  // 預設全部展開；依 pathname 找到當前 group 即使使用者手動折疊也保持展開
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(systemAdminGroups.map((g) => [g.key, true])),
  );

  const isSystemAdmin = role === "system_admin";
  const sidebarTitle = isSystemAdmin
    ? "系統管理"
    : (tenants.find((t) => t.id === tenantId)?.name ?? "AI 客服");

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-primary/20 bg-sidebar text-sidebar-foreground transition-all duration-200",
        isCollapsed ? "w-14" : "w-60",
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-primary/20 px-3">
        {!isCollapsed && (
          <h1 className="truncate text-lg font-semibold font-heading tracking-wider text-primary">
            {sidebarTitle}
          </h1>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0 hover:text-primary transition-colors duration-150"
          onClick={toggle}
        >
          {isCollapsed ? (
            <ChevronsRight className="h-4 w-4" />
          ) : (
            <ChevronsLeft className="h-4 w-4" />
          )}
        </Button>
      </div>
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto scrollbar-none p-2">
        {isSystemAdmin ? (
          <>
            {systemAdminGroups.map((group) => {
              const isGroupActive = group.items.some((i) =>
                pathname?.startsWith(i.href),
              );
              // 若當前頁在此 group 內，強制展開（覆寫使用者手動折疊）
              const isOpen = isGroupActive || openGroups[group.key];
              return (
                <div key={group.key}>
                  <NavSection
                    label={group.label}
                    icon={group.icon}
                    open={isOpen}
                    onToggle={() =>
                      setOpenGroups((prev) => ({
                        ...prev,
                        [group.key]: !isOpen,
                      }))
                    }
                    isCollapsed={isCollapsed}
                  />
                  {isOpen &&
                    group.items.map((item) =>
                      renderNavItem(item, pathname, isCollapsed),
                    )}
                </div>
              );
            })}
            <div className="my-1 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
            <NavSection
              label="一般功能"
              icon={Layers}
              open={generalOpen}
              onToggle={() => setGeneralOpen(!generalOpen)}
              isCollapsed={isCollapsed}
            />
            {generalOpen && generalNavItems.map((item) => renderNavItem(item, pathname, isCollapsed))}
          </>
        ) : (
          <>
            {generalNavItems.map(
              (item) => renderNavItem(item, pathname, isCollapsed),
            )}
          </>
        )}
      </nav>
    </aside>
  );
}

function NavSection({
  label,
  icon: Icon,
  open,
  onToggle,
  isCollapsed,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  open: boolean;
  onToggle: () => void;
  isCollapsed: boolean;
}) {
  if (isCollapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            onClick={onToggle}
            className="flex h-8 w-full items-center justify-center rounded-md text-muted-foreground hover:bg-muted/50 transition-colors duration-150"
          >
            <Icon className="h-3.5 w-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <button
      onClick={onToggle}
      className="flex items-center gap-1.5 px-3 pb-1 pt-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors duration-150"
    >
      <Icon className="h-3 w-3" />
      {label}
      {open ? <ChevronDown className="ml-auto h-3 w-3" /> : <ChevronRight className="ml-auto h-3 w-3" />}
    </button>
  );
}

function renderNavItem(
  item: { href: string; label: string; icon: React.ComponentType<{ className?: string }> },
  pathname: string,
  isCollapsed: boolean,
) {
  const isActive = pathname?.startsWith(item.href);
  const button = (
    <Button
      key={item.href}
      variant={isActive ? "secondary" : "ghost"}
      className={cn(
        isCollapsed ? "justify-center px-0" : "justify-start",
        isActive && "bg-sidebar-accent border-l-2 border-primary text-primary",
        !isActive && "hover:text-primary",
      )}
      asChild
    >
      <Link to={item.href}>
        <item.icon className="h-4 w-4 shrink-0" />
        {!isCollapsed && <span className="ml-2">{item.label}</span>}
      </Link>
    </Button>
  );

  if (isCollapsed) {
    return (
      <Tooltip key={item.href}>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="right">{item.label}</TooltipContent>
      </Tooltip>
    );
  }

  return button;
}
