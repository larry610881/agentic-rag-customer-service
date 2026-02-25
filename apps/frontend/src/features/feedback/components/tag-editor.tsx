"use client";

import { useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface TagEditorProps {
  tags: string[];
  onSave: (tags: string[]) => void;
  isSaving?: boolean;
}

export function TagEditor({ tags, onSave, isSaving }: TagEditorProps) {
  const [currentTags, setCurrentTags] = useState<string[]>(tags);
  const [input, setInput] = useState("");

  const hasChanges =
    JSON.stringify(currentTags.sort()) !== JSON.stringify([...tags].sort());

  function addTag() {
    const trimmed = input.trim();
    if (trimmed && !currentTags.includes(trimmed)) {
      setCurrentTags([...currentTags, trimmed]);
      setInput("");
    }
  }

  function removeTag(tag: string) {
    setCurrentTags(currentTags.filter((t) => t !== tag));
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      addTag();
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {currentTags.map((tag) => (
          <Badge key={tag} variant="secondary" className="gap-1">
            {tag}
            <button
              type="button"
              aria-label={`移除標籤 ${tag}`}
              onClick={() => removeTag(tag)}
              className="ml-0.5 rounded hover:bg-muted"
            >
              <X className="h-3 w-3" />
            </button>
          </Badge>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          placeholder="新增標籤..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          className="h-8 text-sm"
        />
        <Button
          size="sm"
          variant="outline"
          onClick={addTag}
          disabled={!input.trim()}
        >
          新增
        </Button>
      </div>
      {hasChanges && (
        <Button
          size="sm"
          onClick={() => onSave(currentTags)}
          disabled={isSaving}
        >
          儲存標籤
        </Button>
      )}
    </div>
  );
}
