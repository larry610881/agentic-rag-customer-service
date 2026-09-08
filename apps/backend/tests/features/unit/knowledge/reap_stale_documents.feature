Feature: 卡住的「等待中」文件轉為失敗（派工遺失偵測）
  作為系統
  我希望永遠不會有文件停在「等待中」卻沒有任何工作在跑
  以便使用者看到的是真實的失敗，而不是系統假裝還在處理

  Background:
    Given 逾時門檻為 15 分鐘

  Scenario: 佇列已見底，超時的 pending 文件判定為派工遺失
    Given 文件 "doc-1" 狀態為 pending 且已建立 40 分鐘
    And arq 佇列長度為 0
    When 執行 reap_stale_documents
    Then 文件 "doc-1" 狀態應為 failed
    And 文件 "doc-1" 的處理工作應記錄錯誤訊息含 "派工遺失"

  Scenario: 佇列仍有積壓時，合法排隊中的文件不被誤殺
    Given 文件 "doc-1" 狀態為 pending 且已建立 40 分鐘
    And arq 佇列長度為 120
    When 執行 reap_stale_documents
    Then 文件 "doc-1" 狀態應維持 pending

  Scenario: 佇列積壓但已超過絕對上限，仍判定為失敗
    Given 文件 "doc-1" 狀態為 pending 且已建立 400 分鐘
    And arq 佇列長度為 120
    When 執行 reap_stale_documents
    Then 文件 "doc-1" 狀態應為 failed

  Scenario: 未達逾時門檻的文件不動
    Given 文件 "doc-1" 狀態為 pending 且已建立 3 分鐘
    And arq 佇列長度為 0
    When 執行 reap_stale_documents
    Then 文件 "doc-1" 狀態應維持 pending

  Scenario: 找不到對應的處理工作時仍要把文件轉失敗
    Given 文件 "doc-1" 狀態為 pending 且已建立 40 分鐘
    And 文件 "doc-1" 沒有對應的處理工作
    And arq 佇列長度為 0
    When 執行 reap_stale_documents
    Then 文件 "doc-1" 狀態應為 failed
