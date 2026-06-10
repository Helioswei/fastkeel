# fastkeel ⚡

> FastAPI backend scaffold — user auth, social, subscriptions, jobs & LLM.
> pip install fastkeel，一行命令开工。

**状态:** Design — 设计文档已定稿，准备编码。

## 模块

| 模块 | 说明 |
|:----|:------|
| `core` | app factory / config / SQLite / JWT / middleware |
| `user` | 设备注册、登录、JWT 认证 |
| `social` | 搭子关系、群组、邀请码 |
| `payment` | 订阅管理、收据验证、支付流水 |
| `jobs` | APScheduler 定时任务 |
| `contrib/llm` | LLM API 客户端（重试、限流、流式） |

## 使用方式

```bash
pip install fastkeel
fastkeel new my-app --with-user --with-payment
cd my-app
# 写 project/ 下的业务逻辑
```

## LICENSE

MIT
