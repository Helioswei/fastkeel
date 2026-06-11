# fastkeel — 技术方案

**状态**: Draft
**基于**: DESIGN.md v0.2
**最后更新**: 2026-06-11
**版本**: 0.1

---

## 1. 总体架构

### 1.1 架构概述

fastkeel 是一个 pip installable 的 Python 包，通过**导入 + 组合**的方式为项目提供后端骨架。项目代码 `import fastkeel` 后，调用工厂函数和模块注册函数组装自己的应用。

不是模板项目（需要 fork/copy），不是框架（需要继承），是**组合式底座**。

```
┌──────────────────────────────────────────────────────────┐
│                   你的项目（戒了么手机-backend）              │
│                                                          │
│  main.py                                                 │
│  ├── from fastkeel import create_app, Config             │
│  ├── app = create_app(config)                            │
│  ├── include_user(app, config)                           │
│  └── app.include_router(your_biz_router)                 │
│                                                          │
│  project/                                                │
│  ├── models/     ← SQLAlchemy 模型（你建新表）               │
│  ├── routes/     ← FastAPI 路由（你挂业务端点）              │
│  ├── logic/      ← 业务逻辑（指数算法/通知规则）              │
│  └── prompts/    ← LLM prompt 模板                        │
│                                                          │
└─────────────────────┬────────────────────────────────────┘
                      │ pip install fastkeel
┌─────────────────────┴────────────────────────────────────┐
│                  fastkeel (PyPI 包)                        │
│                                                          │
│  fastkeel/core/     → app factory, config, db, auth      │
│  fastkeel/modules/  → user, social, jobs                 │
│  fastkeel/contrib/  → llm, streaming                     │
│  fastkeel/cli/      → fastkeel new <name>                │
└──────────────────────────────────────────────────────────┘
```

### 1.2 关键设计决策

| 决策 | 选择 | 理由 |
|:----|:-----|:------|
| 分发方式 | PyPI + pip install | 不是模板，不 fork，每个项目通过 pip 引入 |
| Python 版本 | 3.11+ | 2026 年主流，typing 语法更简洁 |
| Web 框架 | FastAPI | 研究已验证，FastAPI 是 Python #1 Web 框架 |
| ORM | SQLAlchemy 2.0 | 成熟、ORM 抽象层可切数据库 |
| 数据库默认 | SQLite (WAL 模式) | 零外部服务，单文件部署 |
| 认证 | 匿名 JWT + 设备绑定 | 移动端 App 的典型模式 |
| 定时任务 | APScheduler | 轻量，不需要 Redis/RabbitMQ |
| LLM 调用 | httpx + 重试 + 限流 | 零额外依赖 |
| 配置格式 | TOML + 环境变量覆盖 | Python 生态标准（pyproject.toml 同款）|
| 测试框架 | pytest + httpx | FastAPI 官方推荐的测试方式 |
| 支付验证 | 收据验证 + 订阅生命周期管理 | 不绑定特定支付渠道，项目端实现 verify 回调 |

---

## 2. 包结构

```
fastkeel/
├── pyproject.toml
│
├── fastkeel/
│   ├── __init__.py               # 公开 API：create_app, Config
│   │
│   ├── core/                     # 核心层 — 100% 通用，从不修改
│   │   ├── __init__.py
│   │   ├── app.py                # create_app() 工厂函数
│   │   ├── config.py             # Config 类，TOML + env 加载
│   │   ├── db.py                 # SQLite 引擎 + session 管理
│   │   ├── auth.py               # JWT 签发+验证 + get_current_user 依赖
│   │   └── middleware.py         # CORS / 请求日志 / 全局异常处理
│   │
│   ├── modules/                  # 可选模块 — 按需 include
│   │   ├── __init__.py           # include_user, include_social, include_jobs
│   │   ├── user.py               # UserModel + 注册/登录路由
│   │   ├── social.py             # BuddyModel + GroupModel + 关系路由
│   │   ├── jobs.py               # APScheduler 配置 + 健康检查
│   │   └── payment.py            # SubscriptionModel + 收据验证 + 订阅管理
│   │
│   ├── contrib/                  # 增值集成 — 项目按需 import
│   │   ├── __init__.py
│   │   ├── llm.py                # LLMClient：调用 + 重试 + 限流
│   │   └── streaming.py          # SSEStreamer：FastAPI 流式响应工具
│   │
│   ├── cli/                      # 命令行
│   │   ├── __init__.py
│   │   └── new.py                # fastkeel new 子命令
│   │
│   └── templates/                # 项目骨架 Jinja2 模板
│       └── default/
│           ├── main.py.j2
│           ├── config.toml.j2
│           ├── pyproject.toml.j2
│           ├── project/
│           │   ├── __init__.py.j2
│           │   ├── models/__init__.py.j2
│           │   ├── routes/__init__.py.j2
│           │   ├── logic/__init__.py.j2
│           │   └── prompts/.gitkeep.j2
│           └── tests/
│               ├── __init__.py.j2
│               └── conftest.py.j2
│
├── tests/
│   ├── conftest.py               # 测试夹具 (test app, test db)
│   ├── test_core/
│   │   ├── test_app.py
│   │   ├── test_config.py
│   │   ├── test_auth.py
│   │   └── test_db.py
│   ├── test_modules/
│   │   ├── test_user.py
│   │   ├── test_social.py
│   │   └── test_jobs.py
│   └── test_cli/
│       └── test_new.py
│
├── .github/workflows/
│   ├── test.yml                  # on push/PR → pytest
│   └── publish.yml               # on tag → PyPI
│
├── README.md
└── LICENSE                       # MIT
```

---

## 3. 核心类型定义

### 3.1 Config

```python
# fastkeel/core/config.py

@dataclass
class Config:
    # 应用
    app_name: str = "app"
    debug: bool = False

    # 服务
    host: str = "0.0.0.0"
    port: int = 8000

    # 数据库
    db_url: str = "sqlite:///data/app.db"          # SQLite 默认
    db_echo: bool = False                          # SQLAlchemy echo

    # 认证
    jwt_secret: str = ""                           # 必填，无默认值
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 720                    # 30 天

    # 用户模块
    user_extra_fields: dict[str, type] | None = None  # 扩展字段 {列名: 类型}

    # 社交模块
    social_enable_groups: bool = True              # 是否启用群组功能

    # 任务模块
    jobs_config: dict[str, dict] | None = None     # {任务名: cron 参数}

    # 支付模块
    payment_plans: list[dict] | None = None        # [{id, name, price, duration_days}]
    payment_webhook_secret: str | None = None

    # LLM
    llm_api_key: str | None = None
    llm_api_base: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_max_retries: int = 3
    llm_rate_limit: int = 10                       # 每分钟最大请求数

    # 加载方式
    @classmethod
    def from_toml(cls, path: str) -> "Config":
        """从 TOML 文件加载，环境变量覆盖"""
        ...

    @classmethod
    def from_env(cls) -> "Config":
        """仅从环境变量加载（FASTKEEL_* 前缀）"""
        ...
```

### 3.2 App 工厂

```python
# fastkeel/core/app.py

def create_app(config: Config) -> FastAPI:
    """创建 FastAPI 应用实例。注册中间件、挂载静态文件、添加生命周期钩子。"""
    app = FastAPI(title=config.app_name, ...)
    register_middleware(app, config)
    register_lifespan(app, config)     # 启动时创建表，关闭时释放连接
    return app
```

### 3.3 DB 会话

```python
# fastkeel/core/db.py

engine: Engine | None = None
SessionLocal: sessionmaker | None = None

def init_db(config: Config) -> None:
    """初始化 SQLAlchemy 引擎和会话工厂。"""
    ...

def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：每次请求一个会话，自动提交/回滚。"""
    ...

Base = declarative_base()  # 所有模块的模型都继承这个 Base
```

### 3.4 认证

```python
# fastkeel/core/auth.py

def create_token(user_id: str, config: Config) -> str:
    """签发 JWT。payload: {sub: user_id, exp, iat}"""
    ...

def verify_token(token: str, config: Config) -> str:
    """验证 JWT，返回 user_id。过期/无效抛出 HTTPException(401)。"""
    ...

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    config: Config = Depends(get_config),
) -> UserModel:
    """FastAPI 依赖注入：验证 token 并返回用户对象。"""
    ...
```

---

## 4. 模块接口设计

### 4.1 user 模块

**Model:**

```python
# fastkeel/modules/user.py

class UserModel(Base):
    __tablename__ = "fastkeel_users"
    id: str = Column(String, primary_key=True)    # UUID
    device_id: str = Column(String, unique=True, index=True)
    nickname: str = Column(String, default="")
    avatar_url: str = Column(String, default="")
    is_active: bool = Column(Boolean, default=True)
    created_at: datetime = Column(DateTime, default=func.now())
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now())

    # 扩展字段通过 config.user_extra_fields 动态添加
    # 实现方式：在 init_db() 时读取 config，ALTER TABLE 或创建额外列
```

**扩展字段机制：**

```python
# 项目 config.toml
[user]
extra_fields = { detox_score = "integer", buddy_id = "text" }

# fastkeel 内部：在 init_db() 时
if config.user_extra_fields:
    for field_name, field_type in config.user_extra_fields.items():
        # 映射 Python type → SQLAlchemy Column type
        col_type = type_mapping.get(field_type, Text)
        setattr(UserModel, field_name, Column(col_type, nullable=True))
    # 执行 ALTER TABLE（SQLite 支持 ADD COLUMN）
```

**API 路由：**

| 方法 | 路径 | 说明 | 认证 |
|:----|:-----|:-----|:-----|
| POST | `/api/v1/auth/register` | 设备注册 → 返回 JWT | 无 |
| POST | `/api/v1/auth/login` | 设备 ID + token 验证 → 刷新 JWT | 无 |
| GET  | `/api/v1/auth/me` | 获取当前用户信息 | ✅ JWT |
| PATCH | `/api/v1/auth/me` | 更新昵称/头像 | ✅ JWT |

**include 函数：**

```python
def include_user(app: FastAPI, config: Config) -> None:
    """注册 user 模块的所有路由和模型。"""
    # 1. 确保 DB 已初始化
    # 2. 创建 UserModel 表
    # 3. 注册路由
    app.include_router(user_router, prefix="/api/v1/auth")
```

### 4.2 social 模块

**Models:**

```python
# fastkeel/modules/social.py

class BuddyModel(Base):
    """好友关系（搭子）"""
    __tablename__ = "fastkeel_buddies"
    id: str = Column(String, primary_key=True)
    user_a_id: str = Column(String, ForeignKey("fastkeel_users.id"))
    user_b_id: str = Column(String, ForeignKey("fastkeel_users.id"))
    invite_code: str = Column(String, unique=True, index=True)
    status: str = Column(String, default="pending")   # pending / active / removed
    created_at: datetime

class GroupModel(Base):
    """群组"""
    __tablename__ = "fastkeel_groups"
    id: str = Column(String, primary_key=True)
    name: str = Column(String)
    owner_id: str = Column(String, ForeignKey("fastkeel_users.id"))
    invite_code: str = Column(String, unique=True)
    created_at: datetime

class GroupMemberModel(Base):
    """群组成员"""
    __tablename__ = "fastkeel_group_members"
    group_id: str = Column(String, ForeignKey("fastkeel_groups.id"), primary_key=True)
    user_id: str = Column(String, ForeignKey("fastkeel_users.id"), primary_key=True)
    role: str = Column(String, default="member")     # owner / admin / member
    joined_at: datetime
```

**API 路由：**

| 方法 | 路径 | 说明 |
|:----|:-----|:-----|
| POST | `/api/v1/social/invite` | 生成搭子邀请码 |
| POST | `/api/v1/social/bind` | 通过邀请码绑定搭子 |
| GET  | `/api/v1/social/buddy` | 获取当前搭子信息 |
| DELETE | `/api/v1/social/buddy` | 解除搭子关系 |
| POST | `/api/v1/social/groups` | 创建小组 |
| POST | `/api/v1/social/groups/join` | 通过邀请码加入小组 |
| GET  | `/api/v1/social/groups/{id}` | 获取小组信息+成员 |
| DELETE | `/api/v1/social/groups/{id}` | 解散小组（仅 owner）|

可选：如果 `config.social_enable_groups = False`，群组相关路由不注册。

### 4.3 jobs 模块

```python
# fastkeel/modules/jobs.py

def include_jobs(app: FastAPI, config: Config) -> None:
    """初始化 APScheduler 并注册定时任务。"""
    scheduler = AsyncIOScheduler()
    
    # 内置健康检查任务
    scheduler.add_job(
        heartbeat_check,
        "interval",
        minutes=5,
        id="_fastkeel_heartbeat"
    )
    
    # 项目自定义任务
    if config.jobs_config:
        for job_name, job_params in config.jobs_config.items():
            # job_params: {trigger: "cron", hour: 10, minute: 0}
            # 任务函数由项目在 logic/ 中实现，通过命名约定关联
            scheduler.add_job(
                resolve_job_func(job_name),  # 动态导入 project.logic.<job_name>
                **job_params,
                id=job_name
            )
    
    scheduler.start()
```

**任务函数约定：**

项目在 `project/logic/` 中定义任务函数，函数名对应 `jobs_config` 中的 key：

```python
# project/logic/weekly_report.py
async def weekly_report():
    """每周日生成周报。jobs_config 里 {weekly_report: ...} 对应此函数名"""
    ...
```

### 4.4 payment 模块

**设计原则：** 不绑定特定支付渠道。模块提供订阅模型和通用接口，**收据真实性验证由项目端实现**（因为华为 IAP、小米 IAP、Google Play 各有不同的验证 API）。这种设计让 payment 模块既可用于国内应用商店，也可用于出海场景。

**Model：**

```python
# fastkeel/modules/payment.py

class SubscriptionPlan(Base):
    """订阅套餐定义（通常在 config 中声明，启动时写入）"""
    __tablename__ = "fastkeel_subscription_plans"
    id: str = Column(String, primary_key=True)         # "monthly" / "yearly"
    name: str = Column(String)                          # "月度会员" / "年度会员"
    price: int = Column(Integer)                        # 分（¥10 = 1000）
    currency: str = Column(String, default="cny")
    duration_days: int = Column(Integer)                # 30 / 365
    is_active: bool = Column(Boolean, default=True)

class Subscription(Base):
    """用户订阅记录"""
    __tablename__ = "fastkeel_subscriptions"
    id: str = Column(String, primary_key=True)
    user_id: str = Column(String, ForeignKey("fastkeel_users.id"), index=True)
    plan_id: str = Column(String, ForeignKey("fastkeel_subscription_plans.id"))
    status: str = Column(String, default="active")     # active / expired / cancelled / refunded
    start_date: datetime = Column(DateTime)
    end_date: datetime = Column(DateTime)
    auto_renew: bool = Column(Boolean, default=True)
    provider: str = Column(String, default="")          # "huawei" / "xiaomi" / "google" / ""
    provider_order_id: str = Column(String, default="") # 商店侧订单号
    created_at: datetime = Column(DateTime, default=func.now())
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now())

class PaymentRecord(Base):
    """支付流水记录（审计用）"""
    __tablename__ = "fastkeel_payment_records"
    id: str = Column(String, primary_key=True)
    user_id: str = Column(String, ForeignKey("fastkeel_users.id"), index=True)
    subscription_id: str = Column(String, ForeignKey("fastkeel_subscriptions.id"))
    amount: int = Column(Integer)                       # 分
    currency: str = Column(String, default="cny")
    provider: str = Column(String)                      # "huawei" / "xiaomi" / "google"
    provider_order_id: str = Column(String)
    status: str = Column(String, default="pending")    # pending / completed / failed / refunded
    created_at: datetime = Column(DateTime, default=func.now())
```

**验证流程（非对称设计）：**

```
┌──────────────┐    收据(JSON)    ┌──────────────┐
│  Android App  │ ──────────────→ │   fastkeel    │
│  (华为 IAP)   │                 │  POST /verify │
└──────────────┘                  └──────┬───────┘
                                         │
                              ┌──────────┴──────────┐
                              │  project/logic/      │
                              │  verify_receipt()    │
                              │  ← 项目端实现         │
                              │                     │
                              │  例：华为 IAP →       │
                              │  huawei.devcloud     │
                              │  .com/.../verify     │
                              └──────────┬──────────┘
                                         │ 验证结果
                              ┌──────────┴──────────┐
                              │  fastkeel 处理        │
                              │  ✓ 创建/更新订阅记录   │
                              │  ✓ 创建支付流水       │
                              │  ✓ 返回结果给 App     │
                              └─────────────────────┘
```

**关键设计：** `verify_receipt` 不是 fastkeel 内置的，而是**项目端注册的回调函数**：

```python
# fastkeel/modules/payment.py

# 项目端注册的验证回调
receipt_verifiers: dict[str, Callable] = {}

def register_verifier(provider: str, func: Callable):
    """项目端在 main.py 中注册收据验证函数。"""
    receipt_verifiers[provider] = func

def include_payment(app: FastAPI, config: Config) -> None:
    """注册 payment 模块的所有路由和模型。"""
    # 1. 创建表
    # 2. 注册路由
    app.include_router(payment_router, prefix="/api/v1/payment")
```

```python
# 戒了么手机-backend/project/logic/huawei_verify.py
from fastkeel.modules.payment import register_verifier

async def verify_huawei_receipt(receipt: dict) -> dict:
    """向华为 IAP 验证收据真实性。返回 {user_id, plan_id, valid, ...}"""
    # 调用华为 IAP API
    ...

register_verifier("huawei", verify_huawei_receipt)
```

**API 路由：**

| 方法 | 路径 | 说明 | 认证 |
|:----|:-----|:-----|:-----|
| POST | `/api/v1/payment/verify` | 验证收据 + 创建/更新订阅 | ✅ JWT |
| GET  | `/api/v1/payment/subscription` | 查询当前用户订阅状态 | ✅ JWT |
| POST | `/api/v1/payment/webhook` | 商店侧推送通知（续费/退款/取消）| 无（签名验证）|
| GET  | `/api/v1/payment/plans` | 获取可用套餐列表 | ✅ JWT |

**POST /verify 请求/响应：**

```json
// 请求
{
  "provider": "huawei",
  "receipt": { "orderId": "...", "purchaseToken": "...", "productId": "monthly" },
  "plan_id": "monthly"
}

// 响应
{
  "valid": true,
  "subscription": {
    "status": "active",
    "start_date": "2026-06-11T00:00:00Z",
    "end_date": "2026-07-11T00:00:00Z"
  }
}
```

**webhook 处理：**

```python
@router.post("/webhook")
async def payment_webhook(request: Request):
    """处理商店侧推送的通知（续费/退款/取消）。"""
    body = await request.body()
    provider = request.headers.get("X-Provider", "unknown")
    
    # 查找对应的 verifier 做签名验证
    verifier = receipt_verifiers.get(provider)
    if not verifier:
        raise HTTPException(400, "unknown provider")
    
    event = await verifier.parse_webhook(body, request.headers)
    
    if event["type"] == "renewal":
        # 续费成功 → 延长订阅
        extend_subscription(event["subscription_id"], event["new_end_date"])
    elif event["type"] == "cancellation":
        # 用户取消自动续费 → 标记不续费，但不立即过期
        cancel_auto_renew(event["subscription_id"])
    elif event["type"] == "refund":
        # 退款 → 立即终止订阅
        expire_subscription(event["subscription_id"])
    
    return {"ok": True}
```

**config 新增字段：**

```python
# fastkeel/core/config.py — 新增
@dataclass
class Config:
    ...
    # 支付模块
    payment_plans: list[dict] | None = None  # [{id, name, price, duration_days}]
    payment_webhook_secret: str | None = None
```

**config.toml.j2 新增：**

```toml
{% if with_payment %}
[payment]
plans = [
  { id = "monthly", name = "月度会员", price = 1000, duration_days = 30 },
  { id = "yearly",  name = "年度会员", price = 9800, duration_days = 365 },
]
# webhook_secret = "signing-secret-from-store"
{% endif %}
```

---

## 5. contrib 层

### 5.1 LLM 客户端

```python
# fastkeel/contrib/llm.py

class LLMClient:
    """LLM API 客户端，支持重试、限流、结构化输出。"""

    def __init__(self, config: Config):
        self.client = httpx.AsyncClient(
            base_url=config.llm_api_base,
            headers={"Authorization": f"Bearer {config.llm_api_key}"},
            timeout=60,
        )
        self.semaphore = asyncio.Semaphore(config.llm_rate_limit)
        self.max_retries = config.llm_max_retries

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """普通对话。自动重试（429/5xx），限流。"""
        ...

    async def chat_stream(self, messages: list[dict], **kwargs):
        """流式对话。返回 async generator，逐 chunk 产出。"""
        ...

    async def chat_structured(
        self, messages: list[dict], response_model: type[BaseModel], **kwargs
    ) -> BaseModel:
        """结构化输出。传入 Pydantic model，返回解析后的实例。"""
        ...
```

### 5.2 流式响应工具

```python
# fastkeel/contrib/streaming.py

class SSEStreamer:
    """SSE (Server-Sent Events) 流式响应工具。"""
    
    @staticmethod
    async def from_generator(
        gen: AsyncGenerator[str, None],
    ) -> StreamingResponse:
        """将 async generator 包装为 SSE StreamingResponse。"""
        ...

    @staticmethod
    async def from_llm_stream(
        llm_client: LLMClient,
        messages: list[dict],
    ) -> StreamingResponse:
        """将 LLM 流式输出直接转为 SSE 响应。"""
        ...
```

---

## 6. CLI 设计

### 6.1 `fastkeel new`

```python
# fastkeel/cli/new.py

import typer

app = typer.Typer()

@app.command()
def new(
    name: str = typer.Argument(help="项目名称"),
    with_user: bool = True,
    with_social: bool = False,
    with_payment: bool = False,
    with_jobs: bool = False,
    path: str = ".",
):
    """生成新项目骨架。"""
    target_dir = Path(path) / name
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 渲染模板
    env = Environment(loader=PackageLoader("fastkeel", "templates/default"))
    for template_path in get_template_files():
        dest = target_dir / template_path.relative_to("templates/default")
        dest.parent.mkdir(parents=True, exist_ok=True)
        template = env.get_template(str(template_path))
        dest.write_text(template.render(
            project_name=name,
            with_user=with_user,
            with_social=with_social,
            with_payment=with_payment,
            with_jobs=with_jobs,
        ))
    
    typer.echo(f"✅ {name} 已创建在 {target_dir}")
    typer.echo(f"   cd {name}")
    typer.echo(f"   pip install -e .")
```

### 6.2 项目模板关键内容

**main.py.j2:**

```python
from fastkeel import create_app, Config
{% if with_user %}from fastkeel.modules import include_user{% endif %}
{% if with_social %}from fastkeel.modules import include_social{% endif %}
{% if with_payment %}from fastkeel.modules import include_payment{% endif %}
{% if with_jobs %}from fastkeel.modules import include_jobs{% endif %}

from project.routes import router as biz_router

config = Config.from_toml("config.toml")
app = create_app(config)

{% if with_user %}include_user(app, config){% endif %}
{% if with_social %}include_social(app, config){% endif %}
{% if with_payment %}include_payment(app, config){% endif %}
{% if with_jobs %}include_jobs(app, config){% endif %}
app.include_router(biz_router, prefix="/api/v1")
```

**config.toml.j2:**

```toml
app_name = "{{ project_name }}"
host = "0.0.0.0"
port = 8000
db_url = "sqlite:///data/app.db"

# 必填：生成一个随机密钥
# jwt_secret = "your-secret-here"

[user]
# extra_fields = { field_name = "integer" }

{% if with_social %}
[social]
enable_groups = true
{% endif %}

{% if with_jobs %}
[jobs]
# weekly_report = { trigger = "cron", hour = 10, minute = 0, day_of_week = "sun" }
{% endif %}

```

---

## 7. 数据库迁移策略

FastAPI + SQLite 场景下不需要完整的迁移框架。策略分三层：

| 变更类型 | 处理方式 |
|:---------|:---------|
| 模型定义变化（新增列/修改类型） | SQLite 支持 ALTER TABLE ADD COLUMN。`init_db()` 时检查缺失列并补齐 |
| 模块表创建（user/social/jobs） | 首次 `include_*()` 时自动 `Base.metadata.create_all()` |
| 破坏性变更（重命名/删除列） | 项目升级时手动迁移脚本（出现概率极低，scaffold 的 schema 上线后几乎不碰）|

第一次启动时：

```python
@app.on_event("startup")
async def startup():
    init_db(config)           # 创建引擎
    Base.metadata.create_all()  # 创建所有已注册模型对应的表
```

---

## 8. 项目对 fastkeel 的依赖方式

每个新生成的项目在 `pyproject.toml` 中声明：

```toml
[project]
name = "戒了么手机-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastkeel>=0.1.0",
    # 项目自己的依赖
    "httpx",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-httpx",
    "ruff",
]
```

项目开发者只需在 `project/` 下写业务代码，从不 import fastkeel 内部模块路径（如 `fastkeel/core/db.py`），只通过公开 API 导入：

```python
# ✅ 正确的导入方式
from fastkeel import create_app, Config
from fastkeel.modules import include_user
from fastkeel.core.auth import get_current_user

# ❌ 不正确的导入方式（依赖内部文件路径）
from fastkeel.core.db import engine  # 不应直接操作引擎
```

---

## 9. 测试策略

### 9.1 fastkeel 自身的测试

```python
# tests/conftest.py
@pytest.fixture
def test_config():
    return Config(
        db_url="sqlite:///:memory:",
        jwt_secret="test-secret",
    )

@pytest.fixture
def test_app(test_config):
    app = create_app(test_config)
    include_user(app, test_config)
    return app

@pytest.fixture
def client(test_app):
    with TestClient(test_app) as c:
        yield c
```

### 9.2 项目端测试

`fastkeel new` 生成的项目自带 `conftest.py`，自动配置内存 SQLite 和测试夹具：

```python
# tests/conftest.py
from fastkeel import create_app, Config
from fastkeel.core.db import Base
from fastkeel.core.auth import create_token
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def config():
    return Config(db_url="sqlite:///:memory:", jwt_secret="test")

@pytest.fixture
def app(config):
    app = create_app(config)
    # 注册模块...
    return app

@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_headers(config):
    token = create_token("test-user-id", config)
    return {"Authorization": f"Bearer {token}"}
```

---

## 10. 与戒了么手机的关系（TAD 层面的映射）

```
| 技术方案.md 中描述的后端职责       →    fastkeel 提供的对应
─────────────────────────────       ───────────────────────
用户注册/登录（匿名 JWT）           →    modules.user
搭子关系 CRUD                      →    modules.social（BuddyModel）
小组管理                          →    modules.social（GroupModel）
定时任务（晚间反思、睡眠锁机）        →    modules.jobs
DeepSeek 周报生成                  →    contrib.llm
订阅管理（¥10/月）                  →    modules.payment
搭子退出冷却期逻辑                  →    项目自己在 project/logic/ 写
通知话术生成                       →    项目自己在 project/prompts/ 写
戒断指数计算                       →    项目自己在 project/logic/ 写
收据验证（华为 IAP / 小米 IAP）      →    项目自己在 project/logic/ 注册 verifier
```

戒了么手机项目的 backend 目录结构：

```
戒了么手机-backend/
├── pyproject.toml     # → depends on fastkeel
├── config.toml        # → user + social + jobs + llm
├── main.py            # → create_app + include_[...] + biz routes
│
├── project/
│   ├── models/
│   │   └── detox.py            # DetoxScore, BlockLog, FocusSession
│   ├── routes/
│   │   ├── __init__.py         # biz_router aggregator
│   │   ├── buddy.py            # 搭子业务（在社交基础上加通知逻辑）
│   │   ├── sync.py             # 戒断指数同步
│   │   └── ai.py              # AI 周报/策略推荐
│   ├── logic/
│   │   ├── detox_score.py      # 指数算法：封锁×10+专注/10
│   │   ├── notification.py     # 搭子通知话术生成
│   │   ├── weekly_report.py    # 周报生成（jobs 调用的入口）
│   │   └── unlock_rules.py     # 紧急解锁规则
│   └── prompts/
│       ├── weekly_insight.txt
│       └── strategy.txt
│
└── tests/
    ├── conftest.py
    ├── test_detox.py
    ├── test_buddy.py
    └── test_ai.py
```

---

## 11. 发布流程

### GitHub Actions

**test.yml** — 每次 push/PR：

```yaml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python-version }}" }
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest
```

**publish.yml** — 打 tag 自动发 PyPI：

```yaml
name: Publish to PyPI
on:
  release:
    types: [published]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

### 版本策略

```
0.1.0 — core + user 模块（MVP）
0.2.0 — + social 模块
0.3.0 — + payment 模块
0.4.0 — + jobs 模块 + contrib.llm
0.5.0 — + CLI + 模板
1.0.0 — 用戒了么手机验证后正式发布
```

---

## 12. 已决策事项（原 TBD）

以下 7 项已在 2026-06-11 经讨论确认，决策原因见下：

| # | 问题 | 决策 | 原因 |
|:-:|:-----|:----|:-----|
| 1 | **SQLAlchemy 模型扩展字段** | `ALTER TABLE ADD COLUMN` | SQLite 原生支持，零 JOIN，类型安全。扩展字段在项目初始化时一次性定义，上线后几乎不修改，不会产生 schema drift 问题 |
| 2 | **jobs 任务函数路由** | 命名约定自动 resolve | 约定优于配置：`project/logic/` 目录结构本身就是注册表。重构友好——重命名函数时文件同步改名，不用改两处 |
| 3 | **模板语言** | Jinja2 | FastAPI PackageLoader 立即可用，`fastkeel new` 场景只做简单变量替换，不需要 Mako 的高级能力。选保守技术降低维护成本 |
| 4 | **CLI 框架** | Typer | 底层就是 Click（生态不损失），类型提示驱动减少 60% 样板代码。FastAPI 作者同款 |
| 5 | **异步任务持久化** | 默认启用 SQLiteJobStore | 零外部服务假设下，SQLiteJobStore 不需要额外基础设施。戒了么手机的定时任务（晚间反思、周报）若因进程重启丢失，用户体验极差 |
| 6 | **日志库** | structlog | 兼容 stdlib logging，fastkeel 模块和项目代码共享同一套配置。输出结构化 JSON 方便生产采集（CloudWatch/ELK）。零额外纯 Python 依赖 |
| 7 | **内置 dev 收据验证** | 包含 `dev` provider | 收据验证走网络，开发时阻塞联调。`dev` provider 只读 `receipt.plan_id`，不走网络。`debug=False` 时自动禁用，不会漏到生产。代码量约 15 行 |
