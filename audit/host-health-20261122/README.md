# 全站地址/区块体检（2026-11-22，只读）

触发：蓝可爱鬼换地址后用户问「还有其他哪些站点存在这种问题」。
全程只读：只写本目录，未改 sites.json / site_profiles.json / 正式输出 / 缓存。

## 脚本
- `scan_hosts.py` → `hosts.json`：130 个主机裸 TLS + HTTP 探测（不含浏览器通道）。
- `scan_all_render.py` → `render_all.json`：172 站逐个走 `render_page_text`，记录配置主机、落地主机、落地 topic、数据行数。
- `render_suspects.py` / `topic_identity.py`：对上一步异常站复核并比对 topic 身份。
- `scan_conflicts.py` → `scan_conflicts.json`：172 站走完整生产链路（collect_documents → collect_candidates → find_matches + candidate_conflict_issue_reasons）。
- `conflict_detail.py` / `conflict_context.py` / `tail_sequence.py`：冲突站逐候选打位置、锚点、上下文行。
- `scan_dead_markers.py` / `marker_context.py`：失效文案扫描（「已删除/已下架/不存在」等）。

## 结论一：没有打不开的站
裸探测有 26 个主机 CONNFAIL/301/404，但用项目浏览器通道复核，**172 站全部渲染成功，0 站失败**。
说明裸 curl/socket 探测对本平台无参考价值（正文由 lz-string 脚本渲染，且要过跳转）。

## 结论二：7 站被域名跳转（与蓝可爱鬼同型，但无害）
| 站点 | 配置主机 | 落地主机 | topic 一致 | 326 值 |
|---|---|---|---|---|
| 夹谷笑过 | qwpapph.el7s4-pbxnj-aemcbt.work | zrnmciul.3hgkq-vf0k7-uqffre.cyou | 是 | 5段 |
| 没有之后 | zdwcig.iyo4d-81klf-udwkqg.work | dfpkofhc.9eehc-bvg6w-dnkmno.cyou | 是 | 4段 |
| 天朗气清 | ykafylrj.aa70q-k7jc0-igfkrd.work | jmqmlqdu.rjx9m-5ewz5-mwaciw.work | 是 | 4段 |
| 巷议街谈 | dhqjbz.uxec9-jxs3h-fomubo.work | iotwbmqb.wasbo-ehfv0-qyqhdl.work | 是 | 7段 |
| 六合联盟 | pvxiftuf.yumkw-u4s81-hpytyz.work | lpbxmngd.x3fi2-l9gy9-rkagfz.work | 是 | 5段 |
| 高温凯子 | jogavu.6bl6s-ilo1w-yfnvvl.work | iotwbmqb.wasbo-ehfv0-qyqhdl.work | 是 | 2段 |
| 悠闲自在 | pvxiftuf.yumkw-u4s81-hpytyz.work | lirbervs.ziovj-yrlm2-byxpig.work | 是 | 4段 |

7 站跳转后 topic 全部与配置一致、取值全部命中，**没有抓错帖**。落地主机每次不同，属平台防封，不必改配置。

## 结论三：6 站存在同期双区块冲突（与面红耳赤同根因）
| 站点 | 候选 | 缓存值 | 真值判定 | 下次跑批风险 |
|---|---|---|---|---|
| 面红耳赤 | 5段(锚点模板) | 4段 | 4段（无锚点表 开猴23错） | **静默写错成 5段** |
| 神神道道 | 1段 / 6段 | 1段 | 1段（doc68 开00中） | 报「同一期高可信候选冲突」失败 |
| 夹谷笑过 | 5段 / 7段 | 5段 | 5段（开0000中） | 报冲突失败 |
| 花间辞令 | 3段 / 5段 | 3段 | 3段（开00中） | 报冲突失败 |
| 先人后己 | 2段 / 4段 | 2段 | 2段（开0000准） | 报冲突失败 |
| 玄机码王 | 1段 / 7段 | 1段 | 1段（开00准） | 报冲突失败 |

判别口径：模板块把当期写成「已开奖 + 猪19」，并把 327 之后全部标已开奖；真实块当期开奖位是 `00`/`0000` 占位，且上面几期的开奖号与真实开奖（324 鼠43、325 龙03）对得上。
今天跑批这 6 站取的都是真值，但只因模板块是跑批之后才生成的。

## 结论四：1 站无当期值
蓝可爱鬼：标题已改 326，正文 303 行止于 325（末行期号未改、开奖位 `？00`）。已换新地址，内容与旧地址 sha 一致。

## 未发现
- 失效文案扫描命中 20 站，逐行核对后全部是误报：「部分连错期数记录已删除」（大手大脚，站方自己的说明）、「不存在原生文本绑定关系」（三地主，诗词解析文字）、「404」是页面脚本/字串残留。
- 无「帖子已下架」「无权限」类真实失效。

---

# 第二批：把 7 站的配置地址改成落地地址（2026-11-22，用户授权「开始」）

## 稳定性实测（`test_landing_stability.py` → `landing_stability.json`）
对 7 站的落地地址各连开 5 次：

| 站点 | 原地不跳 | 内容与配置地址一致 | 5 次落地 |
|---|---|---|---|
| 夹谷笑过 | 是 | 是 | srnurztl.19o0y-m8cdt-fxekxw.work:17488 ×5 |
| 没有之后 | 是 | 是 | jmqmlqdu.rjx9m-5ewz5-mwaciw.work:17488 ×5 |
| 天朗气清 | 是 | 是 | lirbervs.ziovj-yrlm2-byxpig.work:17466 ×5 |
| 巷议街谈 | 是 | 是 | iotwbmqb.wasbo-ehfv0-qyqhdl.work:17466 ×5 |
| 六合联盟 | 是 | 是 | iotwbmqb.wasbo-ehfv0-qyqhdl.work:17466 ×5 |
| 高温凯子 | 是 | 是 | pltltcuu.gn117-jsg9x-qcxxsa.work:17455 ×5 |
| 悠闲自在 | 是 | 是 | pdvlvrkg.jjd8j-niebw-pusitw.work:17466 ×5 |

关键修正：之前以为「落地每次不同」，是因为每次都在打开**配置地址**（随机分配入口）；直接打开落地地址后 5/5 稳定。

## 改动（`apply_swap_7.py`）
7 站同步更新 `sites.json`、`site_profiles.json`、`recent_10_cache.json` 的 url 字段；`site_id` 全部不变（身份按 topic 号算）；缓存 `_meta.source_sites_hash` 重算为 `a6e5722d3f57…`。

## 换后验证
- `post_swap_7.py`：7 站走生产链路全部命中，取值与缓存逐一相同（夹谷笑过 5段 / 没有之后 4段 / 天朗气清 4段 / 巷议街谈 7段 / 六合联盟 5段 / 高温凯子 2段 / 悠闲自在 4段）。
- `post_swap_conflicts.py`：7 站同期冲突全部消失（每站只剩 1 个候选）。
- `jiaigu_before_after.py`：夹谷笑过旧入口 docs=216、段值行 1016、候选 `5段/7段` 冲突；新入口 docs=203、段值行 510、只剩 `5段` → 换地址顺带消掉了它的伪候选。
- 配置加载通过（172 站）、`validate_cache_integrity` PASS、pytest 13 passed、compileall 干净。

## 附带说明
`recent_10_cache.json` 的 diff 很大，是因为它本来就带着 322–326 几轮未提交的改动（base_period 从 323 到 326），不是这次换地址造成的；本次只动了 8 个 url 字段（7 站 + 蓝可爱鬼）和两处 hash。
