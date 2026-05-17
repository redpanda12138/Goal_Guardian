# Sing2Eng 模型下载与使用说明

## 一、模型信息（官方）

- **Hugging Face**：https://huggingface.co/ivabojic/whisper-small-sing2eng-translate  
- **GitHub**：https://github.com/IvaBojic/Singlish2English  
- **用途**：Singlish 语音 → 英文文本（翻译任务，不是听写）  
- **基座**：openai/whisper-small，约 242M 参数，权重格式 **safetensors**（约 **967 MB**）

---

## 二、必须包含的文件（缺一不可）

从 Hugging Face 仓库根目录应包含：

| 文件 | 说明 | 大小约 |
|------|------|--------|
| **model.safetensors** | 模型权重（必须） | **967 MB** |
| config.json | 模型结构配置 | 1.38 kB |
| generation_config.json | 生成参数 | 3.84 kB |
| preprocessor_config.json | 特征提取配置 | 339 B |
| vocab.json | 词表 | 1.04 MB |
| merges.txt | BPE 合并表 | 494 kB |
| tokenizer_config.json | 分词器配置 | 283 kB |
| normalizer.json | 文本归一化 | 52.7 kB |
| special_tokens_map.json | 特殊 token | 2.19 kB |
| added_tokens.json | 额外 token | 34.6 kB |
| README.md | 说明 | 5.56 kB |
| .gitattributes | Git 属性 | 1.52 kB |
| fine_tuning.log | 可选 | 8.15 kB |

**若缺少 `model.safetensors`，模型无法加载或会从缓存/网络用别的权重，易出现全 "!" 等异常输出。**

---

## 三、正确下载方式

### 方式 1：huggingface-cli（推荐）

1. 安装并登录（如需下载 gated 或大文件）：
   ```bash
   pip install huggingface_hub
   huggingface-cli login
   ```

2. 下载到项目目录（完整仓库，含 **model.safetensors**）：
   ```bash
   cd talkieai-server/mas
   huggingface-cli download ivabojic/whisper-small-sing2eng-translate --local-dir whisper-model-offline --local-dir-use-symlinks False
   ```

3. 检查是否包含权重文件：
   ```bash
   dir whisper-model-offline\model.safetensors
   # 或
   ls whisper-model-offline/model.safetensors
   ```
   文件约 967 MB，存在则说明下载完整。

### 方式 2：Git LFS（完整克隆）

```bash
cd talkieai-server/mas
git lfs install
git clone https://huggingface.co/ivabojic/whisper-small-sing2eng-translate whisper-model-offline
```

克隆后确认 `whisper-model-offline/model.safetensors` 存在且约 967 MB（若只有几 KB，说明 LFS 未拉取，需 `git lfs pull`）。

### 方式 3：Python 脚本下载

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="ivabojic/whisper-small-sing2eng-translate",
    local_dir="talkieai-server/mas/whisper-model-offline",
    local_dir_use_symlinks=False,
)
```

运行后同样检查 `whisper-model-offline/model.safetensors` 是否存在且约 967 MB。

---

## 四、官方推荐用法（README）

```python
import torch
import torchaudio
from transformers import WhisperProcessor, WhisperForConditionalGeneration

task = "translate"
model_name = "ivabojic/whisper-small-sing2eng-translate"
# 使用本地路径时：
# local_path = "talkieai-server/mas/whisper-model-offline"
# model = WhisperForConditionalGeneration.from_pretrained(local_path)
# processor = WhisperProcessor.from_pretrained(local_path, task)

model = WhisperForConditionalGeneration.from_pretrained(model_name)
processor = WhisperProcessor.from_pretrained(model_name, task)

audio_path = "path_to_audio.wav"  # 16 kHz 单声道，或下面重采样
audio, sr = torchaudio.load(audio_path)
if sr != 16000:
    resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
    audio = resampler(audio)
audio = audio.squeeze().numpy()

inputs = processor(audio=audio, sampling_rate=16000, return_tensors="pt")
with torch.no_grad():
    predicted_ids = model.generate(inputs.input_features)

translation = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
print(translation)
```

要点：

- **Processor**：`WhisperProcessor.from_pretrained(model_name, task)`，其中 `task="translate"`。  
- **音频**：16 kHz 单声道；若原文件不是，用 `torchaudio` 重采样并 `squeeze().numpy()`。  
- **推理**：只传 `inputs.input_features`，不传 `task`/`language`（README 示例如此；若你遇到问题可再试在 `generate` 里显式传 `task="translate"`, `language="en"`）。  
- **本地路径**：把 `model_name` 换成 `"talkieai-server/mas/whisper-model-offline"`（或绝对路径）即可离线使用。

---

## 五、你当前可能的问题

- 在 `talkieai-server/mas/whisper-model-offline` 下**没有** `model.safetensors`（约 967 MB），只有 config/tokenizer 等小文件。  
- 这样要么加载失败，要么用到别处缓存的权重，容易出现“能跑但输出全 `!`”等异常。

**建议**：

1. 按上面「三、正确下载方式」重新下载，并确认 **model.safetensors** 存在且约 967 MB。  
2. 若之前用浏览器或其它工具只下了部分文件，请改用 `huggingface-cli download` 或 `snapshot_download` 完整下载到 `whisper-model-offline`。  
3. 用官方 README 脚本 + 同一段 Singlish 音频，先测试本地目录是否能正常出英文；再对比当前服务里的预处理/调用方式。

---

## 六、测试是否下载完整（快速检查）

在项目根目录或 `talkieai-server` 下运行：

```bash
python -c "
import os
p = 'mas/whisper-model-offline'
for f in ['model.safetensors', 'config.json', 'vocab.json']:
    path = os.path.join(p, f)
    exists = os.path.isfile(path)
    size = os.path.getsize(path) / (1024*1024) if exists else 0
    print(f'{f}: exists={exists}, size_MB={size:.2f}')
"
```

若 `model.safetensors` 的 `exists=False` 或 `size_MB` 远小于 900，说明需要按第三节重新下载。
