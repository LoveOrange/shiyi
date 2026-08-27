# Shiyi Sources

- Last updated: 2026-08-27
- Scope: sources captured by Shiyi for Briefly
- Priority: stable Briefly inputs before open-source breadth

This document defines the source boundary, admission policy, current built-in
sources, and the immediate AI-source maintenance queue. The broader Briefly
portfolio is maintained in [`SOURCE_EXPANSION_BACKLOG.md`](SOURCE_EXPANSION_BACKLOG.md),
which is the single planning list for cross-Category candidate IDs, priorities,
targets, and rollout waves.

- `[x]` means the source exists in the current built-in registry.
- `[ ]` means the source is planned or still requires admission work.
- A checked source is not automatically production-proven, backfilled, or
  editorially important.
- Community sources are radar and supporting evidence. A community claim must
  be corroborated by a traceable primary source before Briefly presents it as a
  factual Event claim.
- A row in the expansion backlog is planning metadata, not a runtime `Source`.
  Only admitted sources may enter `BUILTIN_SOURCES` or a production
  `CaptureConfig`.

## Source model

A `Source` is one independently identifiable target with:

- stable `id`;
- adapter key;
- target;
- enabled state;
- adapter-specific options;
- an independent checkpoint boundary.

Source is a declarative record. `CaptureRunner` selects it and `SourceAdapter`
performs the acquisition. Creator is only optional attribution on the resulting
content.

- An X account captured directly can be a Source.
- An account appearing in X search results is a creator, not the search Source.
- A Reddit subreddit or search query can be a Source.
- A Reddit poster may be absent from `creators` without invalidating the item.

Multiple accounts should normally be separate Source records sharing one
platform adapter. This preserves independent checkpoints and failure isolation.

## Admission policy

Add a built-in source only when it has:

1. a clear Briefly use case;
2. stable target identity and source-native item identity;
3. repeatable public acquisition or explicitly managed credentials;
4. bounded fixtures and deterministic adapter tests;
5. canonical detail content or an explicit incomplete fallback;
6. objective timestamps and provenance.

Do not add a source because it might someday support opportunity discovery.
That interpretation belongs downstream. Prefer canonical primary sources;
community and secondary sources improve discovery and impact evidence but do
not replace available vendor evidence.

## Source checklist

### Official sources: added

- [x] [OpenAI News](https://openai.com/news/rss.xml): OpenAI's official product, model, research, safety, and company announcements.
- [x] [Anthropic News](https://www.anthropic.com/news): Anthropic's official model, product, research, policy, and safety announcements.
- [x] [Hugging Face Blog](https://huggingface.co/blog/feed.xml): Official Hugging Face platform, open-model, library, research, and community articles.
- [x] [Google Research Blog](https://research.google/blog/rss/): Google's official research publications and engineering updates.
- [x] [Google DeepMind Blog](https://deepmind.google/blog/rss.xml): Google DeepMind's official model, research, science, and product announcements.
- [x] [DeepSeek Updates](https://api-docs.deepseek.com/updates): DeepSeek's official model and API release articles.
- [x] [Z.ai Release Notes](https://docs.z.ai/release-notes/new-released.md): Z.ai's official GLM model and developer-platform releases.
- [x] [Kimi Research](https://www.kimi.com/en/blog/): Kimi's official model and research articles with canonical detail pages.
- [x] [Kimi Code Changelog](https://www.kimi.com/code/docs/kimi-code/whats-new.html): Dated Kimi Code model, CLI, and product changes.
- [x] [Qwen Model Releases](https://docs.qwencloud.com/changelog/models.md): Official Qwen model and API release notes for developers.
- [x] [Qwen Code Blog](https://qwenlm.github.io/qwen-code-docs/en/blog/): Official Qwen Code CLI, agent, Skill, integration, and release articles.
- [x] [Zhipu BigModel Releases](https://docs.bigmodel.cn/cn/update/new-releases.md): China-facing GLM model and BigModel platform releases.
- [x] [MiniMax Model Releases](https://platform.minimaxi.com/docs/release-notes/models.md): Official MiniMax model releases, including coding, tool-use, and agent capabilities.
- [x] [MiniMax API Updates](https://platform.minimaxi.com/docs/release-notes/apis.md): Official MiniMax API and developer-platform changes.
- [x] [ByteDance Seed Blog](https://seed.bytedance.com/zh/blog): ByteDance Seed's official model, research, and technical articles.
- [x] [Gemini API Changelog](https://ai.google.dev/gemini-api/docs/changelog.md.txt): Official Gemini model and API availability changes.
- [x] [Mistral News](https://mistral.ai/news): Mistral's official model, product, research, and company announcements.
- [x] [Microsoft AI Blog](https://www.microsoft.com/en-us/microsoft-cloud/blog/topic/ai-resources/feed/): Microsoft's official AI platform and engineering articles.
- [x] [Cohere Blog](https://cohere.com/blog): Cohere's official model, product, research, and enterprise AI articles.
- [x] [Cursor Changelog](https://cursor.com/changelog): Official Cursor product, model-access, agent, and developer workflow changes.
- [x] [GitHub Copilot Changelog](https://github.blog/changelog/label/copilot/feed/): Official GitHub Copilot product and platform changes.
- [x] [OpenClaw Releases](https://github.com/openclaw/openclaw/releases): Official OpenClaw release notes, including prerelease channels.
- [x] [Hermes Agent Releases](https://github.com/NousResearch/hermes-agent/releases): Official NousResearch Hermes Agent release notes.
- [x] [DeepSeek Harness Releases](https://github.com/deepseek-ai/deepseek-harness/releases): Official DeepSeek Harness release notes, including release candidates.
- [x] [Codex Releases](https://github.com/openai/codex/releases): Official OpenAI Codex CLI release notes.
- [x] [Claude Code Releases](https://github.com/anthropics/claude-code/releases): Official Anthropic Claude Code release notes.
- [x] [Google Antigravity Changelog](https://www.antigravity.google/changelog): Official Antigravity 2.0, CLI, IDE, and SDK releases from one server-rendered changelog.
- [x] [GPT-Live System Card](https://deploymentsafety.openai.com/gpt-live/gpt-live.pdf): OpenAI's text-extractable deployment-safety document, with the current material correction date declared in source configuration.
- [x] [OpenAI Content Provenance API guide](https://developers.openai.com/api/docs/guides/content-provenance): Stable developer implementation reference captured as a direct HTML document.
- [x] [Google DeepMind SynthID](https://deepmind.google/models/synthid/): Stable first-party technology reference captured as a direct HTML document.

### Official sources: recommended next

- [ ] [Xiaomi MiMo Model Updates](https://mimo.mi.com/docs/en-US/updates/model): Dated MiMo model releases, upgrades, and deprecations, with separate official detail articles where available.
- [ ] [InclusionAI Blog](https://www.inclusion-ai.org/blog/rss.xml): Ant Group's official Ling, Ring, Ming, LLaDA, multimodal, and open-source research releases.
- [ ] [Meituan Technology Blog](https://tech.meituan.com/rss.xml): Official Meituan engineering articles, including LongCat model releases and deployment work.
- [ ] [OpenBMB MiniCPM](https://github.com/OpenBMB/MiniCPM): Official MiniCPM repository with a dated model-release changelog and canonical model artifacts.
- [ ] [InternLM Models](https://internlm.intern-ai.org.cn/docEn/docs/Models/): Shanghai AI Laboratory's current model milestones, explicit model IDs, and model creation timestamps.
- [ ] [SenseNova Models](https://huggingface.co/sensenova/models): SenseTime's active official model organization; admit only new first-party model identities, not routine repository edits.
- [ ] [BAAI Models](https://huggingface.co/BAAI/models): Beijing Academy of Artificial Intelligence model and collection releases; use an organization allowlist and suppress routine file updates.

### Official sources: queued or watchlist

- [ ] [Tencent TokenHub Product Updates](https://cloud.tencent.com/document/product/1823/130675): Dated Hunyuan and China-model platform availability, migration, pricing, and deprecation changes; treat it as a platform source rather than a replacement for vendor-primary evidence.
- [ ] [Baidu Qianfan Model Updates](https://cloud.baidu.com/doc/qianfan/s/Kmh4stnjp): Dated ERNIE and Qianfan-hosted model launches, upgrades, and retirements.
- [ ] [StepFun Models](https://huggingface.co/stepfun-ai/models): Official StepFun model artifacts; admit after defining a stable new-model identity and timestamp contract instead of treating every repository edit as news.
- [ ] [01.AI Yi Models](https://huggingface.co/01-ai/models): Official Yi artifacts; keep on the watchlist until release activity resumes or a better dated announcement index appears.
- [ ] [iFlytek Open Platform](https://www.xfyun.cn/doc/): Spark model and API documentation; locate a stable dated model-update index before admission.
- [ ] [Huawei Pangu Documentation](https://support.huaweicloud.com/productdesc-pangulm/): Pangu model documentation; locate a stable release-level index rather than capturing general documentation edits.
- [ ] [Official model-hub organizations](https://huggingface.co/models): Organization-scoped new-model discovery for selected Chinese labs on Hugging Face and ModelScope; every organization remains a separate Source and checkpoint boundary.

### Community sources: added

- [x] [Hacker News Top Stories](https://news.ycombinator.com/): High-attention technical discussions used as community radar, with canonical external targets preserved when available.

### Community sources: planned

- [ ] [ModelScope Community](https://community.modelscope.cn/): Chinese open-model releases, community roundups, deployment notes, and ecosystem activity; require stable article identity and canonical detail capture.
- [ ] [OpenXLab](https://openxlab.org.cn/home?lang=en-US): Shanghai AI Laboratory's community model, dataset, application, and project ecosystem; capture only bounded model-release or editorial lanes.
- [ ] [OpenCSG Model Hub](https://opencsg.com/models): Chinese open-model discovery and sharing; determine a stable public API or listing contract before admission.
- [ ] [Hugging Face Daily Papers](https://huggingface.co/papers): Community-curated research discovery with submission identity and objective engagement metrics; useful for early research signals, not automatic publication.
- [ ] [Reddit LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/): High-signal open-weight model releases, benchmarks, deployment experience, and failure reports; use only through approved OAuth access with retention, deletion, and attribution compliance.
- [ ] [V2EX AIGC](https://www.v2ex.com/go/aigc): Chinese practitioner discussion of models, coding tools, availability, pricing, and real usage; prefer V2EX's documented API and preserve topic/reply metrics without editorial interpretation.
- [ ] [LINUX DO Development](https://linux.do/c/develop/4): Chinese developer reports about AI models, agents, tooling, and operational problems; validate public Discourse access, deletion handling, and a bounded AI-tag policy before admission.

### Secondary reporting: planned

- [ ] [InfoQ China](https://www.infoq.cn/topics/ai): Chinese software-development and enterprise AI reporting.
- [ ] [机器之心](https://www.jiqizhixin.com/): Chinese AI research, model, and industry reporting.
- [ ] [量子位](https://www.qbitai.com/): Chinese AI model, product, company, and research reporting.
- [ ] 新智元: locate and validate a stable public index/detail contract before adding a target URL.

### Official social accounts: deferred

Evaluate official Kimi, Qwen, DeepSeek, Zhipu, MiniMax, StepFun, and ByteDance
Seed accounts on WeChat, Weibo, and X only after their official web sources are
reliable. Model each account as an independent Source and use only repeatable,
policy-compliant acquisition; do not use authentication bypasses or brittle
scraping workarounds.

## Current implementation backlog

The obsolete `moonshot-kimi-changelog` target was replaced by `kimi-research`
and `kimi-code-changelog`. The adapters now capture canonical Kimi research
articles and dated Kimi Code entries. The remaining Kimi task is:

- [ ] Backfill the local MongoDB collection when the repaired sources are
  enabled in the scheduled capture run.

Suggested delivery order:

1. Xiaomi MiMo, InclusionAI, OpenBMB MiniCPM, and ModelScope Community.
2. Meituan LongCat, InternLM, SenseNova, and BAAI.
3. Tencent TokenHub, Baidu Qianfan, StepFun, OpenXLab, and V2EX AIGC.
4. Other model hubs, secondary publications, and social accounts after their
   acquisition contracts are understood.

## Content and adapter contract

- Prefer canonical article/detail content over listing previews.
- GitHub release sources request up to 100 recent records from the public
  Releases API, retain prereleases, exclude drafts, and leave release-note
  bodies in canonical content rather than mislabeling them as summaries.
- Shiyi captures release records without deciding whether a version is major or
  editorially important; Briefly owns impact scoring and weekly selection.
- Use `direct-document` only for one explicit, stable public HTML, Markdown, or
  text-extractable PDF target; it is not a generic site crawler.
- Preserve original-language normalized content.
- Record reliable title, URL, published time, and optional creators.
- Store objective platform metrics without interpreting them.
- Set `metadata.is_complete = false` for preview-only fallback; persisted output
  remains not ready.
- Never emit Signal, Trend, Opportunity, credibility, or ranking fields.

```python
class SourceAdapter(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    def capture(self, source: Source) -> AsyncIterator[SourceItem]: ...
```

Implementations should be named by acquisition role, for example
`XCaptureAdapter`, `RedditCaptureAdapter`, or `RssCaptureAdapter`.

## Acceptance and maintenance

Every admitted source must have:

- [ ] A declarative built-in Source in `shiyi sources` with a stable ID,
  adapter key, target, content kind, and description.
- [ ] Correct `--since`, `--until`, and `--max-items` behavior where supported.
- [ ] Idempotent repeated capture without duplicate ContentItems.
- [ ] Stable IDs, provenance, canonical URL, title, usable publication time,
  original-language Markdown, hashes, and readiness timestamps for ready items.
- [ ] Incomplete status when canonical detail content is required but missing.
- [ ] Bounded fixtures and deterministic tests for listing and detail parsing.
- [ ] An opt-in live smoke test for each high-priority public contract.
- [ ] Failure isolation in a multi-source run.

Update this checklist in the same change that adds a registry entry, fixtures,
tests, and live smoke coverage. When a source moves or is retired, update its URL
and description here instead of adding a compatibility alias.

## Future breadth

After Briefly is stable, expansion may include forums, video platforms,
repositories, papers, email, chat, and user-provided feeds. New source kinds
reuse the same `SourceItem -> ContentItem` boundary rather than adding
product-specific models.
