# TideNursery-01 · 潮汐育苗台账

海水育苗场「塘口水质采样与投喂事件」台账种子项目（非库存 / 电商 / 医院）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11 · FastAPI · SQLAlchemy 2 · Pydantic v2 · python-jose · passlib(bcrypt) · uvicorn |
| 前端 | React 18 · Vite · TypeScript · React Router v6 |
| 数据库 | PostgreSQL 15 |
| 部署 | docker-compose · 前端 Nginx 反代 `/api` |

## 端口与账号

| 服务 | 端口 |
| --- | --- |
| 前端 | **3400** |
| 后端 API | **8400** |
| PostgreSQL | **5434** |

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 场长 |
| `technician` | `123456` | 水质技术员 |

## 一键启动

```bash
cd TideNursery-01
docker compose up --build
```

启动后访问：

- 前端：http://localhost:3400
- 后端健康检查：http://localhost:8400/api/health
- API 文档：http://localhost:8400/docs

后端 entrypoint 流程：等待数据库就绪 → `create_all` 建表 → seed 初始数据 → 启动 uvicorn。

## 功能模块

1. **Auth**：JWT 登录（OAuth2 Password），`/api/auth/login`、`/api/auth/me`
2. **Hatchery 育苗场**：`name`、`seawaterSource`、`notes`
3. **Pond 育苗塘**：`hatcheryId`、`pondCode`、`species`、`volumeM3`、`status(stocked|dry|quarantine)`；同场 `pondCode` 唯一
4. **WaterSample 水质样**：`pondId`、`sampledAt`、`tempC`、`salinityPpt`、`doMgL`、`ph`、`notes`；`doMgL > 0` 且 `ph ∈ [6,9]`，否则返回 **400**
5. **FeedEvent 投喂**：`pondId`、`fedAt`、`feedType`、`amountKg`、`operatorName`
6. **MeterReading 电表抄见**：按塘口登记，字段 `pondId`、`readingDate`、`startKwh`(起度)、`endKwh`(止度)、`unitPrice`(单价)；止度必须大于起度，同塘同日唯一
7. **FeedAllocation 电费分摊**：把抄见挂到同塘投喂行上（`meterReadingId` + `feedEventId`），一笔投喂只能挂一张**未封**抄见；封抄后不可再改
8. **Dashboard**：塘总数、quarantine 数、近 24h 采样数、近 7 日投喂总量 kg

### 抄表封账与对账

- **电量公式**：`电量(kWh) = 止度 − 起度`；**电费公式**：`电费 = 电量 × 单价`
- **封抄** `POST /api/meter-readings/{id}/seal`：至少挂 **2 笔**投喂；系统校验电量等于「止度−起度」、电费等于「电量×单价」，误差不超过 **0.01**。不满足返回 **409**，已封账也返回 409
- **对账** `GET /api/meter-readings/{id}/reconciliation`：返回该塘抄见的电量、电费与所挂投喂千克合计 `allocatedFeedKg`，供页面展示
- 投喂挂账接口会校验：投喂须与抄见**同塘**，且该投喂未挂在其他抄见上

## 前端页面

Login · Dashboard · Hatcheries · Ponds · WaterSamples · FeedEvents · MeterReadings（塘页「抄表」进入，按 `?pondId=` 定位塘口）

## 本地开发（可选）

```bash
# 数据库（或用 compose 只起 db）
docker compose up -d db

# 后端
cd backend
pip install -r requirements.txt
set DATABASE_URL=postgresql+psycopg2://tidenursery:tidenursery@localhost:5434/tidenursery
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
uvicorn app.main:app --reload --port 8400

# 前端
cd frontend
npm install
npm run dev
```

## 目录结构

```
TideNursery-01/
├── docker-compose.yml
├── README.md
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── auth.py
│       ├── seed.py
│       ├── models/
│       ├── schemas/
│       └── routers/
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── pages/
        ├── components/
        └── api/
```
