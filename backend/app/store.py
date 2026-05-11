from __future__ import annotations

import hashlib
import json
import os
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

DATA_PATH = Path(os.getenv("SHORTPLAY_DB", Path(__file__).resolve().parent.parent / "data" / "db.json"))
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
_LOCK = threading.Lock()
AUTH_SECRET = os.getenv("SHORTPLAY_AUTH_SECRET", "shortplay-mvp-secret")


def default_password_hash(password: str) -> str:
    return hashlib.sha256(f"{AUTH_SECRET}:{password}".encode("utf-8")).hexdigest()


def default_users() -> list[dict[str, Any]]:
    ts = now()
    default_usage = {
        "video_total_seconds": 2000,
        "video_used_seconds": 0,
        "image_total": 1000,
        "image_used": 0,
        "export_total": 164,
        "export_used": 0,
    }
    return [
        {
            "id": "user_admin",
            "username": "admin",
            "display_name": "管理员",
            "password_hash": default_password_hash("admin123"),
            "role": "admin",
            "status": "active",
            "points": 100000,
            "token": "",
            "usage": {**default_usage},
            "created_at": ts,
            "last_login": "",
        },
        {
            "id": "user_demo",
            "username": "demo",
            "display_name": "演示用户",
            "password_hash": default_password_hash("demo123"),
            "role": "user",
            "status": "active",
            "points": 2000,
            "token": "",
            "usage": {**default_usage},
            "created_at": ts,
            "last_login": "",
        },
    ]


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def seed_data() -> dict[str, Any]:
    ts = now()
    project_id = "proj_haomen"
    episodes_hm = [
        {
            "id": "ep_001",
            "project_id": project_id,
            "no": 1,
            "title": "订婚现场的陌生女人",
            "summary": "女主闯入订婚现场，众人误以为她是服务员。",
            "script": "女主误闯豪门订婚现场，被众人嘲笑是服务员。反派未婚妻当众羞辱她，男主原本沉默，最后当众牵起女主的手，宣布她才是真正的未婚妻。",
            "duration_target": 30,
            "status": "storyboard_ready",
            "updated_at": ts,
        },
        {
            "id": "ep_002",
            "project_id": project_id,
            "no": 2,
            "title": "她才是真正的继承人",
            "summary": "男主当众牵起女主的手，揭开她的真实身份。",
            "script": "男主牵起女主的手，告诉所有宾客她才是真正的继承人。反派未婚妻质疑她的身份，管家拿出尘封多年的亲子鉴定。",
            "duration_target": 25,
            "status": "generating",
            "updated_at": ts,
        },
        {
            "id": "ep_003",
            "project_id": project_id,
            "no": 3,
            "title": "旧照片里的秘密",
            "summary": "女主在旧相册中发现自己与豪门家族的关系。",
            "script": "女主回到老宅，在母亲遗物里发现一张旧照片。照片背后写着一个豪门家族的姓氏，她开始怀疑自己的真实身世。",
            "duration_target": 30,
            "status": "draft",
            "updated_at": ts,
        },
        {
            "id": "ep_004",
            "project_id": project_id,
            "no": 4,
            "title": "未婚妻的反击",
            "summary": "反派不甘失败，公开质疑女主身份。",
            "script": "苏晴不甘失败，公开质疑林晚的身份，试图用一份伪造的资料扭转局面。顾沉提前安排的人出现，揭穿她的谎言。",
            "duration_target": 20,
            "status": "needs_review",
            "updated_at": ts,
        },
    ]
    shots_hm = [
        {
            "id": "shot_001",
            "episode_id": "ep_001",
            "no": 1,
            "title": "女主推门进入",
            "visual": "豪华宴会厅大门被推开，女主站在门口，灯光照在她脸上。",
            "dialogue": "这场订婚，不能继续。",
            "characters": ["林晚"],
            "scene": "豪门宴会厅",
            "duration": 3,
            "status": "completed",
            "updated_at": ts,
        },
        {
            "id": "shot_002",
            "episode_id": "ep_001",
            "no": 2,
            "title": "宾客议论",
            "visual": "宾客回头，反派未婚妻冷笑，现场气氛变得尖锐。",
            "dialogue": "她是谁？也配来这里？",
            "characters": ["苏晴"],
            "scene": "豪门宴会厅",
            "duration": 4,
            "status": "generating",
            "updated_at": ts,
        },
        {
            "id": "shot_003",
            "episode_id": "ep_001",
            "no": 3,
            "title": "男主起身",
            "visual": "男主从主桌缓慢起身，镜头推进，所有人安静下来。",
            "dialogue": "",
            "characters": ["顾沉"],
            "scene": "豪门宴会厅",
            "duration": 5,
            "status": "pending",
            "updated_at": ts,
        },
        {
            "id": "shot_004",
            "episode_id": "ep_001",
            "no": 4,
            "title": "身份反转",
            "visual": "男主走到女主身边，牵起她的手，众人震惊。",
            "dialogue": "她才是我的未婚妻。",
            "characters": ["林晚", "顾沉"],
            "scene": "豪门宴会厅",
            "duration": 6,
            "status": "pending",
            "updated_at": ts,
        },
        {
            "id": "shot_005",
            "episode_id": "ep_002",
            "no": 1,
            "title": "管家呈上鉴定书",
            "visual": "管家双手捧着泛黄的文件夹，缓步走向主席台。",
            "dialogue": "这份亲子鉴定，尘封了二十四年。",
            "characters": ["顾沉"],
            "scene": "豪门宴会厅",
            "duration": 4,
            "status": "completed",
            "updated_at": ts,
        },
        {
            "id": "shot_006",
            "episode_id": "ep_002",
            "no": 2,
            "title": "苏晴崩溃",
            "visual": "苏晴看到鉴定结果，手中的酒杯滑落，碎裂在地。",
            "dialogue": "不可能……这不可能！",
            "characters": ["苏晴"],
            "scene": "豪门宴会厅",
            "duration": 3,
            "status": "completed",
            "updated_at": ts,
        },
        {
            "id": "shot_007",
            "episode_id": "ep_002",
            "no": 3,
            "title": "林晚落泪",
            "visual": "林晚眼眶泛红，顾沉为她拭去眼泪，背景虚化。",
            "dialogue": "我终于找到你了。",
            "characters": ["林晚", "顾沉"],
            "scene": "豪门宴会厅",
            "duration": 5,
            "status": "generating",
            "updated_at": ts,
        },
    ]
    # -- 真假千金 project episodes & shots --
    proj_qj = "proj_qianjin"
    episodes_qj = [
        {
            "id": "ep_qj_01",
            "project_id": proj_qj,
            "no": 1,
            "title": "医院门口的遗弃婴儿",
            "summary": "二十四年前，一个女婴被遗弃在医院门口。",
            "script": "暴雨夜，医院门口的纸箱里传来婴儿啼哭。护士抱起婴儿，发现襁褓中藏着一枚玉佩。二十四年后，这枚玉佩成为揭开身世之谜的关键。",
            "duration_target": 25,
            "status": "storyboard_ready",
            "updated_at": ts,
        },
        {
            "id": "ep_qj_02",
            "project_id": proj_qj,
            "no": 2,
            "title": "玉佩的线索",
            "summary": "女主在旧物市场偶然看到一枚一模一样的玉佩。",
            "script": "白若雪在旧物市场闲逛，一枚玉佩吸引了她的目光——和母亲留给她的那枚一模一样。摊主说这是从一个豪门大宅流出的。",
            "duration_target": 30,
            "status": "draft",
            "updated_at": ts,
        },
        {
            "id": "ep_qj_03",
            "project_id": proj_qj,
            "no": 3,
            "title": "亲生母亲的崩溃",
            "summary": "DNA结果出来，亲生母亲当场崩溃。",
            "script": "在医院走廊，DNA鉴定结果出来了。白若雪的亲生母亲——豪门太太看到结果，双腿发软跪倒在地，二十四年的愧疚瞬间决堤。",
            "duration_target": 28,
            "status": "draft",
            "updated_at": ts,
        },
    ]
    shots_qj = [
        {
            "id": "shot_qj_01",
            "episode_id": "ep_qj_01",
            "no": 1,
            "title": "暴雨中的纸箱",
            "visual": "暴雨夜，医院门口灯光昏暗，一个纸箱在雨中微微晃动。",
            "dialogue": "",
            "characters": [],
            "scene": "医院走廊",
            "duration": 4,
            "status": "completed",
            "updated_at": ts,
        },
        {
            "id": "shot_qj_02",
            "episode_id": "ep_qj_01",
            "no": 2,
            "title": "护士发现婴儿",
            "visual": "护士推门而出，发现纸箱，俯身抱起婴儿，婴儿停止哭泣。",
            "dialogue": "天哪……这是谁家的孩子？",
            "characters": [],
            "scene": "医院走廊",
            "duration": 5,
            "status": "completed",
            "updated_at": ts,
        },
        {
            "id": "shot_qj_03",
            "episode_id": "ep_qj_01",
            "no": 3,
            "title": "玉佩特写",
            "visual": "襁褓中一枚翠绿玉佩特写，上面刻着一个'白'字。",
            "dialogue": "",
            "characters": [],
            "scene": "医院走廊",
            "duration": 3,
            "status": "pending",
            "updated_at": ts,
        },
    ]
    # -- 赘婿逆袭 project --
    proj_zx = "proj_zhuixu"
    episodes_zx = [
        {
            "id": "ep_zx_01",
            "project_id": proj_zx,
            "no": 1,
            "title": "入赘三年的屈辱",
            "summary": "男主入赘豪门三年，被全家人羞辱。",
            "script": "陆景年入赘周家三年，每天被岳母使唤、被小舅子嘲笑。家族聚会上，所有人对他冷嘲热讽，只有他知道，自己隐藏的身份一旦揭开，整个周家都将颤抖。",
            "duration_target": 30,
            "status": "storyboard_ready",
            "updated_at": ts,
        },
        {
            "id": "ep_zx_02",
            "project_id": proj_zx,
            "no": 2,
            "title": "身份揭晓",
            "summary": "男主在家族会议上亮出集团继承人身份。",
            "script": "周家面临破产危机，所有人束手无策。陆景年脱下围裙，拨通一个电话，十分钟后，三架直升机降落在周家庄园。他才是真正的集团继承人。",
            "duration_target": 35,
            "status": "draft",
            "updated_at": ts,
        },
    ]
    shots_zx = [
        {
            "id": "shot_zx_01",
            "episode_id": "ep_zx_01",
            "no": 1,
            "title": "厨房中的身影",
            "visual": "男主在豪华厨房中洗碗，背景传来客厅的嘲笑声。",
            "dialogue": "一个废物，也配姓周？",
            "characters": ["陆景年"],
            "scene": "别墅客厅",
            "duration": 4,
            "status": "completed",
            "updated_at": ts,
        },
        {
            "id": "shot_zx_02",
            "episode_id": "ep_zx_01",
            "no": 2,
            "title": "聚会上的羞辱",
            "visual": "家族聚会，所有人举杯，唯独男主站在角落端盘子。",
            "dialogue": "景年，去给大伙倒茶。",
            "characters": ["陆景年", "周子轩"],
            "scene": "别墅客厅",
            "duration": 5,
            "status": "generating",
            "updated_at": ts,
        },
    ]
    # -- 重生复仇 project --
    proj_rb = "proj_rebirth"
    episodes_rb = [
        {
            "id": "ep_rb_01",
            "project_id": proj_rb,
            "no": 1,
            "title": "重回入职第一天",
            "summary": "女主重生回到被陷害的起点，决心改写命运。",
            "script": "苏念在手术台上闭眼，再睁眼时回到了五年前——入职第一天。她清楚记得谁会在咖啡里下药、谁会偷走她的方案。这一次，她要让所有人付出代价。",
            "duration_target": 30,
            "status": "storyboard_ready",
            "updated_at": ts,
        },
        {
            "id": "ep_rb_02",
            "project_id": proj_rb,
            "no": 2,
            "title": "反将一军",
            "summary": "女主提前布局，让陷害者自食其果。",
            "script": "同事像前世一样在咖啡里下了药，但这次苏念早有准备。她假装喝下，录下了对方篡改方案的全过程。第二天会议上，她当众播放了录像。",
            "duration_target": 28,
            "status": "generating",
            "updated_at": ts,
        },
    ]
    shots_rb = [
        {
            "id": "shot_rb_01",
            "episode_id": "ep_rb_01",
            "no": 1,
            "title": "手术台上的回忆",
            "visual": "手术台无影灯闪烁，女主闭眼，画面闪回五年前的办公室。",
            "dialogue": "如果能重来一次……",
            "characters": [],
            "scene": "总裁办公室",
            "duration": 4,
            "status": "completed",
            "updated_at": ts,
        },
        {
            "id": "shot_rb_02",
            "episode_id": "ep_rb_01",
            "no": 2,
            "title": "睁眼回到过去",
            "visual": "女主猛然睁眼，发现自己坐在工位上，桌上的日历显示五年前。",
            "dialogue": "这一天，终于来了。",
            "characters": [],
            "scene": "总裁办公室",
            "duration": 3,
            "status": "pending",
            "updated_at": ts,
        },
    ]
    all_episodes = episodes_hm + episodes_qj + episodes_zx + episodes_rb
    all_shots = shots_hm + shots_qj + shots_zx + shots_rb
    return {
        "projects": [
            {
                "id": project_id,
                "name": "豪门错爱：身份反转短剧",
                "short_name": "豪门错爱",
                "description": "女主误闯订婚现场，男主当众宣布她才是真正的未婚妻。",
                "status": "active",
                "owner": "演示用户",
                "owner_user_id": "user_demo",
                "cover": "dark",
                "cover_image": "/covers/haomen.jpg",
                "updated_at": ts,
            },
            {
                "id": proj_qj,
                "name": "真假千金：身世揭露系列",
                "short_name": "真假千金",
                "description": "医院门口身份揭露，亲生母亲当场崩溃。",
                "status": "review",
                "owner": "演示用户",
                "owner_user_id": "user_demo",
                "cover": "blue",
                "cover_image": "/covers/qianjin.jpg",
                "updated_at": ts,
            },
            {
                "id": proj_zx,
                "name": "赘婿逆袭：打脸剧情系列",
                "short_name": "赘婿逆袭",
                "description": "男主被羞辱后亮出集团继承人身份。",
                "status": "draft",
                "owner": "管理员",
                "owner_user_id": "user_admin",
                "cover": "green",
                "cover_image": "/covers/zhuixu.jpg",
                "updated_at": ts,
            },
            {
                "id": proj_rb,
                "name": "重生复仇：职场逆袭",
                "short_name": "重生复仇",
                "description": "女主重生回到入职第一天，提前识破同事陷害。",
                "status": "active",
                "owner": "管理员",
                "owner_user_id": "user_admin",
                "cover": "purple",
                "cover_image": "/covers/rebirth.jpg",
                "updated_at": ts,
            },
        ],
        "episodes": all_episodes,
        "shots": all_shots,
        "assets": [
            # -- 豪门错爱 assets --
            {
                "id": "asset_linwan",
                "project_id": project_id,
                "type": "character",
                "name": "女主：林晚",
                "description": "24岁，清冷倔强，白色礼裙，适合逆袭、误会、身份反转剧情。",
                "ref_count": 8,
                "initial": "林",
                "image": "/portraits/linwan.jpg",
                "voice": "温柔清冷女声",
                "voice_url": "/voices/linwan.wav",
                "updated_at": ts,
            },
            {
                "id": "asset_guchen",
                "project_id": project_id,
                "type": "character",
                "name": "男主：顾沉",
                "description": "30岁，豪门继承人，黑色西装，冷峻克制，适合霸总剧情。",
                "ref_count": 6,
                "initial": "顾",
                "image": "/portraits/guchen.jpg",
                "voice": "低沉磁性男声",
                "voice_url": "/voices/guchen.wav",
                "updated_at": ts,
            },
            {
                "id": "asset_suqing",
                "project_id": project_id,
                "type": "character",
                "name": "反派：苏晴",
                "description": "26岁，精致强势，礼服造型，适合冲突和反击剧情。",
                "ref_count": 5,
                "initial": "苏",
                "image": "/portraits/suqing.jpg",
                "voice": "甜美傲娇女声",
                "voice_url": "/voices/suqing.wav",
                "updated_at": ts,
            },
            {
                "id": "asset_banquet",
                "project_id": project_id,
                "type": "scene",
                "name": "豪门宴会厅",
                "description": "金色灯光、大理石地面、订婚仪式布置，适合身份揭露剧情。",
                "ref_count": 4,
                "initial": "宴",
                "image": "/scenes/banquet.jpg",
                "updated_at": ts,
            },
            {
                "id": "asset_hospital",
                "project_id": project_id,
                "type": "scene",
                "name": "医院走廊",
                "description": "冷色调、白色灯光、紧张氛围，适合身世揭露和亲情冲突。",
                "ref_count": 3,
                "initial": "医",
                "image": "/scenes/hospital.jpg",
                "updated_at": ts,
            },
            {
                "id": "asset_img_poster",
                "project_id": project_id,
                "type": "image",
                "name": "主海报设计稿",
                "description": "豪门错爱主视觉海报，1080x1920竖版，用于投放和宣传。",
                "ref_count": 2,
                "initial": "海",
                "image": "/images/poster.jpg",
                "updated_at": ts,
            },
            {
                "id": "asset_audio_bgm",
                "project_id": project_id,
                "type": "audio",
                "name": "主题BGM：错爱",
                "description": "钢琴+弦乐，30秒循环，适合虐心和反转场景。",
                "ref_count": 4,
                "initial": "B",
                "updated_at": ts,
            },
            # -- 真假千金 assets --
            {
                "id": "asset_bairuoxue",
                "project_id": proj_qj,
                "type": "character",
                "name": "女主：白若雪",
                "description": "22岁，温柔善良，护士装造型，适合身世揭露和亲情剧情。",
                "ref_count": 6,
                "initial": "白",
                "image": "/portraits/bairuoxue.jpg",
                "voice": "柔美温婉女声",
                "voice_url": "/voices/bairuoxue.wav",
                "updated_at": ts,
            },
            {
                "id": "asset_scene_hospital",
                "project_id": proj_qj,
                "type": "scene",
                "name": "医院产房外",
                "description": "白色走廊、婴儿啼哭声、紧张等待氛围。",
                "ref_count": 3,
                "initial": "产",
                "image": "/scenes/hospital.jpg",
                "updated_at": ts,
            },
            # -- 赘婿逆袭 assets --
            {
                "id": "asset_lujiinian",
                "project_id": proj_zx,
                "type": "character",
                "name": "男主：陆景年",
                "description": "28岁，隐忍低调，围裙下藏着集团继承人身份。",
                "ref_count": 5,
                "initial": "陆",
                "image": "/portraits/lujiinian.jpg",
                "voice": "沉稳内敛男声",
                "voice_url": "/voices/lujiinian.wav",
                "updated_at": ts,
            },
            {
                "id": "asset_zhouzixuan",
                "project_id": proj_zx,
                "type": "character",
                "name": "反派：周子轩",
                "description": "32岁，周家长子，傲慢跋扈，最终被打脸。",
                "ref_count": 4,
                "initial": "周",
                "image": "/portraits/zhouzixuan.jpg",
                "voice": "嚣张傲慢男声",
                "voice_url": "/voices/zhouzixuan.wav",
                "updated_at": ts,
            },
            {
                "id": "asset_scene_villa",
                "project_id": proj_zx,
                "type": "scene",
                "name": "别墅客厅",
                "description": "豪华别墅内景，适合家族聚会和身份揭晓场景。",
                "ref_count": 3,
                "initial": "宅",
                "image": "/scenes/villa.jpg",
                "updated_at": ts,
            },
            # -- 重生复仇 assets --
            {
                "id": "asset_scene_office",
                "project_id": proj_rb,
                "type": "scene",
                "name": "总裁办公室",
                "description": "现代风格办公室，适合职场博弈和反转剧情。",
                "ref_count": 3,
                "initial": "办",
                "image": "/scenes/office.jpg",
                "updated_at": ts,
            },
            {
                "id": "asset_scene_rooftop",
                "project_id": proj_rb,
                "type": "scene",
                "name": "天台夜景",
                "description": "城市天际线夜景，适合独白和情感爆发场景。",
                "ref_count": 2,
                "initial": "天",
                "image": "/scenes/rooftop.jpg",
                "updated_at": ts,
            },
        ],
        "video_tasks": [
            {
                "id": "task_001",
                "episode_id": "ep_001",
                "shot_id": "shot_001",
                "title": "女主推门进入",
                "duration": 3,
                "progress": 100,
                "status": "completed",
                "updated_at": ts,
            },
            {
                "id": "task_002",
                "episode_id": "ep_001",
                "shot_id": "shot_002",
                "title": "宾客议论",
                "duration": 4,
                "progress": 66,
                "status": "generating",
                "updated_at": ts,
            },
            {
                "id": "task_003",
                "episode_id": "ep_001",
                "shot_id": "shot_003",
                "title": "男主起身",
                "duration": 5,
                "progress": 0,
                "status": "pending",
                "updated_at": ts,
            },
            {
                "id": "task_004",
                "episode_id": "ep_001",
                "shot_id": "shot_004",
                "title": "身份反转",
                "duration": 6,
                "progress": 0,
                "status": "pending",
                "updated_at": ts,
            },
            {
                "id": "task_005",
                "episode_id": "ep_002",
                "shot_id": "shot_005",
                "title": "管家呈上鉴定书",
                "duration": 4,
                "progress": 100,
                "status": "completed",
                "updated_at": ts,
            },
            {
                "id": "task_006",
                "episode_id": "ep_002",
                "shot_id": "shot_006",
                "title": "苏晴崩溃",
                "duration": 3,
                "progress": 100,
                "status": "completed",
                "updated_at": ts,
            },
            {
                "id": "task_007",
                "episode_id": "ep_002",
                "shot_id": "shot_007",
                "title": "林晚落泪",
                "duration": 5,
                "progress": 45,
                "status": "generating",
                "updated_at": ts,
            },
            {
                "id": "task_qj_01",
                "episode_id": "ep_qj_01",
                "shot_id": "shot_qj_01",
                "title": "暴雨中的纸箱",
                "duration": 4,
                "progress": 100,
                "status": "completed",
                "updated_at": ts,
            },
            {
                "id": "task_qj_02",
                "episode_id": "ep_qj_01",
                "shot_id": "shot_qj_02",
                "title": "护士发现婴儿",
                "duration": 5,
                "progress": 100,
                "status": "completed",
                "updated_at": ts,
            },
            {
                "id": "task_zx_01",
                "episode_id": "ep_zx_01",
                "shot_id": "shot_zx_01",
                "title": "厨房中的身影",
                "duration": 4,
                "progress": 100,
                "status": "completed",
                "updated_at": ts,
            },
            {
                "id": "task_rb_01",
                "episode_id": "ep_rb_01",
                "shot_id": "shot_rb_01",
                "title": "手术台上的回忆",
                "duration": 4,
                "progress": 80,
                "status": "generating",
                "updated_at": ts,
            },
        ],
        "video_versions": [
            {
                "id": "ver_001",
                "project_id": project_id,
                "episode_id": "ep_001",
                "name": "第01集 版本A",
                "description": "强冲突开头 / 30s / 已导出",
                "duration": 30,
                "ratio": "9:16",
                "status": "exported",
                "theme": "dark",
                "created_at": ts,
            },
            {
                "id": "ver_002",
                "project_id": project_id,
                "episode_id": "ep_001",
                "name": "第01集 版本B",
                "description": "身份揭露开头 / 15s / 待审核",
                "duration": 15,
                "ratio": "9:16",
                "status": "review",
                "theme": "blue",
                "created_at": ts,
            },
            {
                "id": "ver_003",
                "project_id": project_id,
                "episode_id": "ep_002",
                "name": "第02集 版本A",
                "description": "鉴定书悬念 / 25s / 已导出",
                "duration": 25,
                "ratio": "9:16",
                "status": "exported",
                "theme": "dark",
                "created_at": ts,
            },
            {
                "id": "ver_qj_01",
                "project_id": proj_qj,
                "episode_id": "ep_qj_01",
                "name": "第01集 版本A",
                "description": "暴雨夜开场 / 25s / 已导出",
                "duration": 25,
                "ratio": "9:16",
                "status": "exported",
                "theme": "blue",
                "created_at": ts,
            },
        ],
        "usage": {
            "video_total_seconds": 2000,
            "video_used_seconds": 1286,
            "image_total": 1000,
            "image_used": 438,
            "export_total": 164,
            "export_used": 126,
            "team_members": 2,
        },
        "users": default_users(),
        "point_ledger": [
            {
                "id": "ledger_admin_init",
                "user_id": "user_admin",
                "username": "admin",
                "display_name": "管理员",
                "amount": 100000,
                "type": "init",
                "scene": "系统初始化",
                "description": "管理员初始积分",
                "balance_after": 100000,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_init",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": 2000,
                "type": "init",
                "scene": "系统初始化",
                "description": "演示用户初始积分",
                "balance_after": 2000,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_outline",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": -20,
                "type": "consume",
                "scene": "大纲生成",
                "description": "豪门错爱 · 大纲生成消耗",
                "balance_after": 1980,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_storyboard",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": -20,
                "type": "consume",
                "scene": "分镜生成",
                "description": "豪门错爱 · 第01集分镜生成",
                "balance_after": 1960,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_video",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": -180,
                "type": "consume",
                "scene": "视频生成",
                "description": "豪门错爱 · 第01集视频生成 (18s)",
                "balance_after": 1780,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_compose",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": -30,
                "type": "consume",
                "scene": "视频合成",
                "description": "豪门错爱 · 第01集成片合成",
                "balance_after": 1750,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_image",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": -40,
                "type": "consume",
                "scene": "图片生成",
                "description": "豪门错爱 · 角色参考图生成 x2",
                "balance_after": 1710,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_outline2",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": -20,
                "type": "consume",
                "scene": "大纲生成",
                "description": "真假千金 · 大纲生成消耗",
                "balance_after": 1690,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_storyboard2",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": -20,
                "type": "consume",
                "scene": "分镜生成",
                "description": "真假千金 · 第01集分镜生成",
                "balance_after": 1670,
                "created_at": ts,
            },
            {
                "id": "ledger_demo_video2",
                "user_id": "user_demo",
                "username": "demo",
                "display_name": "演示用户",
                "amount": -90,
                "type": "consume",
                "scene": "视频生成",
                "description": "真假千金 · 第01集视频生成 (9s)",
                "balance_after": 1580,
                "created_at": ts,
            },
        ],
    }


def normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    changed = False
    # Migrate projects without owner_user_id - assign to admin
    for project in data.get("projects", []):
        if "owner_user_id" not in project:
            project["owner_user_id"] = "user_admin"
            changed = True
    # Migrate cover_image field on projects
    _cover_image_map = {
        "proj_haomen": "/covers/haomen.jpg",
        "proj_qianjin": "/covers/qianjin.jpg",
        "proj_zhuixu": "/covers/zhuixu.jpg",
        "proj_rebirth": "/covers/rebirth.jpg",
    }
    for project in data.get("projects", []):
        if "cover_image" not in project and project["id"] in _cover_image_map:
            project["cover_image"] = _cover_image_map[project["id"]]
            changed = True
    # Migrate image field on assets
    _asset_image_map = {
        "asset_linwan": "/portraits/linwan.jpg",
        "asset_guchen": "/portraits/guchen.jpg",
        "asset_suqing": "/portraits/suqing.jpg",
        "asset_banquet": "/scenes/banquet.jpg",
        "asset_hospital": "/scenes/hospital.jpg",
        "asset_bairuoxue": "/portraits/bairuoxue.jpg",
        "asset_lujiinian": "/portraits/lujiinian.jpg",
        "asset_zhouzixuan": "/portraits/zhouzixuan.jpg",
        "asset_scene_hospital": "/scenes/hospital.jpg",
        "asset_scene_villa": "/scenes/villa.jpg",
        "asset_scene_office": "/scenes/office.jpg",
        "asset_scene_rooftop": "/scenes/rooftop.jpg",
    }
    for asset in data.get("assets", []):
        if "image" not in asset and asset["id"] in _asset_image_map:
            asset["image"] = _asset_image_map[asset["id"]]
            changed = True
    # Migrate multi-reference assets for the detail gallery.
    _asset_reference_sources = {
        "asset_linwan": ["/portraits/linwan.jpg", "/images/poster.jpg", "/scenes/banquet.jpg"],
        "asset_guchen": ["/portraits/guchen.jpg", "/scenes/banquet.jpg", "/scenes/office.jpg"],
        "asset_suqing": ["/portraits/suqing.jpg", "/scenes/banquet.jpg", "/images/poster.jpg"],
        "asset_banquet": ["/scenes/banquet.jpg", "/images/poster.jpg", "/scenes/villa.jpg"],
        "asset_hospital": ["/scenes/hospital.jpg", "/portraits/bairuoxue.jpg", "/scenes/office.jpg"],
        "asset_img_poster": ["/images/poster.jpg", "/portraits/linwan.jpg"],
        "asset_bairuoxue": ["/portraits/bairuoxue.jpg", "/scenes/hospital.jpg", "/images/poster.jpg"],
        "asset_lujiinian": ["/portraits/lujiinian.jpg", "/scenes/villa.jpg", "/scenes/office.jpg"],
        "asset_zhouzixuan": ["/portraits/zhouzixuan.jpg", "/scenes/villa.jpg", "/images/poster.jpg"],
        "asset_scene_hospital": ["/scenes/hospital.jpg", "/portraits/bairuoxue.jpg"],
        "asset_scene_villa": ["/scenes/villa.jpg", "/portraits/lujiinian.jpg"],
        "asset_scene_office": ["/scenes/office.jpg", "/scenes/rooftop.jpg"],
        "asset_scene_rooftop": ["/scenes/rooftop.jpg", "/scenes/office.jpg"],
    }
    for asset in data.get("assets", []):
        if "references" not in asset:
            sources = _asset_reference_sources.get(asset["id"], [])
            if sources:
                asset["references"] = [
                    {
                        "id": f'{asset["id"]}_ref_{index + 1}',
                        "type": "image",
                        "name": f'参考图 {index + 1}',
                        "url": source,
                        "note": asset.get("description", ""),
                    }
                    for index, source in enumerate(sources)
                ]
                asset["ref_count"] = max(int(asset.get("ref_count", 0)), len(sources))
            else:
                asset["references"] = []
            changed = True
    # Migrate voice and voice_url fields on character assets
    _asset_voice_map = {
        "asset_linwan": ("温柔清冷女声", "/voices/linwan.wav"),
        "asset_guchen": ("低沉磁性男声", "/voices/guchen.wav"),
        "asset_suqing": ("甜美傲娇女声", "/voices/suqing.wav"),
        "asset_bairuoxue": ("柔美温婉女声", "/voices/bairuoxue.wav"),
        "asset_lujiinian": ("沉稳内敛男声", "/voices/lujiinian.wav"),
        "asset_zhouzixuan": ("嚣张傲慢男声", "/voices/zhouzixuan.wav"),
    }
    for asset in data.get("assets", []):
        if asset.get("type") == "character" and "voice" not in asset:
            voice_info = _asset_voice_map.get(asset["id"])
            if voice_info:
                asset["voice"] = voice_info[0]
                asset["voice_url"] = voice_info[1]
            else:
                asset["voice"] = None
                asset["voice_url"] = None
            changed = True
    if "users" not in data:
        data["users"] = default_users()
        changed = True
    else:
        for user in data["users"]:
            user.setdefault("display_name", user.get("username", "用户"))
            user.setdefault("role", "user")
            user.setdefault("status", "active")
            user.setdefault("points", 1000)
            user.setdefault("token", "")
            user.setdefault("created_at", now())
            user.setdefault("last_login", "")
            user.setdefault("usage", {})
            user["usage"].setdefault("video_total_seconds", 2000)
            user["usage"].setdefault("video_used_seconds", 0)
            user["usage"].setdefault("image_total", 1000)
            user["usage"].setdefault("image_used", 0)
            user["usage"].setdefault("export_total", 164)
            user["usage"].setdefault("export_used", 0)
    if "point_ledger" not in data:
        data["point_ledger"] = []
        for user in data["users"]:
            data["point_ledger"].append(
                {
                    "id": uid("ledger"),
                    "user_id": user["id"],
                    "username": user.get("username"),
                    "display_name": user.get("display_name") or user.get("username"),
                    "amount": int(user.get("points", 0)),
                    "type": "init",
                    "scene": "系统初始化",
                    "description": "兼容旧版本数据时补充初始积分记录",
                    "balance_after": int(user.get("points", 0)),
                    "created_at": now(),
                }
            )
        changed = True
    data.setdefault("usage", {})
    data["usage"].setdefault("video_total_seconds", 2000)
    data["usage"].setdefault("video_used_seconds", 0)
    data["usage"].setdefault("image_total", 1000)
    data["usage"].setdefault("image_used", 0)
    data["usage"].setdefault("export_total", 164)
    data["usage"].setdefault("export_used", 0)
    data["usage"]["team_members"] = len([u for u in data.get("users", []) if u.get("status") == "active"])
    if changed:
        save_data(data)
    return data


def ensure_data_file() -> None:
    if not DATA_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(seed_data(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_data() -> dict[str, Any]:
    ensure_data_file()
    with _LOCK:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return normalize_data(data)


def save_data(data: dict[str, Any]) -> None:
    with _LOCK:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def snapshot() -> dict[str, Any]:
    return deepcopy(load_data())


def update(mutator):
    data = load_data()
    result = mutator(data)
    save_data(data)
    return result
