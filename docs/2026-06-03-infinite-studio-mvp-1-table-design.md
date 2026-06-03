# Infinite Studio（万能 AI 工坊）MVP-1 表设计文档

- 日期：2026-06-03（聚焦第一期 MVP 的数据库表设计定稿）
- 状态：表设计定稿。**本文档正文只覆盖第一期 MVP 的 12 张表及其主键/约束纪律**；计费、负载均衡、应用中心、OAuth/RBAC、规模化等**所有未来演进**集中在末章 §8「未来演进（分块导论）」，仅留方向与要点 hint。

---

## 1. 背景、目标与技术栈

### 1.1 产品与目标

构建一个 **Web 形态的「AI 工坊」产品**：把多种 AI 能力（对话、生图/改图、翻译等）收进统一平台，远期发展为类 Manus 的自主 agent。

**目标定位（按优先级）：**
1. **最终是一款产品**：可分发给亲友体验，做得好可商业化（计费模型「API 用量 → 平台统一积分」，**计费本期不做**，见 §8.1）。
2. **过程中学习现代 agent 工程**，对标大厂 AI 岗。
3. 自然也是作者的日常工具。

**核心架构主线（北极星）：** 统一能力层——每个 AI 能力实现同一套接口，被三种入口共用（① 工具应用 ② 对话 ③ agent）。**一次实现，多处复用。** 本期落地「对话」入口，且对话本身就是一个**单 agent + 工具循环（react_loop）**。

**关键定位：本产品不是 API 网关。** 路由/负载均衡不是产品职责——需要时用现成网关（自建 LiteLLM/one-api）当基础设施顶上，业务库保持简单。

### 1.2 第一期 MVP 范围

| 做 | 不做（见 §8） |
|---|---|
| 用户体系（注册/登录/角色/邀请码）、服务端会话鉴权 | 计费扣费（**不限量**，仅精确记用量） |
| 对话（SSE 流式），react_loop 单 agent + **一个工具（tavily 搜索）** | 多 agent 编排、handoff、负载均衡 |
| agent 定义、tool 注册、provider/model 配置（admin 可配，改提示词不重部署） | 文件/生图、长任务队列、对象存储 |
| 精确记录模型 + 工具用量（`usage_event`，不扣费） | 应用中心发布、OAuth、RBAC |

### 1.3 技术栈

| 层 | 选型 | 理由摘要 |
|---|---|---|
| 前端 | **Vue3 + TypeScript** | 作者强项 |
| 后端 | **Python + FastAPI** | 对标大厂 AI 岗；agent/ML 生态在 Python |
| 数据库 | **PostgreSQL** | 单一事实源；事务可靠；大厂主流 |
| ORM / 迁移 | **SQLAlchemy 2.0 + Alembic** | Python 事实标准 ORM + 官方迁移 |
| 模型接入 | **自建统一 provider 抽象层**（不依赖第三方库） | 密钥自管、不交予会联网的第三方代码（规避供应链投毒窃钥，如 LiteLLM 事件） |

**模型接入分两层**（呼应「逻辑在代码、配置在数据」）：
- **DB 注册表**（`provider` / `model`）= 配置：用哪些供应商/模型、密钥（加密）。
- **代码适配层**（`ProviderAdapter` + 各 family 实现，**内部用各家官方 SDK**）= 逻辑：怎么调、怎么归一化用量。`model.model_family` 字段把「数据」选到「代码适配器」。
- 密钥只在「你的后端 ↔ 该密钥本属的官方供应商」之间流动，**不经任何第三方聚合层**；借 LiteLLM 的 model_list / Dify 的加密存储**设计思路**，但调用自己用官方 SDK 写。

> MinIO、Celery+Redis、pgvector 等本期不引入（§8.7）。

---

## 2. 数据层与表设计纪律

### 2.1 数据层纪律

> **Postgres 是唯一事实源；每加专用存储须有「访问模式 + 规模」理由；派生数据要有同步路径；图片/文件只存元数据+URL，绝不存 base64。** 向量、海量分析、全文检索、队列等按规模触发点逐个加（§8.7）。

### 2.2 跨表约定

- **时间**：所有时间列 `timestamptz`，全程按 **UTC**（仅前端展示转本地）。
- **枚举**：用 `varchar + CHECK`（不用原生 enum；SQLAlchemy `Enum(native_enum=False)`）。

### 2.3 主键纪律（对齐业界主流）

- **每张实体表**一律 `id bigint GENERATED ALWAYS AS IDENTITY` 做 PK——**注册表也不例外**（不拿自然键当 PK）。用 `IDENTITY` 而非旧 `serial`；用 `bigint` 而非 `int`（int4 21 亿溢出是经典事故）。
- **自然键**（`username` / `model_name` / `agent_code` / `tool_identifier` …）按**真实语义命名** + `UNIQUE NOT NULL`，不强行统一成 `key`（避开 SQL 关键字）。别的表按它引用时，FK 可直接指这列（Postgres 允许 FK 指任意**完整** `UNIQUE` 列）；标识可能改名的配 `ON UPDATE CASCADE`。⚠️ 部分唯一索引（`UNIQUE(...) WHERE ...`）**不能**当 FK 目标。
- **对外暴露的资源**（会进 URL/API，如 `conversation` / `run`）加 `public_id uuid UNIQUE`，用 **UUIDv7**（时间有序，Postgres 18 原生 `uuidv7()`；<18 用扩展或应用层生成）。**对外只暴露 `public_id`，顺序 `id` 绝不进 URL**（防枚举/IDOR/泄露体量）。纯内部表（provider / model / usage_event 等）不需要。
- **关联表例外**：纯多对多中间表（如未来 RBAC 的 `role_permission`，§8.6）用复合主键，不另设 `id`。本期无此类表。
- **分库（一句保险，现在不做、不为它设计）**：真到分库那天，只把 id 生成从 IDENTITY 换成分布式发号（Snowflake / Instagram 式），`bigint` 类型与表结构不变。

---

## 3. 数据模型（12 张表）

采用 **`conversation → run → item` 三级模型**（对齐 OpenAI Agents SDK 的 Session→Run→Item）。为未来预留的字段先做成可空普通列，后续 Alembic 补外键。

| 节 | 域 | 表 | 用途 |
|---|---|---|---|
| 3.1 | 用户 | `users` | 账户（用户名/角色/状态/邀请码来源） |
| 3.2 | 用户 | `auth_identity` | 登录方式（密码 / 未来 OAuth） |
| 3.3 | 用户 | `auth_session` | 服务端会话（按设备一行） |
| 3.4 | 用户 | `system_code` | 管理员维护的注册/促销码 |
| 3.5 | 能力 | `agent` | agent 定义（声明式配置；逻辑在代码） |
| 3.6 | 能力 | `tool` | 工具注册表（code-first 目录） |
| 3.7 | 模型 | `provider` | 供应商连接（端点 + 加密密钥） |
| 3.8 | 模型 | `model` | 逻辑模型（挂到一个供应商） |
| 3.9 | 对话 | `conversation` | 会话 |
| 3.10 | 对话 | `run` | 一次执行 |
| 3.11 | 对话 | `item` | run 内有序事件（只追加） |
| 3.12 | 用量 | `usage_event` | 模型 + 工具用量快照（**记录、不扣费**） |

### 3.1 `users` —— 用户账户

（避开 Postgres 保留字 `user`）
```
id                    bigint        PK
username              varchar       NOT NULL, UNIQUE              登录名
display_name          varchar       NULL                         展示名（空则取 username）
email                 varchar       NULL, UNIQUE(partial)        可选；不验证不外发；有值时唯一
role                  varchar       NOT NULL, default 'user'     CHECK IN ('user','admin')；admin 蕴含 user
status                varchar       NOT NULL, default 'active'   CHECK IN ('active','disabled')
invited_by_code_id    bigint        NULL, FK→system_code(id)     注册用的系统码 → 溯到建码管理员
referral_code         varchar       NULL, UNIQUE(partial)        【预留】个人推荐码，不开发
referred_by_user_id   bigint        NULL, FK→users(id)           【预留】被谁的个人码邀请
created_at            timestamptz   NOT NULL, default now()
updated_at            timestamptz   NOT NULL, default now()
```
索引：`UNIQUE(username)`；`UNIQUE(email) WHERE email IS NOT NULL`；`UNIQUE(referral_code) WHERE referral_code IS NOT NULL`；`INDEX(invited_by_code_id)`、`INDEX(referred_by_user_id)`。
- 密码不在此表（在 `auth_identity`）。角色判断**收口在统一函数**（`require_permission(...)`），不散写 `if role=='admin'`，将来无损迁 RBAC（§8.6）。

### 3.2 `auth_identity` —— 登录方式

```
id                  bigint        PK
user_id             bigint        NOT NULL, FK→users(id)
provider            varchar       NOT NULL                     'password' | 'google' | 'github' | ...
provider_user_id    varchar       NULL                         第三方稳定 id；provider='password' 时 NULL
secret_hash         varchar       NULL                         本地密码哈希；OAuth 行为 NULL
email_at_provider   varchar       NULL                         provider 返回邮箱（OAuth 常已验证；用于按邮箱合并/展示已连接）
created_at          timestamptz   NOT NULL, default now()
updated_at          timestamptz   NOT NULL, default now()
```
约束/索引：`UNIQUE(provider, provider_user_id) WHERE provider_user_id IS NOT NULL`；`UNIQUE(user_id, provider)`；`INDEX(user_id)`。本期仅 `provider='password'` 行。

### 3.3 `auth_session` —— 服务端会话

**登录鉴权选型：服务端会话（opaque token + cookie），非 JWT。** 单体 Web、无跨 App SSO、要可即时吊销/踢人；比「JWT + refresh 轮换」更简单，且是通向「中心化会话 + Redis」的直接上坡路。会话存储抽象成 `SessionStore` 接口 → 本期 Postgres，未来换 Redis 无感。

（按设备一行）
```
id             bigint           PK
user_id        bigint           NOT NULL, FK→users(id)
token_hash     varchar          NOT NULL, UNIQUE             cookie 随机串的 SHA-256（绝不存原串）
expires_at     timestamptz      NOT NULL                     滑动续期 + 绝对上限
created_at     timestamptz      NOT NULL, default now()
last_used_at   timestamptz      NULL                         设备列表展示（限流写）
revoked_at     timestamptz      NULL                         吊销标记（或直接删行）
user_agent     varchar          NULL
ip             inet/varchar     NULL
```
索引：`UNIQUE(token_hash)`；`INDEX(user_id)`；`INDEX(expires_at)`（清理）。

**会话鉴权实现规范：**
1. **生成**：`secrets.token_urlsafe(32)`（CSPRNG，~256bit）。
2. **存储**：只存 `sha256(token)`（高熵随机串用 SHA-256 足够，不用 bcrypt）。
3. **Cookie**：`HttpOnly`（挡 XSS）+ `Secure`（仅 HTTPS）+ `SameSite=Lax`（挡多数 CSRF）；写操作再叠 CSRF token。
4. **校验**：取 cookie → sha256 → 查 `auth_session`（未过期/未吊销）→ 查 `users.status='active'` → 注入 `current_user`，否则 401。
5. **续期**：滑动延长 `expires_at` + 绝对上限；`last_used_at` 限流写。
6. **登出/踢人**：删行或置 `revoked_at`，即时生效；全端登出 = 删该 user 全部行。
7. **清理**：定时删过期/已吊销行，规模 ≈ 活跃会话。

### 3.4 `system_code` —— 系统签发的码

（管理员维护：邀请码 now / 促销码 later）
```
id                  bigint        PK
code                varchar       NOT NULL, UNIQUE
type                varchar       NOT NULL                    CHECK IN ('invite','promo')
created_by_user_id  bigint        NOT NULL, FK→users(id)      哪个管理员建（admin 由迁移种子创建，故总有真实建者）
max_uses            int           NULL                        NULL = 不限次
used_count          int           NOT NULL, default 0         注册成功 +1（与建用户同事务，校验未超 max_uses）
expires_at          timestamptz   NULL
enabled             boolean       NOT NULL, default true
metadata            jsonb         NOT NULL, default '{}'      因 type 而异参数
created_at          timestamptz   NOT NULL, default now()
```
索引：`UNIQUE(code)`；`INDEX(type)`；`INDEX(created_by_user_id)`。
- 个人推荐码与系统码按信任边界分开：admin 建的码进本表；用户个人推荐码走 `users.referral_code`（预留）。
- 循环引用（`users.invited_by_code_id ↔ system_code.created_by_user_id`）：建表后 Alembic 分两步补外键；数据顺序先种子 admin。

**创世引导（初始 admin）**：在 **Alembic 数据迁移**中创建第一个 admin——读 `BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD`，**仅当系统尚无 admin 时**创建（写 `users` role='admin' + `auth_identity` password 行）。纪律：**凭据走环境变量、不硬编码**；**幂等**。新注册者一律默认 `role='user'`。

### 3.5 `agent` —— agent 定义

**核心范式（业界印证：OpenAI/Claude Agent SDK、Dify）：逻辑在代码、定义是声明式数据。** 编排逻辑（react_loop 等）写死在代码的「运行时模式」里；agent = 选一个模式 + 一套声明式配置。管理员改提示词 = 改 DB 配置，**不重新部署**。这不是低代码平台——admin 只能编辑已写好逻辑的 agent 的定义字段，不能凭空造逻辑。

（= DB 版的 AgentDefinition；代理键 `id` 做 PK，`agent_code` 唯一）
```
id              bigint   PK
agent_code      varchar  NOT NULL, UNIQUE    稳定引用键（代码 resolve_agent('chat')、run.agent_key 按它引用；不可变）
name            varchar  NOT NULL            展示名
description     varchar  NULL                 （未来 handoff 路由"何时该用我"）
runtime_pattern varchar  NOT NULL  CHECK IN ('react')   代码已注册逻辑；MVP 仅单 agent+工具循环（纯对话=空工具）
model           varchar  NULL                 引用 model.model_name；**无代码默认**，解析时为空/失效则报错（fail-fast）
instructions    text     NULL                 系统提示词；**NULL = 继承代码默认**（overlay）
model_params    jsonb    NOT NULL default '{}'  不规则采样参数(temperature/top_p/...)
allowed_tool_keys text[] NOT NULL default '{}' 可调工具（引用 tool.tool_identifier，如 ['tavily_search']）
max_turns       int      NOT NULL default 1     工具循环步数上限（纯对话=1）
enabled         boolean  NOT NULL default true
created_at      timestamptz NOT NULL default now()
updated_at      timestamptz NOT NULL default now()
```
**字段级分层（关键）**——靠可空性编码：
- `instructions` 可空 → **NULL 继承代码默认提示词**（prompt 可缺省）。
- `model` 无代码默认 → 未配/失效 **解析时报错**，绝不回退内置（密钥/模型这种关键项不许内置）。

### 3.6 `tool` —— 工具注册表

（code-first 目录；代理键 `id` 做 PK，`tool_identifier` 唯一）
```
id            bigint   PK
tool_identifier     varchar  NOT NULL, UNIQUE    代码写死的不可变标识；agent.allowed_tool_keys / item.tool_key / LLM 都按它引用
name          varchar  NOT NULL            展示名
description   text     NULL                给 LLM 看的"何时用我"
input_schema  jsonb    NOT NULL            参数 JSON Schema
output_schema jsonb    NULL
enabled       boolean  NOT NULL default true    【admin 层】启用开关
metadata      jsonb    NOT NULL default '{}'    【admin 层】可配项「模板+值」：代码声明有哪些 key（带占位，如 {"model":null}），后台展示全部 key 供 admin 填（绑定模型/未来定价/限流…）；占位值调用时无效→fail-fast
created_at    timestamptz NOT NULL default now()
updated_at    timestamptz NOT NULL default now()
```
> 模型绑定走 `metadata.model`（软引用 `model.model_name`，resolve 时查不到/禁用则 fail-fast，同 `agent.model`）；工具调模型 → model → provider 拿密钥，复用模型层。`modality` 等 image 专属字段属未来（§8.7），现在不加。

**写入/留存生命周期（`agent` / `tool` 两表机制不同，黄金法则：启动绝不覆盖「人配的那一层」）：**
- **`tool`（代码拥有定义、admin 只调策略）**：启动按 `tool_identifier` upsert。**代码字段**（name/description/schema）随代码刷新（保 LLM 看到的工具说明不过时）；**`enabled`** 永不动；**`metadata`** 按 key 合并——代码模板里 DB 缺的 key 补进来（带占位值），DB 已有的 key **一律不覆盖** → 新可配项自动出现在后台、admin 填过的值不丢。代码删工具 → 标 deprecated/禁用不硬删；代码加工具 → 下次启动出现。
- **`agent`（代码兜底 + DB 覆盖）**：启动**不写** agent 表。`resolve_agent(agent_code)` = **DB 行 ?? 代码默认(提示词/逻辑) ?? 全局 fallback**。`model` 必须由配置提供（无代码默认 → 缺则报错）。**启动从不覆盖 admin 的行 → 配过的提示词跨部署存活**。

### 3.7 `provider` —— 供应商连接

（admin 配，不 seed，密钥加密；代理键 `id` 做 PK，`name` 唯一）
```
id             bigint     PK              代理键
name           varchar    NOT NULL, UNIQUE 连接名（admin 起，如 'openai-main'）；仅 admin UI 展示+下拉去重，代码经 id 关联、不按它字面量引用
base_url       varchar    NULL            自定义端点/代理（可选；也可指向自建网关）
api_key_cipher bytea/text NOT NULL        加密后的密钥（主密钥在 env；明文绝不进代码/DB/前端响应）
enabled        boolean    NOT NULL default true
created_at     timestamptz NOT NULL default now()
updated_at     timestamptz NOT NULL default now()
```
- 密钥安全：env 主密钥加密存（Dify 用 PKCS1_OAEP，起步对称如 Fernet/AES-GCM 即可），**调用时才服务端解密**，任何接口/前端**不返回明文**（Dify 曾因明文回传出 CVE）。
- **不 code-seed**（密钥不可能在代码）；表空 → 无可用供应商。

### 3.8 `model` —— 逻辑模型

（挂到一个供应商；代理键 `id` 做 PK，`model_name` 唯一；agent 引用 `model_name`）
```
id            bigint   PK              代理键
model_name    varchar  NOT NULL, UNIQUE agent.model 引用 + 直接发给 API 的真实模型串 + UI 名（如 'gpt-4o' / 'claude-opus-4-20260101'，必须是供应商认的串）
provider_id   bigint   NOT NULL, FK→provider(id)   服务它的供应商连接（指代理键 id；provider 改名不波及）
model_family  varchar  NOT NULL        CHECK IN ('openai','anthropic','google')
enabled       boolean  NOT NULL default true
created_at    timestamptz NOT NULL default now()
updated_at    timestamptz NOT NULL default now()
-- 售价(积分单价/加价) → 未来 §8.1
```
> 多供应商/负载均衡：MVP 一个模型挂一个供应商；将来要 LB → 加 `model_deployment` 绑定表 或 前置网关（§8.5）。

### 3.9 `conversation` —— 会话

```
id          bigint       PK
public_id   uuid         NOT NULL, UNIQUE, default uuidv7()   对外暴露用（URL/API）；顺序 id 不出库
user_id     bigint       NOT NULL, FK→users(id)
title       varchar      NULL
created_at  timestamptz  NOT NULL default now()
updated_at  timestamptz  NOT NULL default now()
```
索引：`UNIQUE(public_id)`；`INDEX(user_id, updated_at)`。

### 3.10 `run` —— 一次执行

```
id              bigint       PK
public_id       uuid         NOT NULL, UNIQUE, default uuidv7()   对外暴露用（URL/API）；顺序 id 不出库
user_id         bigint       NOT NULL, FK→users(id)
conversation_id bigint       NULL, FK→conversation(id)   属于哪个会话
agent_key       varchar      NOT NULL, default 'chat'    这次哪个 agent 在跑（agent.agent_code 的快照，不设 FK：历史记录不随改名/删除而变）
status          varchar      NOT NULL, default 'running' CHECK IN ('running','completed','failed')
input           jsonb        NULL                        本次输入快照
created_at      timestamptz  NOT NULL default now()
finished_at     timestamptz  NULL
【预留】type, source, app_key, parent_run_id, thread_id（未来多 agent/应用中心）
```
索引：`UNIQUE(public_id)`；`INDEX(conversation_id, created_at)`；`INDEX(user_id, created_at)`。

### 3.11 `item` —— run 内有序事件

（只追加，多态）
```
id          bigint       PK
run_id      bigint       NOT NULL, FK→run(id)
seq         int          NOT NULL                run 内顺序
type        varchar      NOT NULL                CHECK IN ('message','tool_call','tool_output','reasoning','final')
role        varchar      NULL                    'user'|'assistant'|'system'|'tool'
content     jsonb        NOT NULL                多态内容
tool_key    varchar      NULL                    type='tool_call'/'tool_output' 时：哪个工具（引用 tool.tool_identifier）
created_at  timestamptz  NOT NULL default now()
【预留】agent_key, step_index, artifact_id
```
索引：`UNIQUE(run_id, seq)`；`INDEX(run_id, seq)`。重建一次运行 = `SELECT * FROM item WHERE run_id=? ORDER BY seq`。
> 用量不放 item，统一进 `usage_event`，靠 `item_id` 关联。

### 3.12 `usage_event` —— 精确用量

（**记录，不扣费**；统一记「模型 + 工具」）
```
id          bigint       PK
user_id     bigint       NOT NULL, FK→users(id)
run_id      bigint       NOT NULL, FK→run(id)        哪次执行
item_id     bigint       NULL,     FK→item(id)       产生此用量的 item（'message'=LLM / 'tool_call'=工具）
usage_type  varchar      NOT NULL                    判别器（= 未来 charging algorithm）：
                                                     模型 'anthropic_messages'|'openai_chat'|'gemini'… / 工具 'tavily_search'…
usage       jsonb        NOT NULL                    原始用量，形状由 usage_type 决定（Pydantic 判别联合；含模型名/工具 key 标识）
status      varchar      NOT NULL, default 'success' CHECK IN ('success','failed')
request_id  varchar      NOT NULL, UNIQUE            幂等（防重复记录）
created_at  timestamptz  NOT NULL
```
索引：`UNIQUE(request_id)`；`INDEX(user_id, created_at)`；`INDEX(run_id)`；`INDEX(item_id)`；`INDEX(usage_type)`。
- **本期只记不扣**：每次模型/工具调用后写一条，记原始用量；**不触发任何积分扣减**（无标价，也无法算 cost——成本=用量×定价，定价属 §8.1/§8.5）。
- **不归一化**：各家用量形状不同（Anthropic input/output + cache 5m/1h/read、OpenAI prompt/completion/cached/reasoning、Gemini…、tavily 搜索次数），原样按 `usage_type` 进 `usage`，用 **Pydantic 判别联合**在应用层取强类型（= TS 的 `type`+`payload`）。
- 一次 chat turn 调了 tavily：会有**多条 item + 多条 usage_event**（LLM 调用各一条 token、tavily 一条搜索次数），全挂同一 `run_id`，靠 `item_id` 溯源。
- **预留**（未来计费，§8.1）：`provider` 快照、`billing_status`（异步结算接缝）、定价快照、`credits_charged`、`cost`。

**Pydantic 判别联合（`usage` 的应用层类型）：**
```python
class AnthropicMessagesUsage(BaseModel):
    type: Literal["anthropic_messages"]; input_tokens: int; output_tokens: int
    cache_creation_5m_tokens: int = 0; cache_creation_1h_tokens: int = 0; cache_read_tokens: int = 0
class OpenAIChatUsage(BaseModel):
    type: Literal["openai_chat"]; prompt_tokens: int; completion_tokens: int
    cached_tokens: int = 0; reasoning_tokens: int = 0
class TavilySearchUsage(BaseModel):
    type: Literal["tavily_search"]; search_count: int
Usage = Annotated[Union[AnthropicMessagesUsage, OpenAIChatUsage, TavilySearchUsage, ...],
                  Field(discriminator="type")]
```

---

## 4. 统一能力层（架构北极星）

三层：`tool`（原子能力，代码实现）→ `agent`（配置实例）→ `app`（应用中心入口，未来）。上层包装下层，同一能力可在每层各现身一次；三入口最终汇流到 `run → item` 同一套执行表。本期落地「对话」入口 + `agent`/`tool`；`app`/应用中心见 §8.4。

---

## 5. 运行时、错误处理、测试

**运行时（对话，react_loop）**：
```
前端 POST /runs (input + conversation) → 建 run(agent_key='chat')
  → resolve_agent('chat')：DB行 ?? 代码默认；解析 model→provider→适配器（缺 model/密钥则报错）
  → react_loop：LLM 调用(写 message item + usage_event) → 若调工具则 tool_call/tool_output item + usage_event → 回灌续跑（≤max_turns）
  → 每段经 SSE 推前端 → run.status=completed
```
- **单服务起步**；对话 SSE 直出，无队列、无文件、不计费。每次模型/工具调用精确记 `usage_event`（不扣费）。

**错误处理**：provider 超时/限流在适配层重试/降级，失败 → `run.status=failed` + 错误写 item，SSE 推失败事件；**模型/供应商未配置 → 立即报错**（不回退内置）；会话失效 401；用量幂等靠 `request_id` 唯一约束。

**测试**：单元（密码哈希/会话/邀请码核销/resolve_agent 三级回退/用量记录）；集成（注册→登录→对话→react_loop 调 tavily→item & usage_event 落库→SSE）；契约（provider 适配层 mock 各 family）；迁移（Alembic 升降级 + 种子 admin 幂等 + tool seeding upsert 不覆盖策略）。

---

## 6. 明确不做的（YAGNI / 本期）

不做计费扣费（不限量，仅记用量）；不做文件/生图、队列、对象存储；不做多 agent 编排/handoff、负载均衡；不做应用中心发布、OAuth、RBAC、邮箱验证（密码重置=登录态自助改密）；不上 ES/向量库/ClickHouse/MongoDB/Kafka；agent 编排逻辑永远在代码、不靠配置发明。

---

## 7. 参考的开源产品与借鉴点

| 项目 | 借鉴点 |
|---|---|
| Suna / Open WebUI | 整栈选型、工具即代码、可插拔 StorageProvider、多用户趁早上 Postgres |
| OpenAI Agents SDK / Claude Agent SDK | Session→Run→Item 三级、声明式 agent 定义(name/instructions/model/tools)、逻辑在 Runner、handoff 即 tool、定义可存代码/文件→我们存 DB |
| Dify | 定义在 DB(config) + 逻辑在代码(BaseAgentRunner)；模型供应商加密存密钥、不回传 |
| LiteLLM / one-api | model_list / channel+ability 注册结构（**借设计、不接库、不做网关**） |
| Lago / Stripe / TigerBeetle | 预付积分钱包、Credit Grants 批次过期、复式账本两阶段（计费参考，§8.1） |

---

## 8. 未来演进（分块导论）

> 均不在第一期；每块给方向与要点 hint，具体规划时再展开。

### 8.1 计费 / 积分（预付积分、API 用量折价）
- 触发点：对外分发、需限额/收费时。本期 `usage_event` 已精确记量，开计费时接上。
- 三表：`credit_account`(缓存余额，乐观锁/行锁) + `credit_ledger`(只追加流水，entry_type+正负+balance_after+idempotency_key+txn_group_id) + `credit_lot`(积分批次：source/remaining/expires_at/priority，FIFO+过期烧剩余)。余额=SUM(活跃 lot.remaining)，account 是缓存。
- 扣费门控：`balance>0` 放行、调用后按实际扣；并发用 `SELECT…FOR UPDATE` + 幂等键防超扣/重复。
- 计费由 `usage_event.usage_type` → 各自 charging algorithm → 各自定价（模型按 token、工具按次）。
- 异步结算（更后期）：`usage_event.billed` 标记 + worker，或用量入队列 consumer；最终一致换吞吐。
- 业界对照：Stripe Credit Grants、Lago 预付钱包、TigerBeetle 两阶段、巨量引擎现金/赠款、国内积分系统（账户+流水+批次 FIFO+锁定）。

### 8.2 Agent 编排引擎（多 agent）
- 新增 `runtime_pattern`：`orchestrator_executor`/`plan_execute` 等；handoff 以 tool_call 派生子 run（`parent_run_id`）；`config` 加 `sub_agents`/`handoff_target_keys`。
- run/item/parent_run_id 已兼容；引擎选型（LangGraph 等）到时再定。

### 8.3 工具体系扩展
- 更多内置工具、外部工具走 OpenAPI/MCP + 通用适配器；工具计费规则上 `tool`（§8.1）。

### 8.4 应用中心
- 前期写死页面；后期模板化+可发布（模板应用/代码应用），`app` 表（ui_kind / backing tool|agent）。

### 8.5 模型层演进（多供应商 / 负载均衡）
- 要 LB/故障转移：① 加 `model_deployment` 绑定表（model×provider，priority/weight/enabled，对标 LiteLLM router / new-api ability），把 model 的 provider 迁入；或 ② **前置网关**（自建 LiteLLM/one-api），`provider.base_url` 指向它，业务库不变。
- 用量记实际部署（provider 快照）；定价：成本随 deployment、售价随逻辑模型。

### 8.6 身份演进
- OAuth(Google/GitHub)：复用 `auth_identity`（多插 provider 行）；provider 邮箱常已验证。
- RBAC：`role/permission/role_permission/user_role`（纯关联表用复合主键），由 `users.role` 无损回填迁入；前提鉴权已收口在统一函数。
- 上邮件服务后：邮箱验证 / 密码找回（一次性 token）。

### 8.7 文件、长任务与规模化触发点
- 文件/生图（MVP-2 倾向）：+MinIO（可插拔 StorageProvider）+ Celery/Redis；`artifact` 表（元数据+URL，不存 base64）。
- 记忆/RAG：pgvector → 百万级再上 Qdrant/Milvus。
- 会话：量大把 `auth_session` 挪 Redis（换 SessionStore 实现）；秒级踢 access 加 Redis 黑名单。
- 用量分析：`usage_daily_rollup` 预聚合看板；海量上 ClickHouse。全文：先 PG 全文，需要时 ES。
- 分库 / 高并发 ID：代理键生成换 Snowflake/Leaf，表结构不变。
- 原则：按真实规模触发点逐个加，不提前挖坑。

---

## 附 术语速查
- **run / item**：一次执行 / 其内有序事件。**opaque token / 会话**：随机串当钥匙 + 服务端存会话行（有状态、可即时吊销）。**代理键**：无语义的 `bigint IDENTITY` 主键，全表统一用它做 PK；**自然键**：有语义的稳定标识（`model_name`/`agent_code`/`tool_identifier`…），做 `UNIQUE` 不做 PK，可被 FK 引用；**public_id**：对外暴露的不可枚举 UUIDv7，URL/API 只露它。**runtime_pattern**：代码里的编排逻辑（react_loop…）。**usage_type**：用量/计费判别器，决定 usage payload 形状。
