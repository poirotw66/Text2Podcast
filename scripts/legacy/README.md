# 舊版腳本說明

本目錄存放專案早期、在後端服務（`backend/`）出現之前所寫的實驗性命令列腳本：

- `generate_audio.py`
- `generate_audio_emotion.py`
- `generate_audio_gemini.py`
- `generate_audio_gpt4o_mini.py`
- `merge_audio.py`
- `regenerate_failed_segments_gemini.py`

## 現況

這些腳本僅作為歷史參考保留，**目前維護的音訊生成邏輯**已整合並持續開發於：

```
backend/app/services/audio_service.py
```

新功能、修正與優化請一律在 `audio_service.py`（以及對應的 `backend/app` 服務層）中進行，
不要再修改本目錄下的舊版腳本。

## 依賴套件

本目錄的依賴套件獨立列於 `scripts/legacy/requirements.txt`（原專案根目錄的
`requirements.txt` 僅供這些舊版腳本使用，現已移至此處；後端服務的依賴請見
`backend/requirements.txt`，兩者互不影響）。

```bash
pip install -r scripts/legacy/requirements.txt
```

**注意**：此檔案刻意保留 `pydub`（後端已改用直接呼叫 `ffmpeg` 的方式取代
`pydub`，見 `backend/app/services/audio_service.py`）。`pydub` 依賴標準庫的
`audioop` 模組，該模組已於 PEP 594 中在 Python 3.13 移除（且常見替代方案
`audioop-lts` 在 Python 3.11 上也無法安裝），因此這些舊版腳本在 Python 3.13+
環境下將完全無法執行。

## 注意事項

- 本目錄中的腳本**不受任何測試或 CI 流程涵蓋**，其正確性無法保證。
- 腳本之間可能仍有相依關係（例如 `regenerate_failed_segments_gemini.py` 會匯入
  `generate_audio_gemini.py`），因此移動或刪除任一檔案前請先確認引用關係。
- 若僅是想使用命令列方式生成音訊，可參考根目錄 `README.md` 中「命令列使用（舊版）」章節的範例，
  但正式功能開發請透過後端服務進行。
