Feature: 上傳 XML 解析防 XXE (XML Parser Hardening)
    身為平台
    我想要上傳的 XML 以 defusedxml 解析
    以便外部實體與實體膨脹攻擊在解析階段就被拒絕

    Scenario: 正常 XML 解析出文字
        When 解析 XML "<root><a>你好</a><b>世界</b></root>"
        Then 解析結果應含 "你好" 與 "世界"

    Scenario: 含實體宣告的 XML 被拒絕
        When 解析含 DOCTYPE 實體宣告的 XML
        Then 應拋出 XML 解析錯誤且訊息不含實體展開內容
