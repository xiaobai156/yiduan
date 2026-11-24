# 326 期 蓝可爱鬼 取证（2026-11-22）

## 失败记录
```
失败 蓝可爱鬼 https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html 方向: bottom 期数: 326 阶段: 指定期数校验 原因: 无期数；另有 1 个脚本加载失败
```

## 取证结论：无数据（站方标题已改、正文未改）

题页（项目通道 `probe.py`，`collect_documents` 得 229 个文档，errors=[]）：

- 标题 `326期[蓝可爱鬼][绝禁一段]已公开`（注意站方把「绝杀一段」写成「**绝禁**一段」）
- 作者 `蓝可爱鬼 发表于 11月22日 00:30:13`
- 正文成绩表共 303 行 `NNN期:[杀一段]《N段》开:…`，期号 024–326 连续
- 末四行：
  ```
  323期:[杀一段]《3段》开:猴47准
  324期:[杀一段]《5段》开:鼠43准
  325期:[杀一段]《1段》开:龙03错
  325期:[杀一段]《4段》开:？00准      ← 开奖位仍是「？00」未开，期号与上一行重复
  ```
- **全文没有 `326期` 的数据行**（`326期` 只出现在标题和上下篇链接里）

`325期《4段》开:？00准` 与 318 期置之死地那次完全同型：新一期内容已写、期号忘了改、开奖位还是占位符。按 AGENTS.md「无法证明即失败；禁止猜期」，不作为 326 期值写入。

## 为什么解析器给「无定位」而非「无数据」

`duan_app/parsing/custom.py:693 _profile_section_documents` 在 `issue_filter={326}` 下要求 heading 文档本身含 326 期的严格段值（`_document_has_profile_candidate`）；本案 326 期只有标题没有段值 → `candidate_index=None` → 整个 section 被丢弃 → `collect_candidates` 返回 0 候选 → 校验报「无定位」。去掉 issue_filter 扫描同一份 documents 时该 section 能正常入选（score 90），说明丢的是当期值而非页面。

## 文件
- `probe.py`：抓文档 + 列 326 期命中行
- `deep_debug.py`：逐层打印 search text / 结果标记 / issue 分段 / 每段段值
- `evidence/title_block.txt`：标题与开头数据行
- `evidence/tail_rows.txt`：末尾 8 行数据行（含两条 325）
- `evidence/doc13_lines.txt`：doc13 全文 1009 行纯文本
- `evidence/issue_hits.txt`：全文所有 `326期` 命中行

## 附带发现（未处理，属失败清单范围外）
缓存 `recent_10_cache.json` 里蓝可爱鬼 `status=error`、`fingerprint={}`，而 git HEAD 里原有 314–323 十期真实值（314=4段…323=3段）；被今日跑批失败覆盖清空。恢复与否待用户决定。

## URL 更换（2026-11-22，用户指定）
用户指定改为 `https://bbrqhvww.4eylv-8gp30-jpndzw.work:17488/topic/350479.html`。

- 内容等价：新旧两个 URL 渲染出的 303 行成绩表 sha 都是 `bc02a948d5da`，标题锚点同为 `326期[蓝可爱鬼][绝禁一段]已公开`。
- 稳定性：新地址连开 5 次，`source_url` 均停在同一地址（无跳转）；旧地址每次落到不同临时域名。
- 改动文件：`sites.json`（url）、`site_profiles.json`（url；`site_id` 仍为 `d86925ced64564c2`，因 `stable_site_id` 按 `topic_key_from_url` 取 350479）、`recent_10_cache.json`（该站 url 字段 + `_meta.source_sites_hash` 重算为 `2c46e51aa50d…`）。
- 校验：`validate_cache_integrity` PASS、pytest 13 passed、compileall 干净；换后生产链路 `docs=253 errors=[] 数据行=606 candidates=0`，仍是「无定位」，即抓取正常、缺的是 326 期正文值。
- 脚本：`verify_new_url.py`（内容等价）、`stability_new.py`（5 次落地）、`apply_swap_url.py`（改三处配置）、`post_swap_check.py`（换后生产链路）。
