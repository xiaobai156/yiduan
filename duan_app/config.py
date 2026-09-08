# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from duan_app.constants import DEFAULT_FAILURE_RESULT_DIR_NAME, DEFAULT_RESULT_DIR_NAME
from duan_app.domain import Site


PICK_ALIASES = {
    "top": "top",
    "顶部": "top",
    "上": "top",
    "上部": "top",
    "前": "top",
    "前面": "top",
    "bottom": "bottom",
    "尾部": "bottom",
    "底部": "bottom",
    "下": "bottom",
    "下部": "bottom",
    "后": "bottom",
    "后面": "bottom",
}

def normalize_pick(value: object) -> str:
    raw = str(value).strip().lower()
    return PICK_ALIASES.get(raw, raw)

def topic_key_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    match = re.search(r"/topic/(\d+)\.html/?$", parsed.path)
    if match:
        return match.group(1)
    return None

def canonical_url_key(url: str) -> str:
    raw = url.strip()
    parsed = urlparse(raw)
    try:
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return raw
    if not parsed.scheme or not hostname:
        return raw

    scheme = parsed.scheme.lower()
    hostname = hostname.rstrip(".").lower()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))

def unique_sites(sites: list[Site]) -> list[Site]:
    unique: list[Site] = []
    seen: set[str] = set()
    for site in sites:
        if site.url in seen:
            continue
        seen.add(site.url)
        unique.append(site)
    return unique

DEFAULT_SITES = unique_sites([
    Site("吹散思绪", "https://vkrquo.xfbmz-7znxx-miaoej.xyz:16677/topic/157484.html", "top"),
    Site("喝醉的猫", "https://cykiiyt.4hxms-k65ek-jsvqzm.xyz:16677/topic/481063.html", "top"),
    Site("名列前茅", "https://w4shq9.g9ldx-6077s-zvfqqu.work/topic/460994.html", "top"),
    Site("心慌意乱", "https://eqdfqyah.jigmo-9e498-sxucok.xyz:16677/topic/216615.html", "top"),
    Site("猿啼鹤怨", "https://eqdfqyah.jigmo-9e498-sxucok.xyz:16677/topic/216578.html", "top"),
    Site("山河表里", "https://vbxl5.wp5pl-3ztz5-cwgbti.xyz/topic/227237.html", "top"),
    Site("烟雨遥遥", "https://sadoleu.rznla-fgwyr-nzqalp.xyz:16677/topic/453517.html", "top"),
    Site("小康在望", "https://mm.676626m.com:1888/bbs/8033", "top"),
    Site("天朗气清", "https://ykafylrj.aa70q-k7jc0-igfkrd.work:16677/topic/371410.html", "top"),
    Site("天长地久", "https://fhrtnoy.10cus-ki4mn-mlcyap.xyz:16677/topic/447392.html", "top"),
    Site("泪眼问花", "https://narnesm.in79o-is98f-mncjoh.xyz:16677/topic/504958.html", "top"),
    Site("作戏而已", "https://fptnapl.o7l2d-gr6ew-tvgvep.xyz:16677/topic/349634.html", "top"),
    Site("阿世取容", "https://zwhzkjo.fc4fh-otded-nvhceu.xyz:16677/topic/472636.html", "top"),
    Site("斗志昂扬", "https://zkjjuem.y2teq-2zq5t-rpmaqk.work:16677/topic/796367.html", "top"),
    Site("一劳永逸", "https://dvglkfp.mueyy-uiuci-vtqiod.work:16677/topic/430605.html", "top"),
    Site("黑风孽海", "https://dvglkfp.mueyy-uiuci-vtqiod.work:16677/topic/224240.html", "top"),
    Site("雷锋", "https://dvglkfp.mueyy-uiuci-vtqiod.work:16677/topic/209120.html", "top"),
    Site("独一无二", "https://kpfhptru.s8hvq-ssvup-eladiw.xyz:16622/topic/230607.html", "top"),
    Site("深情厚谊", "https://bucgnuda.sbsrh-yvu62-jrtrcm.xyz:16633/topic/256311.html", "top"),
    Site("废物费二", "https://bucgnuda.sbsrh-yvu62-jrtrcm.xyz:16633/topic/256812.html", "top"),
    Site("委决不下", "https://niqyf.niwmj-1z0q3-wpylfo.xyz/topic/207239.html", "top"),
    Site("破烂流丢", "https://0cggq.9o9kf-k9voh-papahr.work/topic/206544.html", "top"),
    Site("悬梁刺股", "https://ikjaekum.yu2af-orn0b-hqbkee.xyz:16677/topic/796600.html", "top"),
    Site("折节下士", "https://4m6dz.5qa9g-yt3d1-vfqhud.xyz/topic/216489.html", "top"),
    Site("巷议街谈", "https://dhqjbz.uxec9-jxs3h-fomubo.work:16677/topic/462301.html", "bottom"),
    Site("河梁之谊", "https://sdzvp.lh8uo-ee9ru-cfpyti.xyz/topic/227458.html", "bottom"),
    Site("混淆视听", "https://aq14f.2gdkh-2qrjm-hxaxji.xyz/topic/392717.html", "bottom"),
    Site("猫三狗四", "https://111.246004.com:9066/Article.Aspx?ListId=247&id=53508", "bottom"),
    Site("罪有应得", "https://eqyyanu.4rfyf-h2bx5-oxsbom.xyz:16677/topic/453392.html", "bottom"),
    Site("南辕北辙", "https://gxixcfq.4hxms-k65ek-jsvqzm.xyz:16677/topic/314301.html", "top"),
    Site("高温凯子", "https://jogavu.6bl6s-ilo1w-yfnvvl.work:16677/topic/678627.html", "bottom"),
    Site("蓝可爱鬼", "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350479.html", "bottom"),
    Site("孤独滋味", "https://zopeuze.1fjlt-g1hbj-hykofq.xyz:16677/topic/448465.html", "bottom"),
    Site("面红耳赤", "https://pcfwjde.22zu6-81144-kdlkyf.xyz:16677/topic/436704.html", "bottom"),
    Site("无怨无悔", "https://kjkkzzg.eiu7u-3edk2-gjzmrl.xyz:16677/topic/446853.html", "bottom"),
    Site("烘云托月", "https://hfauoob.xu36n-9s7v3-jtrkpg.xyz:16677/topic/448332.html", "bottom"),
    Site("六合联盟", "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/500604.html", "bottom"),
    Site("悠闲自在", "https://pvxiftuf.yumkw-u4s81-hpytyz.work:16677/topic/573876.html", "bottom"),
    Site("神魂摇荡", "https://xxn08n.uf6h9-z8vxq-smsfdt.work/topic/230084.html", "bottom"),
    Site("神神道道", "https://gboqrz.d2cda-p5u2y-gwxmnf.work/topic/333165.html", "bottom"),
    Site("力钧势敌", "https://zpyaxwke.rp89b-fwko2-buexgv.xyz:16677/topic/245368.html", "top"),
    Site("皇帝奴才", "https://kfsujebc.djiz8-4tqt6-hubani.xyz:16677/topic/280942.html", "bottom"),
    Site("大吉大利", "https://tzaxdpzf.fwblv-hty1k-xajvao.xyz/view.php?id=10", "bottom"),
    Site("漓沐倾城", "https://979363.com.9795.in:1888/bbs/7643", "top"),
    Site("夹谷笑过", "https://qwpapph.el7s4-pbxnj-aemcbt.work:16677/topic/702079.html", "top"),
    Site("一丝一毫", "https://e7rzi6.q42de-ffhtv-sshfhh.work/topic/497135.html", "top"),
    Site("令闻令望", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/205219.html", "bottom"),
    Site("十拿九稳", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/224745.html", "top"),
    Site("长度三十", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/205645.html", "bottom"),
    Site("众嘘漂山", "https://gboqrz.sm0a0-x9x2c-xyvjdr.work/topic/205462.html", "bottom"),
    Site("澳门招财猫", "https://cthvktrb.am9a6-vk0h6-lwbxab.xyz:16677/topic/324761.html", "top"),
    Site("赛马会第一版", "https://ugtzszfp.ldpiz-8xhrd-wpkjkn.xyz:16677/topic/573666.html", "bottom"),
    Site("赛马会第二版", "https://ugtzszfp.ldpiz-8xhrd-wpkjkn.xyz:16677/topic/639337.html", "bottom"),
    Site("一五一十", "https://spkhheda.6pb1u-v37cv-dcemcz.xyz:16677/topic/445668.html", "bottom"),
    Site("魅笔生花", "https://uhaxnrzx.q76gf-deec8-zqckeo.xyz:16677/topic/615680.html", "top"),
    Site("澳门曾夫人", "https://rafllgob.23z93-ww9uq-tjnvdx.xyz:16677/", "top"),
    Site("武松打虎", "https://ebhxngwb.2ljj5-vdh8s-gbvkgl.xyz:16677/topic/258480.html", "bottom"),
    Site("祝你发财", "https://ebhxngwb.2ljj5-vdh8s-gbvkgl.xyz:16677/topic/255950.html", "bottom"),
    Site("浪静风平", "https://stkfbbns.yrfhc-z5x6i-ykoqqu.xyz:16677/topic/251230.html", "top"),
    Site("锦瑟安然", "https://stkfbbns.yrfhc-z5x6i-ykoqqu.xyz:16677/topic/251232.html", "top"),
    Site("李立", "https://grjawf.sp5ee-ol941-nkuroa.xyz:16677/topic/254826.html", "bottom"),
    Site("蝇营狗苟", "https://bbuueerm.pxcma-jyfok-mvduyw.xyz:16633/topic/455096.html", "top"),
    Site("风止意平", "https://fbgbfg.www27521c.com:8443/gsb/am13.html", "bottom"),
    Site("大放光彩", "https://aszmkf.c3z3l-qrlqm-mwgccr.work:29411/article/admin/6a0837fe08adb5ed7357efce?url=lhw", "bottom"),
    Site("朗朗权坤", "https://kk.212557a.com:1888/art_zhuanqu/8148.html", "top"),
    Site("寒来暑往", "https://ocnrhq.du156-vb27w-tmhsed.xyz:16677/", "top"),
    Site("凉秋瑾言", "https://sheuzjss.tgpcj-9w0vl-mwyhly.work:29422/article/admin/6a2450aaeb2a95d39b6678a7?url=zfw", "bottom"),
    Site("金刚护体", "https://asmfkb.dfkxu-0rwnp-wevqzo.work:29466/article/admin/6a282f6a514a4348ac4f0630?url=fcw", "bottom"),
    Site("忧烟殇往", "https://sndaygl.egjtc-sgs8w-taclan.work:29400/article/admin/6a140eeebf0a6cb1dd38f9dd?url=nmw", "bottom"),
    Site("海晏河清", "https://qdufkx.sjb5z-pi4k6-jlhnig.xyz:16677/topic/797866.html", "top"),
    Site("会飞的猪", "https://mm.737799b.com:1888/art_gsb/8148", "top"),
    Site("女神绝杀", "https://dd.62782b.com:1888/bbs/10746", "top"),
    Site("杨进心水", "https://aa.62782b.com:1888/bbs/10744", "top"),
    Site("创世奇彩", "https://rwraojf.l54vq-9httr-cmdnip.work:29477/article/admin/6a0436d94ea5c20141013e32?url=xdr", "bottom"),
    Site("南天财柱", "https://pgyzulb.iwnn7-gyyip-pnpfqv.work:29477/article/admin/6a153e7b8be59b17287c6d03?url=bflc", "bottom"),
    Site("英雄豪杰", "https://pgyzulb.iwnn7-gyyip-pnpfqv.work:29477/article/admin/6a153b4c8be59b17287c6ce5?url=bflc", "bottom"),
    Site("争战夺宝", "https://qgyhdauu.avht7-lah7b-oavfmr.work:29444/article/admin/6a0193719dbe5d9cedc4eb5d?url=wzw", "bottom"),
    Site("福星王子", "https://gqdbokpx.ji2oa-rdhxt-girktl.work:29411/article/admin/6a02a0b2300734f7aa12dfac?url=hj", "bottom"),
    Site("六合料王", "https://uqdccnri.oy2bh-swrfr-gvzxkk.work:29499/article/admin/6a0331f5e09a39d316b223b4?url=lcz", "bottom"),
    Site("夏意正浓", "https://yzpbdkow.6m1ba-7p7u4-ppolcy.work:29433/article/admin/6a02cfa28bad0a3579e9f741?url=tdg", "bottom"),
    Site("追彩少年", "https://zlkcyl.e6mlx-wj46o-rzcukg.work:29499/article/admin/6a0816e2e0d076537e1df825?url=hyl", "bottom"),
    Site("传真神彩", "https://asmfkb.dfkxu-0rwnp-wevqzo.work:29466/article/admin/6a09a8c2291caff3edcb9002?url=fcw", "bottom"),
    Site("高人彩经", "https://asmfkb.dfkxu-0rwnp-wevqzo.work:29466/article/admin/6a0998a5291caff3edcb8f16?url=fcw", "bottom"),
    Site("蓝田生玉", "https://szfzml.mfuw8-bnsfa-gdaxhk.xyz/view.php?id=460", "bottom"),
    Site("青翠欲滴", "https://xozgdo.um2zi-vbge0-emngyq.work:29422/article/admin/6a1414f4bf0a6cb1dd38fa29?url=sgnn", "bottom"),
    Site("彩民推荐", "https://plwyrcj.4ai8j-p62x5-pnsukp.work:29411/article/admin/6a129a4ed5071f9d0b8b451d?url=gjp", "bottom"),
    Site("素雪怜影", "https://fymxwnyg.ttmzc-muvns-udlfln.work:29455/article/admin/6a096e98291caff3edcb8c03?url=lhbd", "bottom"),
    Site("节节胜利", "https://fymxwnyg.ttmzc-muvns-udlfln.work:29455/article/admin/6a096c0c291caff3edcb8bc5?url=lhbd", "bottom"),
    Site("丰硕成果", "https://18118.73829.com/read.php?tid=472", "bottom"),
    Site("及第成名", "https://aszmkf.c3z3l-qrlqm-mwgccr.work:29411/article/admin/6a0838e608adb5ed7357efe5?url=lhw", "bottom"),
    Site("蛇口蜂针", "https://zxlfxpp.2n0je-9ecrg-kadbbu.work:29411/article/admin/6a141df74346bc68aea4efb3?url=tmw", "bottom"),
    Site("探囊取物", "https://jusbfyu.mkdwi-xa2ua-rsovan.work:29422/article/admin/6a3230163220dda7ed33be33?url=hjc", "bottom"),
    Site("澳门杀肖", "https://jusbfyu.mkdwi-xa2ua-rsovan.work:29422/article/admin/6a31485c49afa07fb590ec77?url=hjc", "bottom"),
    Site("昙花一现", "https://eebysckd.2go6k-y0pfv-fqbdsm.xyz:16677/topic/626102.html", "top"),
    Site("名扬天下", "https://eebysckd.2go6k-y0pfv-fqbdsm.xyz:16677/topic/625517.html", "top"),
    Site("没有之后", "https://zdwcig.iyo4d-81klf-udwkqg.work:16677/topic/350521.html", "bottom"),
    Site("眉头眼尾", "https://kxglojup.fao5v-9u0oz-okhubb.work:16677/topic/237352.html", "bottom"),
    Site("恭喜发财", "https://qdufkx.sjb5z-pi4k6-jlhnig.xyz:16677/topic/798386.html", "bottom"),
    Site("大手大脚", "https://anhomo.n03wh-m2skn-wssphn.xyz/topic/770530.html", "top"),
    Site("秋月春风", "https://mhpayza.30mg9-m9j7l-obwrmb.xyz/topic/766652.html", "bottom"),
    Site("淋漓尽精", "https://oifsonk.e0h72-f6bxs-juqrkd.xyz:16677/topic/450982.html", "top"),
    Site("逍遥浪子", "https://mxiscni.nkh6s-vfni4-lwgfvw.xyz:16677/topic/257907.html", "top"),
    Site("倚靠窗畔", "https://hl.90216a.com/read.php?tid=735", "bottom"),
    Site("敢拼敢博", "https://hl.www73261a.com/read.php?tid=550", "bottom"),
    Site("寻宝先生", "https://hlhl.69281.com/read.php?tid=813", "bottom"),
    Site("玄机码王", "https://hlhl.69281.com/read.php?tid=593", "bottom"),
    Site("天机神料", "https://rmpsmal.hi84f-zpj90-mvqksp.xyz:29477/article/manager/6a48ee7157dc857ae1bf771a?url=jfh", "bottom"),
    Site("彩事顺意", "https://mbsqhpk.8ivvt-u3cx5-enwlld.xyz:29400/article/manager/6a33d099dfa16552b923d069?url=lhzj", "bottom"),
    Site("天上人间", "https://knfoaep.ivqs8-1depw-yoirtw.xyz:29444/article/manager/6a0f0e09fc651d66e6399b89?url=lf", "bottom"),
    Site("金刚财子", "https://drxgkjt.uu1oc-eyjpt-uxyccu.xyz:29400/article/manager/6a33e9afdfa16552b923d41d?url=jyb", "bottom"),
    Site("披金执锐", "https://hcsuuoy.nimo7-9bgj4-fmspxt.xyz:29466/article/manager/6a31433af4129ac0e1595569?url=cww", "bottom"),
    Site("自知者明", "https://hcsuuoy.nimo7-9bgj4-fmspxt.xyz:29466/article/manager/6a31447432c7c4bb3c056f7e?url=cww", "bottom"),
    Site("最佳女主", "https://nwrkkmv.rx287-rkrai-jsjccc.xyz:29499/article/manager/6a33d2b3dfa16552b923d0ab?url=ggz", "bottom"),
])

def site_to_dict(site: Site) -> dict[str, object]:
    item: dict[str, object] = {"name": site.name, "url": site.url, "pick": site.pick}
    if site.retry != 2:
        item["retry"] = site.retry
    if site.cache_bust:
        item["cache_bust"] = True
    if site.confirm:
        item["confirm"] = True
    if site.api_url:
        item["api_url"] = site.api_url
    return item

def write_default_sites_config(path: Path) -> None:
    data = [site_to_dict(site) for site in DEFAULT_SITES]
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8-sig",
    )

def load_sites_config(path: Path) -> list[Site]:
    try:
        raw_items = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"站点配置读取失败：{path}，{exc}") from exc

    if not isinstance(raw_items, list):
        raise ValueError(f"站点配置格式不对：{path} 顶层必须是列表")

    sites: list[Site] = []
    seen_names: dict[str, int] = {}
    seen_urls: dict[str, int] = {}
    seen_topics: dict[str, int] = {}
    for position, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"站点配置第 {position} 项必须是对象")

        raw_name = str(item.get("name", ""))
        name = raw_name.strip()
        url = str(item.get("url", "")).strip()
        pick = normalize_pick(item.get("pick", item.get("region", "top")))
        retry_raw = item.get("retry", 2)
        cache_bust = bool(item.get("cache_bust", False))
        confirm = bool(item.get("confirm", False))
        api_url = str(item.get("api_url", "")).strip() or None
        if raw_name != name:
            raise ValueError(f"站点配置第 {position} 项 name 含首尾空格：{raw_name!r}")
        if not name or not url:
            raise ValueError(f"站点配置第 {position} 项缺少 name 或 url")
        if name in seen_names:
            raise ValueError(f"站点配置第 {position} 项目录名重复：{name}，首次在第 {seen_names[name]} 项")
        url_key = canonical_url_key(url)
        if url_key in seen_urls:
            raise ValueError(f"站点配置第 {position} 项 URL 重复：{url}，首次在第 {seen_urls[url]} 项")
        topic_key = topic_key_from_url(url)
        if topic_key and topic_key in seen_topics:
            raise ValueError(f"站点配置第 {position} 项 topic 重复：{topic_key}，首次在第 {seen_topics[topic_key]} 项")
        if pick not in {"top", "bottom"}:
            raise ValueError(f"站点配置第 {position} 项 pick 只能是 top/bottom/顶部/尾部/上/下")
        try:
            retry = max(0, min(10, int(retry_raw)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"站点配置第 {position} 项 retry 必须是数字") from exc
        seen_names[name] = position
        seen_urls[url_key] = position
        if topic_key:
            seen_topics[topic_key] = position
        sites.append(Site(name, url, pick, retry, cache_bust, confirm, api_url))

    return sites

def default_result_dir(script_dir: Path) -> Path:
    result_dir = script_dir.parent / DEFAULT_RESULT_DIR_NAME
    result_dir.mkdir(parents=True, exist_ok=True)
    return result_dir

def default_failure_result_dir(script_dir: Path) -> Path:
    result_dir = script_dir.parent / DEFAULT_FAILURE_RESULT_DIR_NAME
    result_dir.mkdir(parents=True, exist_ok=True)
    return result_dir

def resolve_failure_path(requested_path: str | None, failure_dir: Path, issues_label: str) -> Path:
    filename = Path(requested_path).name if requested_path else f"{issues_label}期-段-失败.txt"
    return failure_dir / filename
