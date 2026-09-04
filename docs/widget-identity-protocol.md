# Widget 宿主身分綁定協定（identify）

> 對象：把 widget 嵌進自家網站、且希望對話歸戶到自家會員的店家。對應 Issue #68 P7b。
> 這是通用協定，不依網站客製；hash **只能在宿主後端算**，secret 不得進前端。

## 1. 為什麼需要

widget 預設是匿名訪客（伺服器簽發的 visitor id）。宿主網站若已有登入會員，可以把會員 id 綁進 widget 票：對話紀錄與回饋會歸到該會員，異常控管的主體也從「訪客」升級為「終端使用者」（攻擊者換瀏覽器也帶著同一個分數）。

## 2. 後台設定

後台「Widget 身分綁定」（租戶管理員）：
- **輪替 secret**：產生一把新的 identity secret，只顯示一次，請放到宿主後端的密鑰管理。
- **啟用 / 停用**。
- **強制驗證**：開啟後，簽章錯誤的 identify 直接回 403；關閉（預設）時失敗只降級為匿名並計分。

## 3. 協定

宿主後端在使用者登入後計算：

```
exp  = 現在 + N 秒（最多 24 小時）
hash = HMAC-SHA256(secret, `${userId}.${exp}`)  → hex 小寫
```

前端（widget 載入後）呼叫：

```js
window.AgenticRagWidget.identify({ userId, exp, hash, name, email })
  .then((r) => console.log(r.identified, r.reason));
```

widget 會 `POST /api/v1/widget/{code}/identify`（帶現有 widget 票），通過後自動換成帶 `end_user_id` 的新票，之後的聊天、回饋都以該使用者為主體。

回應：

| 狀態 | 意義 |
|------|------|
| 200 `{"identified": true, ...}` | 通過，票已換 |
| 200 `{"identified": false, "reason": "invalid" \| "disabled" \| "not_configured"}` | 未通過，維持匿名 |
| 403 `{"detail": "identity_required"}` | 租戶開強制驗證且簽章錯誤 |
| 401 | 沒有 widget 票（請先載入 widget） |

## 4. 各語言五行範例（宿主後端）

Node.js
```js
const crypto = require("crypto");
const exp = Math.floor(Date.now() / 1000) + 600;
const hash = crypto.createHmac("sha256", process.env.WIDGET_IDENTITY_SECRET)
  .update(`${userId}.${exp}`).digest("hex");
res.json({ userId, exp, hash });
```

PHP
```php
$exp  = time() + 600;
$hash = hash_hmac('sha256', "{$userId}.{$exp}", getenv('WIDGET_IDENTITY_SECRET'));
echo json_encode(['userId' => $userId, 'exp' => $exp, 'hash' => $hash]);
```

Python
```python
import hmac, hashlib, time, os
exp = int(time.time()) + 600
hash_ = hmac.new(os.environ["WIDGET_IDENTITY_SECRET"].encode(),
                 f"{user_id}.{exp}".encode(), hashlib.sha256).hexdigest()
return {"userId": user_id, "exp": exp, "hash": hash_}
```

.NET (C#)
```csharp
var exp = DateTimeOffset.UtcNow.ToUnixTimeSeconds() + 600;
using var h = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
var hash = Convert.ToHexString(h.ComputeHash(Encoding.UTF8.GetBytes($"{userId}.{exp}"))).ToLowerInvariant();
return new { userId, exp, hash };
```

## 5. 安全注意

- secret 只放宿主後端；前端只轉交 `{userId, exp, hash}`。
- exp 建議 5–15 分鐘；超過 24 小時一律無效。
- 簽章失敗會計入異常分數（+2）；連續失敗會被降速。
- 簽發 widget 票的端點每 IP 每分鐘限 30 次，防止換身分重置分數。
