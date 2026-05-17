# 幕燃 v3

本版本在 V2「注册 + 积分消耗 + 管理员能力」基础上，完成了管理员后台与内容生产工作台的拆分。

## 本次修改重点

1. 管理员后台已拆为独立路由：`/admin`。
2. 普通用户仍进入内容生产工作台：`/`。
3. 内容生产工作台不再显示管理员入口。
4. 管理员登录后自动跳转到 `/admin`。
5. 管理员后台只保留平台运营管理内容：运营概览、用户管理、积分调整、积分流水。
6. 管理员后台不包含项目、剧集、剧情、分镜、素材、视频生成等内容生产功能。

## 默认账号

普通用户：`demo / demo123`

管理员：`admin / admin123`

## 启动方式

### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev
```

打开：`http://localhost:5173`

管理员后台：`http://localhost:5173/admin`

## 使用说明

完整使用说明见：[docs/使用说明.md](docs/使用说明.md)
