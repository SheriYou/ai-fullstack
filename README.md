# ai-fullstack (Vue3 + Spring Boot + MySQL)

## 目录结构

- `frontend/`: Vue 3 + Vite + Tailwind CSS
- `backend/`: Spring Boot + MySQL (JPA)
- `docker-compose.yml`: 本地 MySQL（账号/密码：root/root）

## 1) 启动 MySQL

在仓库根目录执行：

```bash
docker compose up -d
```

MySQL 默认端口：`3306`

## 2) 启动后端（Spring Boot）

```bash
cd backend
mvn spring-boot:run
```

后端端口：`8080`

启动时会：

- 自动创建数据库 `ai_fullstack`（通过 JDBC 参数 `createDatabaseIfNotExist=true`）
- 自动建表（Hibernate DDL）
- 自动填充 demo 数据（`data.sql`）

接口：

- `GET  /api/todos`
- `POST /api/todos`  body: `{ "title": "xxx" }`

## 3) 启动前端（Vue3）

```bash
cd frontend
npm install
npm run dev
```

前端默认端口：`5173`，已配置代理到后端 `http://localhost:8080`。

