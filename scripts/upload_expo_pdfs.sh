#!/bin/bash
# 批次上傳秋季展 PDF 到「3D虛擬商品展」租戶的「秋季展KM」知識庫。
#
# 走 API multipart，不走後台 UI：後台是「拿簽名網址前端直傳 GCS」，該桶的 CORS
# 尚未確認設好（2026-09-08 上午 DM 上傳出現「GCS upload network error」）。
# 若 UI 實測可用，這支腳本仍然可用，只是不必要。
#
# 逐檔上傳、不併發：每個 PDF 上傳後會派 OCR 工作到 VM worker，一次灌 33 份會讓
# worker 佇列爆掉，而且失敗時分不清是哪一份的問題。
#
# 用法：
#   EXPO_ADMIN_PASSWORD='Expo2026!poc' bash scripts/upload_expo_pdfs.sh [PDF目錄]

set -uo pipefail

BASE="${BASE_URL:-https://agentic-rag-969010424468.asia-east1.run.app}"
ACCOUNT="${EXPO_ADMIN_ACCOUNT:-expo-admin@example.com}"
KB="${EXPO_KB_ID:-00e73755-da71-4234-bf6e-5872c882d16d}"
DIR="${1:-/mnt/c/Users/P10359945/Downloads/KM_pdf}"
PW="${EXPO_ADMIN_PASSWORD:-}"

if [ -z "$PW" ]; then
  echo "請以環境變數 EXPO_ADMIN_PASSWORD 提供密碼"; exit 2
fi
if [ ! -d "$DIR" ]; then
  echo "找不到目錄：$DIR"; exit 2
fi

login() {
  curl -s -m 30 -X POST "$BASE/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"account\":\"$ACCOUNT\",\"password\":\"$PW\"}" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))'
}

TOKEN=$(login)
if [ -z "$TOKEN" ]; then echo "登入失敗"; exit 1; fi
echo "已登入 $ACCOUNT"

shopt -s nullglob
FILES=("$DIR"/*.pdf)
echo "找到 ${#FILES[@]} 份 PDF，開始上傳（逐檔，不併發）"
echo

ok=0; fail=0
for f in "${FILES[@]}"; do
  name=$(basename "$f")
  code=$(curl -s -o /tmp/expo_up.json -w '%{http_code}' -m 300 \
    -X POST "$BASE/api/v1/knowledge-bases/$KB/documents" \
    -H "Authorization: Bearer $TOKEN" -F "file=@$f")
  # access token 效期比整批上傳短，過期就重登再試一次
  if [ "$code" = "401" ]; then
    TOKEN=$(login)
    code=$(curl -s -o /tmp/expo_up.json -w '%{http_code}' -m 300 \
      -X POST "$BASE/api/v1/knowledge-bases/$KB/documents" \
      -H "Authorization: Bearer $TOKEN" -F "file=@$f")
  fi
  if [ "$code" = "200" ] || [ "$code" = "201" ]; then
    doc=$(python3 -c 'import json;d=json.load(open("/tmp/expo_up.json"));print(d.get("document",{}).get("id","")[:8])' 2>/dev/null)
    echo "  ✓ [$code] $name  → $doc"
    ok=$((ok+1))
  else
    echo "  ✗ [$code] $name"
    head -c 200 /tmp/expo_up.json; echo
    fail=$((fail+1))
  fi
  sleep 2
done

echo
echo "上傳完成：成功 $ok、失敗 $fail"
echo
echo "接著追蹤處理進度（OCR 在 VM worker 上跑，會花幾分鐘）："
cat <<EOF
  TOKEN=\$(curl -s -X POST $BASE/api/v1/auth/login -H 'Content-Type: application/json' \\
    -d '{"account":"$ACCOUNT","password":"<密碼>"}' \\
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
  curl -s "$BASE/api/v1/knowledge-bases/$KB/documents?page=1&page_size=100" \\
    -H "Authorization: Bearer \$TOKEN" \\
    | python3 -c 'import sys,json,collections
d=json.load(sys.stdin); i=d if isinstance(d,list) else d.get("items",[])
print(collections.Counter(x["status"] for x in i))
for x in i:
    if x["status"] not in ("processed",): print(" ", x["status"], x.get("filename"))'
EOF
echo
echo "全部 processed 之後，再跑落庫驗證（頁面標記數是否等於頁數、條目有無重複）。"
