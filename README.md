# DataReportNew

> 让大模型自主分析数据，生成可视化复盘报告的 SaaS 工具

基于 LLM 的智能数据分析报告生成平台。用户上传 Excel 表格 + 描述分析需求，AI Agent 会自主规划、执行 Python 代码处理数据、生成基于 ECharts 的可视化分析报告。

## 核心特性

- **LLM 自主决策**: Agent Loop - LLM 制定计划、调用工具、迭代决策
- **动态代码执行**: Python 动态执行，支持复杂数据处理与可视化
- **流式响应**: 基于 SSE 的实时流式输出，分层结构化事件路由
- **可视化渲染**: ECharts 图表、Markdown、Mermaid 全支持
- **现代 UI**: Cohere 设计风格，shadcn/ui 组件库，明暗主题
- **环境隔离**: Conda 虚拟环境，无污染本地环境

## 项目结构

```
DataReportNew/
├── backend/              # FastAPI 后端
│   ├── main.py          # API 路由
│   ├── agent.py         # Agent 循环核心
│   ├── tools/
│   │   └── run_code.py  # Python 代码执行工具
│   └── requirements.txt
├── frontend/            # React + TypeScript 前端
│   ├── src/
│   │   ├── components/  # UI 组件
│   │   ├── lib/         # 工具与 API
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── scripts/             # 启动/停止脚本
│   ├── start.ps1        # PowerShell 启动
│   ├── stop.ps1         # PowerShell 停止
│   ├── start.bat        # CMD 启动
│   └── stop.bat         # CMD 停止
├── data/                # 上传文件存储
├── outputs/             # 分析输出
├── logs/                # 运行日志
└── README.md
```

## 快速开始

### 环境要求

- Windows 10/11
- Conda (路径: `D:\DailySoft\AI\tool\miniconda3\condabin`)
- Node.js 18+
- 任意兼容 OpenAI API 协议的 LLM 服务

### 启动项目

#### 方式一：PowerShell（推荐）

```powershell
# 在项目根目录执行
.\scripts\start.ps1
```

#### 方式二：CMD

```cmd
scripts\start.bat
```

启动脚本会自动：

1. 检查 Conda 环境 `AItool`，不存在则自动创建
2. 安装后端 Python 依赖（FastAPI、openai 等）
3. 安装前端 npm 依赖（首次运行）
4. 启动后端服务（端口 8000）
5. 启动前端服务（端口 5173）

### 停止项目

```powershell
.\scripts\stop.ps1
```

或：

```cmd
scripts\stop.bat
```

### 重启项目

```powershell
.\scripts\restart.ps1
```

### 访问地址

启动成功后：

- **前端界面**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## 使用流程

1. **配置模型**: 在左侧填写 `base_url`、`api_key`、`model_name`
2. **上传数据**: 拖放或点击上传 Excel/CSV 文件
3. **描述需求**: 在右侧输入分析目标（支持示例快捷选项）
4. **开始分析**: 点击"开始分析"，观察 Agent 自主决策过程
5. **查看报告**: 分析完成后切换到"最终报告"标签查看可视化报告

## Agent 工作机制

### LLM in the Loop

Agent 采用类似 ReAct 的循环：

```
用户目标 → LLM 决策 (plan/run_code/finish)
              ↓
         执行工具 (Python 代码)
              ↓
         结果反馈给 LLM
              ↓
         继续迭代
              ↓
         action=finish → 输出最终报告
```

### 流式协议

后端通过 SSE (Server-Sent Events) 推送结构化事件：

| Event Type | 含义 | 说明 |
|---|---|---|
| `step` | 步骤开始 | 元数据 |
| `data` | 步骤数据 | 包含 action/analysis/code/result 等 |
| `done` | 分析完成 | 终止信号 |

前端将不同类型的内容路由到不同 UI 模块：

- `plan` → 计划卡片
- `run_code` + `code` → 代码块
- `code_result` → 执行结果
- `finish` + `final_answer` → 最终报告（含 Markdown/ECharts/Mermaid 渲染）

### JSON 输出协议

LLM 每轮输出严格 JSON：

```json
{
  "action": "plan" | "run_code" | "finish",
  "analysis": "当前推理说明",
  "code": "Python 代码（当 action=run_code）",
  "plan": ["步骤1", "步骤2"]（当 action=plan）,
  "final_answer": "最终报告（当 action=finish，Markdown 格式，可含 ECharts JSON）",
  "step_summary": "当前步骤总结"
}
```

## 安全说明

- **代码执行沙箱**: `run_code` 使用 `exec` 执行 Python 代码，仅在本地测试使用
- **风险可控**: 不要在生产环境直接执行不可信代码
- **API Key 保护**: 仅存储在浏览器前端，不上传到任何第三方

## 配置说明

### Conda 路径

如需修改 conda 路径，编辑 `scripts/start.ps1` 或 `scripts/start.bat` 中的：

```powershell
$CONDA_PATH = "D:\DailySoft\AI\tool\miniconda3\condabin"
```

### LLM API 兼容性

支持任何 OpenAI 兼容 API：

- OpenAI: `https://api.openai.com/v1`
- Azure OpenAI: `https://{resource}.openai.azure.com/openai/deployments/{model}`
- 国产模型代理（OneAPI 等）
- 自部署的 vLLM/Ollama 兼容服务

### 模型示例

- `gpt-4o` / `gpt-4o-mini` (OpenAI)
- `claude-3-5-sonnet` (Anthropic via proxy)
- `deepseek-chat` (DeepSeek)
- `qwen-plus` / `qwen-turbo` (通义千问)

## 开发说明

### 后端开发

```powershell
# 激活环境
conda activate AItool

# 启动开发服务（自动重载）
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发

```powershell
cd frontend
npm run dev
```

### 构建生产版本

```powershell
cd frontend
npm run build
```

## 技术栈

### 后端
- FastAPI - Web 框架
- OpenAI Python SDK - LLM 调用
- SSE-Starlette - 流式响应
- Pandas - 数据处理
- Python `exec()` - 代码执行

### 前端
- React 18 + TypeScript
- Vite - 构建工具
- Tailwind CSS - 样式
- shadcn/ui 风格组件
- ECharts - 图表库
- React Markdown - Markdown 渲染
- Mermaid - 图表渲染
- Lucide React - 图标

## 设计参考

UI 设计遵循 [Cohere Design System](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/cohere/DESIGN.md)：

- 主色调：#17171c (近黑)
- 强调色：#003c33 (深绿)、#ff7759 (珊瑚色)
- 字体：Space Grotesk (display) + Inter (body)
- 圆角：8px (sm) / 16px (md) / 22px (lg) / 32px (pill)

## License

MIT