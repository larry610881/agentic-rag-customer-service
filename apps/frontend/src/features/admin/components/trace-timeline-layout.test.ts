import { describe, it, expect } from "vitest";
import type { ExecutionNode } from "@/types/agent-trace";
import { buildTraceTimeline } from "./trace-timeline-layout";

function mk(
  id: string,
  type: string,
  start: number,
  end: number,
  parent: string | null = null,
  label = id,
): ExecutionNode {
  return {
    node_id: id,
    node_type: type as ExecutionNode["node_type"],
    label,
    parent_id: parent,
    start_ms: start,
    end_ms: end,
    duration_ms: end - start,
    token_usage: null,
    metadata: {},
  };
}

describe("buildTraceTimeline", () => {
  it("空節點回傳空 layout", () => {
    const layout = buildTraceTimeline([], 100);
    expect(layout.rows).toEqual([]);
    expect(layout.rootId).toBeNull();
    expect(layout.wallMs).toBe(0);
  });

  it("有 request root：root 為 depth 0，其他掛在其下並依 start_ms 排序", () => {
    const nodes = [
      mk("req", "request", 0, 1000),
      mk("llm", "agent_llm", 300, 800, "req"),
      mk("verify", "webhook_verify", 0, 100, "req"),
      mk("orphan", "persist", 850, 900), // 無 parent → 掛 root 下
    ];
    const layout = buildTraceTimeline(nodes, 1000);
    expect(layout.rootId).toBe("req");
    expect(layout.rows.map((r) => r.nodeId)).toEqual([
      "req",
      "verify",
      "llm",
      "orphan",
    ]);
    expect(layout.rows.map((r) => r.depth)).toEqual([0, 1, 1, 1]);
    expect(layout.rows[0].isRoot).toBe(true);
    expect(layout.rows[3].parentId).toBe("req");
  });

  it("子節點縮排在父節點下方（tree order），孫節點 depth 2", () => {
    const nodes = [
      mk("req", "request", 0, 100),
      mk("a", "agent_llm", 0, 50, "req"),
      mk("a1", "tool_call", 10, 30, "a"),
      mk("a1r", "tool_result", 20, 30, "a1"),
      mk("b", "final_response", 50, 100, "req"),
    ];
    const layout = buildTraceTimeline(nodes, 100);
    expect(layout.rows.map((r) => [r.nodeId, r.depth])).toEqual([
      ["req", 0],
      ["a", 1],
      ["a1", 2],
      ["a1r", 3],
      ["b", 1],
    ]);
    expect(layout.rows[1].hasChildren).toBe(true);
    expect(layout.rows[4].hasChildren).toBe(false);
  });

  it("無 request root：wall clock = 0..max(end_ms)，top-level 節點 depth 0", () => {
    const nodes = [
      mk("u", "user_input", 0, 10),
      mk("llm", "agent_llm", 10, 410),
      mk("t", "tool_call", 100, 300, "llm"),
    ];
    const layout = buildTraceTimeline(nodes, 500);
    expect(layout.rootId).toBeNull();
    expect(layout.wallStartMs).toBe(0);
    expect(layout.wallEndMs).toBe(410);
    expect(layout.rows.map((r) => [r.nodeId, r.depth])).toEqual([
      ["u", 0],
      ["llm", 0],
      ["t", 1],
    ]);
  });

  it("left% / width% / 占比相對 wall clock 計算", () => {
    const nodes = [
      mk("req", "request", 100, 1100), // wall = 100..1100，1000ms
      mk("a", "agent_llm", 350, 600, "req"), // left 25%, width 25%
    ];
    const layout = buildTraceTimeline(nodes, 1000);
    const a = layout.rows.find((r) => r.nodeId === "a")!;
    expect(a.leftPct).toBeCloseTo(25);
    expect(a.widthPct).toBeCloseTo(25);
    expect(a.percentOfWall).toBeCloseTo(25);
    const root = layout.rows[0];
    expect(root.leftPct).toBe(0);
    expect(root.widthPct).toBeCloseTo(100);
  });

  it("平行節點：各自占比不超過 100%，且每個 bar 都落在 0–100 內", () => {
    const nodes = [
      mk("req", "request", 0, 1000),
      mk("p1", "tool_call", 100, 900, "req"),
      mk("p2", "tool_call", 100, 700, "req"),
      mk("p3", "tool_call", 200, 950, "req"),
    ];
    const layout = buildTraceTimeline(nodes, 1000);
    for (const r of layout.rows) {
      expect(r.leftPct).toBeGreaterThanOrEqual(0);
      expect(r.leftPct + r.widthPct).toBeLessThanOrEqual(100 + 1e-9);
      expect(r.percentOfWall).toBeLessThanOrEqual(100);
    }
    // 三個平行節點加總 > 100%，但個別都 <= 100%（不做加總即是正確語義）
    const sum = layout.rows
      .filter((r) => !r.isRoot)
      .reduce((acc, r) => acc + r.percentOfWall, 0);
    expect(sum).toBeGreaterThan(100);
    expect(Math.max(...layout.rows.map((r) => r.percentOfWall))).toBe(100);
  });

  it("childrenOverlap：子節點時間重疊 → true；首尾相接不算重疊", () => {
    const overlapping = buildTraceTimeline(
      [
        mk("req", "request", 0, 100),
        mk("a", "tool_call", 10, 60, "req"),
        mk("b", "tool_call", 50, 90, "req"),
      ],
      100,
    );
    expect(overlapping.rows[0].childrenOverlap).toBe(true);

    const sequential = buildTraceTimeline(
      [
        mk("req", "request", 0, 100),
        mk("a", "tool_call", 10, 50, "req"),
        mk("b", "tool_call", 50, 90, "req"),
      ],
      100,
    );
    expect(sequential.rows[0].childrenOverlap).toBe(false);
  });

  it("segments：父列包含直接子節點依 start_ms 排序的色塊", () => {
    const nodes = [
      mk("req", "request", 0, 200),
      mk("b", "vector_search", 100, 150, "req"),
      mk("a", "embed_query", 20, 60, "req"),
      mk("a-child", "tool_result", 30, 40, "a"), // 孫節點不進 root segments
    ];
    const layout = buildTraceTimeline(nodes, 200);
    const root = layout.rows[0];
    expect(root.segments.map((s) => s.nodeId)).toEqual(["a", "b"]);
    expect(root.segments[0].leftPct).toBeCloseTo(10);
    expect(root.segments[0].widthPct).toBeCloseTo(20);
    expect(root.segments[0].nodeType).toBe("embed_query");
    expect(root.segments.every((s) => !s.isGap)).toBe(true);
  });

  it("關鍵路徑：重疊 sibling 中取最長者，循序節點皆為關鍵路徑，只往關鍵節點遞迴", () => {
    const nodes = [
      mk("req", "request", 0, 1000),
      mk("seq1", "webhook_verify", 0, 100, "req"),
      mk("par-long", "tool_call", 100, 800, "req"),
      mk("par-short", "tool_call", 100, 500, "req"),
      mk("short-child", "tool_result", 200, 300, "par-short"),
      mk("long-child", "tool_result", 200, 700, "par-long"),
      mk("seq2", "reply_push", 800, 1000, "req"),
    ];
    const layout = buildTraceTimeline(nodes, 1000);
    const crit = layout.rows
      .filter((r) => r.isCriticalPath)
      .map((r) => r.nodeId)
      .sort();
    expect(crit).toEqual(
      ["req", "seq1", "par-long", "long-child", "seq2"].sort(),
    );
    expect(
      layout.rows.find((r) => r.nodeId === "par-short")!.isCriticalPath,
    ).toBe(false);
    expect(
      layout.rows.find((r) => r.nodeId === "short-child")!.isCriticalPath,
    ).toBe(false);
  });

  it("關鍵路徑：transitive 重疊（A-B、B-C）視為同一 cluster", () => {
    const nodes = [
      mk("req", "request", 0, 100),
      mk("a", "tool_call", 0, 40, "req"),
      mk("b", "tool_call", 30, 70, "req"), // 與 a、c 都重疊
      mk("c", "tool_call", 60, 100, "req"),
    ];
    const layout = buildTraceTimeline(nodes, 100);
    const crit = layout.rows.filter((r) => r.isCriticalPath).map((r) => r.nodeId);
    // a/b/c 等長 40ms，同 cluster → 取 order 最前的 a；root 永遠關鍵
    expect(crit).toEqual(["req", "a"]);
  });

  it("gaps：root 列列出未被任何子孫覆蓋的區間，並標記 isGap", () => {
    const nodes = [
      mk("req", "request", 0, 1000),
      mk("a", "bot_load", 100, 300, "req"),
      mk("a-child", "conversation_load", 250, 400, "a"), // 孫節點也算覆蓋
      mk("b", "agent_llm", 600, 900, "req"),
    ];
    const layout = buildTraceTimeline(nodes, 1000);
    const root = layout.rows[0];
    expect(root.gaps.map((g) => [g.startMs, g.endMs])).toEqual([
      [0, 100],
      [400, 600],
      [900, 1000],
    ]);
    expect(root.gaps.every((g) => g.isGap && g.nodeId === null)).toBe(true);
    expect(root.gaps[1].leftPct).toBeCloseTo(40);
    expect(root.gaps[1].widthPct).toBeCloseTo(20);
    expect(layout.gaps).toEqual(root.gaps);
    // 非 root 列沒有 gaps
    expect(layout.rows[1].gaps).toEqual([]);
  });

  it("gaps：完全覆蓋時為空；無 root 時仍在 layout.gaps 提供", () => {
    const full = buildTraceTimeline(
      [mk("req", "request", 0, 100), mk("a", "agent_llm", 0, 100, "req")],
      100,
    );
    expect(full.rows[0].gaps).toEqual([]);

    const noRoot = buildTraceTimeline(
      [mk("a", "user_input", 0, 10), mk("b", "agent_llm", 50, 100)],
      100,
    );
    expect(noRoot.rootId).toBeNull();
    expect(noRoot.gaps.map((g) => [g.startMs, g.endMs])).toEqual([[10, 50]]);
  });

  it("未知 node_type 不會炸掉，子節點比 root 長時 wall clock 撐到最大 end", () => {
    const nodes = [
      mk("req", "request", 0, 500),
      mk("x", "totally_new_type", 100, 800, "req"),
    ];
    const layout = buildTraceTimeline(nodes, 500);
    expect(layout.wallEndMs).toBe(800);
    const x = layout.rows[1];
    expect(x.leftPct + x.widthPct).toBeLessThanOrEqual(100 + 1e-9);
  });

  it("全部節點 0 時長時退回 total_ms 當 wall clock，不產生 NaN", () => {
    const layout = buildTraceTimeline(
      [mk("a", "user_input", 0, 0), mk("b", "final_response", 0, 0)],
      250,
    );
    expect(layout.wallEndMs).toBe(250);
    for (const r of layout.rows) {
      expect(Number.isNaN(r.leftPct)).toBe(false);
      expect(r.widthPct).toBe(0);
    }
  });
});
