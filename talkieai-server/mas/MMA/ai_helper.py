"""
MAS系统统一的AI调用模块
支持OpenAI GPT和智谱AI
"""
import os
from typing import List, Dict, Optional

# 从环境变量获取配置
AI_SERVER = os.getenv('AI_SERVER', 'ZHIPU')  # 默认使用智谱AI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ZHIPU_AI_API_KEY = os.getenv('ZHIPU_AI_API_KEY', '')
ZHIPU_AI_MODEL = os.getenv('ZHIPU_AI_MODEL', 'glm-4')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1')


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
    from openai import OpenAI
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
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
    try:
        from zhipuai import ZhipuAI
    except ImportError:
        raise ImportError("zhipuai package not installed. Run: pip install zhipuai")
    
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
    
    client = ZhipuAI(api_key=ZHIPU_AI_API_KEY)
    
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
    import re
    
    response = ask_ai(messages, temperature)
    
    # 清理响应内容
    cleaned_response = response.strip()
    
    # 处理 Markdown 代码块
    if cleaned_response.startswith("```json"):
        # 提取 ```json``` 之间的内容
        match = re.search(r'```json\s*\n(.*?)\n```', cleaned_response, re.DOTALL)
        if match:
            cleaned_response = match.group(1).strip()
    elif cleaned_response.startswith("```"):
        # 提取 ``` ``` 之间的内容
        match = re.search(r'```\s*\n(.*?)\n```', cleaned_response, re.DOTALL)
        if match:
            cleaned_response = match.group(1).strip()
    
    # 尝试直接解析 JSON
    try:
        return json.loads(cleaned_response)
    except json.JSONDecodeError:
        # 如果直接解析失败，尝试查找 JSON 对象
        json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 如果都失败，返回默认结构
        print(f"Failed to parse JSON from response: {response}")
        return {
            "preferred_name": "",
            "hobbies": [],
            "family": [],
            "friends": [],
            "travel": []
        }
