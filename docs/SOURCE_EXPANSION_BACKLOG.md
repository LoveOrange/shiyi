# Shiyi 信息源扩展 Backlog

- 所有者：Shiyi
- 消费方：Briefly
- 状态：规划候选，尚未授权批量启用
- 更新时间：2026-08-27

本文件是跨 Category 候选来源及其接入状态的唯一清单。它为每个核心
Category 建立 20–30 个高质量来源的候选组合，由 Shiyi 完成来源侦察、
许可确认、适配、抓取、规范化和中性初分。Briefly 的覆盖目标与下游验收
保留在
[`SOURCE_EXPANSION_TODO.md`](https://github.com/LoveOrange/briefly-ai-weekly/blob/main/docs/SOURCE_EXPANSION_TODO.md)。

候选行不是运行时 `Source`。只有满足接入 Definition of Done 后，来源才可
加入 `BUILTIN_SOURCES` 或生产 `CaptureConfig`。

## 1. 所有权与边界

- Shiyi 是来源系统：负责来源发现、适配、抓取、重试、去重、溯源、规范化，以及可选的中性摘要、Categories 和 Tags。
- Briefly 是编辑判断系统：负责把 Items 聚合成 Event，选择主 Category 和 Tags，在统一 `0..100` 尺度上评分，并按窗口、Category、门槛和 Top N 发布。
- Shiyi 的 Category 只是候选提示，不能直接决定 Briefly 是否发布；来源进入抓取池，也不代表事件自动达标。
- 同一来源能够覆盖多个 Category 时只注册一次。下表会在多个组合中引用它，但实现时必须共享一个稳定 `source_id`。
- 当前 `ai` Daily/Weekly 继续是唯一已上线选择配置。其他 Category 先积累样本和验证需求，不因此复制管线或自动新增栏目。
- 这里的 `tech-business` 与 `tech-policy-macro` 是解释技术产业化的 Lens，不是把 Briefly 扩张成综合财经或政治新闻站。

## 2. 统一状态与优先级

| 标记 | 含义 |
|---|---|
| `[x]` | 已在 Shiyi 内建注册表中，可继续做质量复核 |
| `[ ] P0` | 第一批接入：第一方、稳定、公开，且对目标用户决策价值高 |
| `[ ] P1` | 第二批接入：高价值，但需要专用适配器、论文筛选或更多规范化工作 |
| `[ ] P2` | 第三批雷达：二手媒体、社区、付费墙或授权条件需要确认；默认不直接全文抓取 |
| `[ ] Shared` | 已在另一 Category 计划接入；此处只复用，不再注册 |

来源角色：

- `primary`：公司、实验室、项目或机构的原始发布；
- `research`：论文、期刊、学术机构与科研计划；
- `regulator/data`：监管、政策、统计和结构化数据；
- `secondary-radar`：用于发现、交叉验证和影响证据，不能替代原始来源。

## 3. 每个来源的 Definition of Done

每一行只有在以下事项全部完成后，才能从候选变成定时抓取来源：

- [ ] 确认清晰的 Briefly 使用场景，以及它服务哪一种用户判断；
- [ ] 确认稳定入口、来源原生 item identity、canonical URL 和可重复获取方式；
- [ ] 确认公开抓取、API、RSS 或授权条款；付费墙与禁止自动化的站点只做人工/授权雷达；
- [ ] 选择最简单适配方式：`RSS`、`API`、`index→detail`、`document` 或既有 GitHub/文档适配器；
- [ ] 保存有界 fixture，覆盖窗口、最大条数、详情失败、时间戳、分页和重复运行；
- [ ] 输出合格 `content-item.v1`：正文或明确 incomplete fallback、绝对来源 URL、发布时间、provenance、hash 和 readiness；
- [ ] 用至少 28 天样本人工抽检中性分类，避免把营销文、招聘、活动预告和常规促销误判为重要进展；
- [ ] 将真实 Items 送入 Briefly，验证 Event 聚合、主 Category、Tags、分数分布和达标率；
- [ ] 通过重复来源、单一公司集中度和低信号占比检查后，再启用定时任务。

## 4. 目标组合总览

| Category | 目标数 | 组合重点 | 首批建议 |
|---|---:|---|---:|
| `ai` | 25 | 模型公司、研究机构、开发工具、论文雷达 | 补 5 |
| `semiconductors` | 20 | 设计、制造、设备、EDA、产业组织 | 6 |
| `robotics` | 20 | 具身模型、本体、自动化、科研与产业数据 | 6 |
| `biotechnology` | 20 | 监管、研究、平台公司、合成生物与药物研发 | 6 |
| `energy` | 20 | 储能、核能/聚变、电力、研究与产业数据 | 6 |
| `advanced-materials` | 20 | 论文、国家实验室、关键材料与产业公司 | 5 |
| `quantum` | 20 | 硬件路线、软件栈、科研计划与论文 | 6 |
| `space` | 20 | 航天机构、发射、卫星、空间站与监管 | 6 |
| `tech-business` | 20 | 公司披露、竞争监管、融资与产业结构 | 6 |
| `tech-policy-macro` | 25 | 科技监管、产业政策、贸易、利率与宏观数据 | 8 |

> 数量是每个 Category 的覆盖组合，不是独立注册数。共享来源去重后，实际新增 `source_id` 会少于 210 个。

## 5. Category TODO

### 5.1 `ai`：25 个

当前策略：保留已覆盖的官方 AI 与开发工具来源，补齐 Meta、NVIDIA、AWS、Apple 和研究雷达。Hacker News 等社区只做发现信号，不计入本组合的 25 个高质量主来源。

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [x] | `openai-news` | OpenAI News | primary | <https://openai.com/news/> | 复核现有产出 |
| [x] | `anthropic-news` | Anthropic News | primary | <https://www.anthropic.com/news> | 复核现有产出 |
| [x] | `deepmind-blog` | Google DeepMind | research | <https://deepmind.google/blog/rss.xml> | 与 robotics 共享 |
| [x] | `google-research-blog` | Google Research | research | <https://research.google/blog/rss/> | 复核现有产出 |
| [x] | `huggingface-blog` | Hugging Face Blog | primary | <https://huggingface.co/blog> | 复核现有产出 |
| [x] | `microsoft-ai-blog` | Microsoft AI | primary | <https://blogs.microsoft.com/ai/> | 复核现有产出 |
| [x] | `mistral-news` | Mistral AI | primary | <https://mistral.ai/news> | 复核现有产出 |
| [x] | `cohere-blog` | Cohere | primary | <https://cohere.com/blog> | 复核现有产出 |
| [x] | `deepseek-news` | DeepSeek | primary | <https://api-docs.deepseek.com/updates> | 复核现有产出 |
| [x] | `qwen-model-releases` | Qwen Model Releases | primary | <https://docs.qwencloud.com/changelog/models.md> | 复核现有产出 |
| [x] | `kimi-research` | Kimi Research | research | <https://www.kimi.com/en/blog/> | 复核现有产出 |
| [x] | `z-ai-blog` | Z.ai Release Notes | primary | <https://docs.z.ai/release-notes/new-released.md> | 复核现有产出 |
| [x] | `minimax-model-releases` | MiniMax Model Releases | primary | <https://platform.minimaxi.com/docs/release-notes/models.md> | 复核现有产出 |
| [x] | `bytedance-seed-blog` | ByteDance Seed | research | <https://seed.bytedance.com/zh/blog> | 复核现有产出 |
| [x] | `gemini-api-changelog` | Gemini API Changelog | primary | <https://ai.google.dev/gemini-api/docs/changelog> | 产品能力事实源 |
| [x] | `cursor-changelog` | Cursor Changelog | primary | <https://www.cursor.com/changelog> | AI coding lane |
| [x] | `github-copilot-changelog` | GitHub Copilot Changelog | primary | <https://github.blog/changelog/label/copilot/> | AI coding lane |
| [x] | `codex-releases` | OpenAI Codex Releases | primary | <https://github.com/openai/codex/releases> | AI coding lane |
| [x] | `claude-code-releases` | Claude Code Releases | primary | <https://github.com/anthropics/claude-code/releases> | AI coding lane |
| [ ] P0 | `meta-ai-blog` | Meta AI | primary | <https://ai.meta.com/blog/> | 官方研究与模型发布 |
| [ ] P0 | `nvidia-developer-ai` | NVIDIA Developer Blog | primary | <https://developer.nvidia.com/blog/> | 与 semiconductors、robotics 共享；需规则过滤 AI 标签 |
| [ ] P0 | `aws-machine-learning-blog` | AWS Machine Learning Blog | primary | <https://aws.amazon.com/blogs/machine-learning/> | 过滤客户案例与促销 |
| [ ] P0 | `apple-machine-learning-research` | Apple Machine Learning Research | research | <https://machinelearning.apple.com/> | 论文与工程研究 |
| [ ] P1 | `stanford-hai-news` | Stanford HAI | research | <https://hai.stanford.edu/news> | 研究与政策交叉，避免活动噪声 |
| [ ] P1 | `huggingface-daily-papers` | Hugging Face Daily Papers | research | <https://huggingface.co/papers> | 只能做论文发现；Briefly 不按热度直接达标 |

AI 首批新增：

- [ ] 接入 `meta-ai-blog`、`nvidia-developer-ai`、`aws-machine-learning-blog`、`apple-machine-learning-research`；
- [ ] 对 `stanford-hai-news` 做 28 天噪声率试采；
- [ ] 单独评估 Daily Papers 的候选召回率和人工筛选成本。

### 5.2 `semiconductors`：20 个

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P0 | `nvidia-newsroom` | NVIDIA Newsroom | primary | <https://nvidianews.nvidia.com/rss> | 官方 RSS；与 AI/robotics 的开发博客分开但同机构 |
| [ ] P0 | `amd-newsroom` | AMD Newsroom | primary | <https://www.amd.com/en/newsroom.html> | 芯片、平台与财报前事实 |
| [ ] P0 | `intel-newsroom` | Intel Newsroom | primary | <https://newsroom.intel.com/> | 制程、产品、代工与组织变化 |
| [ ] P0 | `tsmc-press` | TSMC Press Releases | primary | <https://pr.tsmc.com/english/news> | 制程、产能、投资 |
| [ ] P0 | `asml-news` | ASML News | primary | <https://www.asml.com/en/news> | 光刻、供应链、技术路线 |
| [ ] P0 | `samsung-semiconductor-news` | Samsung Semiconductor | primary | <https://semiconductor.samsung.com/news-events/> | 存储、代工、先进封装 |
| [ ] P1 | `sk-hynix-newsroom` | SK hynix Newsroom | primary | <https://news.skhynix.com/> | HBM 与存储 |
| [ ] P1 | `micron-news` | Micron News Releases | primary | <https://investors.micron.com/news-releases> | 存储与资本开支 |
| [ ] P1 | `arm-newsroom` | Arm Newsroom | primary | <https://newsroom.arm.com/> | 架构、数据中心、终端 |
| [ ] P1 | `qualcomm-releases` | Qualcomm Releases | primary | <https://www.qualcomm.com/news/releases> | 边缘计算与终端芯片 |
| [ ] P1 | `broadcom-releases` | Broadcom Releases | primary | <https://investors.broadcom.com/press-releases> | 网络、定制芯片、基础设施软件 |
| [ ] P1 | `applied-materials-newsroom` | Applied Materials | primary | <https://newsroom.appliedmaterials.com/> | 设备与材料工程 |
| [ ] P1 | `lam-research-newsroom` | Lam Research | primary | <https://newsroom.lamresearch.com/> | 晶圆设备 |
| [ ] P1 | `kla-releases` | KLA Releases | primary | <https://ir.kla.com/news-events/press-releases> | 量测与良率 |
| [ ] P1 | `imec-press` | imec Press | research | <https://www.imec-int.com/en/press> | 与 materials、quantum 共享 |
| [ ] P1 | `cea-leti-news` | CEA-Leti News | research | <https://www.leti-cea.com/cea-tech/leti/english/Pages/News/News.aspx> | 与 materials 共享；先验证入口稳定性 |
| [ ] P0 | `semi-newsroom` | SEMI Newsroom | secondary-radar | <https://www.semi.org/en/news-media-press/newsroom> | 产业组织与供应链信号 |
| [ ] P0 | `sia-latest-news` | Semiconductor Industry Association | secondary-radar | <https://www.semiconductors.org/news-events/latest-news/> | 产业数据与政策 |
| [ ] P1 | `synopsys-newsroom` | Synopsys Newsroom | primary | <https://news.synopsys.com/> | EDA、IP、设计工具 |
| [ ] P1 | `cadence-newsroom` | Cadence Newsroom | primary | <https://www.cadence.com/en_US/home/company/newsroom.html> | EDA、系统设计与 AI 设计工具 |

半导体首批：

- [ ] 先接 `nvidia-newsroom`、`amd-newsroom`、`tsmc-press`、`asml-news`、`semi-newsroom`、`sia-latest-news`；
- [ ] 验证同一发布在公司 newsroom、IR 和产业媒体间的 Event 去重；
- [ ] 为产品发布、量产、制程节点、产能/资本开支、出口限制分别建立中性 Tags，不在 Shiyi 产生重要性分数。

### 5.3 `robotics`：20 个

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P0 | `boston-dynamics-news` | Boston Dynamics News | primary | <https://bostondynamics.com/news/> | 产品、部署与研究 |
| [ ] P0 | `figure-news` | Figure | primary | <https://www.figure.ai/news> | 人形机器人 |
| [ ] P0 | `agility-robotics-news` | Agility Robotics | primary | <https://www.agilityrobotics.com/news> | 仓储与量产部署 |
| [ ] P0 | `apptronik-releases` | Apptronik | primary | <https://apptronik.com/company/press-releases> | 人形机器人与合作 |
| [ ] P1 | `one-x-discover` | 1X | primary | <https://www.1x.tech/discover> | 家用具身智能；过滤品牌内容 |
| [ ] P1 | `sanctuary-ai-news` | Sanctuary AI | primary | <https://www.sanctuary.ai/news> | 通用机器人与控制系统 |
| [ ] P0 | `unitree-news` | Unitree | primary | <https://www.unitree.com/news/> | 中国本体与产品进展 |
| [ ] P1 | `ubtech-news` | UBTECH | primary | <https://www.ubtrobot.com/news> | 工业与商用部署 |
| [ ] P0 | `physical-intelligence-blog` | Physical Intelligence | research | <https://www.physicalintelligence.company/blog> | 基础模型与机器人学习 |
| [ ] P1 | `skild-ai-blog` | Skild AI | research | <https://www.skild.ai/blog> | 机器人基础模型 |
| [ ] P1 | `tri-news` | Toyota Research Institute | research | <https://www.tri.global/news> | 研究与真实场景 |
| [ ] P1 | `open-robotics-blog` | Open Robotics | research | <https://www.openrobotics.org/blog> | ROS/Gazebo 生态 |
| [ ] P2 | `ros-discourse` | ROS Discourse | secondary-radar | <https://discourse.ros.org/> | 社区雷达；只收公告类板块 |
| [ ] Shared | `nvidia-developer-ai` | NVIDIA Developer Blog | primary | <https://developer.nvidia.com/blog/> | 复用 AI 来源，按 robotics 标签分类 |
| [ ] Shared | `deepmind-blog` | Google DeepMind | research | <https://deepmind.google/blog/rss.xml> | 已存在，复用机器人研究内容 |
| [ ] P0 | `ifr-news` | International Federation of Robotics | regulator/data | <https://ifr.org/> | 行业装机与市场数据 |
| [ ] P1 | `ieee-ras-news` | IEEE Robotics & Automation Society | research | <https://www.ieee-ras.org/about-ras/latest-news> | 学术与产业组织 |
| [ ] P1 | `science-robotics` | Science Robotics | research | <https://www.science.org/journal/scirobotics> | 论文元数据/摘要，确认许可 |
| [ ] P1 | `arxiv-cs-ro` | arXiv cs.RO | research | <https://export.arxiv.org/api/query?search_query=cat:cs.RO> | API；需二次筛选，不能逐篇入选 |
| [ ] P2 | `robot-report` | The Robot Report | secondary-radar | <https://www.therobotreport.com/> | 产业发现与交叉验证 |

机器人首批：

- [ ] 先接 `boston-dynamics-news`、`figure-news`、`apptronik-releases`、`unitree-news`、`physical-intelligence-blog`、`ifr-news`；
- [ ] 用“演示视频”与“真实部署/量产/性能证据”对照样本校准 Briefly 分数；
- [ ] 对 arXiv 建立主题查询和最大条数，不允许全量论文冲垮 Event 管线。

### 5.4 `biotechnology`：20 个

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P0 | `fda-newsroom` | U.S. FDA Newsroom | regulator/data | <https://www.fda.gov/news-events/fda-newsroom> | 批准、安全与监管事实源 |
| [ ] P0 | `nih-news-releases` | NIH News Releases | research | <https://www.nih.gov/news-events/news-releases> | 公共研究与临床进展 |
| [ ] P0 | `ema-news` | European Medicines Agency | regulator/data | <https://www.ema.europa.eu/en/news> | 欧盟药物监管 |
| [ ] P0 | `broad-institute-news` | Broad Institute | research | <https://www.broadinstitute.org/news> | 基因组、工具与疾病机制 |
| [ ] P0 | `arc-institute-news` | Arc Institute | research | <https://arcinstitute.org/news> | 开放科研与 AI 生物交叉 |
| [ ] P1 | `biorxiv-latest` | bioRxiv | research | <https://www.biorxiv.org/rss/latest.xml> | 预印本；需要领域查询、质量门槛和撤稿状态 |
| [ ] P1 | `medrxiv-latest` | medRxiv | research | <https://www.medrxiv.org/rss/latest.xml> | 临床预印本；明确“未经同行评议” |
| [ ] P1 | `nature-biotechnology` | Nature Biotechnology | research | <https://www.nature.com/nbt/> | 只取许可允许的元数据/摘要 |
| [ ] P1 | `cell-press-news` | Cell Press | research | <https://www.cell.com/press> | 新闻稿与论文落地页 |
| [ ] P1 | `science-translational-medicine` | Science Translational Medicine | research | <https://www.science.org/journal/scitranslmed> | 只取许可范围内内容 |
| [ ] P1 | `crispr-therapeutics-releases` | CRISPR Therapeutics | primary | <https://crisprtx.com/about-us/press-releases-and-presentations> | 临床与监管里程碑 |
| [ ] P1 | `illumina-news` | Illumina News Center | primary | <https://www.illumina.com/company/news-center.html> | 测序平台与产业变化 |
| [ ] P1 | `twist-bioscience-releases` | Twist Bioscience | primary | <https://investors.twistbioscience.com/news-releases> | 合成 DNA 与平台进展 |
| [ ] P1 | `ginkgo-releases` | Ginkgo Bioworks | primary | <https://investors.ginkgobioworks.com/news-releases> | 合成生物平台；过滤普通合作稿 |
| [ ] P0 | `recursion-news` | Recursion | primary | <https://www.recursion.com/news> | AI 药物研发 |
| [ ] P0 | `insitro-news` | insitro | primary | <https://www.insitro.com/> | AI/机器学习与药物发现；确认稳定 news 入口 |
| [ ] P1 | `moderna-releases` | Moderna | primary | <https://investors.modernatx.com/news/news-details> | 平台、临床与监管事件 |
| [ ] P1 | `biontech-releases` | BioNTech | primary | <https://investors.biontech.de/news-releases> | 平台、临床与监管事件 |
| [ ] P2 | `stat-biotech` | STAT Biotechnology | secondary-radar | <https://www.statnews.com/biotechnology/> | 付费墙/授权确认；默认只做发现 |
| [ ] P2 | `synbiobeta-read` | SynBioBeta | secondary-radar | <https://www.synbiobeta.com/read> | 合成生物产业雷达 |

生物科技首批：

- [ ] 先接 `fda-newsroom`、`nih-news-releases`、`ema-news`、`broad-institute-news`、`arc-institute-news`、`recursion-news`；
- [ ] 将“预印本、同行评议、临床阶段、监管批准”作为事实状态，不把它们折成 Shiyi 分数；
- [ ] 对公司新闻用试验注册、论文和监管文件交叉验证，避免仅凭公司宣称形成高分 Event。

### 5.5 `energy`：20 个

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P0 | `doe-newsroom` | U.S. Department of Energy | regulator/data | <https://www.energy.gov/newsroom> | 研究、产业政策与项目 |
| [ ] P0 | `arpa-e-news` | ARPA-E | research | <https://arpa-e.energy.gov/news-and-events/news-and-insights> | 高风险能源技术与项目结果 |
| [ ] P0 | `nrel-news` | National Renewable Energy Laboratory | research | <https://www.nrel.gov/news/> | 光伏、储能、电网与交通 |
| [ ] P0 | `iea-news` | International Energy Agency | regulator/data | <https://www.iea.org/news> | 全球能源数据与政策 |
| [ ] P1 | `irena-news` | IRENA | regulator/data | <https://www.irena.org/News> | 可再生能源部署与成本 |
| [ ] P0 | `eia-today-in-energy` | U.S. EIA Today in Energy | regulator/data | <https://www.eia.gov/todayinenergy/> | 结构化能源数据解释 |
| [ ] P1 | `nature-energy` | Nature Energy | research | <https://www.nature.com/nenergy/> | 论文元数据/摘要，确认许可 |
| [ ] P1 | `cell-joule` | Joule | research | <https://www.cell.com/joule/home> | 能源研究与产业分析 |
| [ ] P0 | `catl-news` | CATL News | primary | <https://www.catl.com/en/news/> | 电池、储能与量产 |
| [ ] P1 | `byd-global-news` | BYD Global News | primary | <https://www.bydglobal.com/en/news> | 电池、汽车与能源系统；过滤车型营销 |
| [ ] P1 | `quantumscape-releases` | QuantumScape | primary | <https://ir.quantumscape.com/resources/press-releases> | 固态电池与验证进展 |
| [ ] P1 | `form-energy-news` | Form Energy | primary | <https://formenergy.com/news/> | 长时储能与工厂部署 |
| [ ] P1 | `redwood-materials-news` | Redwood Materials | primary | <https://www.redwoodmaterials.com/news> | 回收与电池材料供应链 |
| [ ] P0 | `cfs-news` | Commonwealth Fusion Systems | primary | <https://www.cfs.energy/news-and-media/> | 聚变工程与融资/建设里程碑 |
| [ ] P0 | `iter-news` | ITER | research | <https://www.iter.org/news> | 国际聚变工程事实源 |
| [ ] P1 | `helion-news` | Helion | primary | <https://www.helionenergy.com/news/> | 私营聚变；要求第三方证据 |
| [ ] P0 | `nrc-news` | U.S. Nuclear Regulatory Commission | regulator/data | <https://www.nrc.gov/reading-rm/doc-collections/news/> | 核能许可与安全事实源 |
| [ ] P2 | `utility-dive` | Utility Dive | secondary-radar | <https://www.utilitydive.com/> | 电力产业发现 |
| [ ] P2 | `pv-magazine` | pv magazine | secondary-radar | <https://www.pv-magazine.com/> | 光伏产业发现 |
| [ ] P2 | `carbon-brief` | Carbon Brief | secondary-radar | <https://www.carbonbrief.org/> | 气候、能源政策与数据解释 |

能源首批：

- [ ] 先接 `doe-newsroom`、`arpa-e-news`、`nrel-news`、`iea-news`、`eia-today-in-energy`、`catl-news`；
- [ ] 将实验指标、样机、示范项目、商业量产分成不同 Tags；
- [ ] 对能量密度、成本、效率等指标保存原始条件和单位，禁止脱离测试条件比较。

### 5.6 `advanced-materials`：20 个

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P1 | `nature-materials` | Nature Materials | research | <https://www.nature.com/nmat/> | 论文元数据/摘要，确认许可 |
| [ ] P1 | `advanced-materials-wiley` | Advanced Materials | research | <https://advanced.onlinelibrary.wiley.com/journal/15214095> | 论文元数据/摘要，需主题筛选 |
| [ ] P1 | `materials-today` | Materials Today | research | <https://www.materialstoday.com/> | 研究与产业交叉 |
| [ ] P0 | `acs-pressroom` | American Chemical Society Pressroom | research | <https://www.acs.org/pressroom.html> | 研究新闻；追溯原论文 |
| [ ] P1 | `mrs-bulletin` | Materials Research Society | research | <https://www.mrs.org/bulletin> | 材料研究综述与社区 |
| [ ] P0 | `doe-science-news` | DOE Office of Science | research | <https://science.osti.gov/News> | 与 energy 共享机构但单独稳定入口 |
| [ ] P1 | `materials-project` | Materials Project | research | <https://materialsproject.org/> | 验证更新/公告入口和 API 许可 |
| [ ] P1 | `mit-mrl-news` | MIT Materials Research Laboratory | research | <https://mrl.mit.edu/news-events> | 过滤活动，仅取研究成果 |
| [ ] P0 | `slac-news` | SLAC News | research | <https://www6.slac.stanford.edu/news> | 材料表征、能源与量子交叉 |
| [ ] P0 | `nist-materials` | NIST Materials | regulator/data | <https://www.nist.gov/topics/materials> | 标准、测量与研究 |
| [ ] P0 | `usgs-mineral-commodities` | USGS Mineral Commodity Summaries | regulator/data | <https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries> | 年度文档与关键矿物数据 |
| [ ] P1 | `critical-materials-institute` | Critical Materials Institute | research | <https://www.ameslab.gov/cmi/news> | 关键材料与替代路线 |
| [ ] Shared | `imec-press` | imec Press | research | <https://www.imec-int.com/en/press> | 复用 semiconductors 来源 |
| [ ] Shared | `cea-leti-news` | CEA-Leti News | research | <https://www.leti-cea.com/cea-tech/leti/english/Pages/News/News.aspx> | 复用 semiconductors 来源 |
| [ ] P1 | `basf-releases` | BASF News Releases | primary | <https://www.basf.com/global/en/media/news-releases> | 过滤常规公司新闻与营销 |
| [ ] P1 | `dow-news` | Dow News | primary | <https://corporate.dow.com/en-us/news.html> | 先进聚合物与工业材料 |
| [ ] P1 | `corning-news` | Corning News | primary | <https://www.corning.com/worldwide/en/about-us/news-events.html> | 光学、玻璃、半导体材料 |
| [ ] P1 | `umicore-news` | Umicore Newsroom | primary | <https://www.umicore.com/en/newsroom/> | 电池与关键材料循环 |
| [ ] P1 | `rio-tinto-releases` | Rio Tinto Releases | primary | <https://www.riotinto.com/news/releases> | 关键矿物供应与项目 |
| [ ] P1 | `nature-reviews-materials` | Nature Reviews Materials | research | <https://www.nature.com/natrevmats/> | 综述型信号，许可范围内使用 |

先进材料首批：

- [ ] 先接 `acs-pressroom`、`doe-science-news`、`slac-news`、`nist-materials`、`usgs-mineral-commodities`；
- [ ] 建立“性能突破—可制造性—原料约束—成本—规模化”Tags，避免只因实验室峰值指标获得高分；
- [ ] 对年度/季度文档使用 document adapter，并按文档版本而非页面更新时间去重。

### 5.7 `quantum`：20 个

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P0 | `ibm-quantum-research` | IBM Quantum Research | research | <https://research.ibm.com/quantum-computing> | 硬件、纠错与软件栈 |
| [ ] P0 | `google-quantum-ai` | Google Quantum AI | research | <https://quantumai.google/> | 硬件与纠错；验证稳定发布入口 |
| [ ] P0 | `microsoft-quantum-blog` | Microsoft Quantum Blog | research | <https://azure.microsoft.com/en-us/blog/quantum/> | 硬件路线与 Azure Quantum |
| [ ] P1 | `aws-quantum-blog` | AWS Quantum Computing Blog | primary | <https://aws.amazon.com/blogs/quantum-computing/> | 研究与云服务，过滤推广稿 |
| [ ] P0 | `quantinuum-news` | Quantinuum News | primary | <https://www.quantinuum.com/news> | 离子阱、软件与纠错 |
| [ ] P0 | `ionq-releases` | IonQ News | primary | <https://investors.ionq.com/news/default.aspx> | 性能、订单与公司披露分开标注 |
| [ ] P1 | `rigetti-releases` | Rigetti Releases | primary | <https://investors.rigetti.com/news-releases> | 超导硬件 |
| [ ] P1 | `dwave-releases` | D-Wave Releases | primary | <https://ir.dwavesys.com/news-releases> | 退火与门模型不能混同比较 |
| [ ] P1 | `psiquantum-news` | PsiQuantum News | primary | <https://www.psiquantum.com/news> | 光量子与制造合作 |
| [ ] P1 | `xanadu-blog` | Xanadu Blog | research | <https://www.xanadu.ai/blog> | 光量子与软件 |
| [ ] P1 | `quera-news` | QuEra News | primary | <https://www.quera.com/news> | 中性原子路线 |
| [ ] P1 | `atom-computing-news` | Atom Computing | primary | <https://atom-computing.com/news> | 中性原子路线 |
| [ ] P1 | `pasqal-newsroom` | Pasqal Newsroom | primary | <https://www.pasqal.com/newsroom/> | 中性原子与商业部署 |
| [ ] P1 | `alice-bob-newsroom` | Alice & Bob | primary | <https://alice-bob.com/newsroom/> | 猫量子比特与容错路线 |
| [ ] P0 | `nist-quantum` | NIST Quantum Information Science | regulator/data | <https://www.nist.gov/topics/quantum-information-science> | 标准、测量与研究 |
| [ ] P0 | `doe-quantum` | DOE Quantum Information Science | research | <https://www.energy.gov/topics/quantum-information-science> | 国家项目与研究设施 |
| [ ] P1 | `darpa-news` | DARPA News | research | <https://www.darpa.mil/news> | 与其他领域共享；必须按 program/quantum 过滤 |
| [ ] P1 | `arxiv-quant-ph` | arXiv quant-ph | research | <https://export.arxiv.org/api/query?search_query=cat:quant-ph> | API；主题与引用质量二次筛选 |
| [ ] P1 | `prx-quantum` | PRX Quantum | research | <https://journals.aps.org/prxquantum/> | 论文元数据/摘要，确认许可 |
| [ ] P1 | `npj-quantum-information` | npj Quantum Information | research | <https://www.nature.com/npjqi/> | 论文元数据/摘要，确认许可 |

量子首批：

- [ ] 先接 `ibm-quantum-research`、`google-quantum-ai`、`microsoft-quantum-blog`、`quantinuum-news`、`nist-quantum`、`doe-quantum`；
- [ ] 保存物理量定义、实验条件和路线类型，禁止只按“qubit 数”横向排名；
- [ ] 将论文结果、硬件交付、云端可用、客户订单分别标注，Briefly 再判断产业意义。

### 5.8 `space`：20 个

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P0 | `nasa-news` | NASA News | primary | <https://www.nasa.gov/news/> | 任务、科学与工程事实源 |
| [ ] P0 | `esa-newsroom` | ESA Newsroom | primary | <https://www.esa.int/Newsroom> | 欧洲任务与发射 |
| [ ] P0 | `isro-press-releases` | ISRO Press Releases | primary | <https://www.isro.gov.in/PressRelease.html> | 印度任务；验证发布时间规范化 |
| [ ] P1 | `jaxa-press` | JAXA Press Releases | primary | <https://global.jaxa.jp/press/> | 日本任务与研究 |
| [ ] P1 | `cnsa-english-news` | CNSA English | primary | <http://www.cnsa.gov.cn/english/> | 中国航天；验证 HTTPS/入口稳定性与中文原文关联 |
| [ ] P0 | `spacex-updates` | SpaceX Updates | primary | <https://www.spacex.com/updates/> | 发射与项目更新；需稳定 item identity |
| [ ] P0 | `blue-origin-news` | Blue Origin News | primary | <https://www.blueorigin.com/news> | 发射、发动机与空间站 |
| [ ] P0 | `rocket-lab-updates` | Rocket Lab Updates | primary | <https://rocketlabcorp.com/updates/> | 发射、卫星平台与任务 |
| [ ] P1 | `ula-news` | United Launch Alliance News | primary | <https://www.ulalaunch.com/news> | 发射与运载器 |
| [ ] P1 | `arianespace-press` | Arianespace Press Releases | primary | <https://www.arianespace.com/press-release/> | 欧洲商业发射 |
| [ ] P1 | `firefly-news` | Firefly Aerospace News | primary | <https://fireflyspace.com/news/> | 发射与月球任务 |
| [ ] P0 | `axiom-space-newsroom` | Axiom Space Newsroom | primary | <https://www.axiomspace.com/newsroom> | 商业空间站与载人任务 |
| [ ] P1 | `sierra-space-newsroom` | Sierra Space Newsroom | primary | <https://www.sierraspace.com/newsroom/> | 飞船与空间站 |
| [ ] P1 | `vast-updates` | Vast Updates | primary | <https://www.vastspace.com/updates> | 商业空间站 |
| [ ] P1 | `varda-news` | Varda News | primary | <https://www.varda.com/news> | 在轨制造与返回 |
| [ ] P1 | `planet-news` | Planet News | primary | <https://www.planet.com/pulse/> | 地球观测；确认新闻与内容营销边界 |
| [ ] P1 | `maxar-releases` | Maxar Press Releases | primary | <https://www.maxar.com/press-releases> | 卫星制造与地球情报 |
| [ ] P0 | `faa-commercial-space` | FAA Commercial Space | regulator/data | <https://www.faa.gov/space> | 发射许可、事故与监管 |
| [ ] P2 | `spacenews` | SpaceNews | secondary-radar | <https://spacenews.com/> | 产业发现与交叉验证 |
| [ ] P2 | `payload-space` | Payload | secondary-radar | <https://payloadspace.com/> | 商业航天产业雷达 |

商业航天首批：

- [ ] 先接 `nasa-news`、`esa-newsroom`、`spacex-updates`、`rocket-lab-updates`、`axiom-space-newsroom`、`faa-commercial-space`；
- [ ] 统一 mission、launch、vehicle、payload identity，避免同一任务按预告、发射、结果重复成多个 Event；
- [ ] 区分计划日期、实际发射时间、任务完成时间和公告时间。

### 5.9 `tech-business`：20 个

这个组合只跟踪会改变前沿技术供给、竞争、成本、融资或产业结构的商业事件；普通股价波动、泛公司新闻和消费促销不进入候选池。

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P0 | `sec-edgar-data` | SEC EDGAR Data | regulator/data | <https://www.sec.gov/edgar/sec-api-documentation> | 使用官方 API/filing identity，不抓搜索 UI |
| [ ] P0 | `ftc-newsroom` | U.S. FTC Newsroom | regulator/data | <https://www.ftc.gov/news-events/news/press-releases> | 竞争、并购与消费者保护 |
| [ ] P0 | `doj-antitrust-news` | U.S. DOJ Antitrust | regulator/data | <https://www.justice.gov/atr/press-releases> | 反垄断执法与诉讼 |
| [ ] P0 | `eu-competition-news` | European Commission Competition | regulator/data | <https://competition-policy.ec.europa.eu/about/reaching-out/press-releases_en> | 并购、国家援助与平台竞争 |
| [ ] P0 | `microsoft-ir` | Microsoft Investor Relations | primary | <https://www.microsoft.com/en-us/Investor> | 财报、资本开支与重大交易 |
| [ ] P0 | `alphabet-ir` | Alphabet Investor Relations | primary | <https://abc.xyz/investor/> | 财报、资本开支与重大交易 |
| [ ] P0 | `amazon-ir` | Amazon Investor Relations | primary | <https://ir.aboutamazon.com/> | AWS、资本开支与重大交易 |
| [ ] P1 | `meta-ir` | Meta Investor Relations | primary | <https://investor.atmeta.com/> | AI 基建、资本开支与产品经济性 |
| [ ] P1 | `apple-ir` | Apple Investor Relations | primary | <https://investor.apple.com/> | 财报、供应链与重大交易 |
| [ ] P1 | `nvidia-ir` | NVIDIA Investor Relations | primary | <https://investor.nvidia.com/> | 与 semiconductor 共享机构；财务事实独立入口 |
| [ ] P1 | `tsmc-ir` | TSMC Investor Relations | primary | <https://investor.tsmc.com/> | 产能、资本开支与客户结构 |
| [ ] P1 | `asml-ir` | ASML Investor Relations | primary | <https://www.asml.com/en/investors> | 订单、产能与出口限制影响 |
| [ ] P1 | `amd-ir` | AMD Investor Relations | primary | <https://ir.amd.com/> | 财务与重大交易 |
| [ ] P1 | `arm-ir` | Arm Investor Relations | primary | <https://investors.arm.com/> | 授权模式、云端与终端需求 |
| [ ] P1 | `dealroom-insights` | Dealroom Insights | secondary-radar | <https://dealroom.co/blog> | 使用公开报告/新闻，确认 API 与再利用许可 |
| [ ] P2 | `crunchbase-news` | Crunchbase News | secondary-radar | <https://news.crunchbase.com/> | 融资发现；不抓取付费数据库 |
| [ ] P2 | `sifted` | Sifted | secondary-radar | <https://sifted.eu/> | 欧洲科技公司与资本雷达 |
| [ ] P2 | `techcrunch` | TechCrunch | secondary-radar | <https://techcrunch.com/> | 发现后追溯公司/监管原文 |
| [ ] P2 | `reuters-technology` | Reuters Technology | secondary-radar | <https://www.reuters.com/technology/> | 需授权；未获许可前不自动抓取全文 |
| [ ] P2 | `the-information` | The Information | secondary-radar | <https://www.theinformation.com/> | 付费与授权来源；默认人工雷达 |

科技商业首批：

- [ ] 先接 `sec-edgar-data`、`ftc-newsroom`、`doj-antitrust-news`、`eu-competition-news`、`microsoft-ir`、`alphabet-ir`；
- [ ] 首批公司 universe 只覆盖与前沿技术 Brief 高相关的上市公司，不建设通用股票新闻系统；
- [ ] 从 filing/监管原文形成 Event，再用媒体补充影响，不让融资报道或股价变化单独获得高分。

### 5.10 `tech-policy-macro`：25 个

这个组合只纳入会改变科技融资、需求、成本、市场准入、供应链或安全边界的政策与宏观变化。它是跨 Category 的解释 Lens，不是政治时事流。

| TODO | 候选 `source_id` | 来源 | 角色 | 候选入口 | 接入备注 |
|---|---|---|---|---|---|
| [ ] P0 | `us-federal-register-tech` | U.S. Federal Register | regulator/data | <https://www.federalregister.gov/developers/documentation/api/v1> | 用官方 API 和 agency/topic 查询 |
| [ ] P0 | `white-house-ostp` | White House OSTP | regulator/data | <https://www.whitehouse.gov/ostp/news-updates/> | 科技政策与行政行动 |
| [ ] P0 | `nist-ai` | NIST AI | regulator/data | <https://www.nist.gov/artificial-intelligence> | 标准、测量、AI RMF 与评估 |
| [ ] P0 | `us-commerce-bis` | U.S. Commerce BIS | regulator/data | <https://www.bis.gov/press-release> | 出口管制与实体清单；不要与 bank-bis 混淆 |
| [ ] P1 | `cisa-news` | CISA News | regulator/data | <https://www.cisa.gov/news-events/news> | 关键基础设施与网络安全 |
| [ ] P1 | `fcc-news` | FCC News | regulator/data | <https://www.fcc.gov/news-events> | 通信、频谱与平台规则 |
| [ ] P0 | `eu-digital-strategy` | EU Digital Strategy / AI Office | regulator/data | <https://digital-strategy.ec.europa.eu/en/policies/artificial-intelligence> | AI Act、执行、标准与数字政策 |
| [ ] P0 | `eur-lex-digital` | EUR-Lex | regulator/data | <https://eur-lex.europa.eu/> | 使用 CELEX identity，跟踪正式法律文本版本 |
| [ ] P1 | `enisa-news` | ENISA | regulator/data | <https://www.enisa.europa.eu/news> | 网络安全与关键基础设施 |
| [ ] P0 | `uk-dsit-news` | UK DSIT | regulator/data | <https://www.gov.uk/government/organisations/department-for-science-innovation-and-technology> | 科技、AI 与数字政策 |
| [ ] P1 | `uk-cma-news` | UK CMA | regulator/data | <https://www.gov.uk/government/organisations/competition-and-markets-authority> | 并购、竞争与平台监管 |
| [ ] P0 | `china-cac` | 国家互联网信息办公室 | regulator/data | <https://www.cac.gov.cn/> | 数据、算法、生成式 AI 与网络治理 |
| [ ] P0 | `china-miit` | 工业和信息化部 | regulator/data | <https://www.miit.gov.cn/> | 工业、通信、软件和产业政策 |
| [ ] P1 | `china-samr` | 国家市场监督管理总局 | regulator/data | <https://www.samr.gov.cn/> | 竞争、标准与平台监管 |
| [ ] P1 | `china-state-council-policy` | 中国政府网政策 | regulator/data | <https://www.gov.cn/zhengce/> | 用正式文号/政策 identity；按科技影响过滤 |
| [ ] P0 | `pboc-news-data` | 中国人民银行 | regulator/data | <https://www.pbc.gov.cn/> | 利率、流动性与金融政策 |
| [ ] P0 | `china-nbs-data` | 国家统计局 | regulator/data | <https://www.stats.gov.cn/> | 工业、投资、价格与宏观数据 |
| [ ] P0 | `federal-reserve-news` | U.S. Federal Reserve | regulator/data | <https://www.federalreserve.gov/newsevents.htm> | 利率、流动性与金融稳定 |
| [ ] P0 | `ecb-press` | European Central Bank | regulator/data | <https://www.ecb.europa.eu/press/html/index.en.html> | 欧元区利率与金融条件 |
| [ ] P0 | `imf-data-news` | IMF | regulator/data | <https://www.imf.org/en/News> | 全球宏观与国家报告；数据入口单独建 adapter 时再注册 |
| [ ] P0 | `bank-bis` | Bank for International Settlements | regulator/data | <https://www.bis.org/press/index.htm> | 金融条件、支付与监管；与美国商务部 BIS 分开 |
| [ ] P1 | `oecd-digital-economy` | OECD Digital Economy | regulator/data | <https://www.oecd.org/en/topics/digital-economy.html> | 数字经济、生产率与政策比较 |
| [ ] P1 | `world-bank-news` | World Bank | regulator/data | <https://www.worldbank.org/en/news> | 按数字基础设施/产业/宏观主题过滤 |
| [ ] P1 | `wto-news` | WTO News | regulator/data | <https://www.wto.org/english/news_e/news_e.htm> | 贸易规则、关税与争端 |
| [ ] P1 | `unctad-news` | UN Trade and Development | regulator/data | <https://unctad.org/news> | 技术、投资、贸易与供应链 |

科技政策与宏观首批：

- [ ] 先接 `us-federal-register-tech`、`nist-ai`、`us-commerce-bis`、`eu-digital-strategy`、`china-cac`、`china-miit`、`federal-reserve-news`、`china-nbs-data`；
- [ ] 政策以正式文本、文号、发布机构、生效日期和适用对象建 identity，解读稿只作为 supporting Item；
- [ ] 宏观数据只在新增值、修订值或政策决定发生时形成 Item，不把每日市场波动变成新闻流；
- [ ] 每个政策/宏观 Event 必须能回答“它改变了哪个前沿科技领域的成本、供给、需求、准入或风险”，否则不进入 Briefly 候选。

## 6. 不要一次接完：四个实施波次

### Wave 0：契约和测量基线

- [ ] 在 Shiyi 固定候选 Category slug；允许一个 Item 有多个中性 Categories，不把 Category 建成复杂实体；
- [ ] 为来源增加“角色、覆盖 Category、接入状态、许可状态”的规划清单；这些是 source 配置/文档，不写进 Briefly Event；
- [ ] 导出当前 28 天基线：各来源 Items 数、ready 比例、详情成功率、重复率、发布时间缺失率、Briefly Event/qualified 数；
- [ ] 为 `primary`、`research`、`regulator/data`、`secondary-radar` 建立不同但简单的试采检查表；
- [ ] 在 Briefly 保存一批人工审核基准 Event，用于新来源前后分数分布与达标率比较。

### Wave 1：每类 5–8 个第一方来源

- [ ] 只实现各表“首批”清单，约 61 个 Category 覆盖位；共享来源去重注册；
- [ ] 优先复用 Shiyi 已有 RSS、index-detail、GitHub、API 和 document 获取模式；
- [ ] 每实现 5 个 source 立即跑 fixture、重复运行和 28 天小窗口，不累计到最后一起验收；
- [ ] 先保证第一方事件召回，再考虑二手媒体覆盖率。

### Wave 2：研究、监管和产业数据

- [ ] 接入 arXiv/论文期刊时必须限定查询、窗口和最大条数；
- [ ] 接入监管/统计文档时使用原始文号、filing ID、CELEX、series/release ID 等稳定 identity；
- [ ] 对数据修订保留版本和 observed time，避免把网页更新时间当成事件发生时间；
- [ ] 每类扩到 12–15 个有效来源后，先做一次 Briefly 真实样刊，再决定是否继续补量。

### Wave 3：二手雷达与长尾补盲

- [ ] 逐站确认 RSS/API、robots、服务条款、付费墙和再利用许可；
- [ ] 未获授权的 Reuters、The Information、STAT 等仅保留人工/授权雷达，不自动抓全文；
- [ ] 二手来源发现的事件必须尽可能补回公司、论文、监管或数据原文；
- [ ] 只有当某类长期存在第一方盲区时，才补到 20–30 个，不为达到数量指标堆低质量来源。

## 7. Briefly 消费验收

Shiyi 接入完成只表示来源能够稳定产生 canonical-ready `ContentItem`，不表示
来源值得长期保留，更不表示 Event 会自动发布。每个实施波次还必须通过
Briefly 的数据质量、信号质量与产品验证门槛；这些门槛由 Briefly 仓库的
[`SOURCE_EXPANSION_TODO.md`](https://github.com/LoveOrange/briefly-ai-weekly/blob/main/docs/SOURCE_EXPANSION_TODO.md)
统一维护。Shiyi 在本清单中只记录验收结果和来源状态，不复制 Briefly 的
评分、排名或产品配置。

## 8. 跨 Category 去重 TODO

以下是最容易重复注册的来源，实施时先建立一次，再让中性分类覆盖多个领域：

| 来源 | 覆盖范围 | 处理 |
|---|---|---|
| Google DeepMind | AI、robotics、biotechnology | 复用现有 `deepmind-blog` |
| NVIDIA Developer/Newsroom | AI、semiconductors、robotics | Developer 与 Newsroom 可为两个稳定入口；不要按 Category 再复制 |
| imec / CEA-Leti | semiconductors、advanced-materials、quantum | 各机构一次注册，多 Category 分类 |
| DOE / ARPA-E / national labs | energy、advanced-materials、quantum | 稳定栏目可分 source，机构首页不得重复 |
| NIST | materials、quantum、AI policy | 按稳定 topic feed/入口划分，避免同一页面被多个 source 抓取 |
| 公司 newsroom 与 IR | technology、tech-business | 技术发布与财务披露入口可分别注册，但 Briefly 必须聚合成同一真实 Event |
| 政策正文与机构解读 | tech-policy-macro、所有技术 Category | 正式文本为 primary Item，解读为 supporting Item |

## 9. 推荐执行顺序

1. 完成 Wave 0，不修改 Briefly 当前 `ai` 发布选择；
2. 先实现 `semiconductors`、`robotics`、`tech-policy-macro` 的首批，因为它们最直接补足 AI 产业化判断；
3. 再实现 `energy`、`biotechnology`、`space` 的首批，制作 4 周 Frontier Radar 样刊；
4. 最后实现 `advanced-materials`、`quantum`，重点验证低频高价值领域的信号门槛；
5. `tech-business` 先以监管和公司披露为主，二手融资媒体等到授权与用户需求证据明确后再接；
6. 每完成一个波次，都回到 Briefly 的真实 Event 样本评估；没有改善用户判断的来源不因“高质量品牌”而保留。

## 10. 本轮可直接创建的工程 TODO

### Shiyi 仓库

- [ ] 新增 source portfolio manifest，只存规划元数据并引用现有 `Source`，不新建复杂领域模型；
- [ ] 为 Wave 1 每个来源建立独立小任务：入口侦察、许可、fixture、adapter、canonicalization、tests、live smoke；
- [ ] 增加 source quality report：ready、detail success、duplicate、timestamp、category precision 和 candidate yield；
- [ ] 增加按时间窗导出 Category 候选 Items 的只读命令，供 Briefly 离线周期读取；
- [ ] 保持 Shiyi 输出中性，不加入 importance、rank、recommendation 或 Briefly presentation 字段。

### 下游交接

- [ ] 用现有 ACL 和 Event 管线回放 Wave 1 样本，不新增第二套实体或 pipeline；
- [ ] 记录每个来源的 Event contribution、supporting contribution、qualified yield 和 false-positive 样本；
- [ ] 制作四周 Frontier Radar 人工样刊，验证同一 ICP 是否需要跨 AI、芯片、机器人、能源等持续跟踪；
- [ ] 在样刊验证前，不新增公开 archive route、独立邮件产品或 Category 配额；
- [ ] 当真实需求支持新 Brief 时，再为该 Category/Tags 增加确定性 selection 配置和不可变 snapshot。

这些任务由 Briefly 维护；本清单只保留交接依赖，详细门槛见上面的消费验收链接。

## 11. 完成判定

本计划不是以“注册 210 个来源”为完成，而是以以下结果为完成：

- 每个 Category 拥有 20–30 个经过许可与稳定性审查的覆盖位；
- 第一方、研究/数据和二手雷达形成合理组合，且来源去重；
- Shiyi 能稳定产生可审计、可重复、可供 Briefly 消费的 Items；
- Briefly 能从新增 Items 聚合出更完整的 Events，但仍只发布超过同一重要性门槛的内容；
- 至少一个 AI 之外的组合通过连续四周样刊与目标用户验证，证明它提升付费决策价值，而不只是增加新闻数量。
