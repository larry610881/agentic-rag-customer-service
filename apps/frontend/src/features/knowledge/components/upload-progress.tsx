"use client";

import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useTask } from "@/hooks/queries/use-tasks";

interface UploadProgressProps {
  taskId: string;
}

export function UploadProgress({ taskId }: UploadProgressProps) {
  const { data: task } = useTask(taskId);

  if (!task) return null;

  return (
    <div className="flex items-center gap-3 rounded-md border p-3">
      <div className="flex-1">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm font-medium">Processing document</span>
          <Badge
            variant={
              task.status === "completed"
                ? "default"
                : task.status === "failed"
                  ? "destructive"
                  : "secondary"
            }
          >
            {task.status}
          </Badge>
        </div>
        <Progress value={task.progress} className="h-2" />
      </div>
    </div>
  );
}
