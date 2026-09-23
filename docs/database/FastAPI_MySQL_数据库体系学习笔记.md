# FastAPI + MySQL 数据库体系学习笔记

> 目标：从“项目怎么接数据库”一路理解到“运行时连接怎么管理”，再到“生产环境数据库怎么部署和扩展”。
>
> 本文以 **FastAPI + SQLAlchemy + asyncmy + Alembic + MySQL** 为主线，并穿插 NestJS / TypeORM / Prisma 的对照，帮助有 Node.js / NestJS 背景的开发者建立一套完整的数据库心智模型。

---

# 目录

1. 整体知识地图
2. 第一层：开发接入——FastAPI 如何接入 MySQL
3. 第二层：ORM Model 与 Pydantic Schema
4. 第三层：Migration——数据库结构如何演进
5. 第四层：Engine、Connection Pool、Connection
6. 第五层：Session——ORM 的数据库工作上下文
7. 第六层：Transaction 与 Session 生命周期
8. 第七层：连接池的并发、上限与等待
9. 第八层：生产环境数据库部署
10. 第九层：Replication、读写分离与 Sharding
11. 第十层：请求路由与数据库路由
12. 第十一层：日常开发中的重要原则
13. 第十二层：NestJS 对照表
14. 下一阶段建议学习内容

---

# 1. 整体知识地图

先把整个数据库体系看成几层：

```text
HTTP Request
    ↓
FastAPI
    ↓
Pydantic Schema
    ↓
Service
    ↓
SQLAlchemy ORM / AsyncSession
    ↓
Engine
    ↓
Connection Pool
    ↓
Connection
    ↓
asyncmy
    ↓
MySQL
```

同时还有一条“数据库结构管理”链路：

```text
SQLAlchemy ORM Model
        ↓
      Alembic
        ↓
Migration Script
        ↓
CREATE / ALTER / INDEX
        ↓
      MySQL
```

生产环境再往上扩展：

```text
                Load Balancer
                      ↓
          ┌───────────┼───────────┐
          ↓           ↓           ↓
      FastAPI-1   FastAPI-2   FastAPI-3
          │           │           │
       DB Pool      DB Pool      DB Pool
          └───────────┼───────────┘
                      ↓
                Database Layer
                      ↓
          Primary / Replica / Shard
```

可以把整个知识体系分为三大阶段：

```text
开发接入
│
├── SQLAlchemy
├── asyncmy
├── Alembic
├── Pydantic
└── ORM Model / Schema
      ↓
运行时
│
├── Engine
├── Connection Pool
├── Connection
├── Session
├── Transaction
└── commit / rollback
      ↓
生产部署
│
├── API 横向扩容
├── Primary / Replica
├── 读写分离
├── Replication Lag
├── Sharding
└── Multi-Region
```

---

# 2. 第一层：开发接入——FastAPI 如何接入 MySQL

## 2.1 FastAPI 本身不负责数据库

FastAPI 主要负责：

```text
HTTP
Routing
Dependency Injection
Request / Response
数据校验集成
```

它不像 Django 那样自带完整 ORM，因此数据库能力通常由多个库组合完成。

我们当前采用：

```text
FastAPI
+
SQLAlchemy
+
asyncmy
+
Alembic
+
pydantic-settings
```

这些库职责是分开的。

---

## 2.2 SQLAlchemy 是什么

SQLAlchemy 是数据库操作层的核心组件，负责：

```text
ORM
SQL 构造
Session
Transaction
Relationship
Connection Pool
Async Database API
```

例如：

```python
product = Product(
    name="Keyboard",
    price=399,
    stock=10,
)

session.add(product)
await session.commit()
```

你没有手写：

```sql
INSERT INTO products ...
```

但 SQLAlchemy 会根据 ORM 对象生成对应 SQL。

所以可以理解成：

```text
SQLAlchemy
≈ ORM + SQL Toolkit + Session / Transaction 管理
```

### 为什么安装 `sqlalchemy[asyncio]`

```bash
uv add "sqlalchemy[asyncio]"
```

`[asyncio]` 是 Python Package 的 **Extra Dependency** 写法。

它不是另一个库，而是：

```text
SQLAlchemy 本体
+
asyncio 模式需要的额外依赖
```

因为我们会使用：

```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
```

---

## 2.3 asyncmy 是什么

SQLAlchemy 负责数据库操作抽象，但它本身不负责实现完整的 MySQL 网络协议。

真正和 MySQL 建立网络连接的是：

```text
asyncmy
```

例如：

```text
mysql+asyncmy://user:password@127.0.0.1:3306/minishop
```

可以拆成：

```text
mysql
↓
数据库类型

asyncmy
↓
数据库 Driver
```

完整关系：

```text
FastAPI
   ↓
SQLAlchemy
   ↓
asyncmy
   ↓
MySQL
```

类比 NestJS：

```text
SQLAlchemy ≈ TypeORM / Sequelize
asyncmy    ≈ mysql2
```

---

## 2.4 Alembic 是什么

Alembic 不负责日常 CRUD。

它负责：

```text
Database Schema Migration
```

例如第一版：

```text
products

id
name
price
```

第二版增加：

```text
stock
```

长期项目不应该只靠手工执行：

```sql
ALTER TABLE products ADD COLUMN stock INT;
```

而应该通过 Migration：

```bash
uv run alembic revision --autogenerate -m "add stock"
uv run alembic upgrade head
```

所以可以记：

```text
SQLAlchemy
→ 管数据怎么操作

Alembic
→ 管数据库结构怎么变化
```

---

## 2.5 pydantic-settings 是什么

它主要负责应用配置，例如：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=minishop
MYSQL_PASSWORD=xxx
MYSQL_DATABASE=minishop
```

对应 Python：

```python
class Settings(BaseSettings):
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DATABASE: str
```

相比：

```python
os.getenv("MYSQL_PORT")
```

它额外提供：

```text
类型转换
默认值
配置校验
集中管理
```

NestJS 中大致类似：

```text
@nestjs/config
+
dotenv
```

---

# 3. 第二层：ORM Model 与 Pydantic Schema

## 3.1 ORM Model

ORM Model 描述：

> 数据库表长什么样。

例如：

```python
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
    )

    stock: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
```

对应 MySQL：

```text
products
--------
id
name
price
stock
```

---

## 3.2 Pydantic Schema

Pydantic Schema 描述：

> API 接收和返回的数据长什么样。

创建商品：

```python
class ProductCreate(BaseModel):
    name: str
    price: Decimal
    stock: int
```

返回商品：

```python
class ProductResponse(BaseModel):
    id: int
    name: str
    price: Decimal
    stock: int
```

---

## 3.3 为什么 Model 和 Schema 要分开

因为数据库结构和 API 结构通常不完全一样。

例如 User 数据库表：

```text
id
email
password_hash
role
created_at
updated_at
```

注册接口只需要：

```text
email
password
```

返回接口可能只允许：

```text
id
email
created_at
```

绝对不应该返回：

```text
password_hash
```

所以：

```text
SQLAlchemy Model
→ 数据库存什么

Pydantic Schema
→ API 允许输入输出什么
```

完整数据流：

```text
HTTP JSON
   ↓
ProductCreate
   ↓
Service
   ↓
Product ORM
   ↓
SQLAlchemy
   ↓
MySQL
   ↓
Product ORM
   ↓
ProductResponse
   ↓
JSON
```

NestJS 中：

```text
Pydantic Schema
≈ DTO + class-validator
```

---

# 4. 第三层：Migration——数据库结构如何演进

## 4.1 为什么不能只用 `create_all`

学习阶段可能写：

```python
Base.metadata.create_all()
```

它更适合：

```text
数据库没有表
↓
创建表
```

但真实项目的问题是：

```text
Database v1
↓
v2
↓
v3
↓
v4
```

例如：

```text
v1:
products(id, name)

v2:
products(id, name, price)

v3:
products(id, name, price, stock)
```

所以需要保存数据库演进历史。

这就是 Alembic。

---

## 4.2 Migration 的基本工作流

修改 ORM Model：

```python
class Product(Base):
    ...
    stock: Mapped[int]
```

生成 Migration：

```bash
uv run alembic revision --autogenerate -m "add stock"
```

得到：

```text
alembic/versions/
└── xxxx_add_stock.py
```

检查后执行：

```bash
uv run alembic upgrade head
```

---

## 4.3 Migration 要 Review

`--autogenerate` 不代表自动生成的一定完全正确。

正确流程：

```text
修改 Model
↓
autogenerate
↓
人工检查 Migration
↓
确认 SQL / Schema 变化
↓
upgrade
```

尤其是：

```text
字段重命名
表重命名
数据迁移
复杂约束
```

经常需要人工调整。

---

## 4.4 不要随便修改已执行的历史 Migration

例如：

```text
001_create_products.py
```

如果开发、测试、生产都已经执行过，就不要回头直接修改。

应该新增：

```text
002_add_stock.py
```

Migration 本质上类似：

```text
Git Commit History
```

---

# 5. 第四层：Engine、Connection Pool、Connection

这是数据库运行时最核心的基础设施。

先区分：

```text
Engine
Connection Pool
Connection
Session
```

本章先讲前三个。

---

## 5.1 Connection

Connection 是：

> 应用程序和 MySQL 之间真正的数据库连接。

粗略理解：

```text
Python
  │
  │ TCP Connection
  │
  ▼
MySQL
```

建立数据库连接需要：

```text
建立网络连接
身份认证
初始化数据库会话
初始化连接状态
```

因此 Connection 是昂贵资源。

---

## 5.2 为什么需要 Connection Pool

如果每个 HTTP Request 都：

```text
创建 Connection
↓
认证 MySQL
↓
执行 SQL
↓
关闭 Connection
```

高并发下成本很高。

于是出现：

```text
Connection Pool
```

连接池维护一组可重复利用的 Connection：

```text
Pool
├── Conn 1
├── Conn 2
├── Conn 3
├── Conn 4
└── Conn 5
```

请求：

```text
借 Connection
↓
执行 SQL
↓
还给 Pool
```

而不是不断：

```text
创建
销毁
创建
销毁
```

---

## 5.3 Engine

SQLAlchemy：

```python
engine = create_async_engine(...)
```

Engine 可以理解为：

> 整个应用访问数据库的基础设施入口。

它管理：

```text
数据库 URL
Driver
Connection Pool
连接参数
日志
超时
```

所以通常：

```text
Engine 生命周期
≈ Application 生命周期
```

一般是：

```text
一个应用进程
→ 一个 Engine
```

而不是：

```text
每个 Request
→ 新建 Engine
```

三者关系：

```text
Engine
  ↓
Connection Pool
  ↓
Connection
  ↓
MySQL
```

一句话：

```text
Engine
= 数据库基础设施入口

Pool
= 连接仓库

Connection
= 真正和 MySQL 通信的通道
```

---

# 6. 第五层：Session——ORM 的数据库工作上下文

Session 是数据库学习里最容易抽象的概念。

它不是 Connection。

也不只是“数据库连接”。

最适合的理解：

> Session 是一次 ORM 数据库工作的上下文 / 工作台。

---

## 6.1 Session 为什么存在

例如：

```python
product = await session.get(Product, 1)

product.stock -= 1

order = Order(
    user_id=10,
    total_amount=399,
)

session.add(order)

await session.commit()
```

Session 会记录：

```text
加载了 Product(id=1)

Product.stock 被修改

新增了 Order

这些变化属于当前数据库工作上下文
```

可以粗略想象：

```text
Session

loaded:
- Product(id=1)

dirty:
- Product(id=1)

new:
- Order(...)

deleted:
- ...
```

---

## 6.2 Session 和 Connection 的区别

Connection 关心：

```text
执行什么 SQL
返回什么结果
```

Session 关心：

```text
哪些 ORM 对象被加载
哪些对象被修改
哪些对象新增
哪些对象删除
当前事务是什么状态
```

所以：

```text
Connection
= 面向 SQL / 数据库通信

Session
= 面向 ORM 对象 / 业务工作单元
```

---

## 6.3 Session 会管理 ORM 对象状态

例如：

```python
product = await session.get(Product, 1)

product.stock = 9
```

你只是修改 Python 内存里的对象。

但是 Session 知道：

```text
Product(id=1)
stock:
10 → 9
```

之后：

```python
await session.flush()
```

SQLAlchemy 可以生成：

```sql
UPDATE products
SET stock = 9
WHERE id = 1;
```

---

## 6.4 Identity Map

Session 内部会维护：

```text
数据库 Row
↕
Python ORM Object
```

例如：

```python
product1 = await session.get(Product, 1)
product2 = await session.get(Product, 1)
```

同一个 Session 会维护对象身份一致性。

这种机制称为：

```text
Identity Map
```

---

## 6.5 Unit of Work

Session 会收集：

```text
new
dirty
deleted
```

然后统一决定：

```text
INSERT
UPDATE
DELETE
```

这个思想叫：

```text
Unit of Work
```

所以 Session 可以理解为：

> 当前业务中数据库变更的管理器。

---

## 6.6 FastAPI 为什么常用“一请求一 Session”

典型：

```python
async def get_db():
    async with SessionLocal() as session:
        yield session
```

Route：

```python
async def create_product(
    db: AsyncSession = Depends(get_db),
):
    ...
```

生命周期：

```text
Request 开始
↓
创建 Session
↓
Router
↓
Service
↓
数据库操作
↓
commit / rollback
↓
Session close
↓
Request 结束
```

所以：

```text
Session 生命周期
≈ Request / Unit of Work 生命周期
```

---

## 6.7 为什么不能全局共享一个 Session

错误做法：

```python
session = AsyncSession(...)
```

然后所有请求共享。

这样会让：

```text
Request A 的对象
Request B 的对象

Request A 的事务
Request B 的事务

A rollback
B commit
```

混到一起。

尤其 `AsyncSession` 是：

```text
有状态
可变
不应该跨并发任务共享
```

正确：

```text
Request A → Session A
Request B → Session B
Request C → Session C
```

但它们可以共享：

```text
同一个 Engine
同一个 Connection Pool
```

所以：

```text
Engine：共享
Session：隔离
```

---

# 7. 第六层：Transaction 与 Session 生命周期

## 7.1 创建 Session 不等于拿 Connection

```python
session = SessionLocal()
```

只创建 Session。

此时：

```text
不一定已经从 Pool 拿 Connection
```

直到：

```python
await session.execute(...)
```

或：

```python
await session.get(...)
```

或：

```python
await session.flush()
```

真正需要访问数据库时，Session 才会获取 Connection。

---

## 7.2 一次典型生命周期

```python
async with SessionLocal() as session:
    product = await session.get(Product, 1)

    product.stock -= 1

    await session.commit()
```

大致过程：

```text
创建 Session
↓
没有 Connection

session.get()
↓
从 Pool 获取 Connection
↓
开始 Transaction
↓
SELECT

修改 ORM Object
↓
Session 标记 dirty

commit()
↓
flush
↓
UPDATE
↓
COMMIT
↓
Connection 可以归还 Pool
```

---

## 7.3 add

```python
session.add(product)
```

含义：

> 把 ORM 对象加入 Session 管理。

不代表数据库已经完成 INSERT。

---

## 7.4 flush

```python
await session.flush()
```

含义：

> 把 Session 中积累的变化同步到当前数据库事务。

例如：

```text
new
→ INSERT

dirty
→ UPDATE

deleted
→ DELETE
```

但是：

```text
flush ≠ commit
```

此时仍然可以：

```python
await session.rollback()
```

---

## 7.5 commit

```python
await session.commit()
```

含义：

> 正式提交当前事务。

通常 commit 前 SQLAlchemy 会执行必要的 flush。

```text
commit
↓
flush 尚未同步的变化
↓
执行 SQL
↓
COMMIT
```

---

## 7.6 rollback

假设：

```text
创建订单
扣库存
创建订单明细
```

执行一半出现异常：

```python
await session.rollback()
```

当前未提交事务中的修改会撤销。

核心意义：

```text
要么全部成功
要么全部失败
```

---

## 7.7 Transaction 应该尽量短

不推荐：

```python
async with session.begin():
    order = await get_order()

    await call_external_payment_api()

    order.status = "paid"
```

如果外部支付接口需要 30 秒：

```text
Transaction
可能持续 30+ 秒
```

后果：

```text
Connection 占用时间增加
锁持有时间增加
Connection Pool 压力增加
死锁概率增加
请求延迟增加
```

所以重要原则是：

> Transaction 尽量短。

---

# 8. 第七层：连接池的并发、上限与等待

## 8.1 Connection Pool 有上限

典型配置：

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)
```

粗略理解：

```text
常规 Pool:
10 connections

临时 Overflow:
20 connections

峰值:
约 30 connections
```

---

## 8.2 Pool 满了会怎样

假设 30 个 Connection 都被占用：

```text
Request 31
↓
需要执行 SQL
↓
Pool 没有空闲 Connection
↓
等待
```

如果超过：

```text
pool_timeout
```

仍然拿不到连接，就会超时。

所以：

```text
连接池耗尽
↓
新请求排队
↓
延迟上升
↓
超时 / 错误
```

---

## 8.3 Async 模式下“等待”意味着什么

在：

```text
FastAPI
AsyncSession
asyncmy
```

环境中，请求等待数据库连接时通常是：

```text
当前协程等待
```

并不是整个 Python 进程都无法处理其他任务。

Event Loop 仍然可以运行其他可调度任务。

但是对于当前 HTTP Request：

```text
响应会变慢
```

---

## 8.4 Pool 满不一定是 Pool 太小

常见错误：

```text
Pool Timeout
↓
直接把 pool_size 从 10 改成 1000
```

这可能把 MySQL 本身打垮。

连接池耗尽的根因可能是：

```text
慢 SQL
Transaction 太长
Connection 没有及时归还
数据库自身变慢
请求并发突然上涨
Worker 数量太多
```

正确排查：

```text
SQL 是否太慢
Transaction 是否过长
连接是否及时释放
请求并发是多少
应用有多少 Worker
应用有多少 Instance
MySQL max_connections 是多少
```

---

## 8.5 MySQL 自己也有连接上限

除了：

```text
SQLAlchemy Connection Pool
```

MySQL 服务器本身也有：

```text
max_connections
```

所以存在两层限制：

```text
FastAPI Application
↓
SQLAlchemy Pool
↓
MySQL max_connections
```

---

## 8.6 多 Worker / 多实例需要计算总连接数

例如：

```text
4 个 Worker
每个最多 20 connections
```

理论峰值：

```text
4 × 20 = 80
```

如果有 3 个 API 实例：

```text
80 × 3 = 240
```

所以：

> Pool 配置必须结合整个部署规模，而不是只看一个 Python 进程。

---

# 9. 第八层：生产环境数据库部署

## 9.1 最基础模式

```text
Client
↓
Load Balancer / API Gateway
↓
FastAPI
↓
MySQL
```

适合：

```text
小型项目
低到中等流量
```

---

## 9.2 API 横向扩容

当 API 服务成为瓶颈：

```text
                 Load Balancer
                      │
          ┌───────────┼───────────┐
          ↓           ↓           ↓
      API-1       API-2       API-3
          │           │           │
          └───────────┼───────────┘
                      ↓
                    MySQL
```

这些 API：

```text
运行同一套后端代码
```

Load Balancer 决定：

```text
这个请求给 API-1
下一个给 API-3
```

但它们可以仍然访问：

```text
同一个数据库集群
```

这里解决的是：

```text
API / HTTP 层的横向扩容
```

而不是数据库分片。

---

## 9.3 每个 API 实例都有自己的 Pool

例如：

```text
API-1 → Pool 10
API-2 → Pool 10
API-3 → Pool 10
```

那么数据库面对的潜在连接数是这些 Pool 的总和。

因此：

> API 横向扩容会直接增加数据库连接压力。

---

# 10. 第九层：Replication、读写分离与 Sharding

## 10.1 Replication

Replication：

> 同一份数据复制到多个数据库节点。

例如：

```text
Primary
   ↓
Replica-1
Replica-2
```

Primary 接收写入。

Replica 复制 Primary 的数据。

主要用途：

```text
高可用
容灾
读扩展
```

---

## 10.2 读写分离

常见策略：

```text
WRITE
→ Primary

READ
→ Replica
```

例如：

```text
POST /orders
→ Primary

UPDATE /users
→ Primary

GET /products
→ Replica

GET /orders
→ Replica
```

---

## 10.3 Replication Lag

Primary 写成功后，Replica 不一定瞬间同步。

例如：

```text
POST /orders
↓
Primary 创建成功

立即：
GET /orders/123
↓
Replica
↓
可能暂时查不到
```

这种同步延迟叫：

```text
Replication Lag
```

因此：

> SELECT 并不能简单理解成全部无脑走 Replica。

某些要求“读己之写”的场景可能仍然需要访问 Primary。

---

## 10.4 Sharding

Sharding：

> 把不同数据拆到不同数据库。

例如：

```text
user_id % 3
```

路由：

```text
user_id % 3 == 0
→ DB-A

user_id % 3 == 1
→ DB-B

user_id % 3 == 2
→ DB-C
```

结构：

```text
              API
               ↓
         Shard Router
        /      |      \
      DB-A   DB-B    DB-C
```

---

## 10.5 Replication 与 Sharding 的区别

```text
Replication
= 同一份数据的多个副本
```

```text
Sharding
= 不同数据拆到不同数据库
```

目的也不同：

```text
Replication
→ 高可用 / 读扩展

Sharding
→ 容量扩展 / 写扩展
```

---

## 10.6 Sharding 为什么复杂

单库：

```sql
SELECT *
FROM orders
WHERE user_id = 123;
```

分片后首先需要知道：

```text
user_id = 123
在哪个 DB？
```

然后还会出现：

```text
跨库 JOIN
全局 ORDER BY
全局 Pagination
全局唯一 ID
跨库 Transaction
数据重新分片
```

因此：

> 不要在没有明确瓶颈时过早做 Sharding。

---

# 11. 第十层：请求路由与数据库路由

这是生产架构中非常重要的一点：

> HTTP 请求路由和数据库路由，是两个独立的问题。

---

## 11.1 HTTP 请求路由

Load Balancer 决定：

```text
Request
↓
API-1 / API-2 / API-3
```

例如：

```text
Request A
→ API-2
```

---

## 11.2 数据库路由

API-2 接到 Request 后，还可以根据：

```text
user_id
tenant_id
region
读 / 写类型
```

决定访问：

```text
Primary
Replica
DB-A
DB-B
DB-C
```

所以完整链路可能是：

```text
Request
↓
Load Balancer
↓
API-2
↓
Database Router
↓
DB-C
```

---

## 11.3 不要把 API Instance 和 Database 绑死

并不是一定：

```text
API-A → DB-A
API-B → DB-B
API-C → DB-C
```

也可以是：

```text
API-1
├── DB-A
├── DB-B
└── DB-C

API-2
├── DB-A
├── DB-B
└── DB-C
```

每个 API 实例都根据请求信息动态决定数据库。

因此要区分：

```text
问题 1：
这个 HTTP Request 由哪个 API 实例处理？

问题 2：
这个 API 实例应该访问哪个数据库节点？
```

这两层可以完全独立。

---

# 12. 第十一层：日常开发中的重要原则

## 12.1 Engine 通常全局共享

推荐：

```text
Application Process
→ 一个 Engine
```

不要每个 Request 创建 Engine。

---

## 12.2 Session 不要跨并发请求共享

正确：

```text
Request A → Session A
Request B → Session B
```

错误：

```text
所有 Request
→ 一个全局 Session
```

---

## 12.3 Transaction 尽量短

不要在数据库事务里长时间：

```text
等待第三方 HTTP API
sleep
执行复杂非数据库任务
```

这会延长 Connection 和锁的占用时间。

---

## 12.4 Connection Pool 不是越大越好

连接池本质上也是：

```text
数据库保护机制
```

不是：

```text
越大性能越好
```

连接太多反而可能把数据库压垮。

---

## 12.5 数据库约束不要全部交给应用层

例如 Email 唯一。

应用层可以：

```python
if user_exists:
    ...
```

数据库仍然应该有：

```text
UNIQUE(email)
```

原因是并发：

```text
Request A 查询：不存在
Request B 查询：不存在

A INSERT
B INSERT
```

只有数据库 UNIQUE 才是最终防线。

原则：

> 应用层做友好校验，数据库层做最终保证。

---

## 12.6 金额不要使用 float

商城价格推荐：

```python
Decimal
```

数据库：

```text
DECIMAL(10, 2)
```

不要使用浮点类型保存精确金额。

---

## 12.7 注意 ORM 的 N+1 Query

例如：

```text
查询 100 个订单
↓
每个订单单独查询用户
```

SQL 数量：

```text
1 次 Orders
+
100 次 User
=
101 次 SQL
```

这就是：

```text
N+1 Problem
```

以后 SQLAlchemy 会学习：

```text
joinedload
selectinload
```

---

## 12.8 Async ORM 注意隐式 I/O

同步 ORM 中访问：

```python
order.user
```

可能自动执行 SQL。

Async 环境更应该：

> 明确声明需要加载哪些关联数据。

不要过度依赖 Lazy Loading。

---

## 12.9 测试数据库与开发数据库分开

推荐：

```text
minishop_dev
minishop_test
minishop_prod
```

测试环境不要碰生产数据。

---

# 13. 第十二层：NestJS 对照表

对于有 NestJS 背景的人，可以这样理解：

| Python / FastAPI | NestJS / Node 常见对应 | 作用 |
|---|---|---|
| FastAPI | NestJS | Web Framework |
| APIRouter | Controller | HTTP Route |
| Pydantic Schema | DTO + class-validator | API 数据校验 |
| Service | Service | 业务逻辑 |
| SQLAlchemy ORM | TypeORM / Sequelize / Prisma | ORM |
| AsyncSession | EntityManager / ORM 工作单元 | ORM 状态、事务、查询 |
| asyncmy | mysql2 | MySQL Driver |
| Alembic | TypeORM Migration / Prisma Migrate | Schema Migration |
| pydantic-settings | @nestjs/config | 配置管理 |
| pytest | Jest | 测试 |

---

## 13.1 为什么 Python 看起来更“散”

NestJS 通常通过：

```text
Module
Dependency Injection
ORM Integration
CLI
```

把很多能力整合起来。

FastAPI 更强调：

```text
FastAPI
→ HTTP

Pydantic
→ 数据校验

SQLAlchemy
→ ORM / Session

asyncmy
→ MySQL Driver

Alembic
→ Migration
```

第一次看会觉得零件较多。

但优点是：

```text
职责明确
每层可替换
底层机制透明
更容易理解数据库真正是怎么工作的
```

---

# 14. 下一阶段建议学习内容

我们目前已经讨论了：

```text
开发接入
↓
Engine / Pool / Connection
↓
Session
↓
Transaction 基础
↓
生产部署
↓
Replication / Sharding
```

接下来建议按下面顺序继续。

## 14.1 Transaction 深入

重点：

```text
add
flush
commit
rollback
autoflush
autobegin
```

真正搞懂：

```text
什么时候 SQL 发给数据库
什么时候数据真正提交
```

---

## 14.2 数据库事务理论

重点：

```text
ACID

Atomicity
Consistency
Isolation
Durability
```

然后学习：

```text
脏读
不可重复读
幻读
Isolation Level
```

---

## 14.3 并发与锁

重点：

```text
Row Lock
SELECT FOR UPDATE
Lost Update
Deadlock
超卖
```

可以使用 MiniShop 的：

```text
库存扣减
```

作为真实案例。

---

## 14.4 索引

重点：

```text
B-Tree
Primary Key
Unique Index
Composite Index
覆盖索引
索引失效
EXPLAIN
```

---

## 14.5 Relationship 与查询性能

重点：

```text
One-to-Many
Many-to-One
Many-to-Many
JOIN
N+1
joinedload
selectinload
```

---

# 最终心智模型

把数据库体系压缩成一句话：

```text
ORM Model
定义数据库数据结构

Alembic
管理数据库结构版本

Session
管理一次业务中的 ORM 数据变化

Engine
管理数据库访问基础设施

Connection Pool
复用有限数据库连接

Connection
真正和 MySQL 通信

Transaction
保证一组数据库操作作为整体成功或失败

Production Architecture
负责数据库的高可用、扩展和路由
```

开发运行链路：

```text
HTTP Request
    ↓
FastAPI
    ↓
Pydantic
    ↓
Service
    ↓
AsyncSession
    ↓
SQLAlchemy
    ↓
Engine
    ↓
Connection Pool
    ↓
Connection
    ↓
asyncmy
    ↓
MySQL
```

生产环境链路：

```text
Users
  ↓
Load Balancer
  ↓
多个 FastAPI Instances
  ↓
各自 Connection Pool
  ↓
Database Routing
  ↓
Primary / Replica / Shards
```

这就是我们目前从“开发接入”到“运行时连接管理”，再到“生产数据库部署”讨论过的完整第一阶段数据库知识体系。
