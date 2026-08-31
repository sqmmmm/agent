import requests   # requests 是一个流行的 HTTP 客户端库，用于发送网络请求并处理响应
import os        # os：标准库，用于读取环境变量 TAVILY_API_KEY
import re     # 正则表达式库
from tavily import TavilyClient   # tavily：第三方库，需要安装（pip install tavily-python）。它封装了 Tavily Search API 的调用，提供简洁的客户端接口。
                                # 导入Tavily Search API客户端类,它是一个供ai调用的搜索接口，请先在tavily.com注册一个账号，并获取API密钥，然后在环境变量中配置TAVILY_API_KEY
from openai import OpenAI



class OpenAICompatibleClient:
    """
    一个用于调用任何兼容OpenAI接口的LLM服务的客户端。
    """
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.client = OpenAI(
            api_key=self.api_key, 
            base_url=self.base_url
        )

    def generate(self, prompt: str, system_prompt: str = None):
        """
            prompt: 用户输入提示词
            system_prompt: 系统提示词,用于引导模型的行为（角色描述，功能描述，约束条件等）
        """
        if not prompt:
            return "错误：请输入用户提示词"
        print("正在调用大语言模型...", self.model)
        if system_prompt:   # 若提供了 system_prompt，则消息为 [system, user]；否则只有 [user]
            messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}]
        else:
            messages = [{'role': 'user', 'content': prompt}]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages = messages
            )
            print("原始响应:", response)
            print("============"*20)
            return response.choices[0].message.content  # 从 response.choices[0].message.content 提取生成的文本
        except Exception as e:
            print(f"调用LLM API时发生错误: {e}")
            return "错误:调用语言模型服务时出错。"

# 这段代码定义了一个名为 OpenAICompatibleClient 的 Python 类，
# 用于便捷地调用任何兼容 OpenAI API 格式的大语言模型（LLM）服务（如 OpenAI 官方、Azure OpenAI、本地部署的 vLLM、Ollama 等）。
# 类封装了 API 密钥、基础 URL 和模型名称，并提供 generate 方法，支持系统提示词（system prompt）和用户提示词（user prompt），
# 返回模型生成的文本.




def get_attraction(city: str, weather: str) -> str:
    """
    根据城市和天气，使用Tavily Search API搜索并返回优化后的景点推荐。
    """
    # 1. 从环境变量中读取API密钥
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return "错误:未配置TAVILY_API_KEY环境变量。"

    # 2. 初始化Tavily客户端  使用密钥实例化 TavilyClient，后续通过该对象调用搜索方法
    tavily = TavilyClient(api_key=key)
    
    # 3. 构造一个精确的查询
    query = f"'{city}' 在'{weather}'天气下最值得去的旅游景点推荐及理由"
    # 长沙在Patchy rain nearby, 气温31摄氏度天气下最值得去的旅游景点推荐及理由
    
    try:
        # 4. 调用API，include_answer=True会返回一个综合性的回答  这是 Tavily 的特色功能
        response = tavily.search(query, search_depth="basic", include_answer=True)
        # search_depth="basic"：表示使用基础搜索模式（相对 "advanced" 更轻量，消耗更少积分） 可以通过对search按ctrl查看具体参数说明


        
        # 5. Tavily返回的结果已经非常干净，可以直接使用
        # response['answer'] 是一个基于所有搜索结果的总结性回答
        if response.get("answer"):
            return response["answer"]
        
        # 如果没有综合性回答，则格式化原始结果 
        formatted_results = []
        for result in response.get("results", []):
            formatted_results.append(f"- {result['title']}: {result['content']}")  
        # 从 response['results'] 列表中提取每条结果的标题和内容摘要（content 可能是截取的相关段落），组装成无序列表
        
        if not formatted_results:
             return "抱歉，没有找到相关的旅游景点推荐。"

        return "根据搜索，为您找到以下信息:\n" + "\n".join(formatted_results)

    except Exception as e:
        return f"错误:执行Tavily搜索时出现问题 - {e}"


# 这段代码定义了一个名为 get_attraction(city, weather) 的函数，它利用 Tavily Search API（一个为 AI 应用优化的搜索引擎）
# 根据给定的城市和天气状况，搜索并返回该城市在特定天气下值得一游的景点推荐。
# 函数最终返回一个自然语言的回答或一系列搜索结果摘要。


def get_weather(city: str) -> str:    # 返回值类型标注为 str，表示返回一个描述天气的字符串
    """
    通过调用第三方天气 API（wttr.in）查询真实的天气信息。
    API格式：https://wttr.in/{city}?format=j1   
    """
    # API端点，我们请求JSON格式的数据
    url = f"https://wttr.in/{city}?format=j1"  #  格式化字符串  支持变量插值
    
    try:
        # 发起网络请求
        response = requests.get(url)
        # 检查响应状态码是否为200 (成功)
        response.raise_for_status() 
        # 解析返回的JSON数据
        weather_data = response.json()
        print("得到的天气数据:", weather_data)   
        print("============================"*2)    # 这两行将完整的 JSON 数据打印到控制台，仅用于调试。在生产环境中应删除或改用日志（logging.debug），避免暴露大量数据或污染标准输出。    
        # 获取当前天气信息
        # weather_desc = weather_data['current_condition'][0]['weatherDesc'][0]['value']
        # return f"{city}的天气是: {weather}"

        
        # 提取当前天气状况
        current_condition = weather_data['current_condition'][0]   # 从 JSON 中逐层提取数据 是一个列表（通常长度为 1），取第一个元素
        weather_desc = current_condition['weatherDesc'][0]['value']
        temp_c = current_condition['temp_C']
        
        # 格式化成自然语言返回
        return f"{city}当前天气:{weather_desc}，气温{temp_c}摄氏度"
    except requests.exceptions.RequestException as e:
        # 处理网络错误
        return f"错误:查询天气时发出请求，遇到网络问题 - {e}"
    except (KeyError, IndexError) as e:
        # 处理数据解析错误
        return f"错误:解析天气数据失败，可能是城市名称无效 - {e}"

# 这段代码定义了一个名为 get_weather 的函数，它通过调用第三方天气 API（wttr.in）查询指定城市的实时天气状况，
# 并将结果以自然语言字符串形式返回。
# 组装以上的工具函数， 供LLM使用
available_tools = {     # 采用字典（Dict）结构，键值对的方式
    "get_weather": get_weather,
    "get_attraction": get_attraction,
}


# 系统提示词
AGENT_SYSTEM_PROMPT = """
你是一个智能旅行助手。你的任务是分析用户的请求，并使用可用工具一步步地解决问题。

# 可用工具:
- `get_weather(city: str)`: 查询指定城市的实时天气。
- `get_attraction(city: str, weather: str)`: 根据城市和天气搜索推荐的旅游景点。

# 输出格式要求:
你的每次回复必须严格遵循以下格式，包含一对Thought和Action：

Thought: [你的思考过程和下一步计划]
Action: [你要执行的具体行动]

Action的格式必须是以下之一：
1. 调用工具：function_name(arg_name="arg_value")
2. 结束任务：Finish[最终答案]

# 重要提示:
- 每次只输出一对Thought-Action
- Action必须在同一行，不要换行
- 当收集到足够信息可以回答用户问题时，必须使用 Action: Finish[最终答案] 格式结束
- 语言必须是中文.
- 必须严格按照条件进行回答。

请开始吧！
"""
# 提示词工程是非常重要的一步，它决定了智能体的行为和性能。


import sys
from dotenv import load_dotenv
# 获取当前文件的父目录的父目录(即项目根目录)，并添加到sys.path，以后上线需要将myAgents模块发布，这里就不要了
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
load_dotenv(override=True) 	#加载环境变量.env,override=True 表示覆盖已存在的环境变量



if __name__ == "__main__":
    
    #argv存的是数组，假设你的命令是    python   智能旅行推荐助手.py 北京
    # argv[0]存的是脚本文件名，即智能旅行推荐助手.py
    # argv[1]存的是第一个参数，即北京
    args = sys.argv[1:]
    # args就变为：["北京"]
    if len(args) == 0:
    # 没有传参数，默认北京天气
        city = "北京"
    else:
        city = args[0]

    # 测试以上函数
    # --- 1. 配置LLM客户端 ---
    # 请根据您使用的服务，将这里替换成对应的凭证和地址
    open_ai_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("MODEL_NAME")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    TAVILY_API_KEY=os.getenv("TAVILY_API_KEY")


    llm = OpenAICompatibleClient(
        model=model_name,
        api_key=open_ai_key,
        base_url=openai_base_url
    )

    # --- 2. 初始化 ---
    user_prompt = (f"你好，请帮我查询一下今天{city}的天气，然后根据天气推荐一个合适的旅游景点。")
    prompt_history = [f"用户请求: {user_prompt}"]   # 初始化对话历史

    print(f"用户输入: {user_prompt}\n" + "="*40)

    # --- 3. 运行主循环 ---
    for i in range(5): # 设置最大循环次数
        print(f"--- 循环 {i+1} ---\n")
        
        # 3.1. 构建Prompt
        full_prompt = "\n".join(prompt_history)

        # TODO: prompt如何压缩，如何用到缓存？
        
        # 3.2. 调用LLM进行思考
        llm_output = llm.generate(full_prompt, system_prompt=AGENT_SYSTEM_PROMPT)
        # 模型可能会输出多余的Thought-Action，需要截断
        match = re.search(r'(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)', llm_output, re.DOTALL)
        if match:
            truncated = match.group(1).strip()
            if truncated != llm_output.strip():
                llm_output = truncated
                print("已截断多余的 Thought-Action 对")
        print(f"模型输出:\n{llm_output}\n")
        prompt_history.append(llm_output)
        
        # 3.3. 解析并执行行动
        action_match = re.search(r"Action: (.*)", llm_output, re.DOTALL)
        if not action_match:
            observation = "错误: 未能解析到 Action 字段。请确保你的回复严格遵循 'Thought: ... Action: ...' 的格式。"
            observation_str = f"Observation: {observation}"
            print(f"{observation_str}\n" + "="*40)
            prompt_history.append(observation_str)
            continue
        action_str = action_match.group(1).strip()

        if action_str.startswith("Finish"):
            final_answer = re.match(r"Finish\[(.*)\]", action_str).group(1)
            print(f"任务完成，最终答案: {final_answer}")
            break

        # 下一种情况：action是调用函数
        # Action: function_name(arg_name="arg_value")
        tool_name = re.search(r"(\w+)\(", action_str).group(1)    # 提取函数名
        args_str = re.search(r"\((.*)\)", action_str).group(1)    # 提取参数字符串: name="zy", age="20" => {name: zy, age: 20}
        kwargs = dict(re.findall(r'(\w+)="([^"]*)"', args_str))

        if tool_name in available_tools:
            observation = available_tools[tool_name](**kwargs)
        else:
            observation = f"错误:未定义的工具 '{tool_name}'"

        # 3.4. 记录观察结果
        observation_str = f"Observation: {observation}"
        print(f"{observation_str}\n" + "="*40)
        prompt_history.append(observation_str)