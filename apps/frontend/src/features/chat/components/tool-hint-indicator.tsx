import { motion } from "framer-motion";

const RUNNER_HINT = "✍️ 小助手努力打字中...";

interface ToolHintIndicatorProps {
  hint: string;
}

export function ToolHintIndicator({ hint }: ToolHintIndicatorProps) {
  if (hint === RUNNER_HINT) {
    return <RunnerDots />;
  }

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

/** 🏃 running between three dots */
function RunnerDots() {
  // 4 positions: before dot1, between dot1-2, between dot2-3, after dot3
  // x offsets: 0px, 20px, 40px, 60px
  const keyframes = [0, 20, 40, 60, 40, 20];

  return (
    <motion.div
      className="flex items-center gap-1 text-sm text-muted-foreground"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      <span>小助手努力打字中</span>
      <span className="relative ml-1 inline-flex w-[68px] items-center justify-between">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="inline-block h-[5px] w-[5px] rounded-full bg-muted-foreground/40"
          />
        ))}
        <motion.span
          className="absolute text-xs"
          style={{ left: -2, top: -6 }}
          animate={{ x: keyframes }}
          transition={{
            duration: 1.8,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        >
          🏃
        </motion.span>
      </span>
    </motion.div>
  );
}
