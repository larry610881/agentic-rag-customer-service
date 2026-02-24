"use client";

import { motion } from "framer-motion";

interface ToolHintIndicatorProps {
  hint: string;
}

export function ToolHintIndicator({ hint }: ToolHintIndicatorProps) {
  return (
    <motion.div
      className="flex items-center gap-1 text-sm text-muted-foreground"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      <span>{hint}</span>
      <span className="flex gap-[2px]">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="inline-block h-1 w-1 rounded-full bg-muted-foreground"
            animate={{ y: [0, -4, 0] }}
            transition={{
              duration: 0.6,
              repeat: Infinity,
              delay: i * 0.15,
              ease: "easeInOut",
            }}
          />
        ))}
      </span>
    </motion.div>
  );
}
