"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  Bot,
  BookOpen,
  BarChart3,
  Settings,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useSidebarStore } from "@/stores/use-sidebar-store";

const navItems = [
  { href: "/chat", label: "對話", icon: MessageSquare },
  { href: "/bots", label: "機器人", icon: Bot },
  { href: "/knowledge", label: "知識庫", icon: BookOpen },
  { href: "/feedback", label: "回饋分析", icon: BarChart3 },
  { href: "/settings", label: "設定", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const isCollapsed = useSidebarStore((s) => s.isCollapsed);
  const toggle = useSidebarStore((s) => s.toggle);

  return (
    <aside
      className={cn(
        "flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-200",
        isCollapsed ? "w-14" : "w-60",
      )}
    >
      <div className="flex h-14 items-center justify-between border-b px-3">
        {!isCollapsed && (
          <h1 className="truncate text-lg font-semibold">RAG 智能客服</h1>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0"
          onClick={toggle}
        >
          {isCollapsed ? (
            <ChevronsRight className="h-4 w-4" />
          ) : (
            <ChevronsLeft className="h-4 w-4" />
          )}
        </Button>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-2">
        {navItems.map((item) => {
          const isActive = pathname?.startsWith(item.href);
          const button = (
            <Button
              key={item.href}
              variant={isActive ? "secondary" : "ghost"}
              className={cn(
                isCollapsed ? "justify-center px-0" : "justify-start",
                isActive && "bg-sidebar-accent",
              )}
              asChild
            >
              <Link href={item.href}>
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
        })}
      </nav>
    </aside>
  );
}
