#!/usr/bin/env python3
"""
初始化《天命》玄天大陆世界包
包含：地理、势力、修炼体系、货币经济、灵兽妖兽、禁忌秘辛
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# 世界包路径
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

# ============================================================
# 核心设定数据
# ============================================================

WORLD_DATA = {
    "name": "玄天大陆",
    "created_at": datetime.now().isoformat(),
    "version": "1.0",
    "entries": {},
    "sources": [],
    "issues": []
}

# ============================================================
# 1. 世界总纲
# ============================================================

WORLD_DATA["entries"]["world_玄天_0001"] = {
    "id": "world_玄天_0001",
    "kind": "world",
    "name": "玄天大陆",
    "status": "canon",
    "tagline": "万年剑道鼎盛，三宗鼎立，天命剑现世者可改天地格局",
    "content": """玄天大陆，东方玄幻世界。万里疆域，三宗鼎立，王朝更迭。
修炼体系：淬体九重 → 炼气四阶 → 筑基四阶 → 金丹四阶 → 元婴四阶 → 化神四阶 → 炼虚 → 合体 → 大乘 → 渡劫。
上古时期曾有"剑道纪元"，万剑朝宗，后历经"天裂之劫"，大陆板块碎裂，剑道式微。
如今是"复苏纪元"，各大宗门争夺上古剑冢、遗藏。
天命剑传说：上古剑圣遗物，可助持有者突破境界瓶颈，但需以血为祭。"""
}

# ============================================================
# 2. 力量体系
# ============================================================

WORLD_DATA["entries"]["power_修炼_0001"] = {
    "id": "power_修炼_0001",
    "kind": "power",
    "name": "修炼体系",
    "status": "canon",
    "tagline": "十境阶梯，每境可突破，瓶颈触发奇遇或顿悟",
    "fields": [
        {"name": "境界列表", "value": "淬体九重→炼气四阶→筑基四阶→金丹四阶→元婴四阶→化神四阶→炼虚→合体→大乘→渡劫"},
        {"name": "寿命上限", "value": "淬体100年/炼气200年/筑基300年/金丹500年/元婴1000年/化神3000年/炼虚5000年/合体万年/大乘2万年/渡劫飞升"},
        {"name": "核心差异", "value": "淬体强化肉身，炼气沟通天地灵气，筑基凝结道基，金丹凝丹，元婴破丹成婴，化神元神出窍"},
        {"name": "突破条件", "value": "境界感悟+瓶颈契机（奇遇/生死危机/悟道）"},
        {"name": "同境胜负", "value": "技巧/装备/实战经验/心境，非绝对实力压制"}
    ]
}

# 各境界详细定义
REALMS = [
    {"id": "realm_淬体_0001", "name": "淬体九重", "description": "打磨肉身，打基础。一重只能搬石，九重可碎砖裂石。无法御气，只能靠肉身硬抗。"},
    {"id": "realm_炼气_0001", "name": "炼气四阶", "description": "凝聚气旋，沟通天地。初期会轻身术，中期可外放剑气，后期可御器飞行（低空），圆满可短暂滞空。"},
    {"id": "realm_筑基_0001", "name": "筑基四阶", "description": "夯实道基，寿元两百。可御剑飞行，施展本命功法，战斗持久力大幅提升。"},
    {"id": "realm_金丹_0001", "name": "金丹四阶", "description": "凝结金丹，寿元五百。可调动天地之力，一击毁城。"},
    {"id": "realm_元婴_0001", "name": "元婴四阶", "description": "破丹成婴，寿元千载。元婴出窍，肉身损毁亦可重生。"},
    {"id": "realm_化神_0001", "name": "化神四阶", "description": "元神化神，飞天遁地。可操控空间碎片，瞬息千里。"},
    {"id": "realm_炼虚_0001", "name": "炼虚", "description": "炼化虚空，操控空间。"},
    {"id": "realm_合体_0001", "name": "合体", "description": "身心合体，返璞归真。"},
    {"id": "realm_大乘_0001", "name": "大乘", "description": "大乘境界，半步仙人。"},
    {"id": "realm_渡劫_0001", "name": "渡劫", "description": "渡过天劫，飞升仙界。"}
]

for realm in REALMS:
    WORLD_DATA["entries"][realm["id"]] = {
        "id": realm["id"],
        "kind": "realm",
        "name": realm["name"],
        "status": "canon",
        "tagline": realm["description"]
    }

# ============================================================
# 3. 地理板块
# ============================================================

GEOGRAPHY = [
    {"id": "loc_中州_0001", "name": "中州", "type": "region", "tagline": "玄天大陆核心地带，三宗总部所在地"},
    {"id": "loc_北荒_0001", "name": "北荒", "type": "region", "tagline": "苦寒之地，凶兽出没，鲜有人烟"},
    {"id": "loc_南岭_0001", "name": "南岭", "type": "region", "tagline": "瘴气弥漫，丹药资源丰富"},
    {"id": "loc_东海_0001", "name": "东海", "type": "region", "tagline": "海岛星罗棋布，鲛人族聚居"},
    {"id": "loc_西漠_0001", "name": "西漠", "type": "region", "tagline": "古道遗迹，佛门道场"},
    {"id": "loc_天剑山脉_0001", "name": "天剑山脉", "type": "region", "tagline": "正道第一剑宗所在地，终年积雪，剑气侵蚀形成无数剑冢"},
    {"id": "loc_剑冢_0001", "name": "万剑剑冢", "type": "place", "tagline": "天剑山脉后山禁地，上古剑修埋葬之所，蕴含无尽剑意，进入需剑道天赋"},
    {"id": "loc_外门_0001", "name": "天剑宗外门", "type": "place", "tagline": "萧辰所在弟子居所，练剑场、食堂、宿舍分布其中"},
    {"id": "loc_内门_0001", "name": "天剑宗内门", "type": "place", "tagline": "精英弟子居所，距离主城需御剑半日"},
    {"id": "loc_血煞深渊_0001", "name": "血煞深渊", "type": "region", "tagline": "魔道大宗血煞门总部，常年血雾笼罩，阴煞之气浓郁"},
    {"id": "loc_逍遥山_0001", "name": "逍遥山", "type": "region", "tagline": "中立势力逍遥阁所在地，丹道鼎盛，富甲一方"}
]

for geo in GEOGRAPHY:
    WORLD_DATA["entries"][geo["id"]] = {
        "id": geo["id"],
        "kind": geo["type"],
        "name": geo["name"],
        "status": "canon",
        "tagline": geo.get("tagline", "")
    }

# ============================================================
# 4. 势力组织
# ============================================================

FACTIONS = [
    {
        "id": "org_天剑宗_0001",
        "name": "天剑宗",
        "type": "org",
        "status": "canon",
        "tagline": "正道第一剑宗，剑道圣地",
        "fields": [
            {"name": "立场", "value": "正道"},
            {"name": "地理位置", "value": "天剑山脉"},
            {"name": "宗主", "value": "剑圣·李白白（筑基圆满）"},
            {"name": "核心功法", "value": "天剑诀"},
            {"name": "内部结构", "value": "外门（弟子）→内门（精英）→执事堂（管理）→剑阁（传承）→宗主殿"},
            {"name": "资源分配", "value": "外门每月低阶灵石10块，丹药1瓶；内门十倍以上"},
            {"name": "对外关系", "value": "与青云宗联盟，敌视血煞门"}
        ]
    },
    {
        "id": "org_血煞门_0001",
        "name": "血煞门",
        "type": "org",
        "status": "canon",
        "tagline": "魔道大宗，血道功法诡异阴毒",
        "fields": [
            {"name": "立场", "value": "魔道"},
            {"name": "地理位置", "value": "血煞深渊"},
            {"name": "门主", "value": "血煞老祖（金丹初期）"},
            {"name": "核心功法", "value": "血煞真经"},
            {"name": "特点", "value": "以血炼器，以命换功，手段狠辣"},
            {"name": "对外关系", "value": "与正道势同水火，暗中渗透各大宗门"}
        ]
    },
    {
        "id": "org_逍遥阁_0001",
        "name": "逍遥阁",
        "type": "org",
        "status": "canon",
        "tagline": "中立势力，掌控丹药市场",
        "fields": [
            {"name": "立场", "value": "中立"},
            {"name": "地理位置", "value": "逍遥山"},
            {"name": "阁主", "value": "逍遥子（元婴初期）"},
            {"name": "核心业务", "value": "丹药、情报、拍卖"},
            {"name": "特点", "value": "不直接参与纷争，但影响各方经济命脉"},
            {"name": "对外关系", "value": "与三宗均有贸易往来"}
        ]
    },
    {
        "id": "org_青云宗_0001",
        "name": "青云宗",
        "type": "org",
        "status": "canon",
        "tagline": "正道第二大宗门，符箓之道独步天下",
        "fields": [
            {"name": "立场", "value": "正道"},
            {"name": "地理位置", "value": "青云山脉"},
            {"name": "宗主", "value": "青云真人（筑基后期）"},
            {"name": "核心功法", "value": "天青符诀"},
            {"name": "对外关系", "value": "与天剑宗结盟"}
        ]
    },
    {
        "id": "org_东海鲛族_0001",
        "name": "东海鲛族",
        "type": "org",
        "status": "canon",
        "tagline": "鲛人王朝，掌控东海航道",
        "fields": [
            {"name": "立场", "value": "中立偏商"},
            {"name": "地理位置", "value": "蓬莱仙岛"},
            {"name": "首领", "value": "鲛人王（金丹中期）"},
            {"name": "特点", "value": "善御水，珍珠为宝，与陆地宗门贸易密切"},
            {"name": "对外关系", "value": "不介入陆上纷争，但垄断东海航运"}
        ]
    }
]

for faction in FACTIONS:
    WORLD_DATA["entries"][faction["id"]] = {
        "id": faction["id"],
        "kind": faction["type"],
        "name": faction["name"],
        "status": faction["status"],
        "tagline": faction["tagline"],
        "fields": faction.get("fields", [])
    }

# ============================================================
# 5. 人物
# ============================================================

CHARACTERS = [
    {
        "id": "char_萧辰_0001",
        "name": "萧辰",
        "role": "主角",
        "age": 16,
        "gender": "男",
        "realm": "淬体三重→四重",
        "status": "canon",
        "tagline": "孤儿出身，坚韧沉默，左手腕有剑茧，铁剑天命剑封印形态",
        "fields": [
            {"name": "身份", "value": "天剑宗外门弟子"},
            {"name": "性格", "value": "坚韧不拔、沉默寡言、内心有梦、重情重义"},
            {"name": "外貌", "value": "消瘦但结实，眼神坚定，黑发束起，左手腕剑茧"},
            {"name": "背景", "value": "孤儿，被天剑宗长老收养，从小刻苦修炼"},
            {"name": "目标", "value": "成为最强剑修，寻找身世真相"},
            {"name": "金手指", "value": "天命剑（封印中，可助突破瓶颈）"},
            {"name": "关键关系", "value": "苏逸（师兄照顾）、王大（敌对）"}
        ],
        "relations": [
            {"type": "member_of", "to": "org_天剑宗_0001"},
            {"type": "owns", "to": "item_天命剑_0001"}
        ]
    },
    {
        "id": "char_苏逸_0001",
        "name": "苏逸",
        "role": "师兄",
        "age": 19,
        "gender": "男",
        "realm": "炼气初期",
        "status": "canon",
        "tagline": "外门佼佼者，热情豪爽，照顾萧辰",
        "fields": [
            {"name": "身份", "value": "天剑宗外门弟子"},
            {"name": "性格", "value": "热情、豪爽、仗义"},
            {"name": "能力", "value": "轻身术纯熟，山药飘来不喘不沾灰"},
            {"name": "目标", "value": "进入内门"},
            {"name": "关键关系", "value": "萧辰（师弟，照顾）"}
        ],
        "relations": [
            {"type": "member_of", "to": "org_天剑宗_0001"},
            {"type": "loves", "to": "char_萧辰_0001"}
        ]
    },
    {
        "id": "char_王大_0001",
        "name": "王大",
        "role": "反派（前期）",
        "age": 17,
        "gender": "男",
        "realm": "淬体四重",
        "status": "canon",
        "tagline": "外门刺头，欺软怕硬，心胸狭隘",
        "fields": [
            {"name": "身份", "value": "天剑宗外门弟子"},
            {"name": "性格", "value": "傲慢、欺软怕硬、心胸狭隘"},
            {"name": "外貌", "value": "矮小肥胖，眼神阴狠"},
            {"name": "背景", "value": "依附王执事，仗势欺人"},
            {"name": "目标", "value": "打压萧辰，争夺资源"},
            {"name": "弱点", "value": "傲慢导致轻敌，被萧辰击败"}
        ],
        "relations": [
            {"type": "member_of", "to": "org_天剑宗_0001"},
            {"type": "opposed_to", "to": "char_萧辰_0001"},
            {"type": "serves", "to": "char_王执事_0001"}
        ]
    },
    {
        "id": "char_王执事_0001",
        "name": "王执事",
        "role": "中层反派",
        "age": 35,
        "gender": "男",
        "realm": "炼气后期",
        "status": "canon",
        "tagline": "天剑宗执法堂执事，暗中观察萧辰",
        "fields": [
            {"name": "身份", "value": "天剑宗执法堂执事"},
            {"name": "性格", "value": "表面和善，实际精明"},
            {"name": "背景", "value": "与血煞门有暗线联系"},
            {"name": "目标", "value": "试探萧辰底细，可能图谋天命剑"}
        ],
        "relations": [
            {"type": "member_of", "to": "org_天剑宗_0001"}
        ]
    }
]

for char in CHARACTERS:
    WORLD_DATA["entries"][char["id"]] = {
        "id": char["id"],
        "kind": "figure",
        "name": char["name"],
        "status": char["status"],
        "tagline": char["tagline"],
        "fields": char.get("fields", [])
    }
    if "relations" in char:
        WORLD_DATA["entries"][char["id"]]["relations"] = char["relations"]

# ============================================================
# 6. 物品
# ============================================================

ITEMS = [
    {
        "id": "item_天命剑_0001",
        "name": "天命剑",
        "type": "thing",
        "status": "canon",
        "tagline": "上古剑圣遗物，封印形态为生锈铁剑，血祭可激活",
        "fields": [
            {"name": "类型", "value": "法器（Legendary）"},
            {"name": "当前状态", "value": "封印中（铁剑形态）"},
            {"name": "激活条件", "value": "持有者血液+生死危机"},
            {"name": "能力", "value": "突破境界瓶颈、释放寒芒、剑意护主"},
            {"name": "来历", "value": "上古剑圣遗物，封印于万剑剑冢深处"},
            {"name": "持有者", "value": "萧辰"}
        ]
    },
    {
        "id": "item_灵石_0001",
        "name": "下品灵石",
        "type": "thing",
        "status": "canon",
        "tagline": "通用货币，修炼资源",
        "fields": [
            {"name": "类型", "value": "货币/修炼资源"},
            {"name": "层级", "value": "下品<中品<上品<极品"},
            {"name": "兑换", "value": "100下品=1中品，100中品=1上品"},
            {"name": "用途", "value": "购买丹药、功法、装备"}
        ]
    },
    {
        "id": "item_疗伤丹_0001",
        "name": "疗伤丹",
        "type": "thing",
        "status": "canon",
        "tagline": "治愈外伤的基础丹药",
        "fields": [
            {"name": "类型", "value": "丹药"},
            {"name": "品级", "value": "一品"},
            {"name": "功效", "value": "愈合皮肉伤，恢复体力"},
            {"name": "价格", "value": "10下品灵石/颗"},
            {"name": "供应商", "value": "逍遥阁"}
        ]
    },
    {
        "id": "item_聚气丹_0001",
        "name": "聚气丹",
        "type": "thing",
        "status": "canon",
        "tagline": "辅助炼气期修炼的丹药",
        "fields": [
            {"name": "类型", "value": "丹药"},
            {"name": "品级", "value": "二品"},
            {"name": "功效", "value": "帮助凝聚气旋，加快修炼速度"},
            {"name": "价格", "value": "50下品灵石/颗"},
            {"name": "供应商", "value": "逍遥阁"}
        ]
    }
]

for item in ITEMS:
    WORLD_DATA["entries"][item["id"]] = {
        "id": item["id"],
        "kind": item["type"],
        "name": item["name"],
        "status": item["status"],
        "tagline": item["tagline"],
        "fields": item.get("fields", [])
    }

# ============================================================
# 7. 灵兽妖兽
# ============================================================

CREATURES = [
    {
        "id": "race_妖兽_0001",
        "name": "妖兽",
        "type": "race",
        "status": "canon",
        "tagline": "修炼成妖的野兽，可化形，分一到九阶",
        "fields": [
            {"name": "境界对应", "value": "一阶=淬体，五阶=筑基，九阶=元婴"},
            {"name": "特点", "value": "血脉越纯越强，可修炼化形"},
            {"name": "分布", "value": "深山老林、险地秘境"}
        ]
    },
    {
        "id": "race_剑灵_0001",
        "name": "剑灵",
        "type": "race",
        "status": "canon",
        "tagline": "剑道极致产生的灵体，可附于宝剑",
        "fields": [
            {"name": "诞生条件", "value": "万剑剑冢剑意汇聚，或剑修陨落时剑心不灭"},
            {"name": "能力", "value": "辅助剑道修炼，释放剑意攻击"},
            {"name": "稀有度", "value": "极罕见"}
        ]
    }
]

for creature in CREATURES:
    WORLD_DATA["entries"][creature["id"]] = {
        "id": creature["id"],
        "kind": creature["type"],
        "name": creature["name"],
        "status": creature["status"],
        "tagline": creature["tagline"],
        "fields": creature.get("fields", [])
    }

# ============================================================
# 8. 历史秘辛
# ============================================================

HISTORY = [
    {
        "id": "event_天裂之劫_0001",
        "name": "天裂之劫",
        "type": "event",
        "status": "canon",
        "tagline": "上古时期天穹碎裂，剑道纪元终结",
        "fields": [
            {"name": "时间", "value": "约五千年前"},
            {"name": "事件", "value": "天穹出现巨大裂痕，天地灵气暴走，剑道大宗纷纷陨落"},
            {"name": "后果", "value": "大陆板块碎裂，剑道式微，万剑剑冢形成"},
            {"name": "谜团", "value": "天裂是何原因？谁造成了这场灾难？"}
        ]
    },
    {
        "id": "secret_天命剑_0001",
        "name": "天命剑秘辛",
        "type": "secret",
        "status": "canon",
        "tagline": "上古剑圣遗物，可助突破，但代价未知",
        "fields": [
            {"name": "来历", "value": "上古剑圣毕生心血"},
            {"name": "封印原因", "value": "防止落入魔道之手"},
            {"name": "激活代价", "value": "以血为祭，每次激活消耗寿命"},
            {"name": "真正目的", "value": "等待天命之人，重启剑道纪元"}
        ]
    },
    {
        "id": "secret_萧辰身世_0001",
        "name": "萧辰身世之谜",
        "type": "secret",
        "status": "draft",
        "tagline": "孤儿身份背后隐藏着更大秘密",
        "fields": [
            {"name": "已知信息", "value": "被天剑宗长老收养，孤儿"},
            {"name": "悬念", "value": "父母是谁？为何被收养？与天命剑有何关联？"},
            {"name": "推测", "value": "可能是上古剑圣后裔"}
        ]
    }
]

for hist in HISTORY:
    WORLD_DATA["entries"][hist["id"]] = {
        "id": hist["id"],
        "kind": hist["type"],
        "name": hist["name"],
        "status": hist["status"],
        "tagline": hist["tagline"],
        "fields": hist.get("fields", [])
    }

# ============================================================
# 9. 禁忌与规则
# ============================================================

TABOOS = [
    {
        "id": "law_正道禁忌_0001",
        "name": "正道禁忌",
        "type": "law",
        "status": "canon",
        "tagline": "正道联盟约定，禁止使用血道功法",
        "fields": [
            {"name": "内容", "value": "禁止修炼血煞功法、献祭生灵"},
            {"name": "惩罚", "value": "格杀勿论"},
            {"name": "执行者", "value": "正道联盟执法堂"}
        ]
    },
    {
        "id": "law_剑冢规矩_0001",
        "name": "万剑剑冢规矩",
        "type": "law",
        "status": "canon",
        "tagline": "非剑道天赋者不得进入，违者剑意反噬",
        "fields": [
            {"name": "规则", "value": "只有剑道天赋者才能进入剑冢深处"},
            {"name": "后果", "value": "无天赋者强行进入会被剑意绞杀"},
            {"name": "例外", "value": "天命剑持有者可无视此规则"}
        ]
    }
]

for taboo in TABOOS:
    WORLD_DATA["entries"][taboo["id"]] = {
        "id": taboo["id"],
        "kind": taboo["type"],
        "name": taboo["name"],
        "status": taboo["status"],
        "tagline": taboo["tagline"],
        "fields": taboo.get("fields", [])
    }

# ============================================================
# 保存世界包
# ============================================================

def save_world_pack(data, output_path):
    """保存世界包"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 世界包已保存: {output_path}")
    print(f"📊 共 {len(data['entries'])} 个条目")
    
    # 按类型统计
    kind_count = {}
    for entry in data['entries'].values():
        kind = entry['kind']
        kind_count[kind] = kind_count.get(kind, 0) + 1
    
    print("\n📋 条目分布:")
    for kind, count in sorted(kind_count.items()):
        print(f"  {kind}: {count}")

if __name__ == "__main__":
    # 保存主世界包
    save_world_pack(WORLD_DATA, WORLD_DIR / "玄天大陆.json")
    
    # 同时保存到项目目录（方便访问）
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    save_world_pack(WORLD_DATA, PROJECT_DIR / "world-pack.json")
    
    print("\n🌍 玄天大陆世界包初始化完成！")
