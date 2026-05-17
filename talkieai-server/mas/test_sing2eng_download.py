#!/usr/bin/env python3
"""
检查 Sing2Eng 本地目录是否完整，并按 README 方式做一次最小推理测试。
用法：
  cd talkieai-server/mas
  python test_sing2eng_download.py
  或指定音频： python test_sing2eng_download.py path/to/audio.wav
"""
import os
import sys

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_dir = os.path.join(script_dir, "whisper-model-offline")

    # 1) 检查必要文件
    required = {
        "model.safetensors": 900 * 1024 * 1024,  # 至少约 900 MB
        "config.json": 100,
        "generation_config.json": 100,
        "preprocessor_config.json": 100,
        "vocab.json": 100 * 1024,
    }
    print("检查目录:", local_dir)
    all_ok = True
    for name, min_size in required.items():
        path = os.path.join(local_dir, name)
        exists = os.path.isfile(path)
        size = os.path.getsize(path) if exists else 0
        ok = exists and size >= min_size
        if not ok:
            all_ok = False
        print(f"  {name}: exists={exists}, size_MB={size/(1024*1024):.2f}, ok={ok}")

    if not all_ok:
        print("\n缺少或损坏文件，请按 mas/Sing2Eng模型下载与使用说明.md 重新下载。")
        return 1

    # 2) 按 README 加载并生成（无音频则只测加载）
    print("\n加载模型与 processor...")
    import torch
    # 关闭加载进度条与 transformers 警告，便于只看结果
    _env_hf = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")
    _env_tqdm = os.environ.get("TQDM_DISABLE")
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["TQDM_DISABLE"] = "1"
    try:
        import transformers
        transformers.logging.set_verbosity_error()
    except Exception:
        pass
    from transformers import WhisperProcessor, WhisperForConditionalGeneration

    task = "translate"
    processor = WhisperProcessor.from_pretrained(local_dir, task=task)
    model = WhisperForConditionalGeneration.from_pretrained(local_dir)
    if _env_hf is not None:
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = _env_hf
    else:
        os.environ.pop("HF_HUB_DISABLE_PROGRESS_BARS", None)
    if _env_tqdm is not None:
        os.environ["TQDM_DISABLE"] = _env_tqdm
    else:
        os.environ.pop("TQDM_DISABLE", None)
    print("加载成功。")

    audio_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not audio_path or not os.path.isfile(audio_path):
        print("未提供有效音频路径，跳过推理。用法: python test_sing2eng_download.py <audio.wav>")
        return 0

    # 使用 librosa 加载（与 whisper_voice 一致），避免 torchaudio 触发 TorchCodec 报错
    try:
        import librosa
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
    except Exception as e:
        print("librosa 加载失败:", e)
        try:
            import soundfile as sf
            audio, sr = sf.read(audio_path)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr != 16000:
                import librosa as _librosa
                audio = _librosa.resample(audio.astype("float32"), orig_sr=sr, target_sr=16000)
            sr = 16000
        except Exception as e2:
            print("soundfile 加载失败（可安装: pip install soundfile）:", e2)
            return 1

    inputs = processor(audio=audio, sampling_rate=16000, return_tensors="pt")
    with torch.no_grad():
        predicted_ids = model.generate(inputs.input_features)
    text = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
    print("转录结果:", repr(text[:200]))
    if not text.strip() or text.strip().count("!") / max(len(text.strip()), 1) > 0.5:
        print("结果异常（空或几乎全为 !），请检查模型下载与音频格式。")
    else:
        print("结果看起来正常。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
