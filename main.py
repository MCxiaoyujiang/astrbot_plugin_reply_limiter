"""限制机器人回复字符长度的 AstrBot 插件。

核心实现：
    在 ``on_decorating_result``（消息发送前）钩子中拿到即将外发的消息链，
    统计其中所有文本段（Plain）的总字符数，超过上限时按配置进行截断或拦截。

适用平台：
    OneBot（AstrBot 中对应 ``aiocqhttp`` 适配器），同时兼容其他平台。
"""

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

# 配置项默认值，读取配置出错时回退使用
DEFAULT_MAX_LENGTH = 300
DEFAULT_MODE = "truncate"
DEFAULT_SUFFIX = "…"
DEFAULT_BLOCK_NOTICE = "这条回复太长了，已被拦截。"


class ReplyLimiterPlugin(Star):
    """限制机器人回复的字符长度。

    AstrBot v3.5.19 之后会自动检测 Star 子类并注册插件，
    插件元数据统一由 metadata.yaml 提供，无需 @register 装饰器（已弃用）。
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.logger.info(
            f"回复长度限制插件已加载：max_length={self._max_length()}, mode={self._mode()}"
        )

    # ------------------------------------------------------------------
    # 配置读取
    # ------------------------------------------------------------------

    def _enabled(self) -> bool:
        """是否启用限制。"""
        return bool(self.config.get("enabled", True))

    def _max_length(self) -> int:
        """单条回复允许的最大字符数。"""
        raw = self.config.get("max_length", DEFAULT_MAX_LENGTH)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            self.logger.warning(f"max_length 配置非法（{raw!r}），已回退为 {DEFAULT_MAX_LENGTH}")
            return DEFAULT_MAX_LENGTH
        return value if value > 0 else DEFAULT_MAX_LENGTH

    def _mode(self) -> str:
        """超长处理方式：truncate 截断 / block 拦截。"""
        mode = str(self.config.get("mode", DEFAULT_MODE)).strip().lower()
        return mode if mode in ("truncate", "block") else DEFAULT_MODE

    def _suffix(self) -> str:
        """截断后追加的后缀。"""
        suffix = self.config.get("suffix", DEFAULT_SUFFIX)
        return DEFAULT_SUFFIX if suffix is None else str(suffix)

    def _block_notice(self) -> str:
        """拦截模式下替换整条回复的提示语。"""
        notice = self.config.get("block_notice", DEFAULT_BLOCK_NOTICE)
        if notice is None or not str(notice).strip():
            return DEFAULT_BLOCK_NOTICE
        return str(notice)

    def _show_stats(self) -> bool:
        """提示语后是否附带字符统计。"""
        return bool(self.config.get("show_stats", True))

    # ------------------------------------------------------------------
    # 消息链工具
    # ------------------------------------------------------------------

    @staticmethod
    def _is_plain(comp) -> bool:
        """判断消息段是否为纯文本段。"""
        plain_cls = getattr(Comp, "Plain", None)
        if plain_cls is not None and isinstance(comp, plain_cls):
            return True
        # 兼容部分版本中 Plain 被包装的情况
        return type(comp).__name__ == "Plain"

    @classmethod
    def _plain_text(cls, comp) -> str:
        """取出文本段的内容，非文本段返回空字符串。"""
        if not cls._is_plain(comp):
            return ""
        text = getattr(comp, "text", None)
        return text if isinstance(text, str) else ""

    @classmethod
    def _chain_list(cls, result):
        """从结果对象中取出可操作的消息段列表，取不到返回 None。"""
        chain = getattr(result, "chain", None)
        if isinstance(chain, list):
            return chain
        inner = getattr(chain, "chain", None)
        if isinstance(inner, list):
            return inner
        return None

    @classmethod
    def _write_chain(cls, result, new_chain) -> bool:
        """把新的消息段列表写回结果对象。"""
        chain = getattr(result, "chain", None)
        if isinstance(chain, list):
            chain[:] = new_chain
            return True
        inner = getattr(chain, "chain", None)
        if isinstance(inner, list):
            inner[:] = new_chain
            return True
        try:
            result.chain = new_chain
            return True
        except Exception as exc:  # noqa: BLE001 - 兜底，避免影响主流程
            logger.error(f"写回消息链失败: {exc}")
            return False

    @classmethod
    def _text_length(cls, chain) -> int:
        """统计消息链中所有文本段的总字符数。"""
        return sum(len(cls._plain_text(comp)) for comp in chain)

    def _truncate(self, chain, max_length: int):
        """按预算截断文本段，保留截断点之前的图片等非文本段。"""
        suffix = self._suffix()
        budget = max(0, max_length - len(suffix))

        new_chain = []
        exhausted = False
        for comp in chain:
            if not self._is_plain(comp):
                # 非文本段：截断前原样保留，截断后也保留（如图片）
                new_chain.append(comp)
                continue

            if exhausted:
                # 预算耗尽，丢弃后续所有文本段
                continue

            text = self._plain_text(comp)
            if len(text) <= budget:
                new_chain.append(comp)
                budget -= len(text)
                if budget <= 0:
                    exhausted = True
                continue

            kept = text[:budget].rstrip()
            new_chain.append(Comp.Plain(kept + suffix) if kept else Comp.Plain(suffix))
            budget = 0
            exhausted = True

        return new_chain

    def _notice(self, text_len: int, max_length: int, base: str) -> str:
        """拼装提示语，可选附加字符统计。"""
        if self._show_stats():
            return f"{base}（原 {text_len} 字，上限 {max_length} 字）"
        return base

    # ------------------------------------------------------------------
    # 核心钩子：消息发送前
    # ------------------------------------------------------------------

    @filter.on_decorating_result()
    async def limit_reply_length(self, event: AstrMessageEvent):
        """在消息发出前检查并限制回复长度。

        注意：该钩子中不能使用 yield 发送消息，只能修改
        ``event.get_result().chain``。
        """
        if not self._enabled():
            return

        try:
            result = event.get_result()
            if result is None:
                return

            chain = self._chain_list(result)
            if not chain:
                return

            max_length = self._max_length()
            text_len = self._text_length(chain)
            if text_len <= max_length:
                return

            if self._mode() == "block":
                notice = self._notice(
                    text_len, max_length, self._block_notice()
                )
                new_chain = [Comp.Plain(notice)]
            else:
                new_chain = self._truncate(chain, max_length)

            if not self._write_chain(result, new_chain):
                return

            self.logger.info(
                f"回复超长已处理（{self._mode()}）：{text_len} -> "
                f"{self._text_length(new_chain)}，上限 {max_length}"
            )
        except Exception as exc:  # noqa: BLE001 - 保证不影响正常回复
            self.logger.error(f"限制回复长度时出错: {exc}")

    # ------------------------------------------------------------------
    # 运行时管理指令（仅管理员）
    # ------------------------------------------------------------------

    @filter.command_group("replylimit")
    def replylimit(self):
        """回复长度限制管理指令组。"""

    @filter.permission_type(filter.PermissionType.ADMIN)
    @replylimit.command("status")
    async def cmd_status(self, event: AstrMessageEvent):
        """查看当前的回复长度限制配置"""
        yield event.plain_result(self._status_text())

    @filter.permission_type(filter.PermissionType.ADMIN)
    @replylimit.command("set")
    async def cmd_set(self, event: AstrMessageEvent, value: int):
        """设置最大字符数，如 /replylimit set 200"""
        if value <= 0:
            yield event.plain_result("最大字符数必须是正整数。")
            return
        self.config["max_length"] = value
        self.config.save_config()
        yield event.plain_result(f"已设置最大回复长度为 {value} 字符。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @replylimit.command("on")
    async def cmd_on(self, event: AstrMessageEvent):
        """开启回复长度限制"""
        self.config["enabled"] = True
        self.config.save_config()
        yield event.plain_result("已开启回复长度限制。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @replylimit.command("off")
    async def cmd_off(self, event: AstrMessageEvent):
        """关闭回复长度限制"""
        self.config["enabled"] = False
        self.config.save_config()
        yield event.plain_result("已关闭回复长度限制。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @replylimit.command("mode")
    async def cmd_mode(self, event: AstrMessageEvent, value: str):
        """设置超长处理方式：truncate 或 block"""
        value = value.strip().lower()
        if value not in ("truncate", "block"):
            yield event.plain_result("模式只能是 truncate（截断）或 block（拦截）。")
            return
        self.config["mode"] = value
        self.config.save_config()
        yield event.plain_result(f"已切换为 {value} 模式。")

    def _status_text(self) -> str:
        """生成当前配置的文本描述。"""
        state = "开启" if self._enabled() else "关闭"
        mode = "截断" if self._mode() == "truncate" else "拦截"
        return (
            f"回复长度限制：{state}\n"
            f"最大字符数：{self._max_length()}\n"
            f"处理方式：{mode}\n"
            f"截断后缀：{self._suffix()}"
        )
