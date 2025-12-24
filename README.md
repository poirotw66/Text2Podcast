# PPT2Video - 音频生成工具

使用 OpenAI TTS API 从转录文件生成音频。

## 安装

```bash
pip install -r requirements.txt
```

## 配置

设置 OpenAI API Key：

```bash
export OPENAI_API_KEY="your-api-key-here"
```

或在 `.env` 文件中：

```
OPENAI_API_KEY=your-api-key-here
```

## 使用方法

### 基本使用

```bash
python generate_audio.py example/3_enhance_transcipt.txt
```

### 指定输出目录

```bash
python generate_audio.py example/3_enhance_transcipt.txt -o audio_output
```

### 使用标准模型（节省成本）

```bash
python generate_audio.py example/3_enhance_transcipt.txt -m tts-1
```

### 生成并自动合并音频

```bash
python generate_audio.py example/3_enhance_transcipt.txt --merge
```

### 完整参数示例

```bash
python generate_audio.py example/3_enhance_transcipt.txt \
    -o audio_output \
    -m tts-1-hd \
    --merge \
    --merge-output audio_output/final_podcast.mp3
```

## 输出

- 每个对话片段会生成独立的音频文件
- 文件名格式: `Speaker_1_001.mp3`, `Speaker_2_002.mp3` 等
- 会生成 `metadata.json` 文件，包含所有音频文件的元数据

## 声音配置

默认声音配置：
- Speaker 1: `nova` (专业、清晰)
- Speaker 2: `shimmer` (活泼、有活力)

可在 `generate_audio.py` 中修改 `SPEAKER_VOICES` 字典来更改声音。

## 注意事项

- 需要有效的 OpenAI API Key
- `tts-1-hd` 质量更高但成本更高
- `tts-1` 成本较低但质量稍低
- 合并音频功能需要安装 `pydub`（已包含在 requirements.txt）

