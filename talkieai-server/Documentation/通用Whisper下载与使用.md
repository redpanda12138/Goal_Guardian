# 通用 Whisper（openai/whisper-small）下载与使用

当 Sing2Eng 全部失败（pipeline + 3 次 generate 均无效）时，服务会**自动尝试**用通用 Whisper 做一次英文听写（transcribe），以至少返回可用文本。

---

## 一、何时会用到通用 Whisper？

- **自动触发**：无需配置。当 Sing2Eng 的 pipeline、3 次 `generate`、以及再次 pipeline 都得不到有效结果时，会调用通用 Whisper。
- **加载顺序**：
  1. 若设置了环境变量 **`WHISPER_GENERIC_MODEL_PATH`**，从该路径加载；
  2. 否则若存在目录 **`talkieai-server/mas/whisper-generic-offline`**，从该目录加载；
  3. 否则从 **Hugging Face 在线**拉取 `openai/whisper-small`（需联网）。

因此：**不下载也可以**——有网时第一次回退会自动下载并缓存；**要离线使用**则需按下面方式提前下载到本地。

---

## 二、下载方式（推荐放到 mas 下）

### 方式 1：huggingface-cli（推荐）

在能联网的机器上执行：

```bash
cd d:\SECOND WINDOW\NTU_Project\Dissertation\chatgpt-talkieai-main\talkieai-server\mas
pip install -U huggingface_hub
huggingface-cli download openai/whisper-small --local-dir whisper-generic-offline --local-dir-use-symlinks False
```

完成后应存在目录 **`talkieai-server/mas/whisper-generic-offline`**，且内含 **`model.safetensors`**（约 967 MB）及 config、tokenizer 等文件。

### 方式 2：Python 脚本

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="openai/whisper-small",
    local_dir="d:/SECOND WINDOW/NTU_Project/Dissertation/chatgpt-talkieai-main/talkieai-server/mas/whisper-generic-offline",
    local_dir_use_symlinks=False,
)
```

将 `local_dir` 改成你本机的实际路径即可。

### 方式 3：使用其他目录并设置环境变量

若希望放在别的盘或目录（例如 `E:\models\whisper-generic-offline`）：

1. 用上面任一方式下载到该目录；
2. 在启动服务前设置环境变量：
   - **Windows（当前 CMD/PowerShell）**：
     ```bat
     set WHISPER_GENERIC_MODEL_PATH=E:\models\whisper-generic-offline
     ```
   - **Windows 永久**：系统属性 → 环境变量 → 新建用户/系统变量 `WHISPER_GENERIC_MODEL_PATH` = 该路径。
   - **Linux / macOS**：
     ```bash
     export WHISPER_GENERIC_MODEL_PATH=/path/to/whisper-generic-offline
     ```

服务会优先从 **`WHISPER_GENERIC_MODEL_PATH`** 加载，找不到再试 **`mas/whisper-generic-offline`**，再不行才联网拉取。

---

## 三、如何确认已生效？

1. **看日志**  
   当 Sing2Eng 全部失败后，若出现：
   - `Whisper Sing2Eng 全部无效，尝试通用模型 openai/whisper-small (transcribe)`
   - `Whisper 正在从本地加载通用回退模型: ...` 或 `...加载通用回退模型(在线)`
   - `Whisper 通用模型回退成功，长度: xxx`  
   说明通用 Whisper 已参与并成功返回了文本。

2. **离线验证**  
   若已下载到 **`mas/whisper-generic-offline`**，可断网后再次触发一次“语音转文字”（先让 Sing2Eng 失败），若仍能出字且日志里是“从本地加载”，说明本地通用模型已正确调用。

---

## 四、小结

| 场景           | 做法 |
|----------------|------|
| 有网络         | 可不下载，首次回退时自动从 HF 拉取并缓存。 |
| 无网络 / 离线  | 用方式 1 或 2 下载到 `mas/whisper-generic-offline`，或下载到自定义目录并设置 `WHISPER_GENERIC_MODEL_PATH`。 |

**调用关系**：代码中由 `whisper_voice.py` 的 `transcribe_audio` 在 Sing2Eng 全部失败后自动调用 `_ensure_generic_loaded(force=True)` 和 `_run_generic_transcribe(audio_data, sample_rate)`，无需你额外写调用逻辑。
