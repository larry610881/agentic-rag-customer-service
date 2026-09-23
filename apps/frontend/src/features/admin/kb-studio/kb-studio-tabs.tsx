import { cn } from "@/lib/utils";
import {
  KB_STUDIO_TABS,
  type KbStudioTab,
} from "@/features/admin/kb-studio/kb-studio-tab-state";


interface TabsProps {
  active: KbStudioTab;
  onChange: (tab: KbStudioTab) => void;
}

export function KbStudioTabs({ active, onChange }: TabsProps) {
  return (
    <div className="border-b">
      <nav className="flex gap-1 -mb-px overflow-x-auto">
        {KB_STUDIO_TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={cn(
              "px-3 py-2 text-sm whitespace-nowrap border-b-2 transition-colors",
              active === t.key
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
