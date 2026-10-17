# astrbot_plugin_reply_limiter
限制 AstrBot 机器人回复的字符长度。在消息发出前统计回复文本长度，超过上限时自动截断或整条拦截。
  功能
在 on_decorating_result（消息发送前）钩子中生效，对 LLM 回复、其他插件回复一视同仁
只统计文本段（Plain）字符数，图片、语音、@ 等非文本消息段不计入长度
两种超长处理方式：
truncate：截断保留前面的内容，可配置后缀（后缀占用长度额度）
block：整条丢弃，只回一句提示语
截断时会保留截断点之前的非文本段（例如图片），丢弃其后的文本
全部配置支持 WebUI 可视化修改，改完重载插件即生效
配置非法（如 max_length 填了非数字）时自动回退默认值，不会导致插件崩溃
钩子内部异常被完整捕获，出问题时回复原样发出，不影响机器人正常工作。
<img width="512" height="283" alt="image" src="https://github.com/user-attachments/assets/7a752af2-f96f-4616-8e20-e0317e804c50" />
<img width="636" height="340" alt="image" src="https://github.com/user-attachments/assets/e1cc8d02-8cc0-43b2-ac4a-a3c751a3bab5" />
