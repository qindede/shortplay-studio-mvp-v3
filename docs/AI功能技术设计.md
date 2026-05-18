# AI 功能技术设计

## 1. 背景与目标

幕燃 当前产品形态是短剧制作工作台，核心链路为：

项目创建 -> 剧集规划 -> 剧本编辑 -> 分镜拆解 -> 素材管理 -> 镜头视频生成 -> 成片版本管理

现有前端已经预留了多处 AI 操作入口，后端也已有本地占位实现。本设计文档的目标是将这些占位能力替换为真实 AI 服务，并将数据层迁移到 Postgres，支撑后续真实用户、积分消耗、异步任务、任务审计和生产部署。

## 2. 设计原则

1. AI 能力围绕短剧生产链路闭环设计，不做孤立工具。
2. 文本类能力优先同步返回，媒体生成类能力统一异步任务化。
3. 供应商接口封装在服务层，业务路由不直接感知模型厂商细节。
4. 所有真实消耗类操作必须有可审计记录，包括请求输入、任务状态、积分扣减和失败原因。
5. 数据库使用 Postgres，文件、图片、音频、视频本体不入库，只存 URL、路径和元数据。
6. API Key 只允许通过环境变量注入，禁止写入代码仓库和 Markdown 文档。

## 3. AI 能力范围

### 3.1 文本创作

对应能力：

- 项目大纲生成
- 剧集脚本辅助生成
- 分镜脚本生成
- 提示词优化

供应商：

- MiniMax，使用 OpenAI 兼容接口。

后端替换点：

- `build_project_outline`
- `build_storyboard`
- `optimize_prompt`

输出要求：

- 大纲生成必须返回结构化 `episodes`。
- 分镜生成必须返回结构化 `shots`。
- 提示词优化返回纯文本 `optimized`。
- LLM 响应必须做 JSON schema 校验，校验失败时返回明确错误，不写入半成品数据。

### 3.2 图像生成

对应能力：

- 角色资产图
- 场景资产图
- 通用参考图

供应商：

- 火山 Ark / Seedream。

接入接口：

- `POST /api/projects/{project_id}/assets/generate`

生成结果：

- 保存主图到 `assets.image_url`。
- 保存参考图到 `asset_references`。
- 若供应商返回 URL 有时效，后端应下载到本地 `uploads` 或对象存储，再保存稳定 URL。

### 3.3 声音设计与音色克隆

对应能力：

- 角色音色训练
- 音色状态查询
- 试听音频保存

供应商：

- 火山 OpenSpeech voice clone / get voice。

建议流程：

1. 用户上传角色音频样本。
2. 后端生成 `speaker_id`。
3. 创建 `voice_clone` 任务。
4. 定时或手动查询 `get_voice`。
5. 成功后保存 `speaker_id`、`voice_status`、`demo_audio_url`。

MVP 阶段只支持角色资产的音色克隆。

### 3.4 视频生成

对应能力：

- 单镜头视频生成
- 剧集镜头批量生成
- 视频任务状态查询

供应商：

- 火山 Ark / Seedance。

接入接口：

- `POST /api/shots/{shot_id}/generate-video`
- `POST /api/episodes/{episode_id}/generate-videos`
- `GET /api/episodes/{episode_id}/video-tasks`

生成策略：

- 若镜头可匹配角色图或场景图，优先图生视频。
- 否则使用镜头 `visual` 做文生视频。
- 默认参数：`resolution=1080p`、`ratio=9:16`、`duration=shot.duration`、`watermark=true`。

任务状态：

- `pending`
- `generating`
- `completed`
- `failed`

### 3.5 成片版本

MVP 阶段：

- `compose` 只创建成片版本记录。
- 仅允许所有镜头已完成时创建版本。

后续阶段：

- 下载或读取所有镜头视频。
- 按镜头顺序拼接。
- 可叠加字幕、旁白、背景音乐、片头片尾。
- 输出最终视频 URL，保存到 `video_versions.video_url`。

## 4. 技术架构

### 4.1 后端模块划分

建议新增：

```text
backend/app/ai/
  __init__.py
  client.py
  llm.py
  image.py
  voice.py
  video.py
  prompts.py
  schemas.py
```

职责：

- `client.py`：统一 HTTP 请求、超时、重试、错误包装。
- `llm.py`：MiniMax/OpenAI-compatible 调用。
- `image.py`：Seedream 图像生成。
- `voice.py`：音色克隆和状态查询。
- `video.py`：Seedance 视频任务创建和查询。
- `prompts.py`：项目、剧集、分镜、素材、视频提示词模板。
- `schemas.py`：AI 输出结构校验模型。

### 4.2 配置

环境变量：

```text
DATABASE_URL=postgresql://user:password@host:5432/shortplay?sslmode=require
SHORTPLAY_AUTH_SECRET=...

MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_API_KEY=...
MINIMAX_TEXT_MODEL=...

ARK_API_KEY=...
ARK_IMAGE_MODEL=Doubao-Seedream-5.0-lite
ARK_VIDEO_MODEL=doubao-seedance-1-0-pro-fast-251015

VOLC_VOICE_API_KEY=...
```

注意：

- 当前 `backend/docs` 中存在明文供应商 key，实施前应移除或替换为占位符。
- `.env` 必须加入 `.gitignore`。

## 5. Postgres 数据模型

建议使用：

```text
Postgres + SQLAlchemy 2.x + Alembic
```

### 5.1 users

```text
id uuid primary key
username varchar unique not null
password_hash varchar not null
display_name varchar not null
role varchar not null
status varchar not null
points integer not null default 0
usage_json jsonb not null default '{}'
created_at timestamptz not null
last_login_at timestamptz
```

### 5.2 projects

```text
id uuid primary key
owner_user_id uuid references users(id)
name varchar not null
short_name varchar not null
description text
status varchar not null
cover varchar
cover_image_url text
created_at timestamptz not null
updated_at timestamptz not null
```

### 5.3 episodes

```text
id uuid primary key
project_id uuid references projects(id) on delete cascade
no integer not null
title varchar not null
summary text
script text
duration_target integer not null
status varchar not null
created_at timestamptz not null
updated_at timestamptz not null

unique(project_id, no)
```

### 5.4 shots

```text
id uuid primary key
episode_id uuid references episodes(id) on delete cascade
no integer not null
title varchar not null
visual text
dialogue text
characters jsonb not null default '[]'
scene varchar
duration integer not null
status varchar not null
created_at timestamptz not null
updated_at timestamptz not null

unique(episode_id, no)
```

### 5.5 assets

```text
id uuid primary key
project_id uuid references projects(id) on delete cascade
type varchar not null
name varchar not null
description text
initial varchar
image_url text
voice_label text
voice_url text
speaker_id varchar
voice_status varchar
generation_prompt text
provider_meta jsonb not null default '{}'
created_at timestamptz not null
updated_at timestamptz not null
```

### 5.6 asset_references

```text
id uuid primary key
asset_id uuid references assets(id) on delete cascade
type varchar not null
name varchar not null
url text
note text
sort_order integer not null default 0
created_at timestamptz not null
```

### 5.7 ai_jobs

统一记录所有 AI 调用。

```text
id uuid primary key
user_id uuid references users(id)
project_id uuid references projects(id)
episode_id uuid references episodes(id)
shot_id uuid references shots(id)
asset_id uuid references assets(id)

type varchar not null
provider varchar not null
provider_task_id varchar
status varchar not null
progress integer not null default 0

input_json jsonb not null default '{}'
output_json jsonb not null default '{}'
error text
cost_points integer not null default 0

created_at timestamptz not null
updated_at timestamptz not null
completed_at timestamptz
```

`type` 枚举：

```text
outline
storyboard
prompt_optimize
image_asset
voice_clone
video_shot
video_batch
compose
```

`status` 枚举：

```text
pending
running
succeeded
failed
cancelled
```

### 5.8 video_tasks (已合并到 ai_jobs)

> 此表已在 2026-05-18 合并到 `ai_jobs` 表。`type='video_shot'` 的 AiJob 即为视频任务。
> `title`/`duration` 来源于 `shots` 表（join `shot_id`），`preview_url`/`video_url` 存储在 `output_json` 中。

### 5.9 video_versions

```text
id uuid primary key
project_id uuid references projects(id) on delete cascade
episode_id uuid references episodes(id) on delete cascade
name varchar not null
description text
duration integer not null
ratio varchar not null
status varchar not null
theme varchar
preview_url text
video_url text
created_at timestamptz not null
```

### 5.10 point_ledger

```text
id uuid primary key
user_id uuid references users(id)
amount integer not null
type varchar not null
scene varchar not null
description text
balance_after integer not null
ai_job_id uuid references ai_jobs(id)
created_at timestamptz not null
```

## 6. API 设计

保留现有前端 API 路径，减少前端改造。

### 6.1 项目大纲生成

```text
POST /api/projects/generate-outline
```

请求：

```json
{
  "name": "项目名",
  "description": "项目设定",
  "episode_count": 6
}
```

响应：

```json
{
  "cost": 20,
  "episodes": [
    {
      "title": "第1集标题",
      "summary": "本集梗概",
      "script": "本集脚本",
      "duration_target": 30
    }
  ]
}
```

### 6.2 分镜生成

```text
POST /api/episodes/{episode_id}/generate-storyboard
```

行为：

- 读取项目、剧集、脚本、已有资产。
- 调用 LLM 生成镜头列表。
- 替换当前剧集已有 AI 分镜。
- 扣除分镜积分。

### 6.3 资产 AI 生成

```text
POST /api/projects/{project_id}/assets/generate
```

请求：

```json
{
  "type": "character",
  "name": "苏晴",
  "description": "女主角，冷静克制",
  "prompt": "现代都市短剧女主角，半身剧照"
}
```

响应：

```json
{
  "id": "asset_xxx",
  "type": "character",
  "name": "苏晴",
  "image": "/uploads/xxx.png",
  "references": []
}
```

### 6.4 单镜头视频生成

```text
POST /api/shots/{shot_id}/generate-video
```

响应立即返回任务：

```json
{
  "id": "task_xxx",
  "shot_id": "shot_xxx",
  "status": "generating",
  "progress": 0
}
```

前端继续通过：

```text
GET /api/episodes/{episode_id}/video-tasks
```

获取最新状态。

### 6.5 AI 任务查询

建议新增：

```text
GET /api/ai-jobs/{job_id}
GET /api/projects/{project_id}/ai-jobs
```

用于后台排错、用户任务历史和失败重试。

## 7. 积分与事务

### 7.1 扣费原则

文本类：

- 请求校验通过后扣费。
- LLM 调用失败时不写业务结果，可按产品策略退款或不扣。

媒体任务类：

- 远端任务创建成功后扣费。
- 远端任务创建失败不扣费。
- 远端任务执行失败时记录失败原因，是否退款由产品策略决定。

### 7.2 数据库事务

创建 AI 任务时，同一事务内完成：

1. 校验用户权限。
2. 校验积分余额。
3. 创建 `ai_jobs`。
4. 扣减 `users.points`。
5. 写入 `point_ledger`。
6. 创建或更新业务任务记录。

远端 AI 调用不应长时间占用数据库事务。推荐流程：

1. 数据库创建 `ai_jobs=pending`。
2. 调用供应商接口。
3. 成功后更新 `provider_task_id` 和 `status=running`。
4. 失败后更新 `status=failed` 和 `error`。

## 8. 异步任务方案

MVP 可以先使用 FastAPI `BackgroundTasks` 或简单定时轮询。

正式建议：

```text
FastAPI + Celery/RQ/Arq + Redis + Postgres
```

任务类型：

- 查询视频生成状态。
- 查询音色训练状态。
- 下载供应商临时文件到本地或对象存储。
- 成片合成。

轮询策略：

- 初始 5 秒后查询。
- 运行中每 10-20 秒查询。
- 超过最大时长标记失败。
- 每次查询更新 `ai_jobs.progress` 和业务表状态。

## 9. 错误处理

统一错误类型：

```text
AIProviderAuthError
AIProviderRateLimitError
AIProviderTimeoutError
AIProviderValidationError
AIProviderTaskFailedError
AIOutputSchemaError
```

对前端返回：

- 用户可理解的中文错误。
- 不暴露 API Key、供应商原始敏感信息。
- 后端日志保留供应商 `request_id` 或 `log_id` 便于排查。

## 10. 安全要求

1. 移除所有文档中的明文 API Key。
2. 后端环境变量读取密钥。
3. 上传文件限制类型和大小。
4. 音频克隆应增加用户确认，避免未经授权克隆他人声音。
5. AI 输出内容入库前做长度限制。
6. 供应商返回 URL 若包含签名，不直接暴露长期依赖。

## 11. 实施顺序

### 阶段 1：Postgres 基础迁移

目标：

- 引入 SQLAlchemy 和 Alembic。
- 建立用户、项目、剧集、分镜、素材、视频、积分表。
- 将当前 JSON store 替换为数据库访问层。
- 保持现有前端 API 不变。

验收：

- 注册、登录、项目、剧集、分镜、素材、积分流水、版本管理全部可用。

### 阶段 2：LLM 文本能力

目标：

- 接入 MiniMax。
- 替换项目大纲、分镜、提示词优化。
- 增加结构化输出校验。

验收：

- 用户输入项目设定后能生成可编辑剧集大纲。
- 用户输入剧本后能生成可编辑镜头分镜。
- 提示词优化返回中文短剧制作可用 prompt。

### 阶段 3：图像生成

目标：

- 接入 Seedream。
- 替换素材 AI 生成占位图。
- 保存生成图片 URL 和参考记录。

验收：

- 角色、场景、图片资产可以真实生成并在素材库预览。

### 阶段 4：视频生成

目标：

- 接入 Seedance。
- 创建远端视频任务。
- 支持任务状态查询和结果 URL 保存。

验收：

- 单个镜头可生成视频。
- 批量生成可以创建多个任务。
- 视频页能看到进度和最终预览。

### 阶段 5：音色克隆

目标：

- 接入 voice clone 和 get voice。
- 支持角色音色训练和试听。

验收：

- 上传角色音频后能创建音色任务。
- 训练成功后资产详情页能试听 demo。

### 阶段 6：真实成片合成

目标：

- 将完成镜头按顺序拼接为完整短剧视频。
- 输出成片版本 URL。

验收：

- 所有镜头完成后，用户可生成并预览完整成片。

## 12. 需要先处理的问题

1. 当前前后端多处中文文本出现编码异常，建议先统一文件编码为 UTF-8。
2. `backend/docs` 中的明文密钥必须清理。
3. 需要确定 Postgres 部署方式：本地 Docker、云数据库或服务器自建。
4. 需要确定生成文件存储方式：本地 `uploads`、S3 兼容对象存储或火山 TOS。
5. 需要确认视频和音色任务是否允许失败退款。

## 13. 推荐默认决策

如果没有额外产品约束，推荐默认采用：

- 数据库：Postgres 16
- ORM：SQLAlchemy 2.x
- 迁移：Alembic
- 后台任务：先 FastAPI BackgroundTasks，后续升级 Celery/RQ
- 文件存储：MVP 本地 `backend/uploads`，生产迁对象存储
- LLM：MiniMax OpenAI-compatible
- 图像：Seedream
- 视频：Seedance
- 音色：火山 OpenSpeech voice clone
