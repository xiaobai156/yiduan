# 304 期失败站验证记录：禾尽风起

- 时间：2026-10-31
- 项目：杀段_解耦版
- 期数：304
- 站点：禾尽风起（sites.json 第 166 条）
- URL：https://herymche.x6l2j-h6kfu-qdresg.work:29466/article/lottery/6a47ecaa57dc857ae1bf570e?url=txbb
- API：https://herymche.x6l2j-h6kfu-qdresg.work:29466/api/proxy/manager-articles/6a47ecaa57dc857ae1bf570e
- 方向：bottom（尾 3 组）
- 原失败原因：尾部最新3个有效候选期数为[302期、303期]，不含指定304期（失败分类：方向范围外）

## 现场取证（只读，未写缓存/未写正式 TXT）

- 环境限制：本机无可用浏览器通道（browserLane.browsers 为空），改用项目抓取层 `duan_app.fetcher.fetch_text` 直取站点权威响应；页面为 Next.js SPA 空壳（49307 字节，无 /api/ 引用、无“杀/段/期”），正文只能来自该 API，故 API 即权威来源。
- API 响应：209091 字节，JSON 字段 id/authorNickname/title/html/…；`title` 与 `html` 均为 base64。
- 解码 title：`304期：【绝杀一段】〓超级幸运`（标题已改为 304 期）
- 解码 html：143643 字节，含 159期～303期连续历史行，**全文出现 "304" 次数 = 0**，期号集合仅 {300,301,302,303}
- 正文尾部顺序：…302期【2段】开:狗45 准 → 303期【7段】开:虎17 准 → 303期【4段】开:00 准（站方重复行，非本项目引入）→ 段位表 1段:01…7段:49（标准页脚）

## 结论

- 判定：**无数据 / 时序问题**，不是解析异常、不是抓取失败、不是配置过期。
- 依据：站方标题已更新到 304 期，但正文行仍停在 303 期（最后一行为 303 期及其重复行），304 期正文行尚未发布。
- 处置：不改代码、不写正式成功 TXT、不写缓存；该站保留在 304 期失败清单。
- 旁证：304 期成功 TXT 175 站与缓存 175 个 304 值集合完全一致，仅缺该站。

## 产物

- `api_raw.txt`：API 原始响应
- `page_raw.txt`：页面 HTML 原始响应
- `decoded_html.txt`：base64 解码后的正文 HTML
- `verify_site.py`：取证脚本（只读）
