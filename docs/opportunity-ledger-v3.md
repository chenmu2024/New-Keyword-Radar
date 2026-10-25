# 新词雷达 V3：候选生命周期记录

本模块是在原有每日 Google Trends 词根扫描基础上增加的 **证据优先的持久化记录层**，不是自动宣称新词可以盈利的模型，也没有新增任何外部付费 API。

## 数据流

现有 7-Day Seed Scout 在每天六轮定时批次中，继续更新 `state/pending.json` 和 `data/seed-scout-daily/YYYY-MM-DD.json`。扫描结果发布步骤（`src/publish_seed_scout.py`）会在刷新主分支并合并待验证队列后调用 `src/opportunity_tracker.py`，生成：

- `state/opportunities.json`：跨天稳定候选ID、最早/最近发现日期、审核状态、证据字段；保留已经拒绝或暂停的候选。
- `data/opportunities/latest.json`：最近候选、首次出现候选数、D+7/14/30待复查清单。
- `reports/opportunities/latest.md`：供 08:00 ChatGPT V3 早报检索的精简阅读文件。

ID 基于完整Query标准化文本 + 地域，不能凭同一个词自动判断意图相同；不同意图需由日报人工单独标注和核实，不能自动混为新机会。不会从 Trends 变化猜出 Volume/KD/CPC、真实支付或成功概率。

## 人工审核输入

`config/opportunity_reviews.json` 初始为 `{}`，可按如下格式增加经过人工核实的原始证据：

```json
{
  "example full query": {
    "query": "example full query",
    "geo": "",
    "stage": "serp-review",
    "checked_at": "2026-10-25",
    "user_evidence_url": "https://example.org/original-comment",
    "serp_evidence_url": "https://example.org/serp-evidence",
    "feasible_zero_fixed_cost": true,
    "notes": "Evidence reviewed manually; still no guarantee of SEO ranking."
  }
}
```

审核状态：`discovered`、`needs-evidence`、`serp-review`、`ready-to-test`、`watch`、`paused`、`rejected`。只有同时填写审核日期、用户需求链接、SERP证据链接和纯浏览器可行性为真时，才允许标为 `ready-to-test`；这只是允许进一步测试，并不表示产品已验证盈利。已拒绝状态不会因新一天 Rising Query 自动重置。

可在审核文件记录 `review_checks: {"7": {"checked_at": "2026-10-25", "source_url": "https://example.org/recheck"}}`，只有同时包含实际复查日期和来源链接才计为完成。到第14、30天仍未补完的阶段会以 `overdue_stages` 显示。\n\n跟踪到 D+7/D+14/D+30 只表示**需要重新取证**，并不意味着已经做过数据回测、竞争实测或用户支付确认。若在未来新增 `review_checks` 应记载真实核验日期、来源 URL、变化，不得事后伪造。

## 系统边界

- 原有74词根、每天六次 Google Trends 扫描、90天与5年历史筛选逻辑不改。
- 不自动新增 TikTok/X 评论爬虫，不绕过登录/robots/平台条款。
- 08:00 ChatGPT 日报可以按 V3 提示词自行查看公开证据，但不会自动把该证据写入仓库；要形成可复用的证据档案，需要明确把已核实记录写入审核文件。
- 当前 **没有与每小时四线赚钱雷达建立自动双向数据同步**。日报只允许引用实际上可访问的记录。
- 本方案使用现有 GitHub 仓库和 Actions；仍受账号配额、网络限流和 GitHub Actions 执行状态约束。
