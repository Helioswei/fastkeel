# fastkeel — Python 后端脚手架

> pip install fastkeel，一行命令生成完整后端骨架。
> 你的 App 只管写业务逻辑，底层不动。

---

## 一、定位

| 维度 | 答案 |
|:----|:-----|
| **形态** | PyPI 包，pip install 后导入使用 |
| **用途** | 自己的多个 App 项目的后端底座 |
| **分发** | MIT 开源在 GitHub，PyPI 发布 |
| **覆盖场景** | 单机/小规模后端：FastAPI + SQLite + JWT + 定时任务 + LLM 调用 |
| **不覆盖** | 大规模集群、消息队列、Kubernetes、多数据库 |

每个新项目：

```bash
pip install fastkeel
fastkeel new my-project
cd my-project
# 写 project/ 目录下的业务逻辑
```

跟研究里发现的市场空白一脉相承——tiangolo 模板（43.5K⭐）无 SaaS 功能，付费竞品 <300 用户。fastkeel 填"自用顺手开源"这个生态位。

---

## 二、项目结构

```
fastkeel/
├── pyproject.toml
├── fastkeel/                         # pip install 后导入的包
│   ├── __init__.py
│   ├── core/                         # 100% 通用，从不修改
│   │   ├── app.py                    # FastAPI app factory
│   │   ├── config.py                 # 配置加载（环境变量 / TOML）
│   │   ├── db.py                     # SQLite + 迁移
│   │   ├── auth.py                   # 匿名 JWT + 设备绑定
│   │   └── middleware.py             # CORS / 日志 / 错误处理
│   ├── modules/                      # 90% 通用，按需选装
│   │   ├── user.py                   # 用户 CRUD（可扩展字段）
│   │   ├── social.py                 # 好友/群组关系
│   │   └── jobs.py                   # APScheduler 封装
│   ├── contrib/                      # 扩展集成，不强制导入
│   │   ├── llm.py                    # LLM API 调用 + 重试 + 限流
│   │   └── streaming.py              # SSE 流式响应
│   ├── cli/                          # fastkeel 命令行工具
│   │   └── new.py                    # fastkeel new <name>
│   └── templates/                    # 项目生成模板
│       └── default/
│           ├── main.py.j2
│           ├── config.toml.j2
│           ├── pyproject.toml.j2
│           ├── project/
│           │   ├── __init__.py.j2
│           │   ├── models/
│           │   ├── routes/
│           │   ├── logic/
│           │   └── prompts/
│           └── tests/
│               └── conftest.py.j2
│
├── tests/
│   ├── test_core/
│   ├── test_modules/
│   └── test_cli/
│
├── .github/
│   └── workflows/
│       ├── test.yml                   # CI — pytest on PR
│       └── publish.yml                # CD — PyPI on release
│
├── README.md
└── LICENSE                            # MIT
```

---

## 三、使用方式

### 安装

```bash
pip install fastkeel
```

### 创建新项目

```bash
fastkeel new 戒了么手机-backend --modules user,social,jobs
cd 戒了么手机-backend
```

### main.py

```python
from fastkeel import create_app, Config
from fastkeel.modules import include_user, include_social, include_jobs
from project.routes import detox, ai_weekly

config = Config(
    app_name="戒了么手机",
    db_url="sqlite:///data/app.db",
    jwt_secret=os.getenv("JWT_SECRET"),
    user_extra_fields={
        "detox_score": int,
        "buddy_id": Optional[str],
    },
)

app = create_app(config)
include_user(app, config)
include_social(app, config)
include_jobs(app, config)
app.include_router(detox.router, prefix="/api/v1")
```

### 扩展模型

```python
# project/models/detox.py
from fastkeel.core.db import Base
from sqlalchemy import Column, Integer, String, ForeignKey

class DetoxScore(Base):
    __tablename__ = "detox_scores"
    user_id = Column(String, ForeignKey("users.id"))
    score = Column(Integer)
```

---

## 四、模块选装

| 模块 | 提供 | 依赖 | CLI 参数 |
|:----|:-----|:-----|:---------|
| `user` | 注册/登录/资料/设备绑定 | core | `--with-user` |
| `social` | 好友/群组/邀请码 CRUD | user | `--with-social` |
| `payment` | 订阅管理/收据验证/支付流水 | user | `--with-payment` |
| `jobs` | APScheduler + 任务注册 | db | `--with-jobs` |
| `llm` | LLM API 调用 + 重试 + 限流 | core | `--with-llm` |

不选的模块不注册路由、不创建表、不引入依赖。

---

## 五、分层不可逆规则

```
fastkeel/core/      ← 项目永不修改
fastkeel/modules/   ← 项目通过 config 配置，不修改源码
project/            ← 这是项目写业务逻辑的地方
```

如果某个项目需要改 fastkeel 源码 → 抽象边界不对，功能该下沉到配置或上提到 project。

模型扩展不走继承，走 `user_extra_fields` 配置或外键关联新表。

零外部服务假设：默认 SQLite WAL 模式，单进程加锁，升级到 PostgreSQL 只需改 `db_url`。

---

## 六、开源清单（从第一天就做）

- [ ] MIT LICENSE 文件
- [ ] README.md — 一句话说清楚+快速开始+API 文档链接
- [ ] pyproject.toml — Python 3.11+，所有依赖声明
- [ ] GitHub Actions CI — pytest on push/PR
- [ ] GitHub Actions CD — 打 tag 自动发布到 PyPI
- [ ] Makefile — lint / test / build / publish

---

## 七、跟戒了么手机的关系

```
戒了么手机-backend/          fastkeel 生成的独立项目
├── fastkeel/               ← pip install 进来的
├── project/
│   ├── logic/
│   │   ├── detox_score.py      # 指数算法
│   │   ├── notification.py     # 搭子通知
│   │   └── huawei_verify.py    # 华为 IAP 收据验证（register_verifier）
│   ├── routes/
│   │   ├── buddy.py            # 搭子 API
│   │   └── ai.py               # AI 周报
│   └── prompts/
│       ├── weekly_insight.txt
│       └── strategy.txt
├── config.toml
├── main.py
└── pyproject.toml
```

再用新 App 时只需 `fastkeel new`，用户系统/JWT/好友/定时任务/LLM 全都有了。

---

## 八、落地计划

1. 核心 `fastkeel/core/`（app, config, db, auth, middleware）
2. `user` 模块（注册/登录/JWT/设备绑定）
3. `social` 模块（好友/群组/邀请码）
4. `payment` 模块（订阅管理/收据验证/支付流水）
5. `jobs` 模块（APScheduler 封装）
6. `contrib/llm`（LLM API + 重试 + 限流）
7. CLI `fastkeel new` + 模板
8. CI/CD + README + PyPI 发布
