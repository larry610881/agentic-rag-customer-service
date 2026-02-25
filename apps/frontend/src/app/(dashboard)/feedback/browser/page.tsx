"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useFeedbackList } from "@/hooks/queries/use-feedback";
import { FeedbackBrowserTable } from "@/features/feedback/components/feedback-browser-table";

export default function FeedbackBrowserPage() {
  const { data, isLoading } = useFeedbackList(200);

  return (
    <div className="h-full overflow-auto flex flex-col gap-6 p-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/feedback">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h2 className="text-2xl font-semibold">差評瀏覽器</h2>
      </div>
      <FeedbackBrowserTable data={data} isLoading={isLoading} />
    </div>
  );
}
