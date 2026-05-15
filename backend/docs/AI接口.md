# AI 接口配置

所有供应商密钥只能通过环境变量注入，禁止写入代码仓库或 Markdown 文档。

## LLM

- 接口：`https://api.minimaxi.com/v1`
- 环境变量：`MINIMAX_API_KEY`
- 模型：`MINIMAX_TEXT_MODEL`

## 文生图 / 图生图

- 接口：`https://ark.cn-beijing.volces.com/api/v3/images/generations`
- 环境变量：`ARK_API_KEY`
- 模型：`ARK_IMAGE_MODEL`

## 视频生成

- 接口：`https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks`
- 环境变量：`ARK_API_KEY`
- 模型：`ARK_VIDEO_MODEL`

## 音色设计

- 训练接口：`https://openspeech.bytedance.com/api/v3/tts/voice_clone`
- 查询接口：`https://openspeech.bytedance.com/api/v3/tts/get_voice`
- 环境变量：`VOLC_VOICE_API_KEY`
