# CAS Monster MCP

用你已有的 AI 助手查询上海世外中学 TSIMS 的成绩、学业报告和课表，浏览和申请社团，查看 CAS 评价，并起草和提交 CAS 活动记录和反思。

每位同学在自己的电脑上安装，使用自己的学校账号。MCP 在本机运行，复用学校表单的 HTTP 请求，无需安装 Playwright 或 Chromium。模型由你选的客户端提供。

**按顺序来** · [安装](#1-安装) → [保存学校账号](#2-保存学校账号) → [选一个客户端](#3-连接你的客户端) → [查一下社团](#4-验证连接)。

## 1. 安装

准备 Git、Python 3.11 或更新版本，以及你要使用的 AI 客户端。已经下载并解压本仓库的同学，可以跳过 `git clone`，进入解压后的目录继续。

**Windows PowerShell**

```powershell
git clone https://github.com/TommyMaHaoKun/CAS_MCP.git
cd CAS_MCP
py -3 -m venv .venv
$casPython = (Resolve-Path '.venv/Scripts/python.exe').Path
$casServer = (Resolve-Path 'cas_mcp.py').Path
& $casPython -m pip install -r requirements-mcp.txt
```

如果 Windows 找不到 `py`，可先检查 `python --version`，再用 `python -m venv .venv` 代替创建环境的那一行。

**macOS / Linux**

```bash
git clone https://github.com/TommyMaHaoKun/CAS_MCP.git
cd CAS_MCP
python3 -m venv .venv
casPython="$PWD/.venv/bin/python"
casServer="$PWD/cas_mcp.py"
"$casPython" -m pip install -r requirements-mcp.txt
```

后续终端命令继续使用这个窗口。手动填桌面设置或配置文件时，可以用下面的命令查看两个完整路径。

```text
echo "$casPython"
echo "$casServer"
```

## 2. 保存学校账号

在仓库目录运行与你系统对应的命令。

```powershell
# Windows PowerShell
& $casPython -m cas_credentials set
```

```bash
# macOS / Linux
"$casPython" -m cas_credentials set
```

出现 `School username:` 时输入自己的学校用户名。出现 `School password:` 时输入自己的学校密码并回车，密码输入时不会显示字符。看到 `School login saved` 表示凭据已保存在当前系统账号的凭据管理器里。学校网站将在第一次查询时验证登录。

学校密码只在这个终端提示中输入。DeepSeek、Claude 等模型的登录或 API 密钥在各自客户端里管理。学校网站使用 HTTP，请在信任的网络上使用。

## 3. 连接你的客户端

选择下面对应的一节即可。命令里的 `"$casPython"` 和 `"$casServer"` 来自第 1 步，在 PowerShell、Bash 和 Zsh 中可用。

- [Codex 终端和桌面端](#codex)
- [Claude Code 终端和桌面端](#claude-code)
- [OpenCode](#opencode) · [pi](#pi) · [DeepSeek Harness](#deepseek-harness) · [Kimi Code](#kimi-code) · [Qwen Code](#qwen-code)
- [Cursor、VS Code Copilot 和其他客户端](#其他客户端)

### Codex

**终端版**　在终端注册，然后启动 Codex。在 Codex 里输入 `/mcp` 可以查看工具。

```sh
codex mcp add cas_monster -- "$casPython" "$casServer"
codex mcp list
codex
```

**桌面版**　同一台电脑上的 Codex CLI 和桌面端共享 MCP 配置。已经注册的同学可以重启桌面端并新建本地会话。也可以在桌面端打开 **Settings → MCP servers → Add server**，按下表填入设置，保存并选择 **Restart**。

| 字段 | 填什么 |
| --- | --- |
| 名称 | `cas_monster` |
| 类型 | `STDIO` |
| Command | 第 1 步输出的 Python 完整路径 |
| Arguments | 第 1 步输出的 `cas_mcp.py` 完整路径，整个路径作为一个参数 |

[Codex 官方 MCP 指南](https://developers.openai.com/codex/mcp)

### Claude Code

**终端版**　在仓库目录注册后启动 `claude`，再输入 `/mcp` 查看连接。首次启动时按提示确认你信任这个项目的本地配置。

```sh
claude mcp add --transport stdio --scope project cas_monster -- "$casPython" "$casServer"
claude mcp list
claude
```

**桌面版**　在 Claude 桌面应用里进入 **Code** 标签，选择 **本地**运行环境，将项目目录设为你刚安装的 `CAS_MCP`，然后新建会话。终端命令已经在这个目录生成 `.mcp.json`。如果你只使用桌面端，可以手动在这个目录创建 `.mcp.json`，填写下方的[通用 JSON 配置](#通用-json-配置)。首次加载时按提示批准该 MCP。

[Claude Code 终端 MCP 指南](https://code.claude.com/docs/en/mcp) · [Claude Code 桌面指南](https://code.claude.com/docs/en/desktop#coming-from-the-cli)

### OpenCode

先运行 `opencode --version`。**2.x** 可在仓库目录执行以下命令。

```sh
opencode mcp add cas_monster -- "$casPython" "$casServer"
opencode mcp list
opencode
```

如果模型找不到工具，可在项目的 `opencode.json` 中为 `mcp.servers.cas_monster` 加上 `"codemode": false`，再重启。这样客户端会把 CAS 工具直接列给模型。

**1.x** 使用项目下的 `opencode.json`，服务名直接放在 `mcp` 下。替换示例中的两个路径。已有配置时将 `cas_monster` 加进现有 `mcp` 对象。

```json
{
  "mcp": {
    "cas_monster": {
      "type": "local",
      "command": ["C:/Projects/CAS_MCP/.venv/Scripts/python.exe", "C:/Projects/CAS_MCP/cas_mcp.py"],
      "enabled": true
    }
  }
}
```

[OpenCode 2.x MCP 文档](https://opencode.ai/docs/mcp-servers/) · [OpenCode 1.x MCP 文档](https://opencode.ai/v1/docs/mcp-servers/)

### pi

使用带原生 `pi mcp` 命令的版本。下面的注册命令将 CAS 工具直接提供给模型。

```sh
pi mcp add cas_monster --exposure direct -- "$casPython" "$casServer"
pi mcp list
pi
```

如果要使用 DeepSeek，可以先在终端运行 `pi auth login deepseek --api-key` 输入模型密钥，再用 `pi --model deepseek/deepseek-flash` 启动。已配置其他模型的同学可以继续使用自己的模型。

[pi MCP 文档](https://docs.pi.dev/latest/mcp)

### DeepSeek Harness

使用 DeepSeek 官方的 `dsh`。当前 npm 版本要求 Node.js 24.9 或更新版本。安装 Node.js 后，可从仓库目录启动本地 Web 界面，也可使用已安装的 `dsh` 命令。

1. 在仓库目录创建 `cas-monster.cordis.yml`，将下面的两个路径换成第 1 步打印的完整路径。

   ```yaml
   - insert:
       - id: mcp-cas-monster
         name: '@deepseek-ai/dsh-mcp-client'
         config:
           serverName: cas_monster
           transport: stdio
           command: 'C:/Projects/CAS_MCP/.venv/Scripts/python.exe'
           args: ['C:/Projects/CAS_MCP/cas_mcp.py']
   ```

2. 在此目录运行以下命令，打开本地界面并完成 DeepSeek 模型登录。

   ```sh
   npx @deepseek-ai/dsh web --patch ./cas-monster.cordis.yml
   ```

3. 新建会话，使用第 4 步的验证提示词。工具名可能显示为 `mcp__cas_monster__cas_list_clubs`。使用 DeepSeek Harness 桌面端的同学，也可以从设置里的 MCP 管理界面添加本地 stdio 命令，使用相同的 Command 和 Arguments。

[DeepSeek Harness 中文 MCP 指南](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/mcp-memory.zh.md#接入其他-mcp-服务器) · [命令行参考](https://github.com/deepseek-ai/deepseek-harness/tree/master/apps/cli/reference)

### Kimi Code

1. 从仓库目录运行 `kimi`，在会话里输入 `/mcp-config` 添加 stdio 服务。名称填 `cas_monster`，命令填 Python 路径，参数填 `cas_mcp.py` 路径。
2. 也可以在仓库目录创建 `.kimi-code/mcp.json`，填入[通用 JSON 配置](#通用-json-配置)。重启 Kimi Code 后按提示信任该项目。
3. 输入 `/mcp` 查看连接，再用第 4 步的提示词查询。

[Kimi Code 官方 MCP 指南](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/customization/mcp.md)

### Qwen Code

在仓库目录注册并启动 Qwen Code。在会话里输入 `/mcp` 查看连接。

```sh
qwen mcp add --scope project --transport stdio cas_monster "$casPython" "$casServer"
qwen mcp list
qwen
```

也可以把[通用 JSON 配置](#通用-json-配置)合并到项目的 `.qwen/settings.json`，再重启 Qwen Code。

[Qwen Code 官方 MCP 指南](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/mcp.md)

### 其他客户端

- **Cursor** 在项目目录创建 `.cursor/mcp.json`，填入[通用 JSON 配置](#通用-json-配置)，然后在本地 Agent 会话中启用 CAS Monster。 [Cursor MCP 文档](https://cursor.com/docs/mcp)
- **VS Code Copilot** 在命令面板运行 **MCP: Add Server**，选择本地 stdio，并填写第 1 步的命令和参数。当前 Copilot harness 的个人配置可选 **Global → Copilot Global**。 [VS Code MCP 配置参考](https://code.visualstudio.com/docs/agents/reference/mcp-configuration)
- **其他支持本地 stdio 的客户端** 选择 stdio，命令填写虚拟环境中的 Python，参数列表填写 `cas_mcp.py` 的完整路径。两者都要指向客户端实际运行的那台机器。

### 通用 JSON 配置

把路径换成第 1 步打印的实际值。Windows 的 JSON 配置可以用示例里的正斜杠 `/`，macOS 和 Linux 用自己的绝对路径。若文件已有 `mcpServers`，只把 `cas_monster` 这一项合并进去。

```json
{
  "mcpServers": {
    "cas_monster": {
      "command": "C:/Projects/CAS_MCP/.venv/Scripts/python.exe",
      "args": ["C:/Projects/CAS_MCP/cas_mcp.py"]
    }
  }
}
```

## 4. 验证连接

在客户端的本地会话里发这句：

> 请调用 CAS Monster 的 `cas_list_clubs`，列出我的活动记录和反思可选社团，只查询。

返回你账号中的社团列表后，就可以开始用。客户端显示的 `Connected` 表示 MCP 已启动，社团列表返回才验证了学校账号。

填报时，请提供真实活动信息，例如社团、日期、C/A/S 时数和实际做过的事。你可以选择以下两种用法。

- **这轮直接提交**　即使是第一条消息，只要你明确说“请提交”且资料齐全，模型就会调用 `cas_submit_entries`，在同一轮提交并展示完整英文稿和每条回执。
- **先看草稿**　说“请起草这条记录，先给我看”。模型会展示英文稿，等你之后明确要求提交再写入学校系统。

活动标题、描述以及反思的标题、摘要和正文都用英文。每条活动记录须写 120–180 个英文词，分 1–2 段。说明活动内容和自己做了什么，结尾简短反思。表单的社团选项使用学校显示的原名。学校表单的八项 Learning Outcomes 为 Awareness、Challenge、Initiative、Collaboration、Commitment、Global Value、Ethics 和 New Skills。

Reflection 的标题须为 4–10 个英文词，摘要须为以句末标点结尾的 18–22 词单句。正文用纯文本分段。社团反思至少 550 词、4–7 段，建议 600–750 词。Conversation 是整学期的 CAS 反思，至少 250 词、2–4 段，建议 250–350 词。

批量填报时，每条记录都应对应实际活动。出现 `unknown` 回执时，先查学校记录确认该条是否已写入，再决定是否重新提交。

## 查询 TSIMS

| 模块 | 可以这样问 |
| --- | --- |
| 成绩查询 | 查我这学期六门课各次考试的百分制和 IB 成绩。 |
| Academic Report | 查我 2025-2026(T2) 的学业报告，包括总评、课堂表现、TOK 和出勤。 |
| 课表 | 把我这学期的课表按星期和节次列出来，注明教师和教室。 |
| Club Application | 查有哪些学术类社团，看看历史社的介绍和申请状态。 |
| My Clubs | 列出我加入的社团、担任的职务以及 CAS Project。 |
| CAS Evaluation | 查我这学期各社团的 C、A、S 时数和反思评价。 |

按学期查询时，默认选用该模块列出的最新学期。查往期时可指定 TSIMS 上的学期名称，例如 `2025-2026(T2)`。

确定要加入一个具体社团时，可以明确要求提交入社申请。只有你明确要求时，才会在申请中勾选 CAS Project。

## 切换账号、退出和排查

- **换密码**　重新运行第 2 步的 `set`，然后重启客户端。
- **保留多个学校账号**　保存时加 `--profile student2`，并在 MCP 的启动参数里把 `--profile`、`student2` 依次放在 `cas_mcp.py` 后。给这个实例用不同的服务名，例如 `cas_student2`。不同档案各自保存凭据、草稿和回执。不同使用者宜使用各自的电脑或操作系统账号。
- **移除本机登录**　把第 2 步命令中的 `set` 改为 `forget`。如果用了命名档案，保留对应的 `--profile` 参数。然后关闭使用该档案的会话。
- **找不到工具**　检查客户端是否在本机运行、是否读取了正确的项目或用户配置，以及 Command 是否指向安装依赖时用的那个 Python。
- **已连接但登录失败**　确认客户端选择了正确的档案。重新保存学校账号，并在同一台电脑上确认可以打开学校 CAS 网站。
- **Linux 找不到凭据存储**　先启用桌面钥匙串。无钥匙串的环境可以只在默认档案的 MCP 进程中同时提供 `CAS_MONSTER_USERNAME` 和 `CAS_MONSTER_PASSWORD`，例如由系统密钥管理器注入。
- **只想查阅和预览**　为 MCP 进程设置 `CAS_MONSTER_READ_ONLY=1`。

## 开发与测试

运行 `python -m unittest discover -s tests -v`，使用第 1 步创建的 Python。写入测试使用本地模拟学校接口，覆盖首轮直接提交、英文表单字段、Learning Outcomes、重复提交、异常回执和账号隔离。OpenCode 2.3.0 和 pi 1.5.2 都用 DeepSeek `deepseek-flash` 验证了首轮提交并在同一轮展示完整英文稿和两条确认回执。其他客户端的接入步骤依据各自的官方文档。
