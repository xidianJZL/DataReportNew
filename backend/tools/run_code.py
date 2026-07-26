"""
代码执行工具 - 使用 Python 动态执行

提供两个层级:
- run_python_code(code, namespace=None): 单次执行,默认使用全新命名空间
- CodeSession: 跨多次调用的状态保持,用于 Agent 多步骤场景
"""
import io
import sys
import textwrap
from typing import Any


def run_python_code(code: str, namespace: dict | None = None) -> dict[str, Any]:
    """
    在指定命名空间中执行一段 Python 代码,返回 stdout 和异常信息。

    namespace 为 None 时使用全新的空 dict(完全隔离)。
    传入 dict 时复用同一命名空间(用于多轮步骤间共享变量与导入)。
    代码仅用于本地测试,风险可控。
    """
    if namespace is None:
        namespace = {}

    old_stdout = sys.stdout
    stdout_buffer = io.StringIO()
    sys.stdout = stdout_buffer

    error = None
    result_data = None

    try:
        exec(textwrap.dedent(code), namespace)
        if '_result' in namespace:
            result_data = namespace['_result']
    except Exception as e:
        error = repr(e)
    finally:
        sys.stdout = old_stdout

    return {
        "stdout": stdout_buffer.getvalue(),
        "error": error,
        "result": result_data,
    }


class CodeSession:
    """
    跨多次调用的代码执行会话,保持变量与导入。
    适用于 Agent 多步骤分析:第 1 步加载数据,第 2 步复用同一个 df。
    """

    def __init__(self, seed_namespace: dict | None = None):
        self.namespace: dict = dict(seed_namespace or {})

    def run(self, code: str) -> dict[str, Any]:
        return run_python_code(code, self.namespace)

    def reset(self) -> None:
        self.namespace.clear()

    def snapshot(self) -> dict:
        """返回当前命名空间的关键变量名(便于调试)。"""
        return {
            k: type(v).__name__
            for k, v in self.namespace.items()
            if not k.startswith('_') and not callable(v)
        }