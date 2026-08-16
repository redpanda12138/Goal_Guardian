"""
MAS系统统一的AI调用模块
支持OpenAI GPT和智谱AI
"""
import os
from typing import Any, List, Dict, Optional

# 从环境变量获取配置
AI_SERVER = os.getenv('AI_SERVER', 'ZHIPU')  # 默认使用智谱AI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ZHIPU_AI_API_KEY = os.getenv('ZHIPU_AI_API_KEY', '')
ZHIPU_AI_MODEL = os.getenv('ZHIPU_AI_MODEL', 'glm-4')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1')

_openai_client = None
_zhipu_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _get_zhipu_client():
    global _zhipu_client
    if _zhipu_client is None:
        from zhipuai import ZhipuAI
        _zhipu_client = ZhipuAI(api_key=ZHIPU_AI_API_KEY)
    return _zhipu_client


def _message_field(value: Any, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _normalize_model_message(message: Any) -> Dict[str, Any]:
    normalized_calls = []
    for tool_call in _message_field(message, "tool_calls", None) or []:
        function = _message_field(tool_call, "function")
        normalized_calls.append({
            "id": _message_field(tool_call, "id"),
            "function": {
                "name": _message_field(function, "name"),
                "arguments": _message_field(function, "arguments"),
            },
        })
    return {
        "content": _message_field(message, "content"),
        "tool_calls": normalized_calls,
    }


def _convert_zhipu_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    converted = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "assistant" and (
            not converted or converted[-1].get("role") == "system"
        ):
            role = "user"
        converted.append({"role": role, "content": msg.get("content", "")})
    return converted


def ask_ai_message(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    tools: Optional[List] = None,
) -> Dict[str, Any]:
    """Return provider-neutral content and tool calls without executing tools."""
    if AI_SERVER.upper() == "ZHIPU":
        if not ZHIPU_AI_API_KEY:
            raise ValueError("ZHIPU_AI_API_KEY environment variable is not set")
        client = _get_zhipu_client()
        params = {
            "model": ZHIPU_AI_MODEL,
            "messages": _convert_zhipu_messages(messages),
            "temperature": temperature,
            "stream": False,
        }
    else:
        client = _get_openai_client()
        params = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": temperature,
        }
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"
    response = client.chat.completions.create(**params)
    return _normalize_model_message(response.choices[0].message)


def ask_ai(messages: List[Dict[str, str]], temperature: float = 0.7, tools: Optional[List] = None) -> str:
    """
    统一的AI调用接口，支持OpenAI和智谱AI
    
    Args:
        messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
        temperature: 温度参数，默认0.7
        tools: 工具定义列表（仅OpenAI支持）
    
    Returns:
        AI返回的文本内容
    """
    if AI_SERVER.upper() == 'ZHIPU':
        return _ask_zhipu(messages, temperature)
    else:
        return _ask_openai(messages, temperature, tools)


def _ask_openai(messages: List[Dict[str, str]], temperature: float = 0.7, tools: Optional[List] = None) -> str:
    """调用OpenAI API"""
    client = _get_openai_client()
    
    params = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"
    
    response = client.chat.completions.create(**params)
    
    # 处理工具调用响应
    if response.choices[0].message.tool_calls:
        # 如果有工具调用，返回工具调用的结果
        tool_call = response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        import json
        function_args = json.loads(tool_call.function.arguments)
        return json.dumps(function_args)
    
    return response.choices[0].message.content


def _ask_zhipu(messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    """调用智谱AI API"""
    if not ZHIPU_AI_API_KEY:
        raise ValueError("ZHIPU_AI_API_KEY environment variable is not set")
    
    # 转换消息格式：智谱AI不支持在用户消息前使用"assistant"角色
    # 将"assistant"角色转换为"user"角色
    converted_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        # 智谱AI只支持 "user", "assistant", "system" 角色
        # 如果第一条消息是"assistant"，转换为"user"
        if role == "assistant" and len(converted_messages) == 0:
            role = "user"
        # 如果"assistant"在"system"之后且是第一条非system消息，也转换为"user"
        elif role == "assistant" and converted_messages and converted_messages[-1].get("role") == "system":
            role = "user"
        
        converted_messages.append({"role": role, "content": content})
    
    client = _get_zhipu_client()
    
    response = client.chat.completions.create(
        model=ZHIPU_AI_MODEL,
        messages=converted_messages,
        temperature=temperature,
        stream=False
    )
    
    result = response.choices[0].message.content
    
    # 处理可能的JSON格式响应（类似OpenAI的处理）
    # 去掉两边的引号
    result = result.strip('"')
    # 去掉json的转义字符
    result = result.replace('\\"', '"').replace("\\n", "\n").replace("\\", "")
    
    return result


def ask_ai_json(messages: List[Dict[str, str]], temperature: float = 0.7) -> dict:
    """
    调用AI并返回JSON格式结果
    
    Args:
        messages: 消息列表
        temperature: 温度参数
    
    Returns:
        JSON对象（dict）
    """
    import json
    
    response = ask_ai(messages, temperature)
    
    # 如果格式为类似markdown的 ```json\n{}\n```，就去掉前后的 ```json\n 与 \n```
    if response.startswith("```json\n") and response.endswith("\n```"):
        response = response.replace("```json\n", "").replace("\n```", "")
    elif response.startswith("```") and response.endswith("```"):
        # 处理其他代码块格式
        response = response.strip("```").strip()
        if response.startswith("json\n"):
            response = response.replace("json\n", "", 1)
    
    # 去掉两边的引号
    response = response.strip('"')
    # 去掉json的转义字符
    response = response.replace('\\"', '"').replace("\\n", "\n").replace("\\", "")
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        # 如果解析失败，尝试提取JSON部分
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError(f"Failed to parse JSON from AI response: {response}") from e
