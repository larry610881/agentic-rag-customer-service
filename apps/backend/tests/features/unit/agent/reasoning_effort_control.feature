Feature: 推理強度控制 — 關閉（none）、通路對等、供應商對應、審計與 trace (Reasoning Effort Control)
    身為租戶管理者
    我想要在後台把 bot 的推理強度（thinking）關掉或調整
    以便三個通路送模型的請求一致、能從 trace / usage 實證模型是否真的在思考

    # ── A. 值域：none 可存、非法值拒絕、既有 medium 不變 ──

    Scenario Outline: 建立 bot 時的推理強度值域
        Given bot 建立用例
        When 以推理強度 "<effort>" 建立 bot
        Then 建立結果應為 <outcome>

        Examples:
            | effort  | outcome |
            | none    | saved   |
            | low     | saved   |
            | medium  | saved   |
            | high    | saved   |
            | xhigh   | error   |
            | minimal | error   |

    Scenario Outline: 更新 bot 的推理強度值域
        Given 一個推理強度為 "medium" 的既有 bot
        When 將 bot 推理強度更新為 "<effort>"
        Then 更新結果應為 <outcome> 且儲存的推理強度為 "<stored>"

        Examples:
            | effort | outcome | stored |
            | none   | saved   | none   |
            | high   | saved   | high   |
            | turbo  | error   | medium |

    Scenario: 未指定推理強度時既有 bot 維持 medium
        Given 一個推理強度為 "medium" 的既有 bot
        When 只更新 bot 名稱
        Then 儲存的推理強度應為 "medium"

    # ── B. 通路對等：web / widget / LINE、worker 覆寫、快速道 ──

    Scenario Outline: 三通路皆把 bot 的推理強度帶給 Agent
        Given 一個推理強度為 "none" 且沒有 worker 的 bot
        When 以 "<channel>" 通路送出訊息
        Then Agent 收到的 llm_params 應含 reasoning_effort "none"

        Examples:
            | channel |
            | web     |
            | widget  |
            | line    |

    Scenario Outline: worker 沒有自己的推理強度 — 覆寫模型後仍沿用 bot 的值
        Given 一個推理強度為 "none" 且 worker 指定模型 "gpt-5.4" 的 bot
        When 以 "<channel>" 通路送出訊息
        Then Agent 收到的 llm_params 應含 reasoning_effort "none"
        And Agent 收到的 llm_params 模型應為 "gpt-5.4"

        Examples:
            | channel |
            | web     |
            | line    |

    Scenario: 快速道單次生成也帶推理強度
        Given 一個 mode 為 "fast" 且推理強度為 "none" 的 bot，檢索分數 0.85
        When 以 "web" 通路送出訊息
        Then Agent 應以 max_tool_calls 1 被呼叫
        And Agent 收到的 llm_params 應含 reasoning_effort "none"

    # ── C. 供應商對應 ──

    Scenario Outline: OpenAI 相容端點的推理強度對應（綁工具的 agent 路徑）
        When 以供應商 "openai" 模型 "<model>" 建立聊天模型並要求推理強度 "<effort>"
        Then 聊天模型送出的 reasoning_effort 應為 "<sent>"

        Examples:
            | model            | effort | sent    |
            | gpt-5.4          | none   | none    |
            | gpt-5.4          | low    | (省略)  |
            | gpt-5.4          | high   | (省略)  |
            | gpt-4o           | none   | (省略)  |
            | gpt-4o           | high   | (省略)  |
            | o3               | high   | high    |
            | gemini-3.7-flash | none   | none    |
            | gemini-3.7-flash | medium | medium  |

    # 地端 Qwen（ollama 的 OpenAI 相容端點）：thinking 預設開著，只有 none 能關掉。
    # 其餘強度不夾帶，讓模型走自己的預設，避免送出端點不認的值而整個請求 400。
    Scenario Outline: 地端 Qwen 的推理強度對應（ollama OpenAI 相容端點）
        When 以供應商 "ollama" 模型 "<model>" 建立聊天模型並要求推理強度 "<effort>"
        Then 聊天模型送出的 reasoning_effort 應為 "<sent>"

        Examples:
            | model                | effort  | sent   |
            | qwen3.8:27b-q8_0     | none    | none   |
            | qwen3.6:35b-a3b-q8_0 | none    | none   |
            | qwen3.8:27b-q8_0     | minimal | none   |
            | qwen3.8:27b-q8_0     | low     | (省略) |
            | qwen3.8:27b-q8_0     | high    | (省略) |
            | llama3.3:70b         | none    | (省略) |

    Scenario Outline: Anthropic 的推理強度對應（LangChain ChatAnthropic）
        When 以供應商 "anthropic" 模型 "<model>" 建立聊天模型並要求推理強度 "<effort>"
        Then Anthropic 聊天模型的 thinking 應為 "<thinking>" 且 effort 應為 "<sent>"

        Examples:
            | model                    | effort | thinking | sent   |
            | claude-opus-5            | none   | disabled | (省略) |
            | claude-sonnet-5          | none   | disabled | (省略) |
            | claude-opus-4-8          | none   | (省略)   | (省略) |
            | claude-sonnet-4-20250514 | none   | (省略)   | (省略) |
            | claude-opus-5            | low    | adaptive | low    |
            | claude-opus-4-6          | medium | adaptive | medium |
            | claude-sonnet-4-6        | high   | adaptive | high   |
            | claude-fable-5           | none   | (省略)   | (省略) |
            | claude-fable-5           | high   | adaptive | high   |
            | claude-haiku-4-5         | high   | (省略)   | (省略) |

    Scenario Outline: Anthropic 原生 Messages API 請求本體的推理強度對應
        When 以 Anthropic 模型 "<model>" 產生請求本體並要求推理強度 "<effort>"
        Then 請求本體的 thinking 應為 "<thinking>" 且 output_config.effort 應為 "<sent>"

        Examples:
            | model                    | effort | thinking | sent   |
            | claude-opus-5            | none   | disabled | (省略) |
            | claude-opus-4-8          | none   | (省略)   | (省略) |
            | claude-opus-5            | high   | adaptive | high   |
            | claude-sonnet-4-20250514 | high   | (省略)   | (省略) |

    Scenario: Anthropic 開啟 thinking 時回應的第一個區塊是 thinking — 仍取得文字回覆
        Given Anthropic 服務回應含 thinking 區塊與文字區塊
        When 以推理強度 "high" 呼叫 Anthropic generate
        Then 回傳文字應為 "板橋店 2 樓設有快剪"

    Scenario Outline: 有效推理強度（trace 用）— 要求值 vs 實際送出值
        When 以供應商 "<provider>" 模型 "<model>" 解析推理強度要求值 "<effort>"
        Then 有效推理強度應為 "<effective>"

        Examples:
            | provider  | model            | effort | effective        |
            | openai    | gpt-5.4          | none   | none             |
            | openai    | gpt-5.4          | medium | provider_default |
            | openai    | gpt-4o           | none   | provider_default |
            | google    | gemini-3.7-flash | low    | low              |
            | anthropic | claude-opus-5    | none   | none             |
            | anthropic | claude-opus-5    | high   | high             |
            | anthropic | claude-haiku-4-5 | high   | provider_default |
            | anthropic | claude-fable-5   | none   | provider_default |
            | ollama    | qwen3.8:27b-q8_0 | none   | none             |
            | ollama    | qwen3.8:27b-q8_0 | high   | provider_default |

    # ── D. 審計 / 指紋 / trace / usage ──

    Scenario: 稽核視圖與設定快照包含關閉的推理強度
        Given 一個推理強度為 "medium" 的 bot 實體
        When 取快照後把推理強度改為 "none" 再取一次快照
        Then 稽核視圖的 llm_params.reasoning_effort 應為 "none"
        And 快照 diff 應列出 "llm_params.reasoning_effort"

    Scenario: 有效設定指紋隨推理強度改變
        Given 兩份僅推理強度不同（medium 與 none）的有效設定
        Then 兩者的指紋應不同
        And 兩份快照的 llm_params.reasoning_effort 應分別為 "medium" 與 "none"

    Scenario: trace 的 LLM 節點記錄要求值與實際送出值
        Given 一個 ReAct 執行，供應商 "openai" 模型 "gpt-5.4" 要求推理強度 "medium"
        When 執行一次 agent 回覆
        Then agent_llm 節點的 reasoning_effort_requested 應為 "medium"
        And agent_llm 節點的 reasoning_effort_effective 應為 "provider_default"
        And agent_llm 節點的 token_usage.reasoning_tokens 應為 40

    Scenario: usage 記錄 reasoning_tokens（LangChain 路徑）
        Given 一則 output_token_details.reasoning 為 40 的 AIMessage
        When 從 LangChain 訊息擷取 usage
        Then usage 的 reasoning_tokens 應為 40
        And usage 事件的 reasoning_tokens 應為 40

    Scenario: usage 記錄 reasoning_tokens（OpenAI 原生 chat completions）
        Given OpenAI 服務回應 usage.completion_tokens_details.reasoning_tokens 為 25
        When 以推理強度 "none" 呼叫 OpenAI generate
        Then 回傳 usage 的 reasoning_tokens 應為 25

    Scenario: trace 總量彙整 reasoning_tokens
        Given 一個 trace 含兩個 agent_llm 節點，reasoning_tokens 分別為 10 與 15
        When trace 完成
        Then trace total_tokens 的 reasoning_tokens 應為 25
