---
name: Podcast Generation Web App
overview: 建立前後端分離的 podcast 生成系統，使用者上傳文字內容，經過兩步驟優化後產出音訊檔案和優化後的轉錄稿，並提供即時進度更新。
todos:
  - id: backend_structure
    content: 建立後端專案結構（FastAPI），包含 app/、api/、services/、models/ 目錄
    status: completed
  - id: llm_service
    content: 實現 LLM 服務（app/services/llm_service.py），封裝 OpenAI API 調用，整合 src/prompt.py 中的 prompt
    status: completed
    dependencies:
      - backend_structure
  - id: transcript_service
    content: 實現轉錄稿服務（app/services/transcript_service.py），包含兩步驟：1) 生成初始轉錄稿 2) 優化轉錄稿
    status: completed
    dependencies:
      - llm_service
  - id: audio_service
    content: 實現音訊生成服務（app/services/audio_service.py），整合 generate_audio_gemini.py 的核心功能
    status: completed
    dependencies:
      - backend_structure
  - id: api_routes
    content: 實現 API 路由（app/api/routes.py），包含上傳、狀態查詢、下載、SSE 進度串流
    status: completed
    dependencies:
      - transcript_service
      - audio_service
  - id: task_manager
    content: 實現任務管理器，用於追蹤任務狀態和進度（可用記憶體字典或 Redis）
    status: completed
    dependencies:
      - api_routes
  - id: frontend_structure
    content: 建立前端 React 專案結構，包含 components/、services/、hooks/ 目錄
    status: completed
  - id: frontend_upload
    content: 實現上傳表單組件（components/UploadForm.tsx）和 API 客戶端（services/api.ts）
    status: completed
    dependencies:
      - frontend_structure
  - id: frontend_progress
    content: 實現進度追蹤（hooks/useProgress.tsx 使用 SSE）和進度顯示組件（components/ProgressBar.tsx）
    status: completed
    dependencies:
      - frontend_upload
  - id: frontend_download
    content: 實現下載功能（components/DownloadButtons.tsx），支援下載音訊和轉錄稿
    status: completed
    dependencies:
      - frontend_progress
---

# P

odcast Generation Web Application

## 架構概述

建立前後端分離的系統，流程如下：

```javascript
使用者上傳文字 → 步驟1：生成初始轉錄稿 → 步驟2：優化轉錄稿 → 步驟3：生成音訊 → 返回結果
```



## 後端架構 (FastAPI)

### 1. 專案結構

```javascript
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 應用入口
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API 路由
│   ├── services/
│   │   ├── __init__.py
│   │   ├── transcript_service.py    # 轉錄稿生成服務
│   │   ├── audio_service.py         # 音訊生成服務
│   │   └── llm_service.py           # LLM 調用服務
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       # Pydantic 模型
│   └── utils/
│       ├── __init__.py
│       └── file_handler.py  # 檔案處理工具
├── uploads/                 # 上傳檔案暫存
├── outputs/                 # 產出檔案
└── requirements.txt
```



### 2. 核心功能實現

#### `app/services/llm_service.py`

- 封裝 OpenAI API 調用
- 使用 `src/prompt.py` 中的兩個 prompt
- 處理 LLM 回應解析

#### `app/services/transcript_service.py`

- 步驟1：使用 `TRANSCRIPT_WRITER_PROMPT` 生成初始轉錄稿
- 步驟2：使用 `TRANSCRIPT_Rewriter_PROMPT` 優化轉錄稿
- 返回格式：`[("Speaker 1", "text"), ("Speaker 2", "text"), ...]`

#### `app/services/audio_service.py`

- 整合現有的 `generate_audio_gemini.py` 功能
- 將優化後的轉錄稿轉換為音訊檔案
- 返回音訊檔案路徑和 metadata

#### `app/api/routes.py`

- `POST /api/upload` - 上傳文字內容
- `GET /api/status/{task_id}` - 查詢任務狀態
- `GET /api/download/{task_id}/audio` - 下載音訊檔案
- `GET /api/download/{task_id}/transcript` - 下載轉錄稿
- `GET /api/stream/{task_id}` - SSE 進度串流

### 3. 進度追蹤

- 使用 Server-Sent Events (SSE) 實現即時進度更新
- 任務狀態：`pending` → `processing` → `step1` → `step2` → `step3` → `completed` / `failed`
- 使用記憶體或 Redis 儲存任務狀態

### 4. 檔案管理

- 上傳檔案暫存在 `uploads/` 目錄
- 產出檔案儲存在 `outputs/{task_id}/` 目錄
- 定期清理舊檔案（可選）

## 前端架構 (React)

### 1. 專案結構

```javascript
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── UploadForm.tsx       # 上傳表單
│   │   ├── ProgressBar.tsx     # 進度條
│   │   ├── StatusDisplay.tsx   # 狀態顯示
│   │   └── DownloadButtons.tsx # 下載按鈕
│   ├── services/
│   │   └── api.ts              # API 客戶端
│   ├── hooks/
│   │   └── useProgress.tsx     # SSE 進度追蹤 hook
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts (或 create-react-app)
```



### 2. 核心功能

- 文字上傳介面（支援多行文字輸入）
- 即時進度顯示（使用 SSE）
- 下載按鈕（音訊和轉錄稿）
- 錯誤處理和重試機制

## 整合現有代碼

### 重用現有功能

- 將 `generate_audio_gemini.py` 的核心功能整合到 `audio_service.py`
- 將 `src/prompt.py` 的 prompt 直接導入使用
- 保持現有的 TTS 配置和錯誤重試機制

### 資料流程

1. **上傳階段**

- 前端發送文字內容到 `POST /api/upload`
- 後端建立任務，返回 `task_id`
- 開始非同步處理

2. **處理階段**（透過 SSE 推送進度）

- 步驟1：生成初始轉錄稿（30%）
- 步驟2：優化轉錄稿（60%）
- 步驟3：生成音訊檔案（90%）
- 完成（100%）

3. **下載階段**

- 前端透過 `task_id` 下載音訊和轉錄稿

## 技術細節

### 後端依賴

- `fastapi` - Web 框架
- `uvicorn` - ASGI 伺服器
- `openai` - LLM API
- `google-cloud-texttospeech` - TTS API
- `pydantic` - 資料驗證
- `python-multipart` - 檔案上傳處理
- `sse-starlette` - SSE 支援

### 前端依賴

- `react` + `react-dom`
- `axios` 或 `fetch` - HTTP 請求
- `event-source-polyfill` - SSE 支援（如需要）

## 環境變數

- `OPENAI_API_KEY` - OpenAI API 金鑰
- `GOOGLE_APPLICATION_CREDENTIALS` - Google Cloud 認證
- `GOOGLE_CLOUD_PROJECT` - Google Cloud 專案 ID

## 實施步驟

1. 建立後端 FastAPI 專案結構
2. 實現 LLM 服務（整合 prompt）
3. 實現轉錄稿生成服務（兩步驟）
4. 實現音訊生成服務（整合現有代碼）