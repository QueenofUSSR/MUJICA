import os
import subprocess
import json
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

# 初始化OpenAI客户端
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class SystemOperationPool:
    """系统操作方法池 - 封装各类电脑操控方法"""
    
    @staticmethod
    def create_file(file_path: str, content: str = "") -> str:
        """创建文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"成功创建文件: {file_path}"
        except Exception as e:
            return f"创建文件失败: {str(e)}"
    
    @staticmethod
    def delete_file(file_path: str) -> str:
        """删除文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return f"成功删除文件: {file_path}"
            else:
                return f"文件不存在: {file_path}"
        except Exception as e:
            return f"删除文件失败: {str(e)}"
    
    # @staticmethod
    # def create_shell_terminal() -> str:
    #     """创建Shell终端（跨平台）"""
    #     try:
    #         if os.name == 'nt':  # Windows
    #             subprocess.Popen(['cmd.exe'])
    #         else:  # macOS/Linux
    #             subprocess.Popen(['xterm'] if os.name == 'posix' else ['gnome-terminal'])
    #         return "成功打开新的终端窗口"
    #     except Exception as e:
    #         return f"创建终端失败: {str(e)}"
    
    @staticmethod
    def run_terminal_command(command: str) -> str:
        """运行终端命令"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            output = result.stdout if result.stdout else result.stderr
            return f"命令执行结果:\n{output}"
        except Exception as e:
            return f"命令执行失败: {str(e)}"
    
    @staticmethod
    def run(code: str, language: str = "python", program_input: str = "") -> str:
        """运行代码片段（默认Python）。

        可以通过 `program_input` 参数传入字符串，作为被执行程序的标准输入（stdin）。
        如果程序不需要输入，请传入空字符串或省略此参数。
        """
        try:
            if language.lower() == "python":
                # 先检测代码中是否存在读取 stdin 的调用
                input_patterns = re.search(r"\b(input\s*\(|raw_input\s*\(|sys\.stdin|sys\.stdin\.read|sys\.stdin\.readline|sys\.stdin\.buffer)", code)
                if input_patterns and program_input == "":
                    return (
                        "Python代码执行结果:\n"
                        "[INPUT_REQUIRED] 代码包含输入调用（如 input() 或 sys.stdin.read），但未提供 program_input。"
                        " 请提供所需的输入字符串作为 program_input 参数。"
                    )

                # 创建临时Python文件执行
                temp_file = ".temp_code_run.py"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                try:
                    result = subprocess.run(
                        ['python', temp_file],
                        input=program_input,
                        capture_output=True,
                        text=True,
                        encoding='utf-8'
                    )
                finally:
                    # 确保临时文件被删除
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass

                stdout = result.stdout or ""
                stderr = result.stderr or ""

                # 检测典型的输入相关错误（例如 EOFError）或因输入不符合预期导致的异常
                if "EOFError" in stderr or re.search(r"Traceback.*EOFError", stderr, re.S):
                    return (
                        "Python代码执行结果:\n"
                        f"[INPUT_ERROR] 程序在运行时遇到 EOFError，可能是提供的输入不完整或过早结束。\nstderr:\n{stderr}"
                    )

                # 常见因输入格式错误引起的 ValueError（例如 int("")）
                if "ValueError" in stderr and ("invalid literal for int()" in stderr or "could not convert" in stderr):
                    return (
                        "Python代码执行结果:\n"
                        f"[INPUT_ERROR] 提供的输入可能格式不正确，导致 ValueError。\nstderr:\n{stderr}"
                    )

                # 非零退出但无以上特征，返回 stderr 以便排查
                if result.returncode != 0 and stderr:
                    return f"Python代码执行结果:\n[ERROR] 程序以非零退出码结束。stderr:\n{stderr}"

                output = stdout if stdout else stderr
                return f"Python代码执行结果:\n{output}"
            else:
                return f"暂不支持{language}语言的代码执行"
        except Exception as e:
            return f"代码执行失败: {str(e)}"

class Debugger:
    """OpenAI智能Agent"""
    
    def __init__(self, code: str = ""):
        # 初始化时的代码
        self.initial_code = code
        # 初始化对话上下文（包含系统提示）- 重点修复参数键名要求
        content_template = """你是一个可以Debug的智能Agent，拥有以下操作能力：
1. 运行终端命令：参数为command（命令字符串，必填，字符串）
2. 运行并调试：参数为code（代码字符串，必填，字符串）、language（编程语言，可选，默认Python）、program_input（作为程序stdin的字符串，可选，默认空字符串）
3. 制造样例：根据用户需求，生成符合需求的代码样例

你的任务：
- 根据已有的代码```__INITIAL_CODE__```, 分析用户输入，判断是否需要调用上述操作
- 如果需要调用操作，必须以JSON格式返回操作指令，格式如下：
    {
        "operation": "操作名称（run_terminal_command/run_code/generate_examples）",
        "params": {"参数名": "参数值"}
    }
- 参数名必须严格使用英文（如file_path、content、command等），禁止使用中文参数名
- 如果不需要调用操作，直接用自然语言回复用户即可
- 严格遵守JSON格式要求，仅在需要执行操作时返回JSON，其他情况返回自然语言
- 路径参数优先使用相对路径（如./hello.py），符合用户当前工作目录习惯"""
        self.content = content_template.replace("__INITIAL_CODE__", self.initial_code)
        self.conversation_context: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": self.content
            }
        ]
        self.operation_pool = SystemOperationPool()

    def get_agent_response(self, user_input: str) -> tuple[Optional[Dict], str]:
        """
        获取Agent响应
        返回值：(操作指令字典, 自然语言回复)
        """
        # 将用户输入加入上下文
        self.conversation_context.append({"role": "user", "content": user_input})
        
        # 调用OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=self.conversation_context,
            temperature=0.1  # 降低随机性，保证指令准确性
        )
        
        agent_reply = response.choices[0].message.content
        # 将Agent回复加入上下文
        self.conversation_context.append({"role": "assistant", "content": agent_reply})
        
        # 解析是否为操作指令
        try:
            operation_cmd = json.loads(agent_reply)
            # 验证操作指令格式
            if "operation" in operation_cmd and "params" in operation_cmd:
                return operation_cmd, ""
        except json.JSONDecodeError:
            # 不是JSON格式，说明是自然语言回复
            pass
        
        return None, agent_reply

    def run_code(self, code: Optional[str] = None, language: str = "python", program_input: str = "") -> str:
        """运行代码并将输出反馈给模型进行评估。

        流程：
        1. 使用 `SystemOperationPool.run_code` 执行代码并收集输出。
        2. 将源代码、language、program_input 和运行输出作为上下文发给模型，请模型只返回指定格式的 JSON。
        3. 解析并返回模型给出的 JSON（字符串形式），格式为：
           {
               "flag": "true"/"false",
               "code": "代码字符串",
               "comment": "运行结果与修改说明"
           }
        """
        # 使用初始化时的代码
        code = self.initial_code

        # 1) 执行代码并收集输出
        exec_result = self.operation_pool.run(code, language, program_input)
        # 将执行结果中的输出部分抽取出来（如果有前缀行）
        if isinstance(exec_result, str) and "\n" in exec_result:
            output = exec_result.split('\n', 1)[1]
        else:
            output = exec_result

        # 2) 询问模型评估运行结果并请求返回JSON
        eval_system = """你是一个代码执行评估器。根据给定的源代码、语言、程序输入和运行输出，判断程序是否正常运行。
    如果程序没有正常运行（抛出异常或输出不符合预期），请在返回的 JSON 中将 `flag` 置为 "false"，并在 `code` 字段中返回你修改后的可运行代码；如果程序正常运行，`flag` 为 "true"，并在 `code` 字段返回原始代码。
    必须严格只返回一个有效的 JSON 对象，结构如下：
    {
      "flag": "true" 或 "false",
      "output": "程序运行的输出结果字符串",
      "code": "...",
      "comment": "用自然语言描述运行结果、是否报错、错误原因和改动等"
    }
    不要在 JSON 外输出任何其它文本或说明内容。"""

        user_msg = (
            f"源代码:\n{code}\n\n语言: {language}\n\nprogram_input:\n{program_input}\n\n运行输出:\n{output}\n"
        )

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": eval_system},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.0
            )
            agent_reply = response.choices[0].message.content
        except Exception as e:
            return f"评估请求失败: {str(e)}"

        # 3) 尝试解析模型返回的 JSON（允许模型在回复中意外包含前后文本）
        parsed = None
        # 尝试直接解析
        try:
            parsed = json.loads(agent_reply)
        except Exception:
            # 尝试提取第一个JSON对象子串
            m = re.search(r"\{.*\}", agent_reply, re.S)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = None

        if parsed is None:
            # 无法解析时，返回模型原始回复以便调试
            return f"模型未返回可解析的JSON。原始回复:\n{agent_reply}" 

        # 将解析后的 JSON 规范化并处理：打印 `code` 字段，返回 `comment` 字段
        try:
            if isinstance(parsed, dict):
                output = parsed.get("output", "")
                code_str = parsed.get("code", "")
                comment = parsed.get("comment", "")
                flag = parsed.get("flag", "")
                # 打印解析到的代码供用户查看
                print("解析到的代码:\n" + code_str)
                # 更新初始代码为最新代码
                self.initial_code = code_str or self.initial_code
                # 返回结构化结果，便于后端调用者持久化和前端展示
                return {
                    "flag": flag,
                    "code": code_str,
                    "code_str": code_str,
                    "output": output,
                    "comment": comment,
                }
            # 如果不是 dict，则返回其 JSON 字符串形式
            return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            return str(parsed)
        
    def execute_operation(self, operation_cmd: Dict) -> str:
        """执行操作指令"""
        operation = operation_cmd["operation"]
        params = operation_cmd["params"]
        
        # 映射操作名称到方法池
        operation_mapping = {
            "create_file": self.operation_pool.create_file,
            "delete_file": self.operation_pool.delete_file,
            "run_terminal_command": self.operation_pool.run_terminal_command,
            "run_code": self.run_code
        }
        
        if operation not in operation_mapping:
            return f"不支持的操作类型：{operation}"
        
        # 执行操作
        try:
            operation_func = operation_mapping[operation]
            result = operation_func(**params)
            return result
        except TypeError as e:
            # 更友好的参数错误提示
            func_signature = str(operation_func.__annotations__)
            return f"""操作参数错误：{str(e)}
当前操作要求的参数格式：{func_signature}
请检查参数名是否正确（必须为英文）、参数是否缺失"""
        except Exception as e:
            return f"操作执行异常：{str(e)}"

    def interact(self):
        """启动控制台交互"""
        print("=== 智能Debugger已启动，输入'exit'退出对话 ===")
        while True:
            # 获取用户输入
            user_input = input("\n你: ").strip()
            
            # 退出条件
            if user_input.lower() == "exit":
                print("Agent: 对话结束，再见！")
                break
            
            if not user_input:
                print("Agent: 请输入有效内容！")
                continue
            
            # 获取Agent响应
            print("Agent: 正在分析你的请求...")
            operation_cmd, natural_reply = self.get_agent_response(user_input)
            
            if natural_reply:
                # 自然语言回复
                print(f"Agent: {natural_reply}")
            else:
                # 需要执行操作，向用户确认
                operation_name = operation_cmd["operation"]
                params = operation_cmd["params"]
                print(f"\nAgent: 检测到你需要执行以下操作：")
                print(f"操作类型：{operation_name}")
                # print(f"操作参数：{params}")
                
                confirm = input("是否确认执行？(y/n): ").strip().lower()
                if confirm == "y":
                    # 执行操作
                    result = self.execute_operation(operation_cmd)
                    print(f"Agent: 操作执行结果：\n{result}")
                    
                    # 将执行结果加入上下文
                    self.conversation_context.append({
                        "role": "assistant",
                        "content": f"操作执行完成，结果：{result}"
                    })
                else:
                    print("Agent: 已取消操作执行")
                    # 将取消信息加入上下文
                    self.conversation_context.append({
                        "role": "assistant",
                        "content": "用户取消了操作执行"
                    })

if __name__ == "__main__":
    # 启动Debugger
    debugger = Debugger(code="print(Hello, world!')")
    debugger.interact()