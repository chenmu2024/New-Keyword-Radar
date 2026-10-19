# Sitemap → 独立 Web SaaS 真实收入与竞品调查（2026-10-19）

**目标**：从已经进入 Sitemap 原始队列的具体功能中寻找单人、低固定成本、月净收入约 $300–$800 的可复制 Web SaaS；不接受浏览器插件或 App Store 产品；不修改 New Keyword Radar 原始种子、Google Trends 阈值、Sitemap 来源及试运行日期。

**证据等级**：
- A：TrustMRR 页面显示连接 Stripe/支付渠道的数据，附核验更新时间；“累计收入”与“MRR”必须分开。数字仍是平台公开快照，不等于经审计净利润，也不是所监控的 Apify Actor 的收入。
- B：产品自有官网给出明确收费方案，但无法证明已经有付费客户。
- C：免费竞品、等候名单、维护中或已停用页面，不能证明真实付费需求。
- 搜索可见性：已观察到具体竞争网站及其功能页面，但**没有**取得关键词 Volume/KD/CPC、实时 SERP 名次、页面级外链质量或真实非品牌流量数据；一律标记未验证。
- 所有值截至本研究日期。**Sitemap URL 首次出现与“关键词首次产生”是不同概念。**

## 1 — 值得优先调查：多域名 DNS/邮件安全/SSL 到期监控

**来源链接**：[Apify 邮件域名安全审计 Actor](https://apify.com/acinsoft/acinsoft-email-domain-security-audit)。2026-10-19 核查发现其标记为 **Deprecated（停用）**，网页显示月活跃用户 0；售价每次 $0.0075 不能作为真实收入证据。因此真正的付费证据必须来自**其他独立网站**。

| 独立竞品 | 可核实的真实收入快照 | 与拟做产品的关系 |
|---|---|---|
| [Kit.domains — TrustMRR](https://trustmrr.com/startup/kit-domains) | Stripe 连接核验；**MRR $118 / 4 个活跃订阅 / 累计 $1,463**；页面最后更新 2026-10-18 | 多域名到期、DNS 变化、SSL 提醒：相邻的连续付费问题，不是邮件审计一模一样的产品 |
| [DNS Monit — TrustMRR](https://trustmrr.com/startup/dns-monit) | Stripe 核验；**累计 $137**，当前无活跃订阅；更新 2026-10-17 | DNS 变化及 SPF/DKIM/DMARC，功能重合度高，但只证明历史成交 |
| [domainsecurityscanner.com — TrustMRR](https://trustmrr.com/startup/domainsecurityscanner-com) | Stripe 核验；**累计 $29**，当前无活跃订阅；更新 2026-10-14 | SPF、DMARC、DKIM、SSL 等即时健康检测，直接对应免费工具入口 |
| [mailampel.com](https://www.mailampel.com/en) | **定价证明，非付款证明**：首域名免费、额外域名 €5/月 | 免费诊断 + 持续变更监控是可复用的产品分层 |
| [EasyDMARC](https://easydmarc.com/pricing/businesses) | **定价证明，非付款证明**：Plus $44.99/月、Premium $89.99/月（按月计费） | 较复杂的邮件认证报告和托管配置，不能直接视为同档竞争 |

**复制一个“独立网站”而不是插件**：面向小网站主/建站公司，提供域名批量导入、DNS/SPF/DMARC/MX 状态快照、变化提醒、单客户报告。浏览器端提供免费单次检测；付费功能才是每天检查及历史差异与提醒。

**可行性**：基础 DNS 查询和日报可使用免费额度云函数/定时任务；但 SMTP 实连、证书链核验、RDAP/WHOIS 覆盖、邮件送达率需要服务器网络及额度核算，不能承诺完全零费用。先简化为 DNS 与 SSL 状态的可控监控，不承诺完整企业邮件投递分析。

**真实营销与 SEO 尚待验证**：独立工具页已经存在，说明有明显免费入口竞争；不代表目标关键词能排上去或付费客户会从 SEO 来。DR、原始外链数量不用于一票否决。最需要核对的**精确非品牌词**：`dns monitoring service`、`spf dmarc monitoring`、`monitoreo dns dominios`（墨西哥/西语）、`monitoramento dns dominio`（巴西葡语）。需记录 Volume、KD、CPC、实际前十落地页、落地页级反链质量与收费路径。

**判断**：优先级 **1 / 有独立同类持续订阅的收入证据，未证明本产品未来收入或 SEO 可行性**。

## 2 — 有真实订阅但维护成本需控制：品牌提及与竞品提及监控

**来源链接**：[Apify Brand Mentions Monitor](https://apify.com/ahmad_mahameed/brand-mentions-monitor)（已经出现在 Sitemap 队列）。

- [MentionDrop — TrustMRR](https://trustmrr.com/startup/mention-drop)：公开页面标记 Stripe 连接核验；**MRR $121、4 个活跃订阅、累计 $936**；更新 2026-10-18。提供品牌/竞品提及监控，标价 $29 和 $59/月。功能方向接近，但这**不证明** Apify Actor 自己有付费客户。
- 本项目现有 90 天趋势发现 `brand mentions monitor` 热度上升，但 5 年历史检查结果为 `historically_new=false`；**不是合格新词**，不要重新当作蓝海新词推送。
- 简化后的独立 Web SaaS：仅允许用户订阅有权限抓取的公开 RSS、新闻页或明确提供的来源；定时发现包含品牌词的新内容，按条发送提醒或日报。
- 风险：宣称全网实时覆盖、海量社媒内容、AI 全文摘要将引入付费 API 和维护负担，不符合低固定成本要求。
- 待查非品牌词：`brand mentions monitoring`、`brand mention alerts`、`monitoramento de marca`、`monitoreo menciones marca`。搜索量与 SERP 实际竞争未验证。

**判断**：优先级 **2 / 有独立同类实际 MRR，但必须坚持窄来源和预算上限**。

## 3 — 不作为首选：URL 转 Markdown / 网页知识包

**来源链接**：[Apify Website To LLM Knowledge Pack](https://apify.com/attainable_iota/website-to-llm-knowledge-pack) —— 当前显示 **Under maintenance**、0 月活跃用户；其每千结果 $0.50 为挂牌价格，不能证明成交。

- [WellMarked](https://wellmarked.io/) 独立 Web/API 竞品：Pro **$29/月**，Growth **$79/月**，提供单 URL、批量网页及网站爬取成 Markdown；**只验证了挂牌价格，未验证它的订阅收入**。
- [Firecrawl](https://www.firecrawl.dev/crawl) 提供类似的网页提取与爬虫功能；Hobby **$16/月（按年付费）**，有免费额度；**未验证该页面的产品收入**。
- [PlainMarkdown — TrustMRR](https://trustmrr.com/startup/plainmarkdown) 累计收入 **$126**，无活跃订阅，Stripe 连接核验；但其**实际产品是 Chrome 浏览器扩展**（[官网](https://plainmarkdown.com/) 有“Add to Chrome”）。用户明确排除任何插件，因此不能拿它充当独立 Web SaaS 的实际收款样本。其官网现标价 $10 一次性，TrustMRR 资料中的旧定价 $29/年与之不一致。
- 真正做独立网页上传 URL 后跨站爬取并输出 Markdown/JSONL，需要 JavaScript 渲染、反机器人、跨域网络访问、爬取范围限制、robots 协议遵守、出口 IP 与服务器资源；“完全静态零后端”不现实。
- 待查词：`website to markdown converter`、`url to markdown bulk`、`convert website to jsonl`。没有 Volume/KD/CPC 实数，不假称已验证 SEO。

**判断**：优先级 **3 / 竞品有收费功能，但直接同类独立网站的收款证据不足、持续算力成本较高**。

## 4 — 暂不开发：YouTube 缩略图批量下载

**来源链接**：[Apify YouTube Thumbnail Downloader](https://apify.com/atomus/youtube-thumbnail-downloader)，Actor 标价最低每千张 $2（随 Apify 方案有变化）；**未找到独立核验的该 Actor 付费客户收入**。

- [Wow1 免费批量工具](https://www.wow1.com/tool/youtube-thumbnail/bulk)：浏览器内一次处理 20 条视频并导出 ZIP。
- [MetaClipper](https://www.metaclipper.com/pricing)：免费处理 10 个 URL；标价 **$6/月 Pro**，但 Pro 页面明确说处在待上线的**等候名单阶段**，故不应当作已有付费用户或 MRR。
- [YThumbPro](https://ythumbpro.com/) 标价 **$9.99/月**，附加价值主要是 AI 分析、历史、竞品渠道追踪；同样未查到独立收款证据。持续 AI 调用可能增加成本。
- 只做批量缩略图 ZIP 基本属于免费功能；对用户 $300–$800/月的目标，不值得优先开发。
- 可核对的精确非品牌词：`bulk youtube thumbnail downloader`、`youtube thumbnail zip download`。不把免费搜索需求当作有付费需求。

**判断**：优先级 **4 / 仅有挂牌价和大量免费替代，暂停**。

## 本次结论与下一步

1. **进入下一轮产品验证：DNS/邮件安全/SSL 多域名监控**。真实付费成立，但需验证那些付费用户为何选择竞品、具体付费功能、销售路径和运营成本。
2. **备选：受限来源品牌提及监控**。已有 4 个活跃订阅的竞品案例，需优先评估稳定合法的数据来源而不是先做海量抓取。
3. URL→Markdown 与缩略图批量下载暂不建站；不要把浏览器插件、失效 Actor 或等待名单的收入纳入 Web SaaS 证据。
4. **真正的新词通过数依然为 0**。这些竞品机会是“既有付费需求的功能研究”，不是已经核实的蓝海新词。
5. Semrush 精确 Volume/KD/CPC、国家实际 SERP、非品牌流量、页面级自然外链质量及转化率都没有实测值，不填造数字。研究使用公开免费页面，没有新增付费 API 或服务器。

### 公开证据链接

- 原始监控与报告：[raw Sitemap 线索](https://github.com/chenmu2024/New-Keyword-Radar/blob/main/data/sitemap/queue.json) · [Sitemap triage](https://github.com/chenmu2024/New-Keyword-Radar/blob/main/reports/sitemap/triage.md)
- Stripe 关联收入：[Kit.domains](https://trustmrr.com/startup/kit-domains) · [DNS Monit](https://trustmrr.com/startup/dns-monit) · [DomainSecurityScanner](https://trustmrr.com/startup/domainsecurityscanner-com) · [MentionDrop](https://trustmrr.com/startup/mention-drop) · [PlainMarkdown——注意插件排除](https://trustmrr.com/startup/plainmarkdown)
- 真实网站定价：[mailampel](https://www.mailampel.com/en) · [EasyDMARC](https://easydmarc.com/pricing/businesses) · [WellMarked](https://wellmarked.io/) · [Firecrawl](https://www.firecrawl.dev/crawl) · [MetaClipper](https://www.metaclipper.com/pricing) · [Wow1](https://www.wow1.com/tool/youtube-thumbnail/bulk)。
