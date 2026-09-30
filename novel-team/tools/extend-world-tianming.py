#!/usr/bin/env python3
"""
扩展《天命》玄天大陆世界包
新增：详细地理、势力内部、秘辛历史、武力体系
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# 路径
WORLD_DIR = Path("/var/minis/shared/novel-team/.world-packs")

def _project_dir():
    """P2⑤（09-29）：项目路径改走 project_guard resolver，不再写死 my-novel。
    可用 `--project <id>` 指定（默认 tianming）。"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from project_guard import resolve
    pid = "tianming"
    if "--project" in sys.argv:
        pid = sys.argv[sys.argv.index("--project") + 1]
    return resolve(pid).root_dir / "world"

PROJECT_DIR = _project_dir()

# 加载现有世界包
def load_existing():
    world_file = WORLD_DIR / "玄天大陆.json"
    if world_file.exists():
        return json.loads(world_file.read_text(encoding='utf-8'))
    return None

# 保存世界包
def save_world(data, path):
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

# ============================================================
# 1. 详细地理扩展
# ============================================================

EXTENDED_GEOGRAPHY = {
    # 五大区域详细设定
    "regions": [
        {
            "id": "region_中州_详细",
            "name": "中州",
            "parent": "world_玄天_0001",
            "type": "region",
            "status": "canon",
            "tagline": "玄天大陆核心，灵气浓郁，三宗总部所在地",
            "fields": [
                {"name": "地理位置", "value": "大陆中央，四面环山"},
                {"name": "面积", "value": "约80万平方公里"},
                {"name": "灵气浓度", "value": "浓郁（修炼加成1.5倍）"},
                {"name": "主要资源", "value": "灵石矿、灵药、剑材"},
                {"name": "人口密度", "value": "高（宗门弟子+凡人聚集）"},
                {"name": "气候", "value": "四季分明，春季多雨"},
                {"name": "交通", "value": "御剑飞舟为主，陆路为辅"},
                {"name": "主要城市", "value": "天剑城、青云城、逍遥城"}
            ],
            "sub_regions": ["天剑山脉", "青云平原", "天机沼泽", "落霞峡谷"]
        },
        {
            "id": "region_北荒_详细",
            "name": "北荒",
            "parent": "world_玄天_0001",
            "type": "region",
            "status": "canon",
            "tagline": "苦寒之地，凶兽横行，上古战场遗迹",
            "fields": [
                {"name": "地理位置", "value": "大陆北方，天剑山脉以北"},
                {"name": "面积", "value": "约120万平方公里"},
                {"name": "灵气浓度", "value": "稀薄（修炼加成0.7倍）"},
                {"name": "主要资源", "value": "寒铁、妖兽材料、上古遗物"},
                {"name": "人口密度", "value": "极低（散修+商队）"},
                {"name": "气候", "value": "常年积雪，暴风雪频繁"},
                {"name": "危险等级", "value": "高（五阶以上妖兽成群）"},
                {"name": "特殊地点", "value": "雪原古道、寒渊秘境、霜关遗址"}
            ],
            "sub_regions": ["雪原", "寒渊", "霜关遗址", "冰封海"]
        },
        {
            "id": "region_南岭_详细",
            "name": "南岭",
            "parent": "world_玄天_0001",
            "type": "region",
            "status": "canon",
            "tagline": "瘴气弥漫，丹药资源丰富，隐世宗门林立",
            "fields": [
                {"name": "地理位置", "value": "大陆南方，连绵山脉"},
                {"name": "面积", "value": "约95万平方公里"},
                {"name": "灵气浓度", "value": "中等（含特殊瘴气灵气）"},
                {"name": "主要资源", "value": "灵草、丹药、毒虫"},
                {"name": "人口密度", "value": "中等（隐世修士+药农）"},
                {"name": "气候", "value": "湿热，多雨，瘴气重"},
                {"name": "危险等级", "value": "中高（毒虫+瘴气+妖兽）"},
                {"name": "特殊地点", "value": "十万大山、毒瘴谷、百草渊"}
            ],
            "sub_regions": ["十万大山", "毒瘴谷", "百草渊", "云雾峰"]
        },
        {
            "id": "region_东海_详细",
            "name": "东海",
            "parent": "world_玄天_0001",
            "type": "region",
            "status": "canon",
            "tagline": "海岛星罗棋布，鲛人王朝，上古龙宫遗址",
            "fields": [
                {"name": "地理位置", "value": "大陆东方，海域面积约200万平方公里"},
                {"name": "岛屿数量", "value": "大小岛屿约500个"},
                {"name": "灵气浓度", "value": "沿海浓郁，海中中等"},
                {"name": "主要资源", "value": "珍珠、海兽、灵珠、龙宫遗物"},
                {"name": "人口密度", "value": "低（鲛人+渔村）"},
                {"name": "气候", "value": "温暖湿润，台风季节"},
                {"name": "危险等级", "value": "中（海兽+风暴+妖兽）"},
                {"name": "特殊地点", "value": "蓬莱仙岛、东海龙宫遗址、沉船墓"}
            ],
            "sub_regions": ["蓬莱仙岛", "东海龙宫遗址", "沉船墓", "鲛人湾"]
        },
        {
            "id": "region_西漠_详细",
            "name": "西漠",
            "parent": "world_玄天_0001",
            "type": "region",
            "status": "canon",
            "tagline": "古道遗迹，佛门道场，沙漠下的秘密",
            "fields": [
                {"name": "地理位置", "value": "大陆西方，广袤沙漠"},
                {"name": "面积", "value": "约150万平方公里"},
                {"name": "灵气浓度", "value": "稀少（沙地吸灵）"},
                {"name": "主要资源", "value": "古玉、经书、佛骨、沙宝"},
                {"name": "人口密度", "value": "低（僧侣+商队）"},
                {"name": "气候", "value": "干旱，昼夜温差大，沙尘暴"},
                {"name": "危险等级", "value": "中（沙漠+遗迹+诡异事件）"},
                {"name": "特殊地点", "value": "大雷音寺遗址、流沙古国、藏经洞"}
            ],
            "sub_regions": ["大雷音寺遗址", "流沙古国", "藏经洞", "魔鬼城"]
        }
    ],

    # 关键地点详细设定
    "key_locations": [
        {
            "id": "loc_天剑城_详细",
            "name": "天剑城",
            "parent": "loc_中州_0001",
            "type": "place",
            "status": "canon",
            "tagline": "天剑宗外门主城，万人在此生活",
            "fields": [
                {"name": "位置", "value": "天剑山脉南麓"},
                {"name": "人口", "value": "约3万人（含弟子、家属、商贾）"},
                {"name": "功能", "value": "外门弟子居所、物资集散、交易"}
            ]
        },
        {
            "id": "loc_内门城_详细",
            "name": "内门城",
            "parent": "loc_中州_0001",
            "type": "place",
            "status": "canon",
            "tagline": "天剑宗内门所在，需御剑半日可达",
            "fields": [
                {"name": "位置", "value": "天剑山脉中部"},
                {"name": "人口", "value": "约5000人（精英弟子+执事）"},
                {"name": "功能", "value": "内门修炼、传承、机密事务"}
            ]
        },
        {
            "id": "loc_万剑剑冢_详细",
            "name": "万剑剑冢",
            "parent": "loc_天剑山脉_0001",
            "type": "place",
            "status": "canon",
            "tagline": "上古剑修埋葬之所，剑意浓郁，禁地中的禁地",
            "fields": [
                {"name": "位置", "value": "天剑山脉最深处"},
                {"name": "进入条件", "value": "需剑道天赋，无天赋者剑意反噬"},
                {"name": "区域划分", "value": "外围（低阶剑修坟墓）→中层（中阶剑修）→深处（高阶剑修）→最深处（天命剑封印）"},
                {"name": "危险等级", "value": "极高（剑意绞杀+上古禁制）"},
                {"name": "特殊规则", "value": "天命剑持有者可无视禁制"},
                {"name": "核心秘密", "value": "天命剑封印处+上古剑圣遗冢"}
            ],
            "zones": [
                {"name": "外围", "depth": "1-10层", "danger": "低", "description": "普通剑修坟墓，剑意稀薄"},
                {"name": "中层", "depth": "11-50层", "danger": "中", "description": "中阶剑修坟墓，剑意浓郁，需淬体九重以上才能承受"},
                {"name": "深处", "depth": "51-100层", "danger": "高", "description": "高阶剑修坟墓，剑意足以斩杀炼气期以下"},
                {"name": "最深处", "depth": "100层+", "danger": "极高", "description": "天命剑封印处，上古剑圣遗冢，仅限天命剑持有者"}
            ]
        },
        {
            "id": "loc_血煞殿_详细",
            "name": "血煞殿",
            "parent": "loc_血煞深渊_0001",
            "type": "place",
            "status": "canon",
            "tagline": "血煞门权力中心，以血炼器之地",
            "fields": [
                {"name": "位置", "value": "血煞深渊最底层"},
                {"name": "功能", "value": "门主居住、血祭仪式、炼器"},
                {"name": "危险", "value": "血煞之气浓郁，外人难以承受"}
            ]
        },
        {
            "id": "loc_逍遥阁总坛_详细",
            "name": "逍遥阁总坛",
            "parent": "loc_逍遥山_0001",
            "type": "place",
            "status": "canon",
            "tagline": "中立势力总部，丹道鼎盛",
            "fields": [
                {"name": "位置", "value": "逍遥山顶"},
                {"name": "功能", "value": "丹药炼制、情报交易、拍卖"},
                {"name": "特色", "value": "中立区，三宗弟子均可进入交易"}
            ]
        },
        {
            "id": "loc_青云殿_详细",
            "name": "青云殿",
            "parent": "loc_青云山脉_0001",
            "type": "place",
            "status": "canon",
            "tagline": "青云宗总部，符箓之道圣地",
            "fields": [
                {"name": "位置", "value": "青云山脉主峰"},
                {"name": "功能", "value": "符箓炼制、传承"},
                {"name": "特色", "value": "天青符诀发源地"}
            ]
        }
    ]
}

# ============================================================
# 2. 势力内部结构扩展
# ============================================================

EXTENDED_FACTIONS = {
    "org_天剑宗_详细": {
        "id": "org_天剑宗_详细",
        "parent": "org_天剑宗_0001",
        "type": "org_detail",
        "status": "canon",
        "tagline": "正道第一宗内部权力结构",
        "fields": [
            {"name": "宗主", "value": "剑圣·李白白（筑基圆满）"},
            {"name": "大长老", "value": "执法堂长老·张正道（筑基中期）"},
            {"name": "二长老", "value": "传功堂长老·白鹤（筑基后期）"},
            {"name": "三长老", "value": "戒律堂长老·铁面（筑基初期）"}
        ],
        "departments": [
            {
                "name": "宗主殿",
                "leader": "剑圣·李白白",
                "power": "最高决策权",
                "members": "宗主+核心长老",
                "tasks": ["宗门战略", "重大决策", "对外关系"]
            },
            {
                "name": "执事堂",
                "leader": "王执事（副职）+ 赵执事（正职）",
                "power": "日常管理",
                "members": "外门执事约20人",
                "tasks": ["弟子考核", "资源分配", "纪律执行"],
                "corruption": "存在腐败，王执事与血煞门有暗线联系"
            },
            {
                "name": "剑阁",
                "leader": "阁主·风清扬（筑基后期）",
                "power": "功法传承",
                "members": "剑阁长老5人",
                "tasks": ["剑法传授", "典籍保管", "剑冢管理"],
                "secret": "掌握天命剑相关秘密，但被宗主封锁信息"
            },
            {
                "name": "丹堂",
                "leader": "炼丹师·孙婆婆（炼气后期）",
                "power": "丹药炼制",
                "members": "约30名炼药弟子",
                "tasks": ["丹药生产", "供应外门"],
                "dependency": "依赖逍遥阁提供部分高阶丹药"
            },
            {
                "name": "外门",
                "leader": "外门掌门·周长青（炼气圆满）",
                "power": "基础弟子管理",
                "members": "弟子约2000人",
                "tasks": ["日常修炼", "任务执行"],
                "structure": ["杂役弟子（约500人）", "内门候选（约300人）", "正式弟子（约1200人）"]
            },
            {
                "name": "内门",
                "leader": "内门掌门·沈青云（筑基初期）",
                "power": "精英弟子培养",
                "members": "弟子约100人",
                "tasks": ["高级功法传授", "宗门任务"],
                "requirement": "需通过外门选拔，资质达标"
            },
            {
                "name": "执法堂",
                "leader": "铁面长老（筑基初期）",
                "power": "纪律审判",
                "members": "执法弟子约50人",
                "tasks": ["违戒查处", "外敌入侵应对"],
                "corruption_risk": "王执事在此安插眼线"
            }
        ],
        "power_struggle": {
            "faction_main": "保守派（宗主李白白）",
            "faction_reform": "改革派（部分长老）",
            "faction_secret": "神秘派（剑阁长老，掌握天命剑秘密）",
            "faction_enemy": "内奸派（王执事及其党羽，与血煞门勾结）"
        }
    },

    "org_血煞门_详细": {
        "id": "org_血煞门_详细",
        "parent": "org_血煞门_0001",
        "type": "org_detail",
        "status": "canon",
        "tagline": "魔道大宗内部权力结构",
        "fields": [
            {"name": "门主", "value": "血煞老祖（金丹初期）"},
            {"name": "圣女", "value": "血姬（金丹后期，门主弟子）"},
            {"name": "护法", "value": "四大血护（筑基圆满）"}
        ],
        "departments": [
            {
                "name": "门主殿",
                "leader": "血煞老祖",
                "power": "最高决策权",
                "secret": "修炼血煞真经，以万民血气修炼"
            },
            {
                "name": "血堂",
                "leader": "血堂主·屠万山（筑基后期）",
                "power": "对外征伐",
                "tasks": ["攻打正道宗门", "掠夺资源", "培养死士"]
            },
            {
                "name": "煞堂",
                "leader": "煞堂堂主·阴九幽（筑基后期）",
                "power": "情报暗杀",
                "tasks": ["刺探情报", "暗杀敌人", "渗透正道宗门"],
                "corruption": "已在天剑宗安插王执事作为内应"
            },
            {
                "name": "炼血阁",
                "leader": "阁主·血娘子（筑基圆满）",
                "power": "血道功法研究",
                "tasks": ["炼制血器", "研究血道功法", "培养血卫"]
            },
            {
                "name": "圣女殿",
                "leader": "血姬（金丹后期）",
                "power": "传承与培养",
                "tasks": ["培养圣女弟子", "研究血道秘术"],
                "secret": "血姬实为上古血族后裔，血脉纯度极高"
            }
        ],
        "infiltration": {
            "天剑宗": "王执事（中层内应）",
            "青云宗": "未知",
            "逍遥阁": "无直接渗透，但进行商业渗透"
        }
    },

    "org_逍遥阁_详细": {
        "id": "org_逍遥阁_详细",
        "parent": "org_逍遥阁_0001",
        "type": "org_detail",
        "status": "canon",
        "tagline": "中立势力内部结构与经济网络",
        "fields": [
            {"name": "阁主", "value": "逍遥子（元婴初期）"},
            {"name": "副阁主", "value": "白公子（金丹后期）"},
            {"name": "核心成员", "value": "十二丹王（筑基圆满）"}
        ],
        "departments": [
            {
                "name": "丹堂",
                "leader": "丹王·张老（筑基圆满）",
                "power": "丹药生产",
                "tasks": ["丹药炼制", "丹方研究"],
                "secret": "掌握上古丹方《九转还魂丹》残卷"
            },
            {
                "name": "情报堂",
                "leader": "千面狐·柳如烟（金丹初期）",
                "power": "情报收集",
                "tasks": ["市场情报", "宗门动态", "人物档案"],
                "network": "遍布三宗的间谍网络"
            },
            {
                "name": "拍卖堂",
                "leader": "拍卖师·钱万金（筑基后期）",
                "power": "资源交易",
                "tasks": ["拍卖行运营", "稀有物品交易"],
                "secret": "暗中收购上古遗物"
            },
            {
                "name": "护卫堂",
                "leader": "堂主·铁衣侯（筑基圆满）",
                "power": "武装护卫",
                "tasks": ["商队护卫", "宗门安保"]
            }
        ],
        "economic_power": {
            "control": "掌控70%丹药市场",
            "trade_routes": "东海鲛人贸易航线",
            "leverage": "可断供丹药施压各宗门"
        }
    }
}

# ============================================================
# 3. 秘辛与历史扩展
# ============================================================

EXTENDED_SECRETS = {
    "event_天裂之劫_真相": {
        "id": "event_天裂之劫_真相",
        "parent": "event_天裂之劫_0001",
        "type": "secret",
        "status": "draft",
        "tagline": "天裂之劫的真相：上古剑圣为阻止外神入侵，撕裂天穹，代价是剑道纪元终结",
        "fields": [
            {"name": "时间", "value": "约五千年前"},
            {"name": "表层真相", "value": "天穹碎裂，天地灵气暴走"},
            {"name": "深层真相", "value": "上古剑圣发现'外神'即将降临，撕裂天穹以封印通道，但封印失败导致天地崩塌"},
            {"name": "幕后黑手", "value": "外神（异界存在，非本世界原生）"},
            {"name": "天命剑真正作用", "value": "重启封印装置，或彻底关闭通道"},
            {"name": "萧辰身世关联", "value": "可能是上古剑圣转世，或其后裔"}
        ],
        "revealed_chapters": [],
        "mystery_level": "tier_1"
    },

    "secret_上古剑圣_详细": {
        "id": "secret_上古剑圣_详细",
        "type": "secret",
        "status": "draft",
        "tagline": "上古剑圣的真实身份与牺牲",
        "fields": [
            {"name": "真名", "value": "李太白（与天剑宗现任宗主同姓，疑似同脉）"},
            {"name": "身份", "value": "上古剑道纪元最后一名剑帝"},
            {"name": "成就", "value": "一剑开天门，万剑朝宗"},
            {"name": "牺牲", "value": "撕裂天穹封印外神通道，自身化为天命剑"},
            {"name": "转世推测", "value": "可能转世为萧辰（孤儿身世+剑道天赋）"}
        ]
    },

    "secret_外神降临_详细": {
        "id": "secret_外神降临_详细",
        "type": "secret",
        "status": "draft",
        "tagline": "外神即将再次降临，天命剑是唯一钥匙",
        "fields": [
            {"name": "外神定义", "value": "来自其他维度的存在，以灵气/灵魂为食"},
            {"name": "上次入侵", "value": "五千年前，被剑圣封印"},
            {"name": "封印状态", "value": "松动中，每千年一次小裂隙"},
            {"name": "血煞门的真相", "value": "部分高层知道外神存在，试图打开通道迎接'神明'"},
            {"name": "萧辰的使命", "value": "要么重启封印，要么斩杀外神"}
        ]
    },

    "secret_血族后裔_详细": {
        "id": "secret_血族后裔_详细",
        "type": "secret",
        "status": "draft",
        "tagline": "血姬的真实身份：上古血族纯血后裔",
        "fields": [
            {"name": "血姬真名", "value": "姬无月"},
            {"name": "血脉", "value": "上古血族纯血（万中无一）"},
            {"name": "能力", "value": "血脉觉醒后可召唤血族大军"},
            {"name": "立场", "value": "矛盾——渴望融入人类，但又受血脉驱使"},
            {"name": "与萧辰的关系", "value": "未来可能产生情感纠葛"}
        ]
    }
}

# ============================================================
# 4. 武力体系细化
# ============================================================

EXTENDED_POWER_SYSTEM = {
    "battle_power": {
        "淬体期": {
            "description": "肉身打磨阶段，无法御气，纯靠力量和技巧",
            "combat_level": "凡人勇士级别",
            "max_speed": "日行百里",
            "max_stamina": "战斗约半柱香",
            "special_ability": "无",
            "weakness": "惧怕远程攻击，持久战吃亏"
        },
        "炼气期": {
            "description": "凝聚气旋，可外放剑气，开始御物",
            "combat_level": "武林高手级别",
            "max_speed": "日行千里（轻身术）",
            "max_stamina": "战斗约一炷香",
            "special_ability": "轻身术、外放剑气、御器飞行（低空）",
            "weakness": "防御仍脆弱，惧怕淬体九重巅峰"
        },
        "筑基期": {
            "description": "凝结道基，可御剑飞行，持久战能力强",
            "combat_level": "武林宗师级别",
            "max_speed": "御剑飞行，日行万里",
            "max_stamina": "可持续战斗数个时辰",
            "special_ability": "本命剑诀、剑意初成、遁术",
            "weakness": "道基受损则修为大跌"
        },
        "金丹期": {
            "description": "凝结金丹，可调动天地之力，一击毁城",
            "combat_level": "宗师级别，一人可敌一军",
            "max_speed": "御剑瞬息百里",
            "max_stamina": "可持续战斗数日",
            "special_ability": "金丹护体、天地灵气操控、剑气化形",
            "weakness": "金丹被破则修为尽毁"
        },
        "元婴期": {
            "description": "破丹成婴，元婴出窍，肉身损毁亦可重生",
            "combat_level": "绝世高手级别，一人可敌一城",
            "max_speed": "瞬息千里",
            "max_stamina": "近乎无限（元婴不灭可恢复）",
            "special_ability": "元婴出窍、空间操控、法术领域",
            "weakness": "元婴被灭则真死"
        }
    },

    "power_balance": {
        "同级战斗": "技巧/装备/实战经验决定胜负，非绝对压制",
        "小境界差距": "一重差距约10-15%胜率优势，可被装备/技巧弥补",
        "大境界差距": "约10倍实力差距，小境界无法逆斩大境界（除非有Legendary道具）",
        "装备加成": "凡器+10%，灵器+30%，法器+50%，法宝+100%，Legendary无上限",
        "特殊体质": "剑体+剑道修炼速度50%，血体+血道功法效果200%"
    },

    "weapon_tiers": {
        "凡器": {"price": "1-10下品灵石", "bonus": "+10%攻击力"},
        "灵器": {"price": "10-100下品灵石", "bonus": "+30%攻击力"},
        "法器": {"price": "100-1000下品灵石", "bonus": "+50%攻击力，可注入灵力"},
        "法宝": {"price": "1000下品灵石起", "bonus": "+100%攻击力，可成长"},
        "Legendary": {"price": "无价", "bonus": "特殊能力，独一无二"}
    },

    "medicine_tiers": {
        "一品": {"price": "10下品", "effect": "疗伤、基础修炼"},
        "二品": {"price": "50下品", "effect": "辅助突破、增强实力"},
        "三品": {"price": "500下品", "effect": "大幅提升、延缓衰老"},
        "四品": {"price": "5000下品", "effect": "起死回生、延寿"},
        "五品以上": {"price": "无价", "effect": "改变命运"}
    },

    "bloodlines": {
        "普通": {"description": "无特殊血脉", "cultivation_bonus": "无"},
        "剑体": {"description": "天生剑道亲和", "cultivation_bonus": "剑道修炼+50%"},
        "血体": {"description": "血道功法适应性极强", "cultivation_bonus": "血道修炼+200%"},
        "丹体": {"description": "天生炼丹体质", "cultivation_bonus": "炼丹成功率+30%"},
        "上古血脉": {"description": "远古强者血脉残留", "cultivation_bonus": "全属性+20%，觉醒后更强"}
    }
}

# ============================================================
# 5. 新增角色
# ============================================================

EXTENDED_CHARACTERS = [
    {
        "id": "char_李白白_0001",
        "name": "李白白",
        "role": "天剑宗宗主",
        "age": 320,
        "gender": "男",
        "realm": "筑基圆满",
        "status": "canon",
        "tagline": "天剑宗现任宗主，正道领袖之一，与上古剑圣有血缘关系",
        "fields": [
            {"name": "身份", "value": "天剑宗宗主"},
            {"name": "性格", "value": "沉稳、睿智、有担当"},
            {"name": "外貌", "value": "白发白须，仙风道骨"},
            {"name": "背景", "value": "李太白（上古剑圣）的后裔，守护天命剑秘密"},
            {"name": "目标", "value": "等待天命之人，重启封印"},
            {"name": "秘密", "value": "知道萧辰身世，在观察他"}
        ],
        "relations": [
            {"type": "member_of", "to": "org_天剑宗_0001"},
            {"type": "ancestor_of", "to": "char_萧辰_0001"},
            {"type": "sees_potential_in", "to": "char_萧辰_0001"}
        ]
    },
    {
        "id": "char_血姬_0001",
        "name": "血姬",
        "role": "血煞门圣女",
        "age": 200,
        "gender": "女",
        "realm": "金丹后期",
        "status": "canon",
        "tagline": "上古血族纯血后裔，美艳动人，内心矛盾",
        "fields": [
            {"name": "身份", "value": "血煞门圣女"},
            {"name": "真名", "value": "姬无月"},
            {"name": "性格", "value": "外表冷艳，内心柔软，渴望被接受"},
            {"name": "外貌", "value": "红衣似血，容貌绝美，眼神忧郁"},
            {"name": "血脉", "value": "上古血族纯血"},
            {"name": "目标", "value": "寻找属于自己的路，不被血脉控制"},
            {"name": "与萧辰关系", "value": "未来可能产生情愫"}
        ],
        "relations": [
            {"type": "member_of", "to": "org_血煞门_0001"},
            {"type": "opposed_to", "to": "char_萧辰_0001"},
            {"type": "destined_lover", "to": "char_萧辰_0001"}
        ]
    },
    {
        "id": "char_风清扬_0001",
        "name": "风清扬",
        "role": "天剑宗剑阁阁主",
        "age": 280,
        "gender": "男",
        "realm": "筑基后期",
        "status": "canon",
        "tagline": "天剑宗剑道传承者，掌握天命剑部分秘密",
        "fields": [
            {"name": "身份", "value": "天剑宗剑阁阁主"},
            {"name": "性格", "value": "孤傲、执着、守旧"},
            {"name": "外貌", "value": "瘦削，长须，目光如剑"},
            {"name": "背景", "value": "守护剑阁百年，知道天命剑的秘密"},
            {"name": "目标", "value": "找到合适的人继承天命剑"},
            {"name": "与萧辰关系", "value": "早期可能是导师型角色"}
        ],
        "relations": [
            {"type": "member_of", "to": "org_天剑宗_0001"},
            {"type": "mentor_of", "to": "char_萧辰_0001"}
        ]
    },
    {
        "id": "char_逍遥子_0001",
        "name": "逍遥子",
        "role": "逍遥阁阁主",
        "age": 500,
        "gender": "男",
        "realm": "元婴初期",
        "status": "canon",
        "tagline": "中立势力领袖，丹道大宗师，深不可测",
        "fields": [
            {"name": "身份", "value": "逍遥阁阁主"},
            {"name": "性格", "value": "洒脱、精明、中立"},
            {"name": "外貌", "value": "中年模样，常带笑意，目光深邃"},
            {"name": "背景", "value": "活了五百年，见证过天裂之劫的部分真相"},
            {"name": "目标", "value": "维持三方平衡，避免大战"},
            {"name": "秘密", "value": "掌握《九转还魂丹》残卷，可复活元婴以下修士"}
        ],
        "relations": [
            {"type": "leader_of", "to": "org_逍遥阁_0001"},
            {"type": "neutral_to", "to": "char_萧辰_0001"}
        ]
    }
]

# ============================================================
# 主程序
# ============================================================

def main():
    # 加载现有数据
    existing = load_existing()
    
    if existing:
        print(f"📦 已加载现有世界包，共 {len(existing['entries'])} 个条目")
        entries = existing['entries']
    else:
        print("⚠️ 未找到现有世界包，将创建新的")
        entries = {}
    
    # 添加扩展数据
    added_count = 0
    
    # 添加详细地理
    for geo in EXTENDED_GEOGRAPHY["regions"]:
        geo_id = geo["id"]
        if geo_id not in entries:
            entries[geo_id] = {
                "id": geo_id,
                "kind": "region",
                "name": geo["name"],
                "status": geo["status"],
                "tagline": geo["tagline"],
                "fields": geo.get("fields", []),
                "parent": geo.get("parent", "")
            }
            added_count += 1
    
    # 添加详细地点
    for loc in EXTENDED_GEOGRAPHY["key_locations"]:
        loc_id = loc["id"]
        if loc_id not in entries:
            entries[loc_id] = {
                "id": loc_id,
                "kind": loc["type"],
                "name": loc["name"],
                "status": loc["status"],
                "tagline": loc["tagline"],
                "fields": loc.get("fields", []),
                "zones": loc.get("zones", [])
            }
            added_count += 1
    
    # 添加势力详情
    for org_id, org_data in EXTENDED_FACTIONS.items():
        if org_id not in entries:
            entries[org_id] = {
                "id": org_id,
                "kind": org_data.get("type", "org_detail"),
                "name": org_data.get("name", org_id),
                "status": org_data.get("status", "canon"),
                "tagline": org_data.get("tagline", ""),
                "fields": org_data.get("fields", []),
                "departments": org_data.get("departments", [])
            }
            added_count += 1
    
    # 添加秘辛
    for secret_id, secret_data in EXTENDED_SECRETS.items():
        if secret_id not in entries:
            entries[secret_id] = {
                "id": secret_id,
                "kind": secret_data.get("type", "secret"),
                "name": secret_data.get("name", secret_id),
                "status": secret_data.get("status", "draft"),
                "tagline": secret_data.get("tagline", ""),
                "fields": secret_data.get("fields", []),
                "mystery_level": secret_data.get("mystery_level", "tier_1")
            }
            added_count += 1
    
    # 添加详细武力体系
    power_id = "power_武力体系_详细"
    if power_id not in entries:
        entries[power_id] = {
            "id": power_id,
            "kind": "power",
            "name": "详细武力体系",
            "status": "canon",
            "tagline": "各境界战斗表现、装备体系、丹药体系、血脉体系",
            "fields": [
                {"name": "淬体期战斗", "value": "凡人勇士级别，日行百里，半柱香战力"},
                {"name": "炼气期战斗", "value": "武林高手级别，日行千里，一炷香战力"},
                {"name": "筑基期战斗", "value": "宗师级别，御剑飞行，数个时辰战力"},
                {"name": "金丹期战斗", "value": "绝世高手，一击毁城，数日战力"},
                {"name": "元婴期战斗", "value": "传奇级别，瞬息千里，近乎无限战力"}
            ],
            "battle_power": EXTENDED_POWER_SYSTEM["battle_power"],
            "power_balance": EXTENDED_POWER_SYSTEM["power_balance"],
            "weapon_tiers": EXTENDED_POWER_SYSTEM["weapon_tiers"],
            "medicine_tiers": EXTENDED_POWER_SYSTEM["medicine_tiers"],
            "bloodlines": EXTENDED_POWER_SYSTEM["bloodlines"]
        }
        added_count += 1
    
    # 添加新角色
    for char in EXTENDED_CHARACTERS:
        char_id = char["id"]
        if char_id not in entries:
            entries[char_id] = {
                "id": char_id,
                "kind": "figure",
                "name": char["name"],
                "status": char["status"],
                "tagline": char["tagline"],
                "fields": char.get("fields", []),
                "relations": char.get("relations", [])
            }
            added_count += 1
    
    # 保存更新后的世界包
    if existing:
        output_data = existing.copy()
        output_data["entries"] = entries
        output_data["updated_at"] = datetime.now().isoformat()
    else:
        output_data = {
            "name": "玄天大陆",
            "created_at": datetime.now().isoformat(),
            "version": "1.1",
            "entries": entries,
            "updated_at": datetime.now().isoformat()
        }
    
    # 保存文件
    save_world(output_data, WORLD_DIR / "玄天大陆.json")
    save_world(output_data, PROJECT_DIR / "world-pack.json")
    
    print(f"\n✅ 世界包已更新！")
    print(f"📊 新增条目：{added_count} 个")
    print(f"📊 总条目数：{len(entries)} 个")
    
    # 统计分布
    kind_count = {}
    for entry in entries.values():
        kind = entry['kind']
        kind_count[kind] = kind_count.get(kind, 0) + 1
    
    print("\n📋 条目分布:")
    for kind, count in sorted(kind_count.items()):
        print(f"  {kind}: {count}")

if __name__ == "__main__":
    main()
