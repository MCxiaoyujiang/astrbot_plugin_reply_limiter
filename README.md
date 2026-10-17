# astrbot_plugin_reply_limiter

限制 AstrBot 机器人回复的字符长度。在消息发出前统计回复文本长度，超过上限时自动**截断**或整条**拦截**。

## 功能

- 在 `on_decorating_result`（消息发送前）钩子中生效，对 LLM 回复、其他插件回复一视同仁
- 只统计文本段（`Plain`）字符数，图片、语音、`@` 等非文本消息段不计入长度
- 两种超长处理方式：
  - `truncate`：截断保留前面的内容，可配置后缀（后缀占用长度额度）
  - `block`：整条丢弃，只回一句提示语
- 截断时会保留截断点之前的非文本段（例如图片），丢弃其后的文本
- 全部配置支持 WebUI 可视化修改，改完重载插件即生效
- 配置非法（如 `max_length` 填了非数字）时自动回退默认值，不会导致插件崩溃
- 钩子内部异常被完整捕获，出问题时回复原样发出，不影响机器人正常工作

## 安装

把整个 `astrbot_plugin_reply_limiter` 目录放到 AstrBot 的插件目录：

| 部署方式 | 插件目录 |
| --- | --- |
| Docker | `/AstrBot/data/plugins/` |
| Windows 桌面版 | `C:\Users\<用户名>\.astrbot\data\plugins\` |
| 源码部署 | `AstrBot/data/plugins/` |

然后在 WebUI 的「插件」页点击重载，或重启 AstrBot。

## 配置

WebUI →「插件」→ 找到「回复长度限制」→ 配置：

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enabled` | bool | `true` | 是否启用限制 |
| `max_length` | int | `300` | 单条回复最大字符数 |
| `mode` | string | `truncate` | `truncate` 截断 / `block` 拦截 |
| `suffix` | string | `…` | 截断后缀，占用 `max_length` 额度 |
| `block_notice` | text | `这条回复太长了，已被拦截。` | 拦截模式提示语 |
| `show_stats` | bool | `true` | 提示语后附带字符统计 |

## 运行时指令

均为**管理员**指令，无需重载插件即可调整：

```
/replylimit status        查看当前配置
/replylimit set 200       设置最大字符数为 200
/replylimit on            开启限制
/replylimit off           关闭限制
/replylimit mode block    切换为拦截模式
/replylimit mode truncate 切换为截断模式
```

指令写入的改动会持久化到插件配置文件，与 WebUI 修改等价。

## 使用示例

设 `max_length = 10`、`suffix = "..."`、`mode = truncate`：

```
原始回复：abcdefghijklmnopqrst
实际发出：abcdefg...          （总长 10，含 3 字符后缀）
```

设 `max_length = 10`、`mode = block`、`show_stats = true`：

```
原始回复：xxxxxxxxxxxxxxxxxxxxxxxxx（25 字）
实际发出：太长了（原 25 字，上限 10 字）
```

## 关于 OneBot

插件在 AstrBot 的消息发送前钩子上工作，与具体平台适配器解耦。OneBot 协议对应 AstrBot 的 `aiocqhttp` 适配器，已在 `metadata.yaml` 的 `support_platforms` 中声明。

OneBot 相关注意点：

- QQ 单条消息有平台侧长度上限，`max_length` 建议设为明显小于平台上限的值（如 300～2000）
- 若同时开启了 AstrBot 的「消息转发」（`platform_settings.forward_threshold`），超长内容可能被转成合并转发而非单条消息，建议把该阈值设得比 `max_length` 大，或关闭转发，避免两者行为叠加
- 若开启了「分段回复」，分段在长度限制之后处理，因此限制仍按整条回复的总长度计算

## 目录结构

```
astrbot_plugin_reply_limiter/
├── main.py               插件主程序
├── metadata.yaml         插件元数据（AstrBot 识别插件依赖此文件）
├── _conf_schema.json     配置项声明（WebUI 可视化配置依赖此文件）
└── README.md
```

## 开发说明

- 适用 AstrBot v3.5.20+（使用 `metadata.yaml` 而非 `metadata.json`）
- 使用前请把 `metadata.yaml` 中的 `author` 和 `repo` 改成你自己的信息，`main.py` 中 `@register(...)` 的第二个参数同理
- 无第三方依赖，不需要 `requirements.txt`
