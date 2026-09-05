from ch4.llm import HelloAgentsLLM
from executor import ToolExecutor
from search import search


# ReAct 提示词模板
REACT_PROMPT_TEMPLATE = """
请注意，你是一个有能力调用外部工具的智能助手。

可用工具如下:
{tools}

请严格按照以下格式进行回应:

Thought: 你的思考过程，用于分析问题、拆解任务和规划下一步行动。
Action: 你决定采取的行动，必须是以下格式之一:
- `{{tool_name}}[{{tool_input}}]`:调用一个可用工具。
- `Finish[最终答案]`:当你认为已经获得最终答案时。
- 当你收集到足够的信息，能够回答用户的最终问题时，你必须在Action:字段后使用 Finish[最终答案] 来输出最终答案。

现在，请开始解决以下问题:
Question: {question}
History: {history}
"""


class ReActAgent:
    def __init__(self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 5):
        self.llm_client = llm_client   # 初始化大语言模型客户端
        self.tool_executor = tool_executor   # 初始化工具执行器
        self.max_steps = max_steps      # 最大步骤数
        self.history = []                 # 初始化空的历史记录表

    # LLM 返回的是纯文本，我们需要从中精确地提取出Thought和Action。这是通过几个辅助解析函数完成的，它们通常使用正则表达式来实现。
    def _parse_output(self, text: str):
        """解析LLM的输出，提取Thought和Action。
        """
        import re

        # Thought: 匹配到 Action: 或文本末尾
        #  Thought:匹配到Action:或文本末尾
        #  \s*匹配任意数量的空白字符
        #  .*？匹配任意数量的任意字符，非贪婪匹配
        #  (?=\nAction:$)正向断言，后面必须是\nAction：或文本末尾，但这个东西不包含在当前匹配结果中
        #所以它针对的结构是：
        # Thought：我需要先查询北京的天气。\n然后根据天气情况判断是否适合跑步。我喜欢，不喜欢空谈\n
        # Action: search_weather[北京]
        thought_match = re.search(
            r"Thought:\s*(.*?)(?=\nAction:|$)", text, re.DOTALL
            )  # DOTALL表示匹配任意字符，包括换行符
        # Action: 匹配到文本末尾
        action_match = re.search(r"Action:\s*(.*?)$", text, re.DOTALL)

        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None
        return thought, action

    #   负责进一步解析Action字符串，此方法为私有方法，仅用于内部使用，它负责从Action字符串中提取工具名称和输入
    def _parse_action(self, action_text: str):
        """解析Action字符串，提取工具名称和输入。
        action_text: 例如：calculator[123 + 456]
                            show[]
                            search[北京\n天气很好]
        """

        import re

        match = re.match(r"(\w+)\[(.*)\]", action_text, re.DOTALL)
        if match:
            return match.group(1), match.group(2)
        return None, None

    # run 方法是智能体的入口。它的 while 循环构成了 ReAct 范式的主体，max_steps 参数则是一个重要的安全阀，防止智能体陷入无限循环而耗尽资源。
    def run(self, question: str): 
        """
        运行ReAct智能体来回答一个问题。
        """

        import re

        self.history = [] # 每次运行时重置历史记录
        current_step = 0
        # 循环次数限定为最大迭代次数
        while current_step < self.max_steps:
            current_step += 1
            print(f"--- 第 {current_step} 步 ---")

            # 1. 格式化提示词
            tools_desc = self.tool_executor.getAvailableTools()
            # -search: xxx\n
            # -caculator: xxx\n

            history_str = "\n".join(self.history)

            # 初始化系统提示词
            prompt = REACT_PROMPT_TEMPLATE.format(
                tools=tools_desc,
                question=question,
                history=history_str
            )

            # 2. 调用LLM进行思考
            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm_client.think(messages=messages)
            
            if not response_text:
                print("错误:LLM未能返回有效的响应。")
                break

            # 3. 如果LLM由响应，则解析LLM的输出
            thought, action = self._parse_output(response_text)
            
            if thought:
                print(f"思考: {thought}")

            if not action:
                print("警告:未能解析出有效的Action，流程终止。")
                break

            # 4. 根据解析出的Action来执行具体的操作
            if action.startswith("Finish"):
                # 如果是Finish指令，提取最终答案并结束
                # 使用 re.DOTALL 匹配跨行内容
                matchOk = re.match(r"Finish\[(.*)\]", action, re.DOTALL)
                if matchOk:
                    # 如果匹配成功，提取最终答案并结束循环
                    final_answer = matchOk.group(1)
                    print(f"🎉 最终答案: {final_answer}")
                    return final_answer
                else:
                    # 如果LLM没有遵循标准格式输出，做兜底处理
                    print(
                        f"⚠ 警告: 虽然包含Finish，但格式不正确，提取失败。原始输出为：{action}"
                    )
                    # 为了程序不崩溃，可以把action当作答案返回，或者抛出具体错误
                    final_answer = action.replace("Finish[", "").strip(":[]")
                    # 尝试简单粗暴清洗一下
                    print(f"🤔 强制返回清洗后的结果为：{final_answer}")
                    return final_answer


            # 不是Finish指令，则action中就是工具调用指令
            tool_name, tool_input = self._parse_action(action)
            if not tool_name or not tool_input:
                # 无效Action格式和输入，则进行下一次循环
                continue
            # 有效Action格式和输入
            print(f"🎬 行动: {tool_name}[{tool_input}]")
            
            tool_function = self.tool_executor.getTool(tool_name)
            if not tool_function:
                observation = f"错误:未找到名为 '{tool_name}' 的工具。"
            else:
                observation = tool_function(tool_input) # 调用真实工具

            print(f"👀 观察: {observation}")
            
            # 更新历史记录 将本轮的Action和Observation添加到历史记录中
            self.history.append(f"Action: {action}")
            self.history.append(f"Observation: {observation}")

        # 注意：这里代表循环结束，说明人物完成或者超过最大迭代次数
        print(f"已达到最大迭代次数{self.max_steps}，流程终止。")
        return None

if __name__ == "__main__":
  
    lim = HelloAgentsLLM()
    tool_executor = ToolExecutor()
    search_desc ="这是一个网页搜索引擎，当你需要回答关于时速，事实以及在你的知识库中找不到的信息时，应使用此工具"
    tool_executor.registerTool("Search", search_desc, search)
    agent = ReActAgent(llm_client=lim, tool_executor=tool_executor)
    
    #给一个问题
    question ="马斯克的optimus机器人目前的量产状态?它的中国供应链公司有哪些?"
    agent.run(question)


# 从上面的输出可以看到，智能体清晰地展示了它的思考链条：
# 它首先意识到自己的知识不足，需要使用搜索工具；然后，它根据搜索结果进行推理和总结，并在两步之内得出了最终答案。