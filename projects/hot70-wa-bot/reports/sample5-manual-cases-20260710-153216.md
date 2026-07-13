# Hot70 Manual Cases Sample Execution (5)

- time: 20260710-153216
- source: D:\CMP\agent-human-test\projects\hot70-wa-bot\prd\Hot70_Manual_Test_Cases_From_Script - Sheet1.csv
- api: https://uat-paas.transsion.com/whatsapp-bot-service/api
- channel: ch_wa_01
- business_line_id: 1
- login_ok: True
- summary: PASS=1 FAIL=4

| case_id | expected_handoff | result | webhook_http | outbound_count | conversation_status | handoff_target |
|---|---|---|---:|---:|---|---|
| TC-H70-028-H-C02 | 是 | FAIL | 200 | 2 | open |  |
| TC-H70-022-H-C02 | 是 | FAIL | 200 | 2 | open |  |
| TC-H70-026-H-C01 | 是 | FAIL | 200 | 2 | open |  |
| TC-H70-010-N | 否 | PASS | 200 | 1 | open |  |
| TC-H70-035-N | 是 | FAIL | 200 | 1 | open |  |