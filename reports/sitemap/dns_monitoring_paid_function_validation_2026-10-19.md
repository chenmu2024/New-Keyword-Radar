# DNS / SPF / DMARC 变更监控独立 Web SaaS — 付费功能验证
**研究日期：2026-10-19；研究模式：只读外部网页，分析结论写回雷达仓库。原有 18 条 Sitemap 源、关键词、Google Trends 阈值和自动化排期未修改。**

> **结论：继续研究「为小型建站公司管理客户域名」；不建议直接复制「免费 DNS 变更监控」。有独立同类真实付费，但目标受众的搜索需求/获客成本/页面级 SEO 难度还未通过实际 Semrush 和 SERP 全样本校验。这里不是已验证蓝海关键词，也不是开工决定。**

## 1. 明确的客户实际付费问题

客户不一定愿意为「查询 DNS」付费；真正愿意付费的可能是小机构的跨客户管理、集中报警和给客户交付月报等重复工作。

- 关联 Sitemap 原始候选：[Apify/Acinsoft email domain security audit](https://apify.com/acinsoft/acinsoft-email-domain-security-audit)。该 Actor 已停用、0 月活跃，不代表作者有收入；监控源仅用来发现功能名称。
- [Kit.domains TrustMRR](https://trustmrr.com/startup/kit-domains)：Stripe 关联公开页面 **$118 MRR、4 个活跃订阅、累计 $1,463**，最近显示 **2026-10-18** 更新。做域名到期、SSL、DNS 变化提醒；定价资料为 $39/$69/$126 每月；面向 MSP、营销机构、IT/托管团队。**不是原 Apify Actor 的收款。** 创始人公开表明有意出售，称产品开发已完成、获客及分销是瓶颈——增长不能因此视为已得到验证。
- [DNS Monit TrustMRR](https://trustmrr.com/startup/dns-monit)：Stripe 关联公开页面 **累计 $137、无活跃订阅、MRR 未报**，最后更新 **2026-10-17**。监测 DNS 变化、SPF/DKIM/DMARC、域名到期等。**只证明历史成交，不证明稳定订阅。**
- [PromptDNS 自有定价](https://promptdns.com/pricing/)：免费在线工具和单域名监控；Starter $19/月（3 域名）、Pro $49/月（10 域名）、Business $99/月（25 域名及 white-label 报告）。**这是挂牌价格，不是已收款。**
- [DDMARC 官方定价](https://ddmarc.com/pricing/)：2 域名免费；Protect $29/月（5 域名）；更高计划增加报告、历史、企业集成。**仅价格。**
- [Exomonitor 机构页](https://eng.exomonitor.com/for-agencies)：套餐 $19/月 10 客户站点、$29/月 30 站点、$49/月 100 站点，并提供批量导入、SSL/域名/DNS/可用性检查。**仅价格。**

**拒绝一个容易漏掉的反证**：[NsLookup DNS Monitoring](https://www.nslookup.io/dns-monitoring/) 目前公开宣称所有 DNS 记录变更、告警、历史、Webhooks **永久免费，域名不限量**。未实际注册验证其长期服务承诺；但单纯 DNS 检测和提醒已被强免费替代，不能依靠此功能卖订阅。

## 2. 真实在线竞争落地页（非实时排名与流量证明）

公开检索发现的具体功能/订价页面：

| 市场或查询意图 | 具体网页 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| 英文 DNS 变更监控 | https://www.nslookup.io/dns-monitoring/ | 免费直接同类工具 | 无法确认实时 Google 第几名、实际自然流量 |
| 英文 SPF/DMARC 免费入口→订阅 | https://promptdns.com/pricing/ | 低价订阅与付费分层 | 未验证真实付款和 SEO 来源 |
| 英文小型机构域名组合 | https://eng.exomonitor.com/for-agencies | 站点数、批量导入等对标功能 | 未验证真实 MRR 和 SERP 排位 |
| 英文邮件安全 DNS | https://ddmarc.com/pricing/ | 续费卖点为报告留存、计划检查 | 未验证独立自然流量 |
| 西语 DNS + SSL 网站组合 | https://expiroo.com/es/pricing/ | 西文定价页面，$9.99/月的全站监控套餐 | 无法说明墨西哥 SERP 竞争弱 |
| 西语 DNS 专项 | https://www.paessler.com/es/monitoring/technology/dns-monitoring | 成熟公司的西语落地页存在 | 未确认 MX 或 ES 搜索流量和排名 |
| 巴葡 DNS 专题 | https://www.dotcom-monitor.com/pt-br/aprenda-com-o-dotcom-monitor/glossario/o-que-e-monitoramento-de-dns/ | 葡语信息型内容已覆盖 | 不能说该词蓝海或无商业转化 |
| 葡语 DNS 监测工具 | https://app.diagnoseo.com/pt/tools/uptime-monitoring/dns/ | 葡语工具页有竞争 | 不能假设流量来自巴西而不是葡萄牙 |

**SERP 调查边界：**仅通过公开网页检索确认这些竞争落地页的存在，并非用固定国家/浏览器环境导出 Google 前 10 名；没有获取 Ahrefs/Semrush 的独立非品牌流量、关键词 Volume/KD/CPC、单页 referring domains 质量/排名 URL 的实际 backlinks 与位置。全部记为 **unknown**。不得凭 DR、外链总量或搜索摘要判断难度。

**建议只做一次有目的的 Semrush 批量检查，避免反复猜词：**
1. 美国：\`dns monitoring service\`、\`dns change monitoring\`、\`spf dmarc monitoring\`。
2. 墨西哥：\`monitoreo dns\`、\`monitoreo de dominios\`、\`alertas cambios dns\`。
3. 巴西：\`monitoramento dns\`、\`monitoramento de dominio\`、\`alerta alteração dns\`。
优先从这 9 个非品牌短语取 Volume/KD/CPC/真实排名页面；**至今未取得统计实数，不宣称高或低搜索量**。如果一批零/弱流量，则不能凭长尾词猜测推广机会，须重新回到竞品真实流量和获客渠道调查。

## 3. 合理可复制的「付费产品」而不是免费网站功能堆砌

建议区分真正免费的入口与持续收费：
- **免费入口**：单域名 A/AAAA/MX/NS/TXT 检测、SPF 与 DMARC 基础检查、PDF/文本摘要（首次诊断）。不宣称完整投递测试。
- **月度收费功能**：多个客户项目分组、CSV 导入、每天自动拍摄域名状态、旧值→新值对比、每客户独立通知邮箱、异常消除/确认、可下载的每月客户报告；计划从纯公共 DNS 状态开始。
- **暂不做**：平台侧自动改 DNS、邮箱真实送达率测试、全量 DKIM selectors 扫描、全球多探针每分钟检测、完整 SSL 证书链扫描、昂贵社媒/AI API。这些会拉高开发、投诉和运维成本。
- **竞争差异假设**：西葡语本地化+小机构「客户分组/每客户 PDF」，但尚无转化证据，需验证机构是否愿意替换免费工具。

### 小型收入测算，仅用于确定客单价和最低订阅人数

可实验的定价假设：免费 1 个客户组 / 3 域名；专业版 $19/月 15 域名；机构版 $39/月 60 域名+客户分组/报告。
- 10 个机构版客户 × $39 = **$390 月毛收入**；
- 20 个机构版客户 × $39 = **$780 月毛收入**；
- 15 个专业版客户 × $19 = **$285 月毛收入**。
**以上并非收入预测或利润**；Stripe 手续费、税、退款、邮件费、客服工时和运营服务费均未扣除。达到净赚 $300–$800/月不等于毛收入等额，需要真实获客/转化验证。TrustMRR 上 $118 MRR 的真实样本尚低于期望目标。

## 4. 免费运行可行性——分配额度而非「无限免费」

已确认官方当前技术资料：

| 组件 | 已确认的免费能力 | 设计约束与风险 |
|---|---|---|
| [Cloudflare Workers](https://developers.cloudflare.com/workers/platform/limits/) | Free 为 100,000 请求/日；每次免费调用最多 50 subrequests、CPU 10ms、一个账户最多 5 Cron Triggers | Worker 定时分批，不可让一轮 1,000 个域名全在单次触发内查询 |
| [Cloudflare DNS-over-HTTPS JSON API](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/) | 可以 HTTP 查询 DNS A/MX/TXT/NS 等公开信息，不必引入付费 DNS 数据 API | JSON 格式不是正式统一 RFC；缓存 TTL/解析器差异会产生假变更；关键检测须二次确认并遵守服务条款与限流 |
| [Cloudflare D1](https://developers.cloudflare.com/d1/platform/pricing/) | Free 为 5,000,000 行读取/日、100,000 行写入/日，5 GB 总存储 | 同步写入/事件历史需控制大小；达到免费日限额会直接报错 |
| [Resend](https://resend.com/pricing) | 免费 3,000 邮件/月、100 封/日 | 每日邮件数必须聚合、节流、限制频率；无法承诺不限量实时邮件；超额可能需要付费 |

**可以负担的模拟试点**：100 个域名 × 4 种 DNS 记录 × 每日 1 次 ≈ 400 次 DoH 查询/天；分批定时检查、只保留变更快照。该规模处在以上平台公开日额度的数量级范围内，**但尚未完成真实 Cloudflare 账号级压测**，仍需验证每次调用的 subrequests、调度、失败重试和发送配额；上线前不要宣称“每域名实时监控”或“100% 免费承诺”。

**安全边界**：只允许公有域名校验，规范化 IDN/Punycode，限制单租户域名数、分批速率和 HTTP 出站目标，避免任意 URL/内网 IP SSRF；每个付费客户必须验证其控制对应域名或获得授权；私有客户的邮件通知地址必须验证。异常触发去重，出错时不得将上游 DoH/邮件服务不可用误报为 DNS 已被恶意篡改。

## 5. 当前决策与验收条件

- 商业付费需求：**部分成立**（相邻产品有真实 Stripe MRR，直接更小型监控产品有历史收款）；并没有证明这一全新网站可以复制相同获客。
- 免费替代和功能竞争：**强**（NsLookup 无限制免费监控声明）；不允许再将「DNS 变更提醒」本身当作独有付费卖点。
- 付费客群：**机构多客户管理 + 报告为假设**，官网定价页有功能细分，但未访谈或验证真实付费意愿。
- 技术与低成本：**可做有限规模概念验证**，前提是按域名数/每天频率设上限、严控邮件。
- SEO/获客：**未通过**，缺少国家级关键词真实 Volume/KD/CPC、SERP 首页完整竞争数据、目标页面级外链质量及渠道转化数据。
- 新词：**不是新词项目**；本调查仅用于有真实收入证据的可复制小型 SaaS，不改 Sitemap 新词资格。

**下一个客观选择**：先拿 9 个指定短语的三国 Semrush 数据或竞品非品牌流量页面；若低则侧重小型建站公司直接获客（已经有 10–50 个客户域名的服务商，免费试用3个域名后升级），不要仅靠泛词 SEO 引流。正式开发/独立新域名决策等搜索和渠道验证之后再做。

### 证据的时效性
此报告核查时间：2026-10-19。真实收益数据仅是对应页面在核查当日展示的最近 Stripe 关联更新快照，不保证将来金额相同；厂商报价可随时变化。页面存在、搜索检索命中、Semrush 排名关键词与月搜索量是不同的验证对象。
