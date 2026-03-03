# PPT2Video - Podcast 生成工具

一個全端 Podcast 生成應用程式，可從文字內容自動生成專業的 Podcast 音訊。使用 AI 技術將文字轉換為自然流暢的對話式 Podcast，支援多種長度模式和語音設定。

## ✨ 功能特色

- 📝 **智能轉錄生成**：使用 AI 將文字內容轉換為自然的 Podcast 對話稿
- 🎙️ **多種長度模式**：支援 SHORT（7 分鐘）、MEDIUM（15 分鐘）、LONG（30 分鐘）
- 🔊 **高品質語音合成**：使用 Google Cloud TTS (Gemini 2.5 Flash) 生成自然語音
- 🎭 **雙講者對話**：支援兩個不同角色的講者進行對話
- 🎨 **現代化 Web 介面**：React + TypeScript 建構的直觀使用者介面
- 📊 **即時進度追蹤**：透過 Server-Sent Events (SSE) 即時顯示處理進度
- 💾 **完整輸出管理**：自動合併音訊檔案並提供下載功能

## 🏗️ 專案架構

```
PPT2Video/
├── backend/              # FastAPI 後端服務
│   ├── app/
│   │   ├── api/         # API 路由
│   │   ├── models/      # 資料模型
│   │   ├── services/    # 業務邏輯服務
│   │   └── utils/       # 工具函數
│   ├── outputs/         # 生成的輸出檔案
│   └── uploads/         # 上傳的檔案
├── frontend/            # React 前端應用
│   ├── src/
│   │   ├── components/  # React 元件
│   │   ├── pages/       # 頁面元件
│   │   ├── services/    # API 服務
│   │   └── contexts/    # React Context
│   └── public/          # 靜態資源
├── src/                 # 共用程式碼
│   └── prompt.py        # AI Prompt 模板
└── example/             # 範例檔案
```

## 🚀 快速開始

### 前置需求

- Python 3.8+
- Node.js 16+
- Google Cloud 專案（用於 TTS API）
- OpenAI API Key（用於轉錄生成）

### 後端設定

1. **安裝依賴套件**

```bash
cd backend
pip install -r requirements.txt
```

2. **設定環境變數**

建立 `.env` 檔案在 `backend/` 目錄下：

```env
OPENAI_API_KEY=your_openai_api_key
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
GOOGLE_CLOUD_PROJECT=your_project_id
```

或使用環境變數：

```bash
export OPENAI_API_KEY=your_openai_api_key
export GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
export GOOGLE_CLOUD_PROJECT=your_project_id
```

3. **啟動後端服務**

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

後端服務將在以下位置可用：
- API: http://localhost:8000
- API 文件: http://localhost:8000/docs
- 健康檢查: http://localhost:8000/health

### 前端設定

1. **安裝依賴套件**

```bash
cd frontend
npm install
```

2. **設定環境變數（可選）**

建立 `.env` 檔案在 `frontend/` 目錄下：

```env
VITE_API_URL=http://localhost:8000
```

3. **啟動開發伺服器**

```bash
npm run dev
```

前端應用將在 http://localhost:3000 可用

4. **建置生產版本**

```bash
npm run build
npm run preview
```

## 📖 使用方式

### Web 介面使用

1. **步驟 1：上傳內容**
   - 上傳文字檔案或 PDF 檔案
   - 選擇 Podcast 長度模式（SHORT / MEDIUM / LONG）
   - 點擊「開始生成」

2. **步驟 2：編輯轉錄稿**
   - 檢視 AI 生成的轉錄稿
   - 可編輯對話內容
   - 確認後進入下一步

3. **步驟 3：確認設定**
   - 檢視優化後的轉錄稿
   - 確認語音設定
   - 開始生成音訊

4. **步驟 4：下載結果**
   - 檢視生成進度
   - 預覽音訊檔案
   - 下載最終的 Podcast 音訊檔

### 命令列使用（舊版）

專案也提供命令列工具用於直接從轉錄檔生成音訊：

```bash
# 基本使用
python generate_audio.py example/3_enhance_transcipt.txt

# 指定輸出目錄
python generate_audio.py example/3_enhance_transcipt.txt -o audio_output

# 使用標準模型（節省成本）
python generate_audio.py example/3_enhance_transcipt.txt -m tts-1

# 生成並自動合併音訊
python generate_audio.py example/3_enhance_transcipt.txt --merge

# 完整參數範例
python generate_audio.py example/3_enhance_transcipt.txt \
    -o audio_output \
    -m tts-1-hd \
    --merge \
    --merge-output audio_output/final_podcast.mp3
```

## 🔌 API 端點

### 上傳與處理

- `POST /api/upload` - 上傳文字內容並開始 Podcast 生成
- `POST /api/step1` - 步驟 1：生成初始轉錄稿
- `POST /api/step2` - 步驟 2：優化轉錄稿
- `POST /api/step3` - 步驟 3：生成音訊

### 查詢與下載

- `GET /api/status/{task_id}` - 取得任務狀態
- `GET /api/download/{task_id}/audio` - 下載音訊檔案
- `GET /api/download/{task_id}/transcript` - 下載轉錄檔
- `GET /api/stream/{task_id}` - SSE 串流取得進度更新

### 設定

- `GET /api/settings` - 取得設定
- `POST /api/settings` - 更新設定

詳細的 API 文件可在 http://localhost:8000/docs 查看。

## ⚙️ 設定選項

### 語音設定

預設語音配置：
- Speaker 1: `Kore`（專業、清晰）
- Speaker 2: `Charon`（活潑、有活力）

可在 Web 介面的設定頁面或後端服務中修改語音設定。

### Podcast 長度模式

- **SHORT**：約 7 分鐘（1,500–1,800 字）
- **MEDIUM**：約 15 分鐘（3,000–3,500 字）
- **LONG**：約 30 分鐘（6,000–7,000 字）

## 📁 輸出格式

生成的檔案結構：

```
outputs/{task_id}/
├── transcript.txt          # 轉錄稿
├── optimized_transcript.txt # 優化後的轉錄稿
├── metadata.json           # 音訊檔案元資料
├── Speaker_1_001.mp3       # 講者 1 的音訊片段
├── Speaker_2_002.mp3       # 講者 2 的音訊片段
└── merged_audio.mp3        # 合併後的完整音訊
```

## 🔧 技術棧

### 後端
- **FastAPI** - 現代化的 Python Web 框架
- **Google Cloud TTS** - 語音合成服務
- **OpenAI API** - AI 轉錄生成
- **Pydub** - 音訊處理
- **SSE-Starlette** - Server-Sent Events 支援

### 前端
- **React 18** - UI 框架
- **TypeScript** - 型別安全
- **Vite** - 建置工具
- **React Router** - 路由管理
- **Axios** - HTTP 客戶端

## 📝 注意事項

- 需要有效的 OpenAI API Key 和 Google Cloud 憑證
- 確保 Google Cloud 專案已啟用 Text-to-Speech API
- 音訊生成可能需要一些時間，取決於內容長度
- 建議在生產環境中設定適當的 CORS 政策

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 授權本專案採用 MIT 授權。
