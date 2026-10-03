# Aiven 免费 MySQL 自动恢复

这个工作流每小时读取一次 Aiven 服务状态，只在明确处于 `Powered off` 时请求开机。其他状态不修改。GitHub Actions 的定时任务运行在仓库默认分支 `main`，所以工作流必须位于该分支。

## 一次性配置

1. 在 [Aiven Console](https://console.aiven.io/) 打开账号设置，创建 API Token。建议只授予目标项目所需的服务查看和开机权限；不要把 Token 写入仓库或发送到聊天。
2. 在 [GitHub 仓库 Actions Secrets 页面](https://github.com/XZ-1-sc/shuli-zhixue/settings/secrets/actions) 添加 Repository secret：`AIVEN_API_TOKEN`，值为刚创建的 Token。
3. 在同一页面的 **Variables** 标签添加：
   - `AIVEN_PROJECT`：Aiven 项目名称（不是 GitHub 仓库名）。
   - `AIVEN_SERVICE`：Aiven MySQL 服务名称。
4. 在 GitHub 仓库 **Actions → Aiven MySQL auto recovery → Run workflow** 手动运行一次，确认日志显示 `No action needed` 或 `Power-on requested`。
5. 在 GitHub **Settings → Notifications → Actions** 中启用工作流失败通知。

工作流每小时的第 17 分钟（UTC）运行。GitHub 定时运行可能延迟或偶尔跳过，不能保证零停机。Aiven 开机还需恢复时间，可能从数分钟到更久。UptimeRobot 继续监控 `/api/ready` 并提供故障告警。

GitHub 可能在仓库长期无活动后禁用定时工作流；如果 Actions 页面显示工作流已禁用，需要在该页面重新启用。Aiven 免费计划也可能因平台政策、额度或服务故障拒绝自动开机。若自动恢复失败，GitHub Actions 会标红并触发已配置的通知。
