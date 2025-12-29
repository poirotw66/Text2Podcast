#!/usr/bin/env python3
"""
合并音频文件脚本
从 metadata.json 读取音频文件列表并合并
"""

import json
from pathlib import Path

try:
    from pydub import AudioSegment
except ImportError:
    print("错误: 需要安装 pydub")
    print("安装命令: pip install pydub")
    exit(1)


def merge_audio_files(
    metadata_file: str = "output/metadata.json",
    output_file: str = "output/merged_audio.mp3",
    silence_duration_ms: int = 500
):
    """
    合并所有音频文件
    
    Args:
        metadata_file: 元数据文件路径
        output_file: 输出文件路径
        silence_duration_ms: 音频片段之间的静音时长（毫秒）
    """
    # 读取元数据
    metadata_path = Path(metadata_file)
    if not metadata_path.exists():
        print(f"错误: 找不到元数据文件: {metadata_file}")
        return
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    audio_files = metadata.get("audio_files", [])
    
    if not audio_files:
        print("错误: 元数据中没有找到音频文件")
        return
    
    print(f"准备合并 {len(audio_files)} 个音频文件...")
    print()
    
    combined = AudioSegment.empty()
    
    for i, item in enumerate(audio_files, 1):
        file_path = Path(item["file"])
        
        if not file_path.exists():
            print(f"警告: 文件不存在，跳过: {file_path.name}")
            continue
        
        print(f"[{i}/{len(audio_files)}] 添加: {file_path.name} ({item['speaker']})")
        
        try:
            audio = AudioSegment.from_mp3(str(file_path))
            combined += audio
            
            # 添加静音（最后一段不加）
            if i < len(audio_files):
                combined += AudioSegment.silent(duration=silence_duration_ms)
        except Exception as e:
            print(f"  错误: 无法处理文件 {file_path.name}: {e}")
            continue
    
    # 保存合并后的文件
    output_path = Path(output_file)
    output_path.parent.mkdir(exist_ok=True)
    
    print()
    print(f"正在保存合并后的音频文件...")
    combined.export(str(output_path), format="mp3")
    
    # 计算时长
    duration_seconds = len(combined) / 1000.0
    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    
    print()
    print("=" * 50)
    print(f"合并完成！")
    print(f"输出文件: {output_path.absolute()}")
    print(f"总时长: {minutes} 分 {seconds} 秒")
    print(f"文件大小: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("=" * 50)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="合并音频文件")
    parser.add_argument(
        "-m", "--metadata",
        type=str,
        default="output/metadata.json",
        help="元数据文件路径（默认: output/metadata.json）"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output/merged_audio.mp3",
        help="输出文件路径（默认: output/merged_audio.mp3）"
    )
    parser.add_argument(
        "-s", "--silence",
        type=int,
        default=500,
        help="音频片段之间的静音时长，单位毫秒（默认: 500）"
    )
    
    args = parser.parse_args()
    
    merge_audio_files(args.metadata, args.output, args.silence)



