# app/core/audio_utils.py
import torchaudio
import torch
import numpy as np
import librosa
from typing import Tuple
import os
import logging

def preprocess_audio_for_whisper(audio_path: str, target_sr: int = 16000) -> str:
    """
    预处理音频文件，使其符合 Whisper 模型要求
    """
    try:
        # 使用 librosa 加载音频（更好的音频格式兼容性）
        audio_data, sample_rate = librosa.load(audio_path, sr=None)
        
        # 重新采样到目标采样率
        if sample_rate != target_sr:
            audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=target_sr)
        
        # 保存预处理后的音频
        temp_dir = os.path.dirname(audio_path)
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        temp_filename = os.path.join(temp_dir, f"temp_{base_name}_processed.wav")
        
        # 使用 librosa 保存为 WAV 格式
        librosa.output.write_wav(temp_filename, audio_data, target_sr)
        
        logging.info(f"音频预处理完成: {audio_path} -> {temp_filename}")
        return temp_filename
    except Exception as e:
        logging.error(f"音频预处理失败: {e}")
        # 如果预处理失败，返回原始路径
        return audio_path

def validate_audio_file(audio_path: str) -> bool:
    """
    验证音频文件是否有效
    """
    try:
        # 尝试加载音频文件验证其有效性
        audio_data, sample_rate = librosa.load(audio_path, duration=1.0)  # 只加载1秒用于验证
        return len(audio_data) > 0
    except Exception:
        return False