"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const navItems = [
  { href: "/chat", label: "Chat" },
  { href: "/bots", label: "Bots" },
  { href: "/knowledge", label: "Knowledge" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 flex-col border-r bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 items-center border-b px-4">
        <h1 className="text-lg font-semibold">RAG Customer Service</h1>
      </div>
      <nav className="flex flex-col gap-1 p-2">
        {navItems.map((item) => (
          <Button
            key={item.href}
            variant={pathname?.startsWith(item.href) ? "secondary" : "ghost"}
            className={cn(
              "justify-start",
              pathname?.startsWith(item.href) && "bg-sidebar-accent",
            )}
            asChild
          >
            <Link href={item.href}>{item.label}</Link>
          </Button>
        ))}
      </nav>
    </aside>
  );
}
