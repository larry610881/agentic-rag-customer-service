/** Issue #60 — config hash 顯示工具：縮短 + 由字串決定性推導色相 */

export const SHORT_HASH_LEN = 12;

export function shortHash(hash: string): string {
  return hash.length > SHORT_HASH_LEN ? hash.slice(0, SHORT_HASH_LEN) : hash;
}

/** FNV-1a 32-bit；同一 hash 永遠得到同一色相（0-359） */
export function hashHue(hash: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < hash.length; i++) {
    h ^= hash.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h % 360;
}

/** 供 inline style 使用：同 hash → 同色，淺底深字在 light/dark 都可讀 */
export function hashChipStyle(hash: string): {
  backgroundColor: string;
  color: string;
  borderColor: string;
} {
  const hue = hashHue(hash);
  return {
    backgroundColor: `hsl(${hue} 70% 50% / 0.15)`,
    color: `hsl(${hue} 60% 35%)`,
    borderColor: `hsl(${hue} 70% 50% / 0.5)`,
  };
}
