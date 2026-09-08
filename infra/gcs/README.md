# 文件桶（poc-rag-documents-project-pic-ai-innovation-poc）設定

由專案負責人（有 storage admin 權限的帳號）執行；Larry 的帳號沒有 storage.* 權限。

## 1. 瀏覽器直傳 CORS（後台上傳 PDF 走簽名網址直傳 GCS）
```bash
gcloud storage buckets update gs://poc-rag-documents-project-pic-ai-innovation-poc \
  --cors-file=infra/gcs/documents-bucket-cors.json
```
未設定的症狀：後台上傳顯示「GCS upload network error」（瀏覽器 CORS 預檢被擋）。

## 2. VM worker 服務帳號讀寫權限
```bash
gcloud storage buckets add-iam-policy-binding gs://poc-rag-documents-project-pic-ai-innovation-poc \
  --member=serviceAccount:poc-rag-vm-sa@project-pic-ai-innovation-poc.iam.gserviceaccount.com \
  --role=roles/storage.objectAdmin
```
未設定的症狀：worker 處理文件時 403 `storage.objects.get`；目前靠資料庫副本 fallback 撐著，簽名網址直傳的大檔沒有副本會失敗。
