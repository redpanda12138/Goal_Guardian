from threading import Lock

from app.config import Config


def _build_chat_ai():
    if Config.AI_SERVER == "CHAT_GPT":
        from app.ai.impl.chat_gpt_ai import ChatGPTAI

        return ChatGPTAI(
            api_key=Config.CHAT_GPT_KEY,
            base_url=Config.CHAT_GPT_PROXY,
            model=Config.CHAT_GPT_MODEL,
        )
    if Config.AI_SERVER == "ZHIPU":
        from app.ai.impl.zhipu_ai import ZhipuAIComponent

        return ZhipuAIComponent(
            api_key=Config.ZHIPU_AI_API_KEY,
            model=Config.ZHIPU_AI_MODEL,
        )
    raise RuntimeError("AI_SERVER must be CHAT_GPT or ZHIPU")


class _LazyChatAI:
    def __init__(self):
        self._instance = None
        self._lock = Lock()

    def _get_instance(self):
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = _build_chat_ai()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get_instance(), name)


chat_ai = _LazyChatAI()
