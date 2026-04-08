import os
import re
import sys
from openai import OpenAI
from travel import available_tools

# --- Agent System Prompt ---
AGENT_SYSTEM_PROMPT = """
你是一个智能旅行助手。你的任务是分析用户的请求，并使用可用工具一步步地解决问题。

# 可用工具:
- `get_weather(city: str)`: 查询指定城市的实时天气。
- `get_attraction(city: str, weather: str)`: 根据城市和天气搜索推荐的旅游景点。

# 输出格式要求（必须严格遵守）:
你的每次回复必须且只能包含以下两行，不要输出任何其他内容：

Thought: 你的思考过程
Action: 你要执行的行动

Action的格式必须是以下之一：
1. 调用工具：get_weather(city="北京")
2. 结束任务：Finish[你的完整回答内容写在这里]

# 结束任务示例:
Thought: 我已经获取了天气和景点信息，可以给出最终回答了。
Action: Finish[北京今天天气晴朗，气温25度。推荐您去颐和园游玩。]

# 重要提示:
- 每次只输出Thought和Action两行，不要输出其他任何内容
- 不要使用<think>标签
- 不要在Action之后添加额外文字
- Action必须在同一行，不要换行
- Finish[]的方括号内必须包含你的完整回答，不要写"最终答案"这几个字

请开始吧！
"""


class OpenAICompatibleClient:
    """
    一个用于调用任何兼容OpenAI接口的LLM服务的客户端。
    """
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str, system_prompt: str) -> str:
        """调用LLM API来生成回应。"""
        print("正在调用大语言模型...")
        try:
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ]
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            answer = response.choices[0].message.content
            print(f"大语言模型响应成功,input message: {prompt}")
            return answer
        except Exception as e:
            print(f"调用LLM API时发生错误: {e}")
            return "错误:调用语言模型服务时出错。"


def clean_model_output(text: str) -> str:
    """清理模型输出：去除 <think> 标签及其内容。"""
    # 去除 <think>...</think> 完整块
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 去除残留的 <think> 或 </think> 标签
    text = re.sub(r'</?think>', '', text)
    return text.strip()


def parse_finish(action_str: str):
    """
    从 action_str 中提取 Finish[...] 的内容。
    支持多行内容：用最外层的方括号匹配。
    """
    # 找到 Finish[ 之后，贪婪匹配到最后一个 ]
    m = re.match(r'Finish\[(.*)\]$', action_str, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def parse_tool_call(action_str: str):
    """
    从 action_str 中解析工具调用，返回 (tool_name, kwargs) 或 None。
    """
    tool_match = re.search(r"(\w+)\(", action_str)
    args_match = re.search(r"\((.*)\)", action_str, re.DOTALL)
    if not tool_match or not args_match:
        return None
    tool_name = tool_match.group(1)
    args_str = args_match.group(1)
    kwargs = dict(re.findall(r'(\w+)="([^"]*)"', args_str))
    return tool_name, kwargs


def main():
    # --- 1. 配置LLM客户端 ---
    API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY")
    BASE_URL = os.environ.get("OPENAI_BASE_URL", "YOUR_BASE_URL")
    MODEL_ID = os.environ.get("MODEL_ID", "YOUR_MODEL_ID")
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "YOUR_TAVILY_API_KEY")
    os.environ['TAVILY_API_KEY'] = TAVILY_API_KEY

    llm = OpenAICompatibleClient(
        model=MODEL_ID,
        api_key=API_KEY,
        base_url=BASE_URL
    )

    # --- 2. 初始化 ---
    city = sys.argv[1] if len(sys.argv) > 1 else "上海"
    date = sys.argv[2] if len(sys.argv) > 2 else "今天"
    user_prompt = f"你好，请帮我查询一下明天去{city}旅游的天气，然后根据天气推荐合适的旅游景点。"
    prompt_history = [f"用户请求: {user_prompt}"]

    print(f"用户输入: {user_prompt}\n" + "=" * 40)

    # --- 3. 运行主循环 ---
    for i in range(5):
        print(f"--- 循环 {i+1} ---\n")

        # 3.1. 构建Prompt
        full_prompt = "\n".join(prompt_history)

        # 3.2. 调用LLM
        llm_output = llm.generate(full_prompt, system_prompt=AGENT_SYSTEM_PROMPT)

        # 3.3. 清理输出（去除 <think> 等）
        llm_output = clean_model_output(llm_output)

        # 3.4. 截断多余的 Thought-Action 对（只保留第一对）
        ta_match = re.search(
            r'(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)',
            llm_output, re.DOTALL
        )
        if ta_match:
            truncated = ta_match.group(1).strip()
            if truncated != llm_output.strip():
                llm_output = truncated
                print("已截断多余的 Thought-Action 对")

        print(f"模型输出:\n{llm_output}\n")
        prompt_history.append(llm_output)

        # 3.5. 提取 Action 部分
        action_match = re.search(r"Action:\s*(.*)", llm_output, re.DOTALL)

        # 兜底：模型可能省略 "Action:" 前缀，直接在某行写了 Finish[...]
        if not action_match:
            finish_fb = re.search(r"(Finish\[.*\])", llm_output, re.DOTALL)
            if finish_fb:
                action_str = finish_fb.group(1).strip()
            else:
                action_str = None
        else:
            action_str = action_match.group(1).strip()

        # 3.6. 没有找到任何可执行的Action
        if not action_str:
            has_observations = any("Observation:" in h for h in prompt_history)
            if has_observations and len(llm_output) > 20:
                # 工具已调用过，模型直接给出了答案，视为完成
                answer_lines = [l for l in llm_output.split('\n') if not l.startswith('Thought:')]
                final = '\n'.join(answer_lines).strip() or llm_output
                print(f"任务完成，最终答案:\n{final}")
                break
            observation = "错误: 未能解析到 Action 字段。请严格只输出 Thought 和 Action 两行。"
            observation_str = f"Observation: {observation}"
            print(f"{observation_str}\n" + "=" * 40)
            prompt_history.append(observation_str)
            continue

        # 3.7. 处理 Finish
        if "Finish[" in action_str:
            final_answer = parse_finish(action_str)
            if final_answer:
                print(f"任务完成，最终答案:\n{final_answer}")
            else:
                # parse_finish 失败，直接提取 Finish[ 和最后一个 ] 之间的内容
                start = action_str.index("Finish[") + len("Finish[")
                end = action_str.rindex("]")
                final_answer = action_str[start:end].strip()
                print(f"任务完成，最终答案:\n{final_answer}")
            break

        # 3.8. 处理工具调用
        result = parse_tool_call(action_str)
        if not result:
            observation = f"错误: Action 格式不正确。收到: {action_str}"
            observation_str = f"Observation: {observation}"
            print(f"{observation_str}\n" + "=" * 40)
            prompt_history.append(observation_str)
            continue

        tool_name, kwargs = result
        if tool_name in available_tools:
            observation = available_tools[tool_name](**kwargs)
        else:
            observation = f"错误:未定义的工具 '{tool_name}'"

        # 3.9. 记录观察结果
        observation_str = f"Observation: {observation}"
        print(f"{observation_str}\n" + "=" * 40)
        prompt_history.append(observation_str)


if __name__ == "__main__":
    main()