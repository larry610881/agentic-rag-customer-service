import { Phone } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ContactCard } from "@/types/chat";

export interface ContactCardButtonProps {
  contact: ContactCard | undefined;
  className?: string;
}

/**
 * Contact button rendered for the `transfer_to_human_agent` tool's output.
 * Phone type uses `tel:` and stays in-page (iOS / Android 會直撥)。
 * URL type opens a new tab.
 */
export function ContactCardButton({
  contact,
  className,
}: ContactCardButtonProps) {
  if (!contact) return null;

  const label = contact.label?.trim() || "聯絡客服";
  const isPhone = contact.type === "phone";
  const href =
    isPhone && !contact.url.startsWith("tel:")
      ? `tel:${contact.url}`
      : contact.url;

  const linkProps = isPhone
    ? {}
    : { target: "_blank", rel: "noopener noreferrer" };

  return (
    <div className={cn("ml-0 sm:ml-4", className)}>
      <a
        href={href}
        {...linkProps}
        className={cn(
          "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm",
          "bg-primary text-primary-foreground",
          "transition-all duration-150",
          "hover:shadow-md hover:brightness-110",
          "active:scale-95",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
        )}
      >
        <Phone className="h-4 w-4" aria-hidden />
        <span className="font-medium">{label}</span>
      </a>
    </div>
  );
}
