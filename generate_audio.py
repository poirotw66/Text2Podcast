#!/usr/bin/env python3
"""
使用 OpenAI TTS API 生成音频文件
从转录文件生成双人对话的音频
"""

import os
import json
from pathlib import Path
from openai import OpenAI
from typing import List, Tuple, Dict

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # 如果没有安装 python-dotenv，跳过

# 初始化 OpenAI 客户端（延迟初始化，在 main 函数中检查）
client = None

# 为不同说话人配置不同的声音
SPEAKER_VOICES = {
    "Speaker 1": "nova",      # 较专业、清晰的声音
    "Speaker 2": "shimmer"    # 较活泼、有活力的声音
}

# TTS 模型配置
TTS_MODEL = "tts-1"  # 使用高质量模型，如需节省成本可改为 "tts-1"
AUDIO_FORMAT = "mp3"    # 输出格式：mp3, opus, aac, flac


def parse_transcript(file_path: str) -> List[Tuple[str, str]]:
    """
    解析转录文件
    
    Args:
        file_path: 转录文件路径
        
    Returns:
        包含 (speaker, text) 元组的列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # 解析 Python 列表格式
    # 格式: [("Speaker 1", "text"), ...]
    try:
        transcript = eval(content)
        return transcript
    except Exception as e:
        raise ValueError(f"无法解析转录文件: {e}")


def get_client() -> OpenAI:
    """获取 OpenAI 客户端（延迟初始化）"""
    global client
    if client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 未设置，请检查 .env 文件或环境变量")
        client = OpenAI(api_key=api_key)
    return client


def generate_single_audio(
    text: str,
    voice: str,
    output_file: Path,
    model: str = TTS_MODEL
) -> bool:
    """
    生成单个音频文件
    
    Args:
        text: 要转换的文本
        voice: 声音类型
        output_file: 输出文件路径
        model: TTS 模型
        
    Returns:
        是否成功
    """
    try:
        print(f"  生成音频: {output_file.name}")
        
        openai_client = get_client()
        response = openai_client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format=AUDIO_FORMAT
        )
        
        # 保存音频文件
        response.stream_to_file(str(output_file))
        return True
        
    except Exception as e:
        print(f"  错误: {e}")
        return False


def generate_audio_from_transcript(
    transcript_file: str,
    output_dir: str = "output",
    model: str = TTS_MODEL
) -> Dict:
    """
    从转录文件生成所有音频
    
    Args:
        transcript_file: 转录文件路径
        output_dir: 输出目录
        model: TTS 模型
        
    Returns:
        包含生成结果的字典
    """
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # 解析转录文件
    print(f"解析转录文件: {transcript_file}")
    transcript = parse_transcript(transcript_file)
    print(f"找到 {len(transcript)} 段对话\n")
    
    # 生成音频
    audio_files = []
    success_count = 0
    fail_count = 0
    
    for i, (speaker, text) in enumerate(transcript, 1):
        print(f"[{i}/{len(transcript)}] {speaker}:")
        print(f"  文本: {text[:50]}..." if len(text) > 50 else f"  文本: {text}")
        
        # 选择声音
        voice = SPEAKER_VOICES.get(speaker, "alloy")
        
        # 生成输出文件名
        output_file = output_path / f"{speaker.replace(' ', '_')}_{i:03d}.{AUDIO_FORMAT}"
        
        # 生成音频
        if generate_single_audio(text, voice, output_file, model):
            audio_files.append({
                "speaker": speaker,
                "index": i,
                "file": str(output_file),
                "text": text,
                "voice": voice
            })
            success_count += 1
        else:
            fail_count += 1
        
        print()
    
    # 保存元数据
    metadata_file = output_path / "metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_segments": len(transcript),
            "success": success_count,
            "failed": fail_count,
            "audio_files": audio_files
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成！")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"输出目录: {output_path.absolute()}")
    print(f"元数据: {metadata_file}")
    
    return {
        "success": success_count,
        "failed": fail_count,
        "audio_files": audio_files,
        "output_dir": str(output_path)
    }


def merge_audio_files(
    metadata_file: str,
    output_file: str = "output/merged_audio.mp3",
    silence_duration_ms: int = 500
) -> str:
    """
    合并所有音频文件（需要安装 pydub）
    
    Args:
        metadata_file: 元数据文件路径
        output_file: 输出文件路径
        silence_duration_ms: 音频片段之间的静音时长（毫秒）
        
    Returns:
        合并后的文件路径
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        print("错误: 需要安装 pydub 才能合并音频")
        print("安装命令: pip install pydub")
        return None
    
    # 读取元数据
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    audio_files = metadata.get("audio_files", [])
    
    if not audio_files:
        print("没有找到音频文件")
        return None
    
    print(f"合并 {len(audio_files)} 个音频文件...")
    
    combined = AudioSegment.empty()
    
    for i, item in enumerate(audio_files, 1):
        file_path = item["file"]
        print(f"  [{i}/{len(audio_files)}] 添加: {Path(file_path).name}")
        
        audio = AudioSegment.from_mp3(file_path)
        combined += audio
        
        # 添加静音（最后一段不加）
        if i < len(audio_files):
            combined += AudioSegment.silent(duration=silence_duration_ms)
    
    # 保存合并后的文件
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True)
    combined.export(str(output_path), format="mp3")
    
    print(f"\n合并完成: {output_path.absolute()}")
    return str(output_path)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="使用 OpenAI TTS API 生成音频")
    parser.add_argument(
        "transcript_file",
        type=str,
        help="转录文件路径"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output",
        help="输出目录（默认: output）"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=TTS_MODEL,
        choices=["tts-1", "tts-1-hd"],
        help=f"TTS 模型（默认: {TTS_MODEL}）"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="生成后自动合并所有音频文件（需要 pydub）"
    )
    parser.add_argument(
        "--merge-output",
        type=str,
        default=None,
        help="合并后的输出文件路径（默认: output/merged_audio.mp3）"
    )
    
    args = parser.parse_args()
    
    # 检查 API Key（会在 get_client() 中再次检查，这里提前检查给出友好提示）
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("错误: 请设置 OPENAI_API_KEY")
        print("方法 1: 在 .env 文件中设置: OPENAI_API_KEY=your-api-key")
        print("方法 2: 设置环境变量: export OPENAI_API_KEY='your-api-key'")
        return
    
    # 检查文件是否存在
    if not Path(args.transcript_file).exists():
        print(f"错误: 文件不存在: {args.transcript_file}")
        return
    
    # 生成音频
    result = generate_audio_from_transcript(
        args.transcript_file,
        args.output,
        args.model
    )
    
    # 如果需要合并
    if args.merge:
        metadata_file = Path(args.output) / "metadata.json"
        merge_output = args.merge_output or str(Path(args.output) / "merged_audio.mp3")
        merge_audio_files(str(metadata_file), merge_output)


if __name__ == "__main__":
    main()

