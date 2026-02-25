"use client";

import { useState } from "react";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { FeedbackResponse, Rating } from "@/types/feedback";

interface FeedbackBrowserTableProps {
  data: FeedbackResponse[] | undefined;
  isLoading: boolean;
}

const PAGE_SIZE = 10;

export function FeedbackBrowserTable({
  data,
  isLoading,
}: FeedbackBrowserTableProps) {
  const [ratingFilter, setRatingFilter] = useState<"all" | Rating>("all");
  const [page, setPage] = useState(0);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>回饋瀏覽器</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[400px] w-full" />
        </CardContent>
      </Card>
    );
  }

  const filtered =
    ratingFilter === "all"
      ? (data ?? [])
      : (data ?? []).filter((f) => f.rating === ratingFilter);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>回饋瀏覽器</CardTitle>
        <Select
          value={ratingFilter}
          onValueChange={(v) => {
            setRatingFilter(v as "all" | Rating);
            setPage(0);
          }}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="篩選評分" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部</SelectItem>
            <SelectItem value="thumbs_up">正面</SelectItem>
            <SelectItem value="thumbs_down">負面</SelectItem>
          </SelectContent>
        </Select>
      </CardHeader>
      <CardContent>
        {filtered.length === 0 ? (
          <p className="py-8 text-center text-muted-foreground">
            無符合條件的回饋
          </p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>時間</TableHead>
                  <TableHead>評分</TableHead>
                  <TableHead>通路</TableHead>
                  <TableHead>留言</TableHead>
                  <TableHead>標籤</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {paged.map((fb) => (
                  <TableRow key={fb.id}>
                    <TableCell className="whitespace-nowrap text-sm">
                      {new Date(fb.created_at).toLocaleDateString("zh-TW")}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          fb.rating === "thumbs_up" ? "default" : "destructive"
                        }
                      >
                        {fb.rating === "thumbs_up" ? "+" : "-"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{fb.channel}</TableCell>
                    <TableCell className="max-w-[200px] truncate text-sm">
                      {fb.comment ?? "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {fb.tags.map((tag) => (
                          <Badge key={tag} variant="outline" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" asChild>
                        <Link href={`/feedback/${fb.conversation_id}`}>
                          <ExternalLink className="h-4 w-4" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                共 {filtered.length} 筆
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  上一頁
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一頁
                </Button>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
