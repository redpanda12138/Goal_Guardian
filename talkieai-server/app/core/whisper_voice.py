import re
import torch
from transformers import pipeline
from transformers import WhisperProcessor, WhisperForConditionalGeneration, GenerationConfig
import torchaudio
import tempfile
import os
from typing import Optional
import logging
import librosa
import numpy as np

class WhisperVoiceProcessor:
    def __init__(self, model_name: str = "ivabojic/whisper-medium-sing2eng-translate"):
        """初始化 Whisper 模型"""
        self.device = 0 if torch.cuda.is_available() else -1
        self._torch_device = torch.device("cuda" if self.device >= 0 else "cpu")
        self.model_name = model_name
        self.pipe = None

        # 使用本地模型路径
        self.load_model_from_local_path()
    
    def load_model_from_local_path(self):
        """从本地路径加载模型"""
        current_file_dir = os.path.dirname(os.path.abspath(__file__))  # app/core/
        parent_dir = os.path.dirname(current_file_dir)  # app/
        grandparent_dir = os.path.dirname(parent_dir)  # talkieai-server/

        # 一键切换模型：
        # 1) WHISPER_MODEL_PATH: 指定绝对/相对路径（优先级最高）
        # 2) WHISPER_MODEL_PROFILE: medium | offline（默认 medium）
        custom_model_path = (os.environ.get("WHISPER_MODEL_PATH") or "").strip()
        model_profile = (os.environ.get("WHISPER_MODEL_PROFILE") or "medium").strip().lower()

        profile_to_dir = {
            "medium": "whisper-medium-sing2eng-translate",
            "offline": "whisper-model-offline",
        }
        profile_dir_name = profile_to_dir.get(model_profile, profile_to_dir["medium"])

        if custom_model_path:
            local_model_path = custom_model_path
            if not os.path.isabs(local_model_path):
                local_model_path = os.path.abspath(os.path.join(grandparent_dir, local_model_path))
            logging.info(
                f"Whisper 使用自定义模型路径(WHISPER_MODEL_PATH): {local_model_path}"
            )
        else:
            local_model_path = os.path.abspath(
                os.path.join(grandparent_dir, "mas", profile_dir_name)
            )
            logging.info(
                f"Whisper 按 profile 加载模型: profile={model_profile}, path={local_model_path}"
            )

        # 兼容旧目录布局：项目根目录下直接放 whisper-model-offline
        if not os.path.exists(local_model_path):
            project_root_dir = os.path.dirname(grandparent_dir)
            legacy_offline_path = os.path.abspath(
                os.path.join(project_root_dir, "whisper-model-offline")
            )
            if os.path.exists(legacy_offline_path):
                local_model_path = legacy_offline_path
                logging.info(f"Whisper 使用旧版兼容路径: {local_model_path}")
        
        # 检查路径是否存在
        if os.path.exists(local_model_path):
            try:
                logging.info(f"模型路径存在，开始加载模型: {local_model_path}")
                # 禁用加载进度条与冗余日志（含 Loading weights 的 tqdm）
                _env_hf = os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS")
                _env_tqdm = os.environ.get("TQDM_DISABLE")
                os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
                os.environ["TQDM_DISABLE"] = "1"
                try:
                    import transformers
                    transformers.logging.set_verbosity_error()
                except Exception:
                    pass
                # 与官方 README 一致：Processor 加载时传入 task="translate"（Sing2Eng 为翻译任务）
                self.processor = WhisperProcessor.from_pretrained(local_model_path, task="translate")
                self.model = WhisperForConditionalGeneration.from_pretrained(local_model_path)
                self.model = self.model.to(self._torch_device)
                if self._torch_device.type == "cuda" and torch.cuda.is_bf16_supported():
                    self.model = self.model.to(torch.float16)
                logging.info(f"Whisper Processor+Model 加载成功，设备: {'GPU' if self.device >= 0 else 'CPU'}")
                if _env_hf is not None:
                    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = _env_hf
                else:
                    os.environ.pop("HF_HUB_DISABLE_PROGRESS_BARS", None)
                if _env_tqdm is not None:
                    os.environ["TQDM_DISABLE"] = _env_tqdm
                else:
                    os.environ.pop("TQDM_DISABLE", None)
                self.pipe = None  # 已取消 pipeline 回退，不再加载
            except Exception as e:
                try:
                    if _env_hf is not None:
                        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = _env_hf
                    else:
                        os.environ.pop("HF_HUB_DISABLE_PROGRESS_BARS", None)
                    if _env_tqdm is not None:
                        os.environ["TQDM_DISABLE"] = _env_tqdm
                    else:
                        os.environ.pop("TQDM_DISABLE", None)
                except NameError:
                    pass
                logging.error(f"从本地路径加载模型失败: {e}")
                import traceback
                traceback.print_exc()
                self.pipe = None
                self.processor = None
                self.model = None
        else:
            logging.error(f"本地模型路径不存在: {local_model_path}")
            logging.info(f"当前工作目录: {os.getcwd()}")
            # 列出可能的路径供调试
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_file_dir)
            grandparent_dir = os.path.dirname(parent_dir)
            logging.info(f"talkieai-server目录: {grandparent_dir}")
            if os.path.exists(grandparent_dir):
                try:
                    dir_contents = os.listdir(grandparent_dir)
                    logging.info(f"talkieai-server目录内容: {dir_contents}")
                    # 检查 mas 目录是否存在
                    mas_dir = os.path.join(grandparent_dir, "mas")
                    if os.path.exists(mas_dir):
                        logging.info(f"mas目录存在: {mas_dir}")
                        mas_contents = os.listdir(mas_dir)
                        logging.info(f"mas目录内容: {mas_contents}")
                        # 检查两个可切换模型目录是否存在
                        model_dir = os.path.join(mas_dir, profile_dir_name)
                        if os.path.exists(model_dir):
                            logging.info(f"模型目录存在: {model_dir}")
                            logging.error(f"但是代码计算的路径是: {local_model_path}")
                            logging.error(f"路径不匹配！请检查路径计算逻辑")
                        else:
                            logging.error(f"模型目录不存在: {model_dir}")
                    else:
                        logging.error(f"mas目录不存在: {mas_dir}")
                except Exception as e:
                    logging.error(f"列出目录内容失败: {e}")
            self.pipe = None

    def transcribe_audio(self, audio_path: str, language: Optional[str] = "en") -> Optional[str]:
        """转录音频文件。language 默认 "en"（英文）；传 "zh" 等则固定其他语言；None 为自动检测。"""
        if not (self.processor and self.model) and not self.pipe:
            logging.error("Whisper 模型未正确初始化")
            return None
        try:
            if not os.path.exists(audio_path):
                logging.error(f"音频文件不存在: {audio_path}")
                return None
            # 与 test_sing2eng_download.py 一致：直接从原始路径加载，不做预处理，避免重采样/写回导致模型输出退化（全 !）
            path_to_use = audio_path
            logging.info(f"Whisper 转录输入: {path_to_use}")
            audio_data, sample_rate = librosa.load(path_to_use, sr=16000, mono=True)
            duration = len(audio_data) / float(sample_rate) if len(audio_data) else 0
            peak = float(np.abs(audio_data).max()) if len(audio_data) else 0
            logging.info(f"Whisper 音频: duration={duration:.2f}s, samples={len(audio_data)}, peak={peak:.4f}")
            if duration < 0.3:
                logging.warning(f"音频过短 ({duration:.2f}s)，可能仅得到占位符: {audio_path}")
            if peak < 1e-6:
                logging.warning("音频几乎静音 (peak≈0)，模型可能只输出占位符")
            # 不再做 peak 归一化与默认降噪，保持与 Sing2Eng README 一致，避免输入分布偏移导致全 "!" 退化

            # 仅当明确启用时做降噪：WHISPER_NOISEREDUCE=1
            if os.environ.get("WHISPER_NOISEREDUCE", "").strip() in ("1", "true"):
                try:
                    import noisereduce as nr
                    audio_data = nr.reduce_noise(y=audio_data, sr=sample_rate, prop_decrease=0.4)
                except ImportError:
                    pass

            transcription = ""
            last_raw_from_model = ""

            # Processor+Model：先做与 test_sing2eng_download.py 完全一致的 README 式调用（CPU float32、不截断、不传 task），再 fallback
            if self.processor and self.model:
                model_dtype = next(self.model.parameters()).dtype
                # 与测试脚本一致：processor(audio=..., return_tensors="pt")，不传 task
                proc_readme = self.processor(
                    audio_data,
                    sampling_rate=sample_rate,
                    return_tensors="pt",
                )
                # 测试脚本在 CPU float32 下 generate，不 to(device/dtype)；此处对齐：临时 CPU float32 推理
                input_features_readme = proc_readme.input_features
                _saved_device = next(self.model.parameters()).device
                _saved_dtype = next(self.model.parameters()).dtype
                try:
                    self.model = self.model.to("cpu", torch.float32)
                    with torch.no_grad():
                        predicted_ids = self.model.generate(input_features_readme)
                finally:
                    self.model = self.model.to(_saved_device, _saved_dtype)
                raw = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
                last_raw_from_model = raw
                transcription = self._normalize_transcription(raw)
                _sample = (raw[:120] + "…") if len(raw) > 120 else raw
                logging.info(
                    f"Whisper README式(不截断/不传task): raw_len={len(raw)}, normalized_ok={bool(transcription)}, sample={repr(_sample)}"
                )
                # 2b) README 式无效时再走截断 + task=translate/transcribe
                if not transcription:
                    proc_out = self.processor(
                        audio_data,
                        sampling_rate=sample_rate,
                        return_tensors="pt",
                        return_attention_mask=True,
                    )
                    input_features = proc_out.input_features
                    attention_mask = getattr(proc_out, "attention_mask", None)
                    n_frames = min(
                        input_features.shape[-1],
                        max(1, int(len(audio_data) * input_features.shape[-1] / (30.0 * sample_rate))),
                    )
                    if n_frames < input_features.shape[-1]:
                        input_features = input_features[:, :, :n_frames].contiguous()
                        attention_mask = torch.ones((1, n_frames), dtype=torch.long, device=input_features.device)
                    elif attention_mask is None and input_features is not None and n_frames > 0:
                        mask = torch.zeros(
                            (1, input_features.shape[-1]),
                            dtype=torch.long,
                            device=input_features.device,
                        )
                        mask[:, :n_frames] = 1
                        attention_mask = mask
                    try:
                        x = input_features.detach().float().numpy()
                        logging.info(
                            f"Whisper input_features: shape={x.shape}, min={float(x.min()):.4f}, max={float(x.max()):.4f}, mean={float(x.mean()):.4f}"
                        )
                    except Exception:
                        pass
                    input_features = input_features.to(device=self._torch_device, dtype=model_dtype)
                    if attention_mask is not None:
                        attention_mask = attention_mask.to(self._torch_device)
                    gen_common = {
                        "task": "translate",
                        "language": language or "en",
                    }
                    if attention_mask is not None:
                        gen_common["attention_mask"] = attention_mask
                    with torch.no_grad():
                        predicted_ids = self.model.generate(input_features, **gen_common)
                    raw = self.processor.batch_decode(
                        predicted_ids, skip_special_tokens=True
                    )[0].strip()
                    last_raw_from_model = raw
                    transcription = self._normalize_transcription(raw)
                    _sample = (raw[:120] + "…") if len(raw) > 120 else raw
                    logging.info(
                        f"Whisper 第1次(translate): raw_len={len(raw)}, normalized_ok={bool(transcription)}, sample={repr(_sample)}"
                    )
                    # 第二次尝试：仍为 translate
                    if not transcription:
                        logging.info("Whisper 第二次尝试: task=translate, language=en")
                        with torch.no_grad():
                            predicted_ids = self.model.generate(input_features, **gen_common)
                        raw = self.processor.batch_decode(
                            predicted_ids, skip_special_tokens=True
                        )[0].strip()
                        last_raw_from_model = raw
                        transcription = self._normalize_transcription(raw)
                        _sample = (raw[:120] + "…") if len(raw) > 120 else raw
                        logging.info(
                            f"Whisper 第2次(translate): raw_len={len(raw)}, normalized_ok={bool(transcription)}, sample={repr(_sample)}"
                        )
                    # 第三次尝试：transcribe 模式（仍用模型默认 generation_config，不加重 penalty）
                    if not transcription:
                        logging.info("Whisper 第三次尝试: task=transcribe")
                        gen_transcribe = {**gen_common, "task": "transcribe"}
                        with torch.no_grad():
                            predicted_ids = self.model.generate(input_features, **gen_transcribe)
                        raw = self.processor.batch_decode(
                            predicted_ids, skip_special_tokens=True
                        )[0].strip()
                        last_raw_from_model = raw
                        transcription = self._normalize_transcription(raw)
                        _sample = (raw[:120] + "…") if len(raw) > 120 else raw
                        logging.info(
                            f"Whisper 第3次(transcribe): raw_len={len(raw)}, normalized_ok={bool(transcription)}, sample={repr(_sample)}"
                        )
            # 已改为仅用原始路径加载，不再生成预处理临时文件，无需清理
            # 模型在静音/极短音频时常只输出占位符 "-" 或全标点（如 "!!!"），已由 _normalize_transcription 统一处理
            if transcription and transcription.strip() in ("-", ""):
                transcription = ""
            if transcription:
                logging.info(f"Whisper 转录成功，长度: {len(transcription)}")
            else:
                logging.warning("Whisper 返回空或无效（如全标点），已视为未识别到内容")
                if self.processor and self.model and last_raw_from_model is not None and len(last_raw_from_model) > 0:
                    sample = (last_raw_from_model[:300] + "…") if len(last_raw_from_model) > 300 else last_raw_from_model
                    logging.info(f"Whisper 末次原始输出(供排查): len={len(last_raw_from_model)}, sample={repr(sample)}")
            return transcription if transcription else ""
        except Exception as e:
            logging.error(f"Whisper音频转录失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _normalize_transcription(self, text: str) -> str:
        """将仅含占位符或退化模式（如 !!A!!B!!C、全标点）的结果视为空，避免误展示与误打成功日志"""
        if not text or not isinstance(text, str):
            return ""
        s = text.strip()
        if not s or s in ("-",):
            return ""
        # 去掉仅由标点/空格组成的“假”结果（无字母、数字、中日韩字符）
        if not re.search(r"[a-zA-Z0-9\u4e00-\u9fff]", s):
            return ""
        effective = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "", s)
        # 有效字符过少（如仅 1 个字母混在大量 "!!!" 中）视为无效
        if len(effective) < 2:
            return ""
        # 长文本中有效字符占比过低视为无效（真实转写多为连续词语，有效占比高；退化输出如 !!A!!B!!C 约 1/3）
        if len(s) > 80 and len(effective) / len(s) < 0.40:
            return ""
        # 含大量 "!" 的重复模式（如 !!$!!%!!A!!B!!）视为模型退化，丢弃
        if s.count("!") / max(len(s), 1) > 0.25:
            return ""
        # 显式检测 "!!" + 单字符 重复多次（模型退化输出），丢弃
        if len(s) > 50 and s.count("!!") >= 15:
            return ""
        # 出现 Unicode 替换符 视为解码异常，丢弃
        if "\ufffd" in s:
            return ""
        return s

    def _extract_text_from_result(self, result) -> str:
        """兼容多种 pipeline 返回格式，统一取出文本"""
        if result is None:
            return ""
        # 返回 list（多段）时取第一段
        if isinstance(result, list):
            if not result:
                return ""
            result = result[0]
        if not isinstance(result, dict):
            return ""
        # 常见键名
        text = result.get("text") or result.get("transcription") or ""
        if isinstance(text, str):
            return text.strip()
        # 含 chunks 时拼接
        chunks = result.get("chunks")
        if chunks and isinstance(chunks, list):
            parts = []
            for c in chunks:
                if isinstance(c, dict) and c.get("text"):
                    parts.append(c["text"])
                elif isinstance(c, str):
                    parts.append(c)
            return " ".join(parts).strip()
        return ""
    
    def preprocess_audio(self, audio_path: str, target_sr: int = 16000) -> str:
        """
        预处理音频文件，使其符合 Whisper 模型要求
        """
        try:
            # 使用 librosa 加载音频（更兼容的音频处理库），强制单声道
            audio_data, sample_rate = librosa.load(audio_path, sr=None, mono=True)
            duration = len(audio_data) / sample_rate if len(audio_data) else 0
            if duration < 0.2:
                logging.warning(f"音频过短 ({duration:.2f}s)，可能无法识别: {audio_path}")
            # 重新采样到目标采样率
            if sample_rate != target_sr:
                audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=target_sr)
            
            # 保存预处理后的音频到临时文件
            temp_dir = os.path.dirname(audio_path)
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            temp_filename = os.path.join(temp_dir, f"temp_processed_{base_name}.wav")
            # 使用 soundfile 保存（因为 librosa.output 已弃用）
            import soundfile as sf
            sf.write(temp_filename, audio_data, target_sr)
            return temp_filename
        except ImportError:
            # 如果没有安装soundfile，回退到原来的处理方式
            try:
                import scipy.io.wavfile as wavfile
                audio_data, sample_rate = librosa.load(audio_path, sr=None)
                if sample_rate != target_sr:
                    audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=target_sr)
                temp_dir = os.path.dirname(audio_path)
                temp_filename = os.path.join(temp_dir, f"temp_processed_{os.path.basename(audio_path)}")
                wavfile.write(temp_filename, target_sr, (audio_data * 32767).astype(np.int16))
                return temp_filename
            except Exception as e:
                logging.warning(f"音频预处理失败，使用原始文件: {e}")
                return audio_path  # 返回原始路径，让模型尝试处理

# 全局实例
try:
    whisper_processor = WhisperVoiceProcessor()
    logging.info("Whisper处理器初始化完成")
except Exception as e:
    logging.error(f"Whisper处理器初始化失败: {e}")
    import traceback
    traceback.print_exc()
    # 创建一个pipe为None的实例，这样应用程序可以启动，但功能不可用
    whisper_processor = WhisperVoiceProcessor.__new__(WhisperVoiceProcessor)
    whisper_processor.device = 0 if torch.cuda.is_available() else -1
    whisper_processor._torch_device = torch.device("cuda" if whisper_processor.device >= 0 else "cpu")
    whisper_processor.model_name = "ivabojic/whisper-medium-sing2eng-translate"
    whisper_processor.pipe = None
    whisper_processor.processor = None
    whisper_processor.model = None
    whisper_processor.load_model_from_local_path = lambda: None
    whisper_processor.transcribe_audio = lambda audio_path, language=None: None
