# -*- coding: utf-8 -*-
"""Build tmp/hlm/part-1.json from chapter sources; all quotes/texts cut verbatim."""
import json, re, sys

BASE = "tmp/hlm/ch/ch-%02d.md"

def body_lines(n):
    lines = open(BASE % n, encoding="utf-8").read().split("\n")
    idx = next(j for j, l in enumerate(lines)
               if re.match(r"^\[\d+\]", l.strip()) or re.match(r"^〔[一二三四五六七八九十]+〕", l.strip()))
    return lines[:idx]

def line(n, j):
    return body_lines(n)[j - 1].strip()

CARDS = [
 dict(n=1,
  role="全书楔子：立石头下凡与还泪因果，以甄家小荣枯预演贾府大荣枯",
  gist="顽石求僧道携入红尘，甄士隐梦中闻绛珠还泪之说；英莲元宵走失，葫芦庙起火，士隐随跛足道人出家。",
  points=["顽石自叹无材补天，苦求二仙携入红尘",
          "僧道说绛珠要以一生眼泪偿还神瑛灌溉之恩",
          "士隐梦中见通灵宝玉与太虚幻境对联",
          "英莲元宵被霍启失落，甄家遭火后士隐出家"],
  quote="他既下世为人，我也去下世为人，但把我一生所有的眼泪还他，也偿还得过他了。",
  quote_from="绛珠仙子", text=[33, 93]),
 dict(n=2,
  role="借冷子兴之口交代宁荣二府世系虚实，为黛玉进府张本",
  gist="娇杏被雨村纳为妾后扶正；雨村革职后入林家教读，黛玉丧母；冷子兴细说贾府人丁与衰败之相。",
  points=["娇杏因昔日回顾雨村，被纳为妾后扶正",
          "雨村被参革职，入林如海家教黛玉读书",
          "冷子兴说贾府外面的架子未倒、内囊已尽",
          "演说带出宝玉衔玉而生与元春入宫"],
  quote="如今外面的架子虽未甚倒，内囊却也尽上来了。",
  quote_from="冷子兴", text=[15, 33]),
 dict(n=3,
  role="黛玉初入荣国府，以她的眼睛量出贾府规矩人情，宝黛初见",
  gist="雨村凭林如海荐书得贾政之力复职；黛玉拜见贾母与两位母舅，初见凤姐、宝玉，宝玉因摔玉。",
  points=["雨村随黛玉入都，凭林如海荐书谋得复职",
          "黛玉见贾母，贾母搂住他心肝肉儿般大哭",
          "王熙凤未见其人先闻其声，携黛玉手打量",
          "宝玉称这个妹妹曾见过，狠命摔通灵玉"],
  quote="这个妹妹我曾见过的。",
  quote_from="宝玉", text=[17, 23]),
 dict(n=4,
  role="以英莲案揭护官符，写四大家族权势与官场徇情",
  gist="雨村审拐卖案，门子献护官符与乱判之计，雨村徇情放了薛蟠；薛家携英莲进京，寄居梨香院。",
  points=["门子出示护官符，点明四大家族一损俱损",
          "雨村明知被卖者是英莲，仍照门子之计乱判",
          "薛蟠打死冯渊，携母妹与英莲入都",
          "薛家寄居梨香院，宝钗由此进入荣府"],
  quote="贾不假，白玉为堂金作马。",
  quote_from="护官符", text=[9, 15]),
 dict(n=5,
  role="全书总预言：以册子与曲文预定诸钗结局，也是宝玉情悟的起点",
  gist="宝玉在秦氏房中睡去，随警幻游太虚幻境，翻看金陵十二钗册子、听红楼梦十二支曲，醒后与袭人初试云雨。",
  points=["宝玉随警幻入太虚幻境，见薄命司册子",
          "判词暗点黛玉、宝钗、凤姐等人结局",
          "十二支曲演尽众女儿荣枯，宝玉不解",
          "警幻以意淫点拨，醒后与袭人初试云雨"],
  quote="假作真时真亦假，无为有处有还无。",
  quote_from="原文", text=[33, 47]),
 dict(n=6,
  role="由宝玉云雨情转入刘姥姥进府，以穷亲戚眼睛写凤姐当家",
  gist="刘姥姥因冬事艰难，带板儿来荣府打秋风，经周瑞家的引见见到凤姐，得银子二十两。",
  points=["宝玉梦醒后与袭人初试云雨情",
          "刘姥姥家冬事无着，狗儿怂恿她去荣府",
          "周瑞家的念旧情，引刘姥姥进荣府后门",
          "凤姐先诉艰难，终究给了二十两银子"],
  quote="谋事在人，成事在天。",
  quote_from="刘姥姥", text=[11, 57]),
 dict(n=7,
  role="以送宫花串起各房，写宝钗冷香丸与黛玉小性，末以焦大醉骂揭宁府",
  gist="周瑞家的送宫花遍走各房，宝钗自述冷香丸；宝玉在宁府会秦钟，二人相契；焦大醉骂宁府爬灰养小叔子。",
  points=["周瑞家的送宫花，顺路串起迎探惜与黛玉",
          "宝钗细说冷香丸配制，周瑞家的听得称奇",
          "宝玉在宁府见秦钟人品出众，自惭形秽",
          "焦大醉骂爬灰养小叔子，凤姐宝玉装作不闻"],
  quote="养小叔子的养小叔子，我什么不知道？",
  quote_from="焦大", text=[37, 39]),
 dict(n=8,
  role="金玉良缘初次对看，黛玉半含酸，宝钗金锁正式登场",
  gist="宝玉到梨香院探宝钗，宝钗看通灵玉、莺儿点出金锁；黛玉随后到，借雪雁送手炉讽宝玉听宝钗的话。",
  points=["宝钗细看通灵玉，念莫失莫忘、仙寿恒昌",
          "莺儿说金锁上的字与玉上的字是一对",
          "黛玉见宝玉在宝钗处吃酒，语带酸意",
          "李嬷嬷拦酒，黛玉借手炉奚落宝玉"],
  quote="莫失莫忘，仙寿恒昌。",
  quote_from="宝钗", text=[13, 41]),
 dict(n=9,
  role="写家塾之乱，借顽童闹学写贾府子弟不成器",
  gist="宝玉与秦钟入家塾，金荣欺侮秦钟，茗烟等大闹学堂；贾瑞偏袒金荣，终逼金荣磕头赔罪。",
  points=["宝玉约秦钟入塾，袭人替他打点书笔",
          "贾政训斥李贵，命宝玉先学四书",
          "金荣讥秦钟，茗烟等大打出手闹学堂",
          "贾瑞徇私弹压不住，金荣只得磕头赔罪"],
  quote="一龙生九种，九种各别。",
  quote_from="原文", text=[13, 31]),
 dict(n=10,
  role="借金氏受辱与张太医论病，写秦氏病势已成",
  gist="金荣之母与璜大奶奶欲向秦氏理论，被尤氏一番话吓退；贾珍请张太医为秦氏诊脉，断为思虑太过、病势可虑。",
  points=["金荣回家抱怨，其母与璜大奶奶要讨说法",
          "尤氏说秦氏病重经不起气，金氏不敢开口",
          "贾珍延请张太医入府为秦氏诊脉",
          "张太医断秦氏心性高强、思虑太过"],
  quote="大奶奶是个心性高强聪明不过的人",
  quote_from="张太医", text=[23, 27]),
 dict(n=11,
  role="宁府家宴写秦氏病危，园中相遇写贾瑞起淫心，两条线并进",
  gist="贾敬寿辰宁府排宴，凤姐探秦氏，秦氏自陈没福；凤姐在园中遇贾瑞，贾瑞言语挑逗，凤姐假意周旋。",
  points=["宁府为贾敬寿辰排家宴，贾母未来",
          "凤姐探秦氏，秦氏说未必熬得过年去",
          "贾瑞从假山后现身，向凤姐请安挑逗",
          "凤姐假意含笑周旋，心中已定主意"],
  quote="我自想着，未必熬的过年去呢。",
  quote_from="秦氏", text=[23, 35]),
 dict(n=12,
  role="凤姐毒设相思局惩治贾瑞，以风月宝鉴收束，写痴妄色欲的下场",
  gist="贾瑞两番夜入荣府赴约，被冻、被泼粪，仍不思改；病中得跛足道人所授风月宝鉴，只照正面而亡。",
  points=["贾瑞夜入穿堂赴约，被关一夜几乎冻死",
          "凤姐再设局，贾蓉贾蔷泼他一身尿粪",
          "贾瑞病重，跛足道人授风月宝鉴",
          "贾瑞不听只照背面之嘱，正照而亡"],
  quote="千万不可照正面，只照他的背面，要紧，要紧！",
  quote_from="跛足道人", text=[21, 29]),
 dict(n=13,
  role="秦氏之死与凤姐协理宁府，完成家族警示并交出管家权",
  gist="秦氏托梦凤姐，嘱置祭祀家塾；秦氏死后贾珍大办丧事，为贾蓉捐龙禁尉；尤氏病，贾珍请凤姐协理宁国府。",
  points=["秦氏托梦凤姐，说三春去后诸芳尽",
          "秦氏嘱置义田家塾，为家族留后路",
          "贾珍为贾蓉捐龙禁尉，丧仪极尽奢靡",
          "凤姐受宁府对牌，先理出五件积弊"],
  quote="三春去后诸芳尽，各自须寻各自门。",
  quote_from="原文", text=[9, 51]),
 dict(n=14,
  role="凤姐理事写才干威权，同时以林如海之死断黛玉退路",
  gist="凤姐分派宁府人役、按时点卯，严惩迟到者；送殡路上北静王水溶见宝玉并赠念珠；林如海病故。",
  points=["凤姐定名册分班，卯正二刻点卯理事",
          "凤姐严惩迟到媳妇，宁府威重令行",
          "北静王水溶路遇宝玉，赠圣上亲赐念珠",
          "林如海病故，黛玉自此长留贾府"],
  quote="本来要饶你，只是我头一次宽了，下次人就难管，不如现开发的好。",
  quote_from="凤姐", text=[9, 21]),
 dict(n=15,
  role="凤姐弄权铁槛寺写贪权，秦钟智能写少年情欲",
  gist="送殡至铁槛寺，凤姐受老尼之托，假贾琏之名逼守备退亲，索银三千；秦钟在馒头庵与智能私会。",
  points=["老尼求凤姐出面，了结张金哥与守备的亲事",
          "凤姐自称不信阴司报应，开口索银三千",
          "凤姐命来旺儿假托贾琏写信退亲",
          "秦钟馒头庵私会智能，被宝玉撞见"],
  quote="你是素日知道我的，从来不信什么是阴司地狱报应的，凭是什么事，我说要行就行。",
  quote_from="凤姐", text=[29, 33]),
 dict(n=16,
  role="元春封妃带来省亲盛事，秦钟之死作结，一盛一衰对照",
  gist="元春封凤藻宫尚书、加封贤德妃，贾府筹建省亲别墅；秦钟病重，宝玉探视，秦钟临终劝宝玉立志功名而逝。",
  points=["夏太监传旨，元春晋封贤德妃",
          "贾府议定借东府花园起造省亲别院",
          "贾蔷下姑苏采买女孩子与行头",
          "秦钟病危，临终劝宝玉立志功名"],
  quote="怎么不肯早来？再迟一步也不能见了。",
  quote_from="秦钟", text=[39, 63]),
 dict(n=17,
  role="前半试才题额写宝玉才情，后半归省写元春之悲与盛极之奢",
  gist="贾政带宝玉游新园，命其题匾联；元宵元妃归省，与贾母王夫人相见泣诉，命姊妹题诗，赏戏后回銮。",
  points=["贾政携宝玉游园，一路命其题匾拟联",
          "宝玉驳天然二字，题沁芳、有凤来仪",
          "元妃归省，见贾母王夫人泣诉宫中苦",
          "元妃命姊妹题诗，改浣葛山庄为稻香村"],
  quote="当日既送我到那不得见人的去处，好容易今日回家娘儿们一会，不说说笑笑，反倒哭起来。",
  quote_from="元春", text=[17, 131]),
 dict(n=18,
  role="省亲后转入日常，以袭人赎身之说着力写宝玉的依恋",
  gist="宝玉撞见茗烟与丫头私会；到袭人家探望，袭人假称要赎身回家，逼宝玉答应三件事；黛玉午睡，宝玉编耗子精故事逗她。",
  points=["宝玉在宁府小书房撞见茗烟与丫头私会",
          "袭人回家，宝玉追到花家探望",
          "袭人假说赎身，要宝玉依她三件事",
          "宝玉编耗子精故事，黛玉按倒他要拧"],
  quote="别说两三件，就是两三百件，我也依。",
  quote_from="宝玉", text=[45, 67]),
 dict(n=19,
  role="写凤姐弹压赵姨娘母子与宝黛湘云口角，展府内嫡庶与儿女心思",
  gist="李嬷嬷辱骂袭人，凤姐拉走她并弹压；贾环输钱赖账，赵姨娘护短，凤姐训斥；湘云来，黛玉因宝玉亲近湘云而气恼，宝玉以亲不间疏劝解。",
  points=["李嬷嬷排揎袭人，凤姐赶来拉走弹压",
          "贾环赖莺儿的钱，赵姨娘护短",
          "凤姐训斥赵姨娘与贾环，正言弹妒意",
          "黛玉因湘云来而气恼，宝玉以亲不间疏劝解"],
  quote="亲不间疏，先不僭后",
  quote_from="宝玉", text=[25, 45]),
 dict(n=20,
  role="写宝玉与袭人怄气、贾琏与平儿偷情遮掩，转进夫妻婢妾纠葛",
  gist="宝玉替湘云梳头，袭人见之气恼；宝玉续庄子自遣，黛玉题诗讥他；贾琏趁大姐出痘与多姑娘私通，平儿发现青丝替他瞒过凤姐。",
  points=["宝玉替湘云梳头，袭人见之气恼不理他",
          "宝玉续庄子胠箧，黛玉题诗讥他",
          "贾琏趁大姐出痘与多姑娘私通",
          "平儿抖出青丝，替贾琏瞒过凤姐"],
  quote="这蹄子认真要降伏我，仔细你的皮要紧！",
  quote_from="凤姐", text=[41, 63]),
]

# ch-17 是「第十七回至十八回」合并回，整行 26 字超过 title 上限 24，
# 只能截取原题前半（仍是原题连续前缀），后半「荣国府归省庆元宵」由 role/gist 承担。
TITLE_CUT = {17: "第十七回至十八回 大观园试才题对额"}

def main():
    out = []
    bad = []
    for c in CARDS:
        n = c["n"]
        raw = open(BASE % n, encoding="utf-8").read()
        title = body_lines(n)[0].rstrip()
        assert title.startswith("# ")
        title = title[2:].strip()
        if n in TITLE_CUT:
            assert title.startswith(TITLE_CUT[n]), "cut title must be a prefix of the source title"
            title = TITLE_CUT[n]
        texts = [line(n, j) for j in c["text"]]
        # constraints
        if len(title) > 24:
            bad.append(f"n{n} title {len(title)}")
        if len(c["role"]) > 34:
            bad.append(f"n{n} role {len(c['role'])}")
        if not (10 <= len(c["gist"]) <= 70):
            bad.append(f"n{n} gist {len(c['gist'])}")
        for p in c["points"]:
            if len(p) > 40:
                bad.append(f"n{n} point {len(p)}:{p}")
            if re.search(r"[0-9A-Za-z]", p):
                bad.append(f"n{n} point has latin/digit: {p}")
        if not (2 <= len(c["points"]) <= 4):
            bad.append(f"n{n} points count")
        if len(c["quote"]) > 90:
            bad.append(f"n{n} quote {len(c['quote'])}")
        if c["quote"] not in raw:
            bad.append(f"n{n} quote not substring")
        if len(c["quote_from"]) > 12:
            bad.append(f"n{n} quote_from too long")
        if not (1 <= len(texts) <= 3):
            bad.append(f"n{n} text count")
        for t, j in zip(texts, c["text"]):
            if not (60 <= len(t) <= 400):
                bad.append(f"n{n} text line{j} len {len(t)}")
            if t not in raw:
                bad.append(f"n{n} text line{j} not substring")
        for t in texts:
            if t not in raw:
                bad.append(f"n{n} text not substring")
        if any(re.search(r"[A-Za-z]", s) for s in [c["role"], c["gist"] + "".join(c["points"])]):
            bad.append(f"n{n} contains latin letters")
        out.append(dict(n=n, title=title, role=c["role"], gist=c["gist"],
                        points=c["points"], quote=c["quote"],
                        quote_from=c["quote_from"], text=texts))
    print("checks:", "OK" if not bad else "FAIL")
    for b in bad:
        print(" -", b)
    if bad:
        sys.exit(1)
    with open("tmp/hlm/part-1.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("written", len(out), "cards")

main()
