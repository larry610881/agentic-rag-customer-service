import { useState } from "react";
import { Link } from "react-router-dom";
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
  total?: number;
  page: number;
  onPageChange: (page: number) => void;
}

const PAGE_SIZE = 10;

const TAG_LABELS: Record<string, string> = {
  irrelevant: "不相關",
  incorrect: "不正確",
  incomplete: "不完整",
  offensive: "語氣不好",
  slow: "回應太慢",
  hallucination: "幻覺",
  other: "其他",
};

const CHANNEL_LABELS: Record<string, string> = {
  web: "網頁",
  line: "LINE",
  widget: "Widget",
};

export function FeedbackBrowserTable({
  data,
  isLoading,
  total,
  page,
  onPageChange,
}: FeedbackBrowserTableProps) {
  const [ratingFilter, setRatingFilter] = useState<"all" | Rating>("all");
  const [searchQuery, setSearchQuery] = useState("");

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

  const filtered = (data ?? []).filter((f) => {
    if (ratingFilter !== "all" && f.rating !== ratingFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchComment = f.comment?.toLowerCase().includes(q);
      const matchBot = f.bot_name?.toLowerCase().includes(q);
      const matchTag = f.tags.some((t) => t.toLowerCase().includes(q));
      if (!matchComment && !matchBot && !matchTag) return false;
    }
    return true;
  });

  const serverTotal = total ?? filtered.length;
  const totalPages = Math.max(1, Math.ceil(serverTotal / PAGE_SIZE));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>回饋瀏覽器</CardTitle>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="搜尋留言、機器人、標籤..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              onPageChange(0);
            }}
            className="h-9 w-48 rounded-md border bg-transparent px-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
          />
        <Select
          value={ratingFilter}
          onValueChange={(v) => {
            setRatingFilter(v as "all" | Rating);
            onPageChange(0);
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
        </div>
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
                  <TableHead>機器人</TableHead>
                  <TableHead>評分</TableHead>
                  <TableHead>通路</TableHead>
                  <TableHead>留言</TableHead>
                  <TableHead>標籤</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((fb) => (
                  <TableRow key={fb.id}>
                    <TableCell className="whitespace-nowrap text-sm">
                      {new Date(fb.created_at).toLocaleString("zh-TW", {
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </TableCell>
                    <TableCell className="text-sm">
                      {fb.bot_name ?? "-"}
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
                    <TableCell className="text-sm">{CHANNEL_LABELS[fb.channel] ?? fb.channel}</TableCell>
                    <TableCell className="max-w-[200px] truncate text-sm">
                      {fb.comment ?? "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {fb.tags.map((tag) => (
                          <Badge key={tag} variant="outline" className="text-xs">
                            {TAG_LABELS[tag] ?? tag}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" asChild>
                        <Link to={`/feedback/${fb.conversation_id}`}>
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
                共 {serverTotal} 筆
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => onPageChange(page - 1)}
                >
                  上一頁
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages - 1}
                  onClick={() => onPageChange(page + 1)}
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
