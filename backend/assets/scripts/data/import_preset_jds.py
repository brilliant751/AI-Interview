"""导入系统预置 JD 与公司数据（可重复执行）。"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def ensure_schema(conn: sqlite3.Connection) -> None:
    """确保 companies / job_descriptions 相关字段存在。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
          company_id TEXT PRIMARY KEY,
          name TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL DEFAULT 'ACTIVE',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name)")
    rows = conn.execute("PRAGMA table_info(job_descriptions)").fetchall()
    cols = {str(row[1]) for row in rows}
    if "company_id" not in cols:
        conn.execute("ALTER TABLE job_descriptions ADD COLUMN company_id TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jd_company_id ON job_descriptions(company_id)")


def company_id_of(name: str) -> str:
    """根据公司名生成稳定 company_id。"""
    base = "".join(ch for ch in name.lower() if ch.isalnum())
    return f"cmp_{base[:40] or 'unknown'}"


def load_payload() -> list[dict]:
    """加载预置 JD 数据。"""
    return [
        {
            "title": "算法实习生 - 推荐 / 搜索",
            "company": "字节跳动",
            "job_role": "算法",
            "content_text": "岗位方向：推荐算法、排序模型、用户行为分析\n薪资：300–400 元 / 天\n地点：北京 / 上海 / 深圳\n岗位职责：参与推荐/搜索算法迭代，优化召回、排序、精排模型；数据清洗、特征工程、模型训练与AB测试；分析用户行为数据，提升推荐准确率与用户体验。\n任职要求：硕士及以上，计算机/数学/统计相关，2026/2027届；扎实机器学习/深度学习基础，熟悉PyTorch/TensorFlow；熟练Python/C++，有推荐/搜索实习/竞赛经验优先。",
        },
        {
            "title": "大模型研发实习生",
            "company": "阿里巴巴",
            "job_role": "算法",
            "content_text": "岗位方向：大模型训练、微调、推理优化、多模态\n薪资：350–500 元 / 天\n地点：杭州 / 北京\n岗位职责：参与大模型预训练、SFT、RLHF全流程；优化模型推理速度和显存占用；跟踪前沿技术并参与方案设计。\n任职要求：硕士及以上，AI/计算机相关；熟悉Transformer架构，熟练PyTorch；有大模型训练/微调经验优先；英文文献阅读能力强。",
        },
        {
            "title": "C++ 后端开发实习生",
            "company": "腾讯",
            "job_role": "后端开发",
            "content_text": "岗位方向：后端服务、分布式系统、高并发\n薪资：280–380 元 / 天\n地点：深圳 / 北京 / 上海\n岗位职责：后端服务开发、接口设计、性能优化；参与分布式架构与问题排查；配合测试运维上线与监控。\n任职要求：本科及以上，熟练C++/Linux；熟悉MySQL/Redis、网络编程、多线程。",
        },
        {
            "title": "前端开发实习生",
            "company": "快手",
            "job_role": "前端开发",
            "content_text": "岗位方向：Web前端、移动端H5、跨端开发\n薪资：250–350 元 / 天\n地点：北京\n岗位职责：Web/H5页面开发、交互实现、兼容调试；配合产品/UI落地需求并优化前端性能；参与工程化和组件库建设。\n任职要求：熟悉HTML/CSS/JavaScript，掌握Vue/React；了解Webpack/Vite、Git。",
        },
        {
            "title": "数据开发实习生",
            "company": "京东",
            "job_role": "数据开发",
            "content_text": "岗位方向：数据仓库、ETL、数据治理、数据分析\n薪资：250–350 元 / 天\n地点：北京\n岗位职责：参与数仓建设与ETL开发优化；数据清洗整合建模；维护数据平台质量与稳定性。\n任职要求：熟练SQL；熟悉Hive/Spark、Python，有数据开发经验优先。",
        },
        {
            "title": "AI 数据标注实习生",
            "company": "明胜品智",
            "job_role": "数据标注",
            "content_text": "岗位方向：图像/文本/语音标注、数据审核\n薪资：120–130 元 / 天\n地点：南京\n岗位职责：图像/文本/语音/视频精准标注，数据审核与质量校验，整理标注文档。\n任职要求：本科及以上，细心耐心，支持培训上岗。",
        },
        {
            "title": "产品经理实习生",
            "company": "美团",
            "job_role": "产品",
            "content_text": "岗位方向：本地生活、外卖/到店、产品功能迭代\n薪资：250–350 元 / 天\n地点：北京 / 上海\n岗位职责：需求调研、PRD撰写、推进开发测试上线、用户反馈与数据分析迭代。\n任职要求：逻辑清晰，沟通协调能力强，熟练Axure/墨刀优先。",
        },
        {
            "title": "电商运营实习生",
            "company": "拼多多",
            "job_role": "运营",
            "content_text": "岗位方向：店铺运营、活动策划、用户增长\n薪资：200–300 元 / 天\n地点：上海\n岗位职责：店铺日常运营、活动报名投放复盘、销售数据与竞品分析、售后处理。\n任职要求：熟悉电商平台规则，熟练Excel，数据敏感。",
        },
        {
            "title": "内容运营实习生",
            "company": "小红书",
            "job_role": "运营",
            "content_text": "岗位方向：社区内容、创作者运营、内容策划\n薪资：200–300 元 / 天\n地点：上海\n岗位职责：内容选题与发布、创作者关系维护、内容数据分析与活动策划执行。\n任职要求：网感强、文字功底好，熟悉新媒体平台。",
        },
        {
            "title": "市场推广实习生",
            "company": "抖音",
            "job_role": "市场",
            "content_text": "岗位方向：品牌营销、活动策划、用户增长\n薪资：220–320 元 / 天\n地点：北京 / 上海\n岗位职责：市场活动执行复盘、社媒内容投放与粉丝运营、竞品分析与合作落地。\n任职要求：创意强、沟通好，熟练Office/剪映。",
        },
        {
            "title": "游戏运营实习生",
            "company": "腾讯游戏",
            "job_role": "运营",
            "content_text": "岗位方向：游戏运营、活动策划、用户运营\n薪资：250–350 元 / 天\n地点：深圳 / 上海\n岗位职责：版本活动上线复盘、玩家反馈处理、DAU/留存/付费分析。\n任职要求：热爱游戏，沟通能力强，抗压能力好。",
        },
        {
            "title": "投行实习生 - 股权承做",
            "company": "中信证券",
            "job_role": "金融",
            "content_text": "岗位方向：IPO、再融资、并购重组、材料撰写\n薪资：200–300 元 / 天\n地点：北京 / 上海 / 深圳\n岗位职责：尽调、材料撰写、底稿整理、中介沟通、行业研究。\n任职要求：硕士及以上，金融/会计/法律相关，熟练Excel/PPT。",
        },
        {
            "title": "行业研究实习生",
            "company": "易方达基金",
            "job_role": "金融",
            "content_text": "岗位方向：消费/科技/医药研究\n薪资：200–300 元 / 天\n地点：广州 / 北京 / 上海\n岗位职责：行业与公司研究、报告撰写、数据库更新、投资支持。\n任职要求：财务基础扎实，英文读写流利。",
        },
        {
            "title": "咨询实习生",
            "company": "麦肯锡",
            "job_role": "咨询",
            "content_text": "岗位方向：战略咨询、行业研究、项目支持\n薪资：300–500 元 / 天\n地点：北京 / 上海 / 深圳\n岗位职责：数据研究分析、访谈纪要、PPT制作、客户沟通支持。\n任职要求：逻辑与分析能力强，英文流利。",
        },
        {
            "title": "风险管理实习生",
            "company": "微众银行",
            "job_role": "风控",
            "content_text": "岗位方向：信用风险、市场风险、模型验证\n薪资：250–350 元 / 天\n地点：深圳\n岗位职责：模型开发验证监控、信贷数据分析、风险报告输出。\n任职要求：熟悉SQL/Python，逻辑严谨。",
        },
        {
            "title": "Java 开发实习生（秋储）",
            "company": "滴滴出行",
            "job_role": "后端开发",
            "content_text": "岗位方向：Java Web、后端服务、业务系统开发\n薪资：200–300 元 / 天\n地点：杭州\n实习要求：5天/周，3个月+，可转正\n岗位职责：Java后端开发、系统设计建模、联调排障、代码评审。\n任职要求：熟悉Spring/Spring Boot/MyBatis、MySQL/Redis、分布式与缓存。",
        },
        {
            "title": "Java 后台开发实习生",
            "company": "腾讯",
            "job_role": "后端开发",
            "content_text": "岗位方向：Java Web、后台服务、高并发系统\n薪资：200–280 元 / 天\n地点：长沙 / 深圳\n岗位职责：后台服务设计编码测试维护，接口开发与性能优化。\n任职要求：熟悉Spring Boot、MyBatis、MySQL、Redis，多线程与Linux基础。",
        },
        {
            "title": "Java Web开发实习生",
            "company": "网易（杭州）网络有限公司",
            "job_role": "后端开发",
            "content_text": "岗位方向：Web端后端开发、业务系统搭建、接口开发\n薪资：220-320元/天\n地点：杭州\n实习要求：5天/周，3个月+，可转正（2026届优先）\n岗位职责：负责Web端后端服务开发与接口实现；参与需求分析、数据库设计、接口文档编写；优化接口性能并排查异常；参与代码评审与技术文档维护。\n任职要求：本科及以上，2026/2027届；扎实Java基础，熟悉OOP、多线程、IO、集合；熟练Spring Boot/Spring MVC/MyBatis；熟悉MySQL与SQL优化，了解索引事务分库分表；熟悉HTTP、Git、Maven，有Web项目经验优先。",
        },
        {
            "title": "Web后端开发实习生（Java）",
            "company": "上海哔哩哔哩科技有限公司",
            "job_role": "后端开发",
            "content_text": "岗位方向：Web端后端开发、用户体系接口、Web应用维护\n薪资：200-300元/天\n地点：上海\n实习要求：4天/周，3个月+，2026届优先\n岗位职责：参与B站Web端后端业务开发；负责用户与内容展示接口迭代；配合前端联调与问题修复；优化接口响应速度。\n任职要求：熟悉MySQL、Redis，了解缓存机制与消息队列优先；具备Java Web项目开发能力。",
        },
        {
            "title": "Java Web开发实习生",
            "company": "贝壳",
            "job_role": "后端开发",
            "content_text": "岗位方向：Web端后端开发、房产服务系统、接口优化\n薪资：200-280元/天\n实习要求：5天/周，3个月+\n岗位职责：负责房产交易、房源展示相关模块接口开发；配合前端联调，保障交互流畅和数据准确。\n任职要求：熟悉Java与并发基础、MySQL与Redis、SQL优化技巧。",
        },
        {
            "title": "Java Web开发实习生",
            "company": "携程旅游网络技术（上海）有限公司",
            "job_role": "后端开发",
            "content_text": "岗位方向：Web端后端开发、旅游业务系统、接口开发\n地点：上海\n岗位职责：参与Web端后端模块开发、接口设计与性能优化；配合前端联调，编写接口文档与测试用例。\n任职要求：扎实Java基础，熟悉JVM；熟悉MySQL、Redis，了解MQ与分布式缓存。",
        },
        {
            "title": "Java Web开发实习生",
            "company": "途虎养车",
            "job_role": "后端开发",
            "content_text": "岗位方向：Web端后端开发、汽车服务系统、业务接口开发\n薪资：180-280元/天\n实习要求：4天/周，3个月+\n岗位职责：实现门店管理、订单处理、商品展示相关接口；配合前端联调并解决技术问题。\n任职要求：掌握Java基础与多线程；熟悉MySQL、Git、Maven。",
        },
        {
            "title": "Web全栈开发实习生",
            "company": "小红书",
            "job_role": "全栈开发",
            "content_text": "岗位方向：Web全栈开发、前端页面+Java后端接口\n薪资：220-320元/天\n实习要求：5天/周，3个月+\n岗位职责：负责Web端前后端协同开发，完成接口与页面联调。\n任职要求：前端熟悉HTML/CSS/JS与Vue/React；后端熟悉Java、Spring Boot、MyBatis、MySQL、Redis。",
        },
        {
            "title": "Web全栈开发实习生",
            "company": "北京淘友天下科技发展有限公司（脉脉）",
            "job_role": "全栈开发",
            "content_text": "岗位方向：Web全栈开发、职场社交平台\n地点：北京\n岗位职责：前端页面开发优化，后端接口实现，测试修复与版本迭代。\n任职要求：具备前后端开发基础，熟悉Vue与Spring Boot/MyBatis。",
        },
        {
            "title": "Web全栈开发实习生",
            "company": "拉勾网",
            "job_role": "全栈开发",
            "content_text": "岗位方向：招聘Web端、Java后端+前端协同\n薪资：190-290元/天\n实习要求：5天/周，3个月+\n岗位职责：实现招聘页面、企业管理、简历管理功能；完成后端业务逻辑与前端联调。\n任职要求：扎实Java，熟悉Spring Boot/MyBatis、MySQL、Redis；前端熟悉HTML/CSS/JS。",
        },
        {
            "title": "Web端后端开发实习生",
            "company": "智联招聘",
            "job_role": "后端开发",
            "content_text": "岗位方向：招聘系统Web接口、业务模块开发\n薪资：150-250元/天\n实习要求：4天/周，2个月+\n岗位职责：开发招聘信息展示、简历投递接口；参与数据库设计优化与数据迁移。\n任职要求：熟悉Java、Spring Boot、MyBatis、MySQL、Redis。",
        },
        {
            "title": "Web开发实习生（Java）",
            "company": "广东恒企教育科技有限公司",
            "job_role": "后端开发",
            "content_text": "岗位方向：教育类Web系统开发\n地点：广州\n岗位职责：完成Java后端接口开发，配合前端联调，优化接口性能。\n任职要求：本科及以上，熟悉Java、Spring Boot、MyBatis、MySQL、Redis。",
        },
        {
            "title": "Web端后端开发实习生",
            "company": "安恒信息",
            "job_role": "后端开发",
            "content_text": "岗位方向：安全类Web系统、接口开发\n薪资：160-260元/天\n实习要求：4天/周，3个月+\n岗位职责：开发安全监测、数据统计接口；配合前端联调并排查问题。\n任职要求：熟悉Java、Spring Boot、MyBatis；了解网络安全优先。",
        },
        {
            "title": "Java Web开发实习生（通用模板）",
            "company": "未明确公司",
            "job_role": "后端开发",
            "content_text": "岗位职责：负责Web端后端模块开发，参与接口设计、数据库建模、联调测试与代码评审。\n任职要求：扎实Java基础，熟悉Spring Boot/MyBatis、MySQL/Redis、Git/Maven，有Java Web项目经验优先。\n投递重点：突出Java Web技术栈与前后端联调经验；优先满足4-5天/周、3个月+实习要求。",
        },
    ]


def main() -> None:
    """执行导入。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="SQLite 数据库路径")
    parser.add_argument("--report", default="", help="导入报告输出路径")
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        payload = load_payload()
        created_company = 0
        upserted_jd = 0

        for row in payload:
            company_name = str(row["company"]).strip()
            company_id = company_id_of(company_name)
            before = conn.execute("SELECT 1 FROM companies WHERE company_id = ?", (company_id,)).fetchone()
            conn.execute(
                """
                INSERT OR IGNORE INTO companies(company_id, name, status)
                VALUES (?, ?, 'ACTIVE')
                """,
                (company_id, company_name),
            )
            if before is None:
                created_company += 1

            existing = conn.execute(
                """
                SELECT jd_id FROM job_descriptions
                WHERE source_type = 'SYSTEM_PRESET' AND title = ? AND company_id = ?
                LIMIT 1
                """,
                (row["title"], company_id),
            ).fetchone()
            jd_id = str(existing["jd_id"]) if existing else f"jd_preset_{abs(hash((row['title'], company_name))) % 10_000_000_000}"
            conn.execute(
                """
                INSERT INTO job_descriptions(
                  jd_id, user_id, company_id, source_type, title, job_role, content_text, status, is_deleted, updated_at
                ) VALUES (?, NULL, ?, 'SYSTEM_PRESET', ?, ?, ?, 'READY', 0, datetime('now'))
                ON CONFLICT(jd_id) DO UPDATE SET
                  company_id = excluded.company_id,
                  title = excluded.title,
                  job_role = excluded.job_role,
                  content_text = excluded.content_text,
                  status = 'READY',
                  is_deleted = 0,
                  deleted_at = NULL,
                  updated_at = datetime('now')
                """,
                (jd_id, company_id, row["title"], row["job_role"], row["content_text"]),
            )
            upserted_jd += 1

        conn.commit()
        summary = {
            "db": str(db_path),
            "created_company": created_company,
            "upserted_jd": upserted_jd,
            "total_payload": len(payload),
        }
        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

