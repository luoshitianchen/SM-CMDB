# 配置管理数据库（CMDB）服务 多环境差异矩阵（MULTI_ENV_MATRIX）

> 服务：`sm-cmdb` ｜ 端口 8020 ｜ 数据库 `sm_cmdb`

| 维度 | dev | staging | prod |
| --- | --- | --- | --- |
| namespace | sm-dev | sm-staging | sm-prod |
| 副本数 | 1 | 2 | 3 |
| HPA（min/max） | 1 / 3 | 2 / 5 | 3 / 10 |
| requests(cpu/mem) | 50m / 64Mi | 100m / 128Mi | 200m / 256Mi |
| limits(cpu/mem) | 200m / 128Mi | 500m / 256Mi | 1 / 512Mi |
| 数据库 | sm_cmdb（dev 实例） | sm_cmdb（staging 实例） | sm_cmdb（生产主库） |
| 镜像 tag | dev | staging | 语义版本（AppVersion） |
| 日志级别 | debug | info | warn |
| 域名 | sm-cmdb.dev.sm.example.com | sm-cmdb.staging.sm.example.com | sm-cmdb.sm.example.com |
| TLS | 无 | sm-tls | sm-tls |
| 发布方式 | 自动 | 自动+测试门禁 | CAB 审批 |
