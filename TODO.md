# TODO

## 发布

- [ ] **发布到 PyPI** — `python -m build && twine upload dist/*`（需要 PyPI token 和 GitHub Release）
  - 检查 pyproject.toml 版本号（当前 0.1.0，0.5.0 语义更准确？）

## 功能缺口

- [ ] **`user_extra_fields` 动态列** — Config 已有 `user_extra_fields: dict[str, type]`，但 `init_db()` 里的 `ALTER TABLE ADD COLUMN` 逻辑还没实现。参考 TAD.md §4.1
- [ ] **`payment_webhook_secret` 验证** — Config 已有字段，但 webhook handler 没做签名校验
- [ ] **structlog 初始化** — middleware 已经 `import structlog` 并 `logger.error()`，但 `create_app()` 里没配置 structlog 的输出格式（可读/JSON）
- [ ] **jobs 优雅关闭** — include_jobs 启动 scheduler 但 app shutdown 时没调用 `scheduler.shutdown()`

## 质量改进

- [ ] **Swagger `/docs` 验证** — FastAPI 自动生成。确认所有 endpoint 的 request/response schema 正确展示
- [ ] **端到端测试生成的项目** — `fastkeel new` → `pip install` → `uvicorn main.py` → curl。之前只测了直接创建 app，没测生成的 main.py 本身
- [ ] **`resolve_job_func` 实际验证** — `project.logic.{job_name}` 的约定只在 real project 中才能真正测试。考虑用 pytest 模拟 project 包结构
- [ ] **Python 3.14 兼容** — `datetime.utcnow()` 等 deprecation warnings，测试在 Python 3.11-3.13 均可通过

## Future

- [ ] **戒了么手机后端** — 用 fastkeel 生成真实项目，写项目逻辑（detox score、AI weekly report、buddy notification）
- [ ] **contrib/llm 更多 provider** — 目前默认 DeepSeek。openai、anthropic、ollama 等可通过 `llm_api_base` 切换，但 chat_structured 的 JSON mode 依赖特定 API
- [ ] **测试 CI** — 提交后 GitHub Actions test.yml 是否通过（已验证 config 正确但没跑过）
