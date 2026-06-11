# fastkeel ⚡

> FastAPI backend scaffold — user auth, social, subscriptions, jobs & LLM.
> `pip install fastkeel`，一行命令生成完整后端骨架。

**Status:** v0.5.0 — 生产就绪，[MIT](./LICENSE) 开源。

---

## 快速开始

```bash
# 安装
pip install fastkeel

# 生成项目
fastkeel new my-app --with-user --with-social --with-payment --with-jobs
cd my-app

# 安装依赖并启动
pip install uvicorn
python main.py
```

生成的项目直接可用：注册、登录、搭子关系、支付订阅、定时任务 — 一个 `main.py` 全搞定。

---

## CLI 用法

```bash
fastkeel new <项目名> [--with-user] [--with-social] [--with-payment] [--with-jobs] [--path <路径>]
```

| 参数 | 默认 | 说明 |
|:----|:-----|:-----|
| `--with-user` | True | 设备注册 + JWT 认证 |
| `--with-social` | False | 搭子关系 + 群组管理 |
| `--with-payment` | False | 订阅管理 + 收据验证 |
| `--with-jobs` | False | APScheduler 定时任务 |
| `--path` | `.` | 项目生成路径 |

不选的模块不注册路由、不创建表、不引入依赖。

---

## 模块

| 模块 | 提供 |
|:----|:------|
| `core` | FastAPI app factory、Config (TOML + env)、SQLite (WAL)、JWT、CORS + 统一错误处理 |
| `user` | 设备注册、登录、JWT 认证、资料更新 |
| `social` | 搭子邀请码、搭子绑定/解除、群组创建/加入/解散 |
| `payment` | 套餐管理、收据验证（渠道无关）、订阅生命周期、支付流水 |
| `jobs` | APScheduler 定时任务、心跳检查、SQLite 持久化 |
| `contrib/llm` | LLM API 客户端（自动重试、限流、流式、结构化输出）|

### 架构

```
你的项目
├── main.py          # import fastkeel → compose app
├── config.toml      # TOML 配置（环境变量覆盖）
├── project/         # 你的业务逻辑
│   ├── routes/
│   ├── logic/
│   └── prompts/
└── tests/

        │ pip install fastkeel
        v
fastkeel (this repo)
├── core/            # 100% 通用，不修改
├── modules/         # 90% 通用，include_*() 选装
├── contrib/         # 扩展集成，按需 import
└── cli/             # fastkeel new 命令
```

分层规则：
- `core/` — 项目**永不修改**。需要改意味着抽象边界要调整
- `modules/` — 通过 config 配置，**不修改源码**
- `project/` — 写业务逻辑的地方

---

## 开发

```bash
# Setup
git clone https://github.com/helioswei/fastkeel
cd fastkeel
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Commands
make lint           # ruff check .
make test           # pytest
make build          # python -m build
make publish        # build + twine upload

# Test single file
pytest tests/test_modules/test_user.py -v
```

### 测试 (122 tests, 1.5s)

| 测试集 | 测试数 |
|:-------|:-------|
| `test_core/` (config, db, auth, middleware, app) | 47 |
| `test_modules/test_user.py` | 13 |
| `test_modules/test_social.py` | 21 |
| `test_modules/test_payment.py` | 13 |
| `test_modules/test_jobs.py` | 5 |
| `test_contrib/test_llm.py` | 8 |
| `test_cli/test_new.py` | 9 |
| `test_integration.py` | 6 |
| **合计** | **122** |

---

## 设计文档

- [DESIGN.md](./DESIGN.md) — 设计理念、分层规则、模块规格
- [TAD.md](./TAD.md) — 详细技术方案、API 签名、测试策略
- [CLAUDE.md](./CLAUDE.md) — 给 AI 助手的代码库指南

---

MIT © 2026 Helioswei
