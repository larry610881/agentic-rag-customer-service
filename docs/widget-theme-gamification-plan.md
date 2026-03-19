# Widget 客製化主題 + 遊戲化互動 — 實作計畫

> 本文件為純計畫文件，列出所有需要變更的檔案、具體程式碼片段、資料流，供後續實作時直接對照。

---

## 目錄

1. [Phase 1: 主題客製化系統](#phase-1-主題客製化系統)
2. [Phase 2: 遊戲化互動系統](#phase-2-遊戲化互動系統)
3. [實作順序與依賴關係](#實作順序與依賴關係)
4. [驗證方式](#驗證方式)

---

## Phase 1: 主題客製化系統

### 1.1 設計決策

| 決策 | 理由 |
|------|------|
| Theme 放 Bot JSON 欄位，非獨立表 | 無獨立生命週期，每次 widget 載入跟 bot config 一起拿 |
| CSS `var()` + inline fallback | 即使 theme JS 失敗仍正常顯示 |
| `NULL` = 全部預設值 | 向後相容，零儲存開銷 |

### 1.2 WidgetTheme 屬性定義

```
primary_color    "#3b82f6"   FAB、user bubble、send btn
primary_hover    "#2563eb"   hover 狀態
header_bg        "#1e293b"   header 背景
header_text      "#ffffff"   header 文字
bot_bubble_bg    "#f1f5f9"   bot 訊息泡泡背景
bot_bubble_text  "#1e293b"   bot 訊息泡泡文字
user_bubble_text "#ffffff"   user 訊息泡泡文字
panel_bg         "#ffffff"   面板背景
border_radius    "lg"        sm=8px / md=12px / lg=16px / full=24px
panel_width      400         320~480
panel_height     560         400~700
fab_size         56          40~72
fab_position     "bottom-right"  bottom-right / bottom-left
```

---

### 1.3 Backend 變更清單

#### 1.3.1 Domain — `apps/backend/src/domain/bot/entity.py`

新增 `WidgetTheme` frozen dataclass（放在 `BotLLMParams` 之前）：

```python
BORDER_RADIUS_MAP = {"sm": 8, "md": 12, "lg": 16, "full": 24}

@dataclass(frozen=True)
class WidgetTheme:
    """Widget 外觀主題（Value Object）"""
    primary_color: str = "#3b82f6"
    primary_hover: str = "#2563eb"
    header_bg: str = "#1e293b"
    header_text: str = "#ffffff"
    bot_bubble_bg: str = "#f1f5f9"
    bot_bubble_text: str = "#1e293b"
    user_bubble_text: str = "#ffffff"
    panel_bg: str = "#ffffff"
    border_radius: str = "lg"
    panel_width: int = 400
    panel_height: int = 560
    fab_size: int = 56
    fab_position: str = "bottom-right"

    def to_dict(self) -> dict: ...
    @staticmethod
    def from_dict(data: dict) -> "WidgetTheme": ...
```

Bot dataclass 加欄位（在 `widget_greeting_animation` 之後）：

```python
widget_theme: WidgetTheme | None = None
```

#### 1.3.2 Infrastructure — `apps/backend/src/infrastructure/db/models/bot_model.py`

新增欄位（在 `widget_greeting_animation` 之後）：

```python
widget_theme: Mapped[dict | None] = mapped_column(
    JSON, nullable=True, default=None
)
```

#### 1.3.3 Migration — `apps/backend/migrations/add_widget_theme.sql`

```sql
ALTER TABLE bots ADD COLUMN widget_theme JSON DEFAULT NULL;
```

#### 1.3.4 Infrastructure — `apps/backend/src/infrastructure/db/repositories/bot_repository.py`

**`_to_entity()` 方法**（約 line 99，`widget_greeting_animation` 之後加）：

```python
widget_theme=(
    WidgetTheme.from_dict(model.widget_theme)
    if model.widget_theme
    else None
),
```

**`save()` 方法 — update 分支**（約 line 189，`widget_greeting_animation` 之後加）：

```python
existing.widget_theme = bot.widget_theme.to_dict() if bot.widget_theme else None
```

**`save()` 方法 — create 分支**（約 line 253，`widget_greeting_animation` 之後加）：

```python
widget_theme=bot.widget_theme.to_dict() if bot.widget_theme else None,
```

**import 補充**：`from src.domain.bot.entity import ... WidgetTheme`

#### 1.3.5 Interfaces — `apps/backend/src/interfaces/api/widget_router.py`

**`WidgetConfigResponse`** 加欄位：

```python
class WidgetConfigResponse(BaseModel):
    # ... 現有欄位 ...
    theme: dict | None = None   # WidgetTheme JSON or null
```

**`widget_config()` endpoint** 回傳加：

```python
theme=bot.widget_theme.to_dict() if bot.widget_theme else None,
```

---

### 1.4 Widget 變更清單

#### 1.4.1 Types — `apps/widget/src/types.ts`

```typescript
export interface WidgetTheme {
  primary_color: string;
  primary_hover: string;
  header_bg: string;
  header_text: string;
  bot_bubble_bg: string;
  bot_bubble_text: string;
  user_bubble_text: string;
  panel_bg: string;
  border_radius: "sm" | "md" | "lg" | "full";
  panel_width: number;
  panel_height: number;
  fab_size: number;
  fab_position: "bottom-right" | "bottom-left";
}
```

`WidgetConfig` 加：

```typescript
theme?: WidgetTheme;
```

#### 1.4.2 新檔 — `apps/widget/src/theme.ts`

```typescript
const RADIUS_MAP = { sm: "8px", md: "12px", lg: "16px", full: "24px" };

export function applyTheme(root: HTMLElement, theme?: WidgetTheme): void {
  if (!theme) return;
  const s = root.style;
  s.setProperty("--aw-primary", theme.primary_color);
  s.setProperty("--aw-primary-hover", theme.primary_hover);
  s.setProperty("--aw-primary-shadow", hexToShadow(theme.primary_color));
  s.setProperty("--aw-header-bg", theme.header_bg);
  s.setProperty("--aw-header-text", theme.header_text);
  s.setProperty("--aw-bot-bubble-bg", theme.bot_bubble_bg);
  s.setProperty("--aw-bot-bubble-text", theme.bot_bubble_text);
  s.setProperty("--aw-user-bubble-text", theme.user_bubble_text);
  s.setProperty("--aw-panel-bg", theme.panel_bg);
  s.setProperty("--aw-radius", RADIUS_MAP[theme.border_radius] || "16px");
  s.setProperty("--aw-panel-width", `${theme.panel_width}px`);
  s.setProperty("--aw-panel-height", `${theme.panel_height}px`);
  s.setProperty("--aw-fab-size", `${theme.fab_size}px`);
  // fab_position 影響 left/right，由 widget.ts 處理
}

function hexToShadow(hex: string): string {
  // "#3b82f6" → "rgba(59,130,246,0.4)"
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},0.4)`;
}
```

#### 1.4.3 CSS 變數化 — `apps/widget/src/styles/widget.css`

以下為需要替換的對照表（`原值 → var(--aw-*, 原值)`）：

| 選擇器 | 屬性 | 原值 | 改為 |
|--------|------|------|------|
| `.aw-fab` | `width` | `56px` | `var(--aw-fab-size, 56px)` |
| `.aw-fab` | `height` | `56px` | `var(--aw-fab-size, 56px)` |
| `.aw-fab` | `background` | `#3b82f6` | `var(--aw-primary, #3b82f6)` |
| `.aw-fab` | `box-shadow` | `rgba(59,130,246,0.4)` | `var(--aw-primary-shadow, rgba(59,130,246,0.4))` |
| `.aw-fab:hover` | `box-shadow` | `rgba(59,130,246,0.5)` 部分 | 同上但 0.5 alpha |
| `.aw-panel` | `width` | `400px` | `var(--aw-panel-width, 400px)` |
| `.aw-panel` | `height` | `560px` | `var(--aw-panel-height, 560px)` |
| `.aw-panel` | `border-radius` | `16px` | `var(--aw-radius, 16px)` |
| `.aw-panel` | `background` | `#fff` | `var(--aw-panel-bg, #fff)` |
| `.aw-header` | `background` | `#1e293b` | `var(--aw-header-bg, #1e293b)` |
| `.aw-header` | `color` | `#fff` | `var(--aw-header-text, #fff)` |
| `.aw-header__close` | `color` | `#fff` | `var(--aw-header-text, #fff)` |
| `.aw-bubble--user` | `background` | `#3b82f6` | `var(--aw-primary, #3b82f6)` |
| `.aw-bubble--user` | `color` | `#fff` | `var(--aw-user-bubble-text, #fff)` |
| `.aw-bubble--bot` | `background` | `#f1f5f9` | `var(--aw-bot-bubble-bg, #f1f5f9)` |
| `.aw-bubble--bot` | `color` | `#1e293b` | `var(--aw-bot-bubble-text, #1e293b)` |
| `.aw-send-btn` | `background` | `#3b82f6` | `var(--aw-primary, #3b82f6)` |
| `.aw-send-btn:hover` | `background` | `#2563eb` | `var(--aw-primary-hover, #2563eb)` |
| `.aw-send-btn:disabled` | `background` | `#93c5fd` | 維持不變（淺色 disabled 狀態） |
| `.aw-input:focus` | `border-color` | `#93c5fd` | 維持不變 |
| `.aw-sources__toggle` | `color` | `#3b82f6` | `var(--aw-primary, #3b82f6)` |
| `.aw-feedback__tag--selected` | `border-color` | `#3b82f6` | `var(--aw-primary, #3b82f6)` |
| `.aw-feedback__submit` | `background` | `#3b82f6` | `var(--aw-primary, #3b82f6)` |
| `.aw-feedback__submit:hover` | `background` | `#2563eb` | `var(--aw-primary-hover, #2563eb)` |

**fab_position 處理**：`widget.ts` 建構 FAB 時，若 `theme.fab_position === "bottom-left"`，改設：

```typescript
fab.style.left = "24px";
fab.style.right = "auto";
// panel 也改 left
panel.style.left = "24px";
panel.style.right = "auto";
// greeting 也改 left
greeting.style.left = "24px";
greeting.style.right = "auto";
```

#### 1.4.4 Widget 整合 — `apps/widget/src/widget.ts`

constructor 中，`document.body.appendChild(this.root)` 之後呼叫：

```typescript
import { applyTheme } from "./theme";
// ...
applyTheme(this.root, config.theme);
```

Bundle 增量估計：~1KB minified。

---

### 1.5 Frontend Admin 變更清單

#### 1.5.1 Types — `apps/frontend/src/types/bot.ts`

```typescript
export interface WidgetTheme {
  primary_color: string;
  primary_hover: string;
  header_bg: string;
  header_text: string;
  bot_bubble_bg: string;
  bot_bubble_text: string;
  user_bubble_text: string;
  panel_bg: string;
  border_radius: "sm" | "md" | "lg" | "full";
  panel_width: number;
  panel_height: number;
  fab_size: number;
  fab_position: "bottom-right" | "bottom-left";
}
```

`Bot` / `CreateBotRequest` / `UpdateBotRequest` 加：

```typescript
widget_theme?: WidgetTheme | null;
```

#### 1.5.2 新檔 — `apps/frontend/src/features/bot/components/widget-theme-editor.tsx`

元件功能：
- **色彩選擇器**：6 個 `<input type="color">` 對應 primary_color / primary_hover / header_bg / header_text / bot_bubble_bg / bot_bubble_text / user_bubble_text / panel_bg
- **圓角選擇**：Radio group (sm / md / lg / full) 帶預覽
- **尺寸滑桿**：panel_width (320~480) / panel_height (400~700) / fab_size (40~72)
- **位置選擇**：bottom-right / bottom-left toggle
- **即時預覽**：右側小型 widget mock 預覽

Props 介面：

```typescript
interface WidgetThemeEditorProps {
  value: WidgetTheme | null;
  onChange: (theme: WidgetTheme) => void;
}
```

#### 1.5.3 `apps/frontend/src/features/bot/components/bot-detail-form.tsx`

在 Widget tab（`TAB_KEYS.WIDGET`）的「歡迎招呼語」section 之後、「嵌入碼預覽」section 之前，新增：

```tsx
{/* 外觀主題 */}
<section className="flex flex-col gap-4">
  <h3 className="text-lg font-semibold">外觀主題</h3>
  <p className="text-sm text-muted-foreground">
    自訂 Widget 的顏色、圓角、尺寸。留空則使用預設藍色主題。
  </p>
  <Controller
    name="widget_theme"
    control={control}
    render={({ field }) => (
      <WidgetThemeEditor value={field.value} onChange={field.onChange} />
    )}
  />
</section>
```

Zod schema 加：

```typescript
widget_theme: z.object({...}).nullable().optional(),
```

---

### 1.6 BDD Feature — `apps/backend/tests/features/unit/bot/widget_theme.feature`

```gherkin
Feature: Widget Theme Customization
  Bot 擁有者可以自訂 Widget 外觀主題

  Scenario: 設定主題後 config API 回傳 theme
    Given 一個啟用 Widget 的 Bot 設定了自訂主題
    When 我透過 Widget Config API 取得設定
    Then 應回傳包含 theme 欄位的設定

  Scenario: 未設定主題時 config API 回傳 null theme
    Given 一個啟用 Widget 的 Bot 未設定主題
    When 我透過 Widget Config API 取得設定
    Then theme 欄位應為 null

  Scenario: WidgetTheme Value Object 預設值正確
    Given 一個預設的 WidgetTheme
    Then primary_color 應為 "#3b82f6"
    And border_radius 應為 "lg"
    And panel_width 應為 400
    And fab_position 應為 "bottom-right"

  Scenario: WidgetTheme JSON 往返轉換
    Given 一個自訂的 WidgetTheme 帶 primary_color "#ff0000"
    When 我將它轉為 dict 再轉回 WidgetTheme
    Then 結果應與原始物件相等
```

---

## Phase 2: 遊戲化互動系統

### 2.1 新限界上下文：Engagement

**理由**：VisitorEngagement 有獨立聚合根、獨立生命週期、獨立持久化、獨立業務邏輯（streak 計算、badge 判定），不屬於 Conversation 或 Bot。

#### 2.1.1 目錄結構

```
apps/backend/src/domain/engagement/
├── __init__.py
├── entity.py           # VisitorEngagement（聚合根）
├── repository.py       # VisitorEngagementRepository（介面）
└── value_objects.py    # StreakInfo, Milestone, Badge
```

#### 2.1.2 Domain Entity — `entity.py`

```python
from dataclasses import dataclass, field
from datetime import date, timedelta


MILESTONES = [5, 10, 25, 50, 100]


@dataclass
class VisitorEngagement:
    """訪客互動聚合根"""
    id: str = ""
    visitor_id: str = ""
    bot_id: str = ""
    tenant_id: str = ""
    total_messages: int = 0
    current_streak_days: int = 0
    longest_streak_days: int = 0
    last_active_date: str = ""  # "YYYY-MM-DD"
    badges: list[str] = field(default_factory=list)

    def record_message(self, today: str) -> list[str]:
        """記錄一則訊息，回傳觸發的事件名稱列表。"""
        events: list[str] = []
        self.total_messages += 1

        # Streak 計算
        if self.last_active_date != today:
            if self._is_consecutive(self.last_active_date, today):
                self.current_streak_days += 1
            else:
                self.current_streak_days = 1
            self.last_active_date = today
            if self.current_streak_days > self.longest_streak_days:
                self.longest_streak_days = self.current_streak_days

        # Milestone 檢查
        if self.total_messages in MILESTONES:
            events.append(f"messages_{self.total_messages}")

        # Badge 判定（首次提問）
        if self.total_messages == 1 and "first_question" not in self.badges:
            self.badges.append("first_question")
            events.append("badge_first_question")

        return events

    @staticmethod
    def _is_consecutive(prev_date_str: str, today_str: str) -> bool:
        if not prev_date_str:
            return False
        prev = date.fromisoformat(prev_date_str)
        today = date.fromisoformat(today_str)
        return (today - prev) == timedelta(days=1)
```

#### 2.1.3 Repository Interface — `repository.py`

```python
from abc import ABC, abstractmethod
from src.domain.engagement.entity import VisitorEngagement


class VisitorEngagementRepository(ABC):
    @abstractmethod
    async def find_by_visitor_and_bot(
        self, visitor_id: str, bot_id: str
    ) -> VisitorEngagement | None: ...

    @abstractmethod
    async def save(self, engagement: VisitorEngagement) -> None: ...
```

#### 2.1.4 Value Objects — `value_objects.py`

```python
from dataclasses import dataclass

MILESTONE_MESSAGES = {
    5: "太棒了！已經問了 5 個問題 🎯",
    10: "好奇心旺盛！第 10 個問題達成 🌟",
    25: "知識探索家！25 個問題里程碑 🏆",
    50: "超級用戶！50 個問題！💎",
    100: "傳奇訪客！100 個問題！👑",
}

BADGE_DEFINITIONS = {
    "first_question": {"name": "首次提問", "emoji": "🎉"},
    "streak_3": {"name": "連續 3 天", "emoji": "🔥"},
    "streak_7": {"name": "一週不間斷", "emoji": "⭐"},
}
```

---

### 2.2 Infrastructure 變更

#### 2.2.1 Model — `apps/backend/src/infrastructure/db/models/visitor_engagement_model.py`

```python
class VisitorEngagementModel(Base):
    __tablename__ = "visitor_engagements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    current_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[str] = mapped_column(String(10), default="")
    badges: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, ...)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, ...)

    __table_args__ = (
        Index("ix_ve_visitor_bot", "visitor_id", "bot_id", unique=True),
        Index("ix_ve_tenant_id", "tenant_id"),
    )
```

#### 2.2.2 Repository — `apps/backend/src/infrastructure/db/repositories/visitor_engagement_repository.py`

標準 SQLAlchemy 實作，`find_by_visitor_and_bot` + `save`（upsert 模式）。

#### 2.2.3 Migration — `apps/backend/migrations/add_visitor_engagements.sql`

```sql
CREATE TABLE visitor_engagements (
    id VARCHAR(36) PRIMARY KEY,
    visitor_id VARCHAR(36) NOT NULL,
    bot_id VARCHAR(36) NOT NULL,
    tenant_id VARCHAR(36) NOT NULL,
    total_messages INT NOT NULL DEFAULT 0,
    current_streak_days INT NOT NULL DEFAULT 0,
    longest_streak_days INT NOT NULL DEFAULT 0,
    last_active_date VARCHAR(10) NOT NULL DEFAULT '',
    badges JSON NOT NULL DEFAULT ('[]'),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE INDEX ix_ve_visitor_bot (visitor_id, bot_id),
    INDEX ix_ve_tenant_id (tenant_id)
);
```

---

### 2.3 Application 層

#### 2.3.1 Use Case — `apps/backend/src/application/engagement/record_engagement_use_case.py`

```python
@dataclass
class RecordEngagementCommand:
    visitor_id: str
    bot_id: str
    tenant_id: str

@dataclass
class EngagementResult:
    streak: int
    milestone: str | None = None
    badge: str | None = None

class RecordEngagementUseCase:
    def __init__(self, repo: VisitorEngagementRepository):
        self._repo = repo

    async def execute(self, command: RecordEngagementCommand) -> EngagementResult:
        engagement = await self._repo.find_by_visitor_and_bot(
            command.visitor_id, command.bot_id
        )
        if engagement is None:
            engagement = VisitorEngagement(
                id=str(uuid4()),
                visitor_id=command.visitor_id,
                bot_id=command.bot_id,
                tenant_id=command.tenant_id,
            )
        today = date.today().isoformat()
        events = engagement.record_message(today)
        await self._repo.save(engagement)

        milestone = next((e for e in events if e.startswith("messages_")), None)
        badge = next((e for e in events if e.startswith("badge_")), None)

        return EngagementResult(
            streak=engagement.current_streak_days,
            milestone=milestone,
            badge=badge.replace("badge_", "") if badge else None,
        )
```

#### 2.3.2 Container DI — `apps/backend/src/container.py`

```python
visitor_engagement_repository = providers.Factory(
    SQLAlchemyVisitorEngagementRepository,
    session=session,
)
record_engagement_use_case = providers.Factory(
    RecordEngagementUseCase,
    repo=visitor_engagement_repository,
)
```

---

### 2.4 SSE Piggyback — 資料流

在 `widget_router.py` 的 `widget_chat_stream()` 中，chat stream 完成後、`done` 事件之前插入 engagement event：

```
Widget → POST /chat/stream {message, visitor_id header}
  Backend:
    1. 正常 chat SSE streaming (token, sources, etc.)
    2. stream 結束後、yield done 之前：
       → RecordEngagementUseCase.execute(visitor_id, bot_id, tenant_id)
       → yield SSE: {"type":"engagement", "streak":3, "milestone":"messages_10"}
    3. yield done
```

**widget_router.py 變更**（在 `event_generator()` 內）：

```python
# After chat stream completes, before yielding 'done' to client:
# (The 'done' event is handled in chat-panel.ts case "done")
# We inject engagement event BEFORE the loop ends, captured via a flag

# 在 event_generator 開頭取得 use case：
record_engagement = container.record_engagement_use_case()

# 在 for loop 結束後（stream 結束），done event 之前：
if visitor_id:
    try:
        eng_result = await record_engagement.execute(
            RecordEngagementCommand(
                visitor_id=visitor_id,
                bot_id=bot.id.value,
                tenant_id=bot.tenant_id,
            )
        )
        eng_event = {"type": "engagement", "streak": eng_result.streak}
        if eng_result.milestone:
            eng_event["milestone"] = eng_result.milestone
        if eng_result.badge:
            eng_event["badge"] = eng_result.badge
        yield f"data: {json.dumps(eng_event, ensure_ascii=False)}\n\n"
    except Exception:
        logger.exception("widget.engagement.error")
```

**注意**：需要調整現有 stream 架構，因為目前 `done` 事件是由 `SendMessageUseCase` 的 stream 本身產出的，不是 `widget_router.py` 產出的。需要在 `event_generator()` 裡攔截 `done` 事件，先 yield engagement，再 yield done：

```python
async def event_generator():
    last_event = None
    async for event in use_case.execute_stream(command):
        if event.get("type") == "done":
            # 先 yield engagement，再 yield done
            if visitor_id:
                # ... engagement logic ...
                yield f"data: {json.dumps(eng_event)}\n\n"
            yield f"data: {json.dumps(event)}\n\n"
            continue
        # ... 其餘 event 處理 ...
```

---

### 2.5 Widget SSE Event 擴展

#### 2.5.1 Types — `apps/widget/src/types.ts`

SSEEvent union 加：

```typescript
| { type: "engagement"; streak: number; milestone?: string; badge?: string }
```

#### 2.5.2 Chat Panel — `apps/widget/src/chat/chat-panel.ts`

`sendMessage()` 的 event switch 加：

```typescript
case "engagement":
  this.handleEngagement(event);
  break;
```

```typescript
private handleEngagement(event: { streak: number; milestone?: string; badge?: string }): void {
  // 更新 header streak 顯示
  this.updateStreak(event.streak);
  // 顯示 milestone toast
  if (event.milestone) {
    this.showMilestoneToast(event.milestone);
  }
}
```

#### 2.5.3 Streak 指示器（Header 右側）

在 `ChatPanel` constructor 建立 header 時，close button 之前加 streak 元素：

```typescript
// Header 結構: [name] [streak 🔥3] [close]
this.streakEl = document.createElement("span");
this.streakEl.className = cls("header__streak");
this.streakEl.style.display = "none";  // 初始隱藏
header.insertBefore(this.streakEl, closeBtn);
```

```typescript
private updateStreak(streak: number): void {
  if (streak >= 2) {
    this.streakEl.textContent = `🔥${streak}`;
    this.streakEl.style.display = "inline";
  }
}
```

CSS：

```css
.aw-header__streak {
  font-size: 14px;
  margin-right: 8px;
  opacity: 0.9;
}
```

#### 2.5.4 Milestone Toast

bot bubble 下方顯示慶祝訊息，3 秒後自動消失：

```typescript
private showMilestoneToast(milestone: string): void {
  const msg = MILESTONE_MESSAGES[milestone] || `🎯 ${milestone}`;
  const toast = document.createElement("div");
  toast.className = cls("milestone-toast");
  toast.textContent = msg;
  this.getMessagesContainer().appendChild(toast);
  this.messageList.scrollToBottom();
  setTimeout(() => toast.remove(), 3000);
}
```

CSS：

```css
.aw-milestone-toast {
  align-self: center;
  padding: 8px 16px;
  border-radius: 20px;
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  color: #78350f;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  animation: aw-toast-in 0.3s ease-out;
}
@keyframes aw-toast-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
```

#### 2.5.5 建議問題 Chips

建議問題來源：由 Bot 的 LLM 在回覆最後產生（需要 prompt 調整），或由後端 config 設定靜態建議問題。

**MVP 方案**：使用 SSE 新事件類型 `suggestions`：

```typescript
| { type: "suggestions"; questions: string[] }
```

Widget 在 bot bubble 之後渲染可點擊 chips：

```typescript
private addSuggestionChips(questions: string[], afterBubble: HTMLElement): void {
  const container = document.createElement("div");
  container.className = cls("suggestions");
  for (const q of questions) {
    const chip = document.createElement("button");
    chip.className = cls("suggestions__chip");
    chip.textContent = q;
    chip.addEventListener("click", () => {
      container.remove();
      this.input.value = q;
      this.sendMessage();
    });
    container.appendChild(chip);
  }
  afterBubble.parentElement?.insertBefore(container, afterBubble.nextSibling);
  this.messageList.scrollToBottom();
}
```

CSS：

```css
.aw-suggestions {
  max-width: 82%;
  align-self: flex-start;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.aw-suggestions__chip {
  padding: 6px 12px;
  border: 1px solid var(--aw-primary, #3b82f6);
  border-radius: 16px;
  background: transparent;
  color: var(--aw-primary, #3b82f6);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.aw-suggestions__chip:hover {
  background: var(--aw-primary, #3b82f6);
  color: var(--aw-user-bubble-text, #fff);
}
```

---

### 2.6 BDD Feature — `apps/backend/tests/features/unit/engagement/visitor_engagement.feature`

```gherkin
Feature: Visitor Engagement Gamification
  訪客互動遊戲化機制

  Scenario: 首次訊息建立 engagement 記錄
    Given 一個新訪客 "visitor-001" 對 Bot "bot-001"
    When 訪客發送第一則訊息
    Then engagement 記錄應被建立
    And total_messages 應為 1
    And current_streak_days 應為 1
    And 應觸發 "badge_first_question" 事件

  Scenario: 連續兩天訊息 streak 增加
    Given 訪客 "visitor-001" 昨天有發送訊息
    When 訪客今天發送訊息
    Then current_streak_days 應為 2

  Scenario: 跳過一天 streak 重置
    Given 訪客 "visitor-001" 前天有發送訊息但昨天沒有
    When 訪客今天發送訊息
    Then current_streak_days 應為 1

  Scenario: 第 5 則訊息觸發里程碑
    Given 訪客 "visitor-001" 已發送 4 則訊息
    When 訪客發送第 5 則訊息
    Then 應觸發 "messages_5" 里程碑事件

  Scenario: 同一天多次訊息 streak 不重複計算
    Given 訪客 "visitor-001" 今天已發送過訊息
    When 訪客今天再發送一則訊息
    Then current_streak_days 應維持不變
    And total_messages 應增加 1
```

---

## 實作順序與依賴關係

```
Phase 1（主題系統）:
  Step 1: BDD feature file (widget_theme.feature)
  Step 2: Domain WidgetTheme VO → Bot entity
  Step 3: Infrastructure: model + migration + repository
  Step 4: Interfaces: widget config response
  Step 5: Widget CSS var() + theme.ts + widget.ts
  Step 6: Frontend: types + theme-editor + bot-detail-form
  Step 7: Unit tests (step definitions)

Phase 2（遊戲化）:
  Step 1: BDD feature file (visitor_engagement.feature)
  Step 2: Domain: engagement/ bounded context
  Step 3: Infrastructure: model + migration + repository
  Step 4: Application: RecordEngagementUseCase
  Step 5: Container DI
  Step 6: Interfaces: SSE engagement event in widget_router
  Step 7: Widget: streak + milestone toast + suggestion chips
  Step 8: Unit tests (step definitions)

Final:
  - Run all tests: uv run python -m pytest tests/unit/ -v
  - Frontend tests: npm run test
  - Lint: ruff check + mypy
```

**依賴關係圖**：

```
P1.Step2 → P1.Step3 → P1.Step4 ─┐
                                  ├→ P1.Step5 → P1.Step6
P1.Step1 ─────────────────────────┘

P2.Step2 → P2.Step3 → P2.Step4 → P2.Step5 → P2.Step6 ─┐
                                                         ├→ P2.Step7
P2.Step1 ────────────────────────────────────────────────┘
```

Phase 1 和 Phase 2 之間**無依賴**，可平行實作。

---

## 驗證方式

### Phase 1
1. `cd apps/backend && uv run python -m pytest tests/unit/ -v --tb=short` — widget theme 測試通過
2. Admin 建立 Bot → 設定主題顏色 → Widget embed 確認顏色生效
3. 不設主題的 Bot → Widget 顯示預設藍色主題
4. Widget CSS fallback 驗證：即使 theme JS 失敗，widget 仍正常顯示

### Phase 2
1. `cd apps/backend && uv run python -m pytest tests/unit/ -v --tb=short` — engagement 測試通過
2. Widget 連續 2 天對話 → header 顯示 🔥2
3. 發送第 5 則訊息 → 看到 milestone toast
4. Bot 回覆後 → 看到建議問題 chips → 點擊自動發送

### Bundle 大小驗證
```bash
cd apps/widget && npm run build
# 確認 widget.js < 25KB (gzipped)
```
