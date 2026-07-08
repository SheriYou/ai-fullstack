# G1 环境 Checklist — Hot70 WA Bot

全部 ✅ 后方可 L1/L2/L3。

## 测试环境（传音）

- [ ] Web 工作台可访问：`https://uat-paas.transsion.com/whatsapp-bot-web/`
- [ ] 后端 API 可达：`https://uat-paas.transsion.com/whatsapp-bot-service/api`
- [ ] 测试账号可登录（admin / 坐席账号）
- [ ] 机器人服务健康；`agentModeEnabled=1`
- [ ] 记录 **businessLineId**、默认 **channelKey**
- [ ] webhook secret 与 `spec/api-notes.md` 一致

## 智齿（external-handoff 场景）

- [ ] 沙箱/测试环境可用
- [ ] WA API 回调指向传音测试环境
- [ ] 智齿在线客服工作台可登录
- [ ] Hot70 专属 **技能组** 已配置（Q01）
- [ ] 渠道 `providerType=ZHICHI` 且 `externalHandoffEnabled=true`
- [ ] 技能组 **groupid** 已填入 `spec/handoff-allocation.md`
- [ ] 实测 `historyLimit`（默认 **50**）

## 配置核验（Q04 / Q06）

- [ ] `minConfidenceForAutoReply` 实测值（默认 **0.65**）
- [ ] 确认 `humanHandoffMode` 仅存库；AI 自动转人工走 **本地** 路径

## 本地坐席（LOCAL handoff 场景）

- [ ] ≥1 坐席账号 **online** 且可自动分配
- [ ] Web 工作台可收发消息

## WhatsApp / 探针

- [ ] WhatsApp 测试号 ≥2（L3 真机）或 webhook 模拟（L2）
- [ ] L2：`BOT_TEST_API_URL` 与 channelKey 已写入 `config.env`

## 文档

- [ ] `spec/api-notes.md` 路径与密钥已核对
- [ ] `spec/handoff-dual-path.md` Q07 产品已知晓双路径
