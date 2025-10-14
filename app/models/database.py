import os
import time
import re
import logging
import json
import random
import string
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple, Set

import psycopg2
from psycopg2.extras import RealDictCursor, Json

try:
    # 使用项目配置管理
    from config.config import config_manager
except Exception:
    class _Dummy:
        def get(self, k, d=None):
            return os.getenv(k, d)
        def get_flask_config(self):
            return {}
    config_manager = _Dummy()

logger = logging.getLogger(__name__)

# ---------------------------------
# Schema columns -> dynamic aliases
# ---------------------------------

SCHEMA_ALIAS_PATTERNS: Dict[str, List[re.Pattern]] = {
    'name': [re.compile(p) for p in [r'姓名', r'名字', r'(?i)\bname\b', r'客户名', r'联系人']],
    'id_card': [re.compile(p) for p in [r'身份证', r'身份证号', r'(?i)id[_\-\s]?card', r'证件号', r'证件号码']],
    'phone': [re.compile(p) for p in [r'手机号', r'手机', r'电话', r'联系电话', r'(?i)\bphone\b', r'移动电话']],
    'email': [re.compile(p) for p in [r'邮箱', r'电子邮件', r'(?i)\bemail\b']],
    'spouse_name': [re.compile(p) for p in [r'配偶姓名', r'配偶名字', r'(?i)spouse[_\-\s]?name', r'配偶$']],
    'spouse_phone': [re.compile(p) for p in [r'配偶手机号', r'配偶电话', r'(?i)spouse[_\-\s]?phone']],
    'relatives_names': [re.compile(p) for p in [r'直系亲属姓名', r'直系姓名', r'亲属姓名', r'亲属$', r'(?i)relative[_\-\s]?name']],
    'relatives_phones': [re.compile(p) for p in [r'直属手机号', r'直系亲属手机号', r'直系手机号', r'亲属手机号', r'(?i)relative[_\-\s]?phone']],
    'relatives_relations': [re.compile(p) for p in [r'直系关系', r'直系亲属关系', r'亲属关系', r'(?i)relatives?[_\-\s]?relations?', r'(?i)relationship']],
    'relationship': [re.compile(p) for p in [r'直属关系', r'直系亲属关系', r'亲属关系', r'(?i)relationship', r'(?i)relatives?[_\-\s]?relations?']],
    'gender': [re.compile(p) for p in [r'性别', r'(?i)gender']],
    'native_place': [re.compile(p) for p in [r'籍贯', r'(?i)native[_\-\s]?place']],
    'birth_date': [re.compile(p) for p in [r'出生日期', r'出生日', r'(?i)birth[_\-\s]?date']],
    'company': [re.compile(p) for p in [r'单位名称', r'单位名', r'公司', r'公司名称', r'(?i)company']],
    'position': [re.compile(p) for p in [r'职位', r'部门', r'岗位', r'(?i)position']],
    'qq': [re.compile(p) for p in [r'(?i)^qq$']],
    'weibo_uid': [re.compile(p) for p in [r'(?i)weibo[_\-\s]?uid', r'(?i)\buid\b']],
}


# 旧的基于文件的 schema 列缓存已移除，改为仅使用数据库枚举与内存缓存。


def _build_dynamic_aliases(columns_by_table: Dict[str, List[str]]) -> Dict[str, Set[str]]:
    aliases: Dict[str, Set[str]] = {k: set() for k in SCHEMA_ALIAS_PATTERNS.keys()}
    for _t, cols in columns_by_table.items():
        for col in cols:
            col_str = str(col)
            for key, patterns in SCHEMA_ALIAS_PATTERNS.items():
                if any(p.search(col_str) for p in patterns):
                    aliases[key].add(col_str)
    return aliases


_DYNAMIC_ALIASES: Dict[str, Set[str]] = {}
_SCHEMA_CACHE: Dict[str, Any] = {
    'timestamp': 0.0,
    'columns_by_table': {},
}

def _ensure_dynamic_aliases_loaded() -> None:
    """懒加载动态别名：优先使用数据库实时列名，失败时回退到本地schema_columns.json。
    为避免在模块导入阶段提前连接数据库，此方法仅在实际调用别名解析时触发。
    可通过环境变量控制：
      - AUTO_ALIAS_FROM_DB: '1'/'true' 优先使用数据库（默认）
      - ALIAS_TABLE_LIMIT: 限制枚举表数量，避免巨大库开销（默认200）
    """
    global _DYNAMIC_ALIASES
    if _DYNAMIC_ALIASES:
        return
    columns_by_table: Dict[str, List[str]] = {}
    try:
        # 延迟到此时再调用，list_all_table_columns 在下文定义
        limit = int(os.getenv('ALIAS_TABLE_LIMIT', '200'))
        columns_by_table = list_all_table_columns(limit=limit)
    except Exception:
        # 数据库不可用时，别名保持为空集合
        columns_by_table = {}
    _DYNAMIC_ALIASES = _build_dynamic_aliases(columns_by_table)


def _get_aliases(canonical_key: str, defaults: List[str]) -> List[str]:
    _ensure_dynamic_aliases_loaded()
    dyn = list(_DYNAMIC_ALIASES.get(canonical_key, set()))
    seen = set()
    ordered: List[str] = []
    for n in defaults + dyn:
        if n not in seen:
            ordered.append(n)
            seen.add(n)
    return ordered

# 扫描配置（防止请求超时）
SCAN_MAX_TABLES: int = int(os.getenv('SCAN_MAX_TABLES', '200'))
SCAN_LIMIT_PER_TABLE: int = int(os.getenv('SCAN_LIMIT_PER_TABLE', '8'))
SCAN_STATEMENT_TIMEOUT_MS: int = int(os.getenv('SCAN_STATEMENT_TIMEOUT_MS', '5000'))
SCAN_TOTAL_TIME_BUDGET_MS: int = int(os.getenv('SCAN_TOTAL_TIME_BUDGET_MS', '8000'))
SOURCE_DETAIL_STATEMENT_TIMEOUT_MS: int = int(os.getenv('SOURCE_DETAIL_STATEMENT_TIMEOUT_MS', '60000'))


class DatabaseError(Exception):
    pass


class ValidationError(Exception):
    pass


_PG_CONN: Optional[psycopg2.extensions.connection] = None


def _get_conn_params() -> Dict[str, Any]:
    # 仅使用 PG_* 键名，从配置文件读取；不再支持环境变量或 POSTGRES_* 键
    host = config_manager.get('PG_HOST') or 'localhost'
    port = int(config_manager.get('PG_PORT') or '5432')
    dbname = config_manager.get('PG_DATABASE') or 'stranger'
    user = config_manager.get('PG_USER') or 'postgres'
    password = config_manager.get('PG_PASSWORD') or 'postgres'
    return {
        'host': host,
        'port': port,
        'dbname': dbname,
        'user': user,
        'password': password,
    }


def get_db() -> psycopg2.extensions.connection:
    global _PG_CONN
    if _PG_CONN and not _PG_CONN.closed:
        return _PG_CONN
    params = _get_conn_params()
    try:
        _PG_CONN = psycopg2.connect(**params)
        _PG_CONN.autocommit = True
        ensure_profile_schema(_PG_CONN)
        return _PG_CONN
    except Exception as e:
        raise DatabaseError(f"Failed to connect to PostgreSQL: {e}")


def get_collection(db: Any) -> str:
    """保持兼容，返回主表名。"""
    return 'profile'


def create_indexes(db: Any) -> None:
    conn = db if isinstance(db, psycopg2.extensions.connection) else get_db()
    with conn.cursor() as cur:
        # pg_trgm 扩展（支持三元组索引）
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        except Exception:
            pass
        # 基本索引
        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_profile_name ON profile(name);
        CREATE INDEX IF NOT EXISTS idx_profile_company ON profile(company);
        CREATE INDEX IF NOT EXISTS idx_profile_position ON profile(position);
        -- 为避免因尾随空格导致的姓名匹配遗漏，增加表达式索引
        CREATE INDEX IF NOT EXISTS idx_profile_name_lower_trim ON profile ((LOWER(TRIM(name))));
        """)
        # trigram 索引用于模糊匹配（姓名/公司）
        try:
            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_profile_name_trgm ON profile USING gin (name gin_trgm_ops);
            CREATE INDEX IF NOT EXISTS idx_profile_company_trgm ON profile USING gin (company gin_trgm_ops);
            """)
        except Exception:
            pass
        # JSONB 索引
        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_profile_phones ON profile USING gin (phones);
        CREATE INDEX IF NOT EXISTS idx_profile_emails ON profile USING gin (emails);
        CREATE INDEX IF NOT EXISTS idx_profile_qqs ON profile USING gin (qqs);
        CREATE INDEX IF NOT EXISTS idx_profile_weibo_uids ON profile USING gin (weibo_uids);
        CREATE INDEX IF NOT EXISTS idx_profile_relatives_names ON profile USING gin (relatives_names);
        CREATE INDEX IF NOT EXISTS idx_profile_relations ON profile USING gin (relatives_relations);
        """)


def list_all_table_columns(limit: Optional[int] = None) -> Dict[str, List[str]]:
    """枚举所有用户表及其列名，返回 {"schema.table": [columns...]}

    - 跳过系统 schema：pg_catalog, information_schema
    - 仅包含 BASE TABLE（不含视图）
    - 可选限制返回的表数量以避免开销
    """
    conn = get_db()
    result: Dict[str, List[str]] = {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        sql = (
            """
            SELECT c.table_schema, c.table_name, c.column_name, c.ordinal_position
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON c.table_schema = t.table_schema AND c.table_name = t.table_name
            WHERE t.table_type = 'BASE TABLE'
              AND c.table_schema NOT IN ('pg_catalog','information_schema')
            ORDER BY c.table_schema, c.table_name, c.ordinal_position
            """
        )
        cur.execute(sql)
        rows: List[Dict[str, Any]] = cur.fetchall() or []
        # 组装为字典
        for r in rows:
            key = f"{r['table_schema']}.{r['table_name']}"
            result.setdefault(key, []).append(str(r['column_name']))
        # 可选表数量限制
        if limit is not None and len(result) > int(limit):
            # 保留前 limit 个键
            keys = list(result.keys())[: int(limit)]
            result = {k: result[k] for k in keys}
    return result


# ---------------------------
# Schema & helpers
# ---------------------------

def ensure_profile_schema(conn: psycopg2.extensions.connection) -> None:
    """创建枚举、表与触发器（若不存在）。"""
    with conn.cursor() as cur:
        # 性别枚举
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gender_enum') THEN
                    CREATE TYPE gender_enum AS ENUM ('男','女');
                END IF;
                -- 确保包含“其他”
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = 'gender_enum' AND e.enumlabel = '其他'
                ) THEN
                    ALTER TYPE gender_enum ADD VALUE '其他';
                END IF;
            END$$;
            """
        )

        # 主表
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id VARCHAR(32),             -- 新主键（迁移时填充）
                id_card VARCHAR(32),        -- 次唯一键（可为空）
                name VARCHAR(50),
                gender gender_enum,
                native_place VARCHAR(100),
                birth_date DATE,
                phones JSONB,                -- [{"type":"主要","number":"13800138000"},...]
                emails JSONB,                -- [{"type":"工作","address":"test@example.com"},...]
                qqs JSONB,                   -- ["123456",...]
                weibo_uids JSONB,            -- ["weibo_123",...]
                company VARCHAR(100),
                position VARCHAR(50),
                spouse_name VARCHAR(50),
                spouse_phone VARCHAR(20),
                relatives_names JSONB,       -- ["张三","李四"]
                relatives_phones JSONB,      -- ["13800138000","13900139000"]
                relatives_relations JSONB,   -- [{"name":"张三","relation":"父亲"},...]
                data_sources JSONB,          -- ["source_table1","source_table2"]
                ai_confidence JSONB,         -- 预留AI字段
                created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
            );
            """
        )

        # 迁移：确保存在 id 列、设置主键到 id、为 id_card 建唯一约束
        # 1) 添加 id 列（若不存在）
        cur.execute("ALTER TABLE profile ADD COLUMN IF NOT EXISTS id VARCHAR(32);")
        # 2) 为已有记录填充随机 id：不再用 id_card 作为回填来源
        try:
            # 选择需要回填的记录：id 为空/空串，或 id 等于 id_card；使用ctid精确定位行
            cur.execute("SELECT ctid, id, id_card FROM profile WHERE (id IS NULL OR TRIM(id)='') OR (id_card IS NOT NULL AND TRIM(id)=TRIM(id_card));")
            rows = cur.fetchall() or []
            for _ctid, _id, _idc in rows:
                # 生成唯一随机id，避免与现有值冲突
                rid = _generate_random_id(18)
                # 简单冲突检查，若冲突则重试（概率极低）
                retry = 0
                while retry < 5:
                    cur.execute("SELECT 1 FROM profile WHERE id=%s", (rid,))
                    if cur.fetchone():
                        rid = _generate_random_id(18)
                        retry += 1
                    else:
                        break
                # 仅更新当前行
                cur.execute("UPDATE profile SET id=%s WHERE ctid=%s", (rid, _ctid))
        except Exception:
            # 若回填过程出错，继续后续步骤，避免阻断启动
            pass
        # 3) 为 id_card 添加唯一索引（作为次唯一键）
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_profile_id_card ON profile (id_card);")
        # 3.1) 允许 id_card 为空：兼容无身份证的轻量记录
        try:
            cur.execute("ALTER TABLE profile ALTER COLUMN id_card DROP NOT NULL;")
        except Exception:
            # 已为可空或旧版本约束不同，忽略
            pass
        # 4) 切换主键到 id（若当前主键仍为 id_card）
        cur.execute(
            """
            DO $$
            DECLARE
                pk_name TEXT;
            BEGIN
                SELECT tc.constraint_name INTO pk_name
                FROM information_schema.table_constraints tc
                WHERE tc.table_name = 'profile' AND tc.constraint_type = 'PRIMARY KEY';
                IF pk_name IS NOT NULL THEN
                    -- 若主键存在且不是在 id 上，则尝试删除
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.key_column_usage kcu
                        WHERE kcu.table_name = 'profile' AND kcu.constraint_name = pk_name AND kcu.column_name = 'id'
                    ) THEN
                        EXECUTE 'ALTER TABLE profile DROP CONSTRAINT ' || pk_name;
                    END IF;
                END IF;
                -- 若没有以 id 为主键的约束，则创建
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name
                    WHERE tc.table_name = 'profile' AND tc.constraint_type = 'PRIMARY KEY' AND kcu.column_name = 'id'
                ) THEN
                    -- 先确保 id 非空（不再从 id_card 回填）
                    EXECUTE 'ALTER TABLE profile ALTER COLUMN id SET NOT NULL';
                    EXECUTE 'ALTER TABLE profile ADD CONSTRAINT profile_id_pkey PRIMARY KEY (id)';
                END IF;
            END$$;
            """
        )

        # 更新时间触发器
        cur.execute(
            """
            CREATE OR REPLACE FUNCTION set_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at := NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'profile_set_updated_at'
                ) THEN
                    CREATE TRIGGER profile_set_updated_at
                    BEFORE UPDATE ON profile
                    FOR EACH ROW EXECUTE PROCEDURE set_updated_at();
                END IF;
            END$$;
            """
        )

        # 行政区划代码映射表（身份证前六位 -> 名称）
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS region_code_map (
                code VARCHAR(6) PRIMARY KEY,
                name TEXT NOT NULL
            );
            """
        )


def _generate_random_id(length: int = 18) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(random.choice(alphabet) for _ in range(length))


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    s = re.sub(r"\D", "", str(phone))
    if not s:
        return None
    if s.startswith('86') and len(s) > 11:
        s = s[-11:]
    return s
def _normalize_qq(qq: Optional[str]) -> Optional[str]:
    if not qq:
        return None
    s = re.sub(r"\D", "", str(qq))
    if not s:
        return None
    if 5 <= len(s) <= 12:
        return s
    return None


def _json_add_unique(obj: Optional[List[str]], value: Optional[str]) -> List[str]:
    arr = list(obj or [])
    v = (value or '').strip()
    if v and v not in arr:
        arr.append(v)
    return arr


def _merge_unique(a: Optional[List[str]], b: Optional[List[str]], transform=lambda x: x) -> List[str]:
    """合并两个列表并去重，允许对元素做归一化转换。"""
    result: List[str] = []
    for src in (a or []):
        val = transform(src)
        if val and val not in result:
            result.append(val)
    for src in (b or []):
        val = transform(src)
        if val and val not in result:
            result.append(val)
    return result


def _rel_add_relation(rel_list: Optional[List[Dict[str, Any]]], name: Optional[str], relation: Optional[str]) -> List[Dict[str, Any]]:
    """在关系对象数组中加入唯一项 {name, relation}。"""
    lst: List[Dict[str, Any]] = list(rel_list or [])
    n = (name or '').strip()
    r = (relation or '').strip()
    if not n or not r:
        return lst
    key = f"{n}|{r}"
    if key not in {f"{d.get('name')}|{d.get('relation')}" for d in lst if isinstance(d, dict)}:
        lst.append({'name': n, 'relation': r})
    return lst


def _merge_profile(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """将两个 profile 风格的字典进行合并，数组字段做并集去重，保留已有标量优先。"""
    if not a and not b:
        return None
    if not a:
        return dict(b or {})
    if not b:
        return dict(a or {})

    # 关键约束：不同身份证号的记录绝不合并，防止跨人污染
    try:
        ida = str(a.get('id_card') or '').strip()
        idb = str(b.get('id_card') or '').strip()
        if ida and idb and ida != idb:
            # 返回已有记录，忽略另一条不同身份证的数据
            return dict(a)
    except Exception:
        # 防御性：即使读取失败也不跨合并
        return dict(a)

    merged = dict(a)

    # 标量字段：保留已有，若为空则使用新值
    for key in ['id_card', 'name', 'gender', 'native_place', 'birth_date', 'company', 'position', 'spouse_name']:
        if not merged.get(key):
            merged[key] = b.get(key) or merged.get(key)
    # 配偶手机号归一化后合并为标量（若已有为空则覆盖）
    if not merged.get('spouse_phone') and b.get('spouse_phone'):
        merged['spouse_phone'] = _normalize_phone(b.get('spouse_phone'))

    # 数组字段：并集去重
    merged['phones'] = _merge_unique(merged.get('phones'), b.get('phones'), _normalize_phone)
    merged['emails'] = _merge_unique(merged.get('emails'), b.get('emails'), lambda x: (str(x).strip() or None))
    merged['qqs'] = _merge_unique(merged.get('qqs'), b.get('qqs'), lambda x: (str(x).strip() or None))
    merged['weibo_uids'] = _merge_unique(merged.get('weibo_uids'), b.get('weibo_uids'), lambda x: (str(x).strip() or None))
    spouse_words = {'配偶', '妻子', '丈夫'}
    merged['relatives_names'] = _merge_unique(merged.get('relatives_names'), b.get('relatives_names'), lambda x: (str(x).strip() or None))
    merged['relatives_phones'] = _merge_unique(merged.get('relatives_phones'), b.get('relatives_phones'), _normalize_phone)
    merged['relatives_types'] = [t for t in _merge_unique(merged.get('relatives_types'), b.get('relatives_types'), lambda x: (str(x).strip() or None)) if t not in spouse_words]

    # 合并对象关系并过滤掉配偶相关
    rel_a = [d for d in (merged.get('relatives_relations') or []) if isinstance(d, dict)]
    rel_b = [d for d in (b.get('relatives_relations') or []) if isinstance(d, dict)]
    rel_merged: List[Dict[str, Any]] = []
    for d in rel_a:
        rel_merged = _rel_add_relation(rel_merged, d.get('name'), d.get('relation'))
    for d in rel_b:
        rel_merged = _rel_add_relation(rel_merged, d.get('name'), d.get('relation'))
    rel_merged = [d for d in rel_merged if (d.get('relation') or '') not in spouse_words]
    merged['relatives_relations'] = rel_merged

    # 数据来源：仅存储表名字符串，合并并去重
    ds_a = a.get('data_sources') or []
    ds_b = b.get('data_sources') or []
    merged_ds: List[str] = []
    for item in (ds_a + ds_b):
        if isinstance(item, dict):
            t = item.get('table') or item.get('source') or item.get('name')
        else:
            t = str(item).strip() if item is not None else None
        if t and t not in merged_ds:
            merged_ds.append(t)
    merged['data_sources'] = merged_ds

    return merged


def _parse_id_card_info(id_card: str) -> Tuple[Optional[str], Optional[date], Optional[str]]:
    """返回 (gender, birth_date, native_place_code)。按规范解析。"""
    code = re.sub(r"\s+", "", id_card or '')
    if len(code) < 17:
        return (None, None, None)
    # 性别：第17位奇偶
    try:
        gender = '男' if int(code[16]) % 2 == 1 else '女'
    except Exception:
        gender = None
    # 出生日期：第7-14位
    b = code[6:14]
    birth = None
    if re.fullmatch(r"\d{8}", b):
        try:
            birth = datetime.strptime(b, "%Y%m%d").date()
        except Exception:
            birth = None
    # 籍贯：前6位地区码（此处回填地区码本身；可扩展字典映射）
    native_place = code[:6] if re.fullmatch(r"\d{6}", code[:6]) else None
    return (gender, birth, native_place)


def _luhn_check_18(code: str) -> bool:
    """按需求使用 Luhn 校验最后一位。允许末位为 X 视作 10。"""
    s = re.sub(r"\s+", "", code or '')
    if not re.fullmatch(r"[0-9A-Z]{18}", s):
        return False
    digits = [int(c) if c.isdigit() else (10 if c == 'X' else 0) for c in s]
    checksum = 0
    # Luhn：从右往左，偶位乘2减9
    for i, d in enumerate(reversed(digits[:-1])):
        if i % 2 == 0:
            dd = d * 2
            if dd > 9:
                dd -= 9
            checksum += dd
        else:
            checksum += d
    check_digit = (10 - (checksum % 10)) % 10
    return check_digit == (digits[-1] if digits[-1] < 10 else 10)


def validate_or_generate_id(id_card: Optional[str]) -> Optional[str]:
    """仅规范化身份证号；不生成随机值。返回大写规范值或 None。"""
    if id_card:
        code = id_card.strip().upper()
        # 保留原值但统一格式（即使校验失败也不改写为随机）
        return code
    return None


# ---------------------------
# CRUD & Query
# ---------------------------

def upsert_profile(profile_data: Dict[str, Any], source_table: Optional[str] = None) -> Dict[str, Any]:
    """新增或更新主表。仅写入 profile，不修改源表。"""
    conn = get_db()
    # 次唯一键：不生成随机，仅规范化
    id_card = validate_or_generate_id(profile_data.get('id_card'))
    # 主唯一键：优先使用传入的 id；否则生成随机；不再回退到 id_card
    raw_id = (str(profile_data.get('id')).strip().upper() if profile_data.get('id') is not None else None)
    primary_id = raw_id or _generate_random_id(18)
    name = (profile_data.get('name') or '').strip() or None

    # 自动解析身份证字段
    gender_auto, birth_auto, native_auto = _parse_id_card_info(id_card)
    gender = profile_data.get('gender') or gender_auto
    birth_date = profile_data.get('birth_date') or birth_auto
    native_place = profile_data.get('native_place') or native_auto

    # 统一性别值到枚举范围：男/女/其他；其他值（如“未知”）置空
    if gender is not None:
        g = str(gender).strip()
        gender = g if g in ('男', '女', '其他') else None

    phones = profile_data.get('phones') or []
    emails = profile_data.get('emails') or []
    qqs = profile_data.get('qqs') or []
    weibo_uids = profile_data.get('weibo_uids') or []
    company = profile_data.get('company')
    position = profile_data.get('position')
    spouse_name = profile_data.get('spouse_name')
    spouse_phone = _normalize_phone(profile_data.get('spouse_phone'))
    relatives_names = profile_data.get('relatives_names') or []
    relatives_phones = [p for p in map(_normalize_phone, profile_data.get('relatives_phones') or []) if p]
    relatives_types = profile_data.get('relatives_types') or []
    # 合并已有对象关系与数组关系，并过滤掉“配偶/妻子/丈夫”不写入直系亲属
    input_rel_objs = [d for d in (profile_data.get('relatives_relations') or []) if isinstance(d, dict)]
    merged_rel_objs: List[Dict[str, Any]] = []
    for nm, tp in zip(relatives_names, relatives_types):
        merged_rel_objs = _rel_add_relation(merged_rel_objs, nm, tp)
    for d in input_rel_objs:
        merged_rel_objs = _rel_add_relation(merged_rel_objs, d.get('name'), d.get('relation'))
    spouse_words = {'配偶', '妻子', '丈夫'}
    merged_rel_objs = [d for d in merged_rel_objs if (d.get('relation') or '') not in spouse_words]
    # 根据合并后的对象关系回填数组字段（保持去重）
    rel_name_set: List[str] = []
    rel_type_set: List[str] = []
    for d in merged_rel_objs:
        rel_name_set = _json_add_unique(rel_name_set, d.get('name'))
        rel_type_set = _json_add_unique(rel_type_set, d.get('relation'))
    # 过滤掉配偶对应的手机号（按 name 对齐）
    spouse_names = {d.get('name') for d in (profile_data.get('relatives_relations') or []) if isinstance(d, dict) and (d.get('relation') or '') in spouse_words}
    filtered_name_phone_pairs = [(nm, ph) for nm, ph in zip(relatives_names, relatives_phones) if nm not in spouse_names]
    relatives_names = rel_name_set
    relatives_types = rel_type_set
    relatives_phones = [ph for _, ph in filtered_name_phone_pairs]
    relatives_relations = merged_rel_objs
    data_sources = profile_data.get('data_sources') or []
    # 允许 source_table 为字符串或字典，仅取表名
    _source_key = None
    if isinstance(source_table, dict):
        _source_key = source_table.get('table') or source_table.get('source') or source_table.get('name')
    elif isinstance(source_table, str):
        _source_key = source_table

    # 规范化 data_sources 为字符串数组并去重
    norm_sources: List[str] = []
    for s in (data_sources if isinstance(data_sources, list) else []):
        if isinstance(s, dict):
            t = s.get('table') or s.get('source') or s.get('name')
        else:
            t = str(s).strip() if s is not None else None
        if t and t not in norm_sources:
            norm_sources.append(t)
    if _source_key:
        sk = str(_source_key).strip()
        if sk and sk not in norm_sources:
            norm_sources.append(sk)
    data_sources = norm_sources

    # 规范化数组值
    phones = [p for p in map(_normalize_phone, phones) if p]
    emails = [e.strip() for e in emails if e]
    qqs = [str(q).strip() for q in qqs if q]
    weibo_uids = [str(u).strip() for u in weibo_uids if u]
    relatives_names = [n.strip() for n in relatives_names if n]
    relatives_types = [t.strip() for t in relatives_types if t and t not in spouse_words]

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 判断是否存在（按主键 id）
        cur.execute("SELECT 1 FROM profile WHERE id=%s", (primary_id,))
        exists = cur.fetchone() is not None

        if exists:
            cur.execute(
                """
                UPDATE profile SET
                    name=%s,
                    gender=%s,
                    native_place=%s,
                    birth_date=%s,
                    phones=%s,
                    emails=%s,
                    qqs=%s,
                    weibo_uids=%s,
                    company=%s,
                    position=%s,
                    spouse_name=%s,
                    spouse_phone=%s,
                    relatives_names=%s,
                    relatives_phones=%s,
                    relatives_relations=%s,
                    data_sources=%s
                WHERE id=%s
                RETURNING *
                """,
                (
                    name, gender, native_place, birth_date,
                    Json(phones), Json(emails), Json(qqs), Json(weibo_uids),
                    company, position, spouse_name, spouse_phone,
                    Json(relatives_names), Json(relatives_phones), Json(relatives_relations),
                    Json(data_sources), primary_id
                )
            )
        else:
            cur.execute(
                """
                INSERT INTO profile (
                    id, id_card, name, gender, native_place, birth_date,
                    phones, emails, qqs, weibo_uids,
                    company, position,
                    spouse_name, spouse_phone,
                    relatives_names, relatives_phones, relatives_relations,
                    data_sources
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,
                    %s,%s,
                    %s,%s,
                    %s,%s,%s,
                    %s
                ) RETURNING *
                """,
                (
                    primary_id, id_card, name, gender, native_place, birth_date,
                    Json(phones), Json(emails), Json(qqs), Json(weibo_uids),
                    company, position,
                    spouse_name, spouse_phone,
                    Json(relatives_names), Json(relatives_phones), Json(relatives_relations),
                    Json(data_sources)
                )
            )

        rec = cur.fetchone()
        return dict(rec or {})


def _columns_for_search(conn) -> Dict[str, List[str]]:
    """列出所有非 profile 表且可搜索的列。"""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT table_schema, table_name, column_name
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog','information_schema')
              AND table_name <> 'profile'
            """
        )
        cols: Dict[str, List[str]] = {}
        for r in cur.fetchall() or []:
            key = f"{r['table_schema']}.{r['table_name']}"
            cols.setdefault(key, []).append(r['column_name'])
        return cols


def _find_existing_profile_candidate(profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """在主表基于多特征查找可能同一人的候选记录：
    优先级：id_card > phone(含配偶/亲属) > qq > email > weibo_uid > 复合(name+birth_date/native_place/company)
    命中则返回主表记录，否则返回 None。
    """
    conn = get_db()

    # 归一化输入特征
    id_card = (str(profile.get('id_card') or '').strip() or None)
    name = (str(profile.get('name') or '').strip() or None)
    birth = profile.get('birth_date')
    if isinstance(birth, str):
        try:
            birth = datetime.fromisoformat(birth).date()
        except Exception:
            birth = None
    native_place = (str(profile.get('native_place') or '').strip() or None)
    company = (str(profile.get('company') or '').strip() or None)
    spouse_phone = _normalize_phone(profile.get('spouse_phone'))

    # phones：包含主号、配偶号、亲属号
    phone_set: List[str] = []
    for p in (profile.get('phones') or []):
        if isinstance(p, dict) and p.get('number'):
            ph = _normalize_phone(p.get('number'))
            if ph:
                phone_set.append(ph)
        else:
            ph = _normalize_phone(p)
            if ph:
                phone_set.append(ph)
    if spouse_phone:
        phone_set.append(spouse_phone)
    for rp in (profile.get('relatives_phones') or []):
        ph = _normalize_phone(rp)
        if ph:
            phone_set.append(ph)

    # qqs
    qq_set: List[str] = []
    for q in (profile.get('qqs') or []):
        if isinstance(q, dict) and q.get('qq'):
            qq_set.append(str(q.get('qq')).strip())
        else:
            s = str(q).strip()
            if s:
                qq_set.append(s)

    # emails（统一小写）
    email_set: List[str] = []
    for e in (profile.get('emails') or []):
        s = str(e).strip()
        if s:
            email_set.append(s)

    weibo_set: List[str] = []
    for u in (profile.get('weibo_uids') or []):
        s = str(u).strip()
        if s:
            weibo_set.append(s)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1) 身份证号优先
        if id_card:
            try:
                cur.execute("SELECT * FROM profile WHERE id_card=%s LIMIT 1", (id_card,))
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception:
                pass

        # 2) 手机号（含配偶/亲属手机号）
        for ph in phone_set:
            try:
                ph86 = f"86{ph}"
                cur.execute(
                    """
                    SELECT * FROM profile
                    WHERE EXISTS (
                        SELECT 1 FROM jsonb_array_elements(phones) AS p
                        WHERE p->>'number'=%s OR p->>'number'=%s
                    )
                    OR EXISTS (
                        SELECT 1 FROM jsonb_array_elements_text(phones) AS t
                        WHERE regexp_replace(t, '[^0-9]', '', 'g')=%s OR regexp_replace(t, '[^0-9]', '', 'g')=%s
                    )
                    OR regexp_replace(COALESCE(spouse_phone,''), '[^0-9]', '', 'g')=%s OR regexp_replace(COALESCE(spouse_phone,''), '[^0-9]', '', 'g')=%s
                    OR EXISTS (
                        SELECT 1 FROM jsonb_array_elements_text(relatives_phones) AS rp
                        WHERE regexp_replace(rp, '[^0-9]', '', 'g')=%s OR regexp_replace(rp, '[^0-9]', '', 'g')=%s
                    )
                    LIMIT 1
                    """,
                    (ph, ph86, ph, ph86, ph, ph86, ph, ph86)
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception:
                continue

        # 3) QQ
        for qq in qq_set:
            try:
                cur.execute(
                    """
                    SELECT * FROM profile
                    WHERE EXISTS (
                        SELECT 1 FROM jsonb_array_elements(qqs) AS q WHERE q->>'qq'=%s
                    )
                    OR EXISTS (
                        SELECT 1 FROM jsonb_array_elements_text(qqs) AS q WHERE q=%s
                    )
                    LIMIT 1
                    """,
                    (qq, qq)
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception:
                continue

        # 4) 邮箱
        for em in email_set:
            try:
                cur.execute(
                    """
                    SELECT * FROM profile
                    WHERE EXISTS (
                        SELECT 1 FROM jsonb_array_elements_text(emails) AS e WHERE LOWER(e)=LOWER(%s)
                    )
                    LIMIT 1
                    """,
                    (em,)
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception:
                continue

        # 5) 微博 UID
        for wb in weibo_set:
            try:
                cur.execute(
                    """
                    SELECT * FROM profile
                    WHERE EXISTS (
                        SELECT 1 FROM jsonb_array_elements_text(weibo_uids) AS u WHERE u=%s
                    )
                    LIMIT 1
                    """,
                    (wb,)
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception:
                continue

        # 6) 复合特征：name + birth_date
        if name and isinstance(birth, date):
            try:
                cur.execute(
                    "SELECT * FROM profile WHERE LOWER(TRIM(name))=LOWER(%s) AND birth_date=%s LIMIT 1",
                    (name, birth)
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception:
                pass

        # 7) 复合特征：name + native_place
        if name and native_place:
            try:
                cur.execute(
                    "SELECT * FROM profile WHERE LOWER(TRIM(name))=LOWER(%s) AND native_place=%s LIMIT 1",
                    (name, native_place)
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception:
                pass

        # 8) 复合特征：name + company
        if name and company:
            try:
                cur.execute(
                    "SELECT * FROM profile WHERE LOWER(TRIM(name))=LOWER(%s) AND LOWER(TRIM(company))=LOWER(%s) LIMIT 1",
                    (name, company)
                )
                r = cur.fetchone()
                if r:
                    return dict(r)
            except Exception:
                pass

    return None


def _table_priority_score(full_table: str, cols: List[str], keywords: Dict[str, Any]) -> int:
    """为跨表扫描计算优先级分数，提升更可能命中的表。

    策略：
    - hukou 类表（户口相关）优先（名称包含 'hukou'）
    - 根据查询关键词，若表包含对应别名列则提高分数（name/phone/id_card/qq/weibo_uid）
    - 对仅按姓名查询但无明显姓名列的表给予轻微分数，避免完全被排除
    """
    s = 0
    tbl = str(full_table or '').lower()
    # 明显的户口相关表优先
    if 'hukou' in tbl:
        s += 10

    # 别名列匹配加权
    def has_alias(cols: List[str], canonical: str, defaults: List[str]) -> bool:
        aliases = _get_aliases(canonical, defaults)
        lower_aliases = [str(a).lower() for a in aliases]
        for c in (cols or []):
            lc = str(c).lower()
            if lc in lower_aliases:
                return True
            # 退化为包含关系匹配列名
            if any(a in lc for a in lower_aliases):
                return True
        return False

    # name
    if keywords.get('name'):
        s += 1  # 基础分
        if has_alias(cols, 'name', ['name', 'NAME', '姓名', '名字']):
            s += 4

    # id_card
    if keywords.get('id_card') and has_alias(cols, 'id_card', ['id_card', 'ID_CARD', '身份证', '身份证号']):
        s += 3
    # phone（含配偶/亲属手机号）
    if keywords.get('phone'):
        phone_hit = (
            has_alias(cols, 'phone', ['phone', 'PHONE', '手机号', '手机', '电话']) or
            has_alias(cols, 'spouse_phone', ['spouse_phone', '配偶手机号']) or
            has_alias(cols, 'relatives_phones', ['直系亲属手机号', '亲属手机号', '直属手机号'])
        )
        if phone_hit:
            s += 3
    # qq
    if keywords.get('qq') and has_alias(cols, 'qq', ['qq', 'QQ']):
        s += 2
    # weibo_uid
    if keywords.get('weibo_uid') and has_alias(cols, 'weibo_uid', ['weibo_uid', 'WEIBO_UID', 'uid', 'UID']):
        s += 2
    # email
    if keywords.get('email') and has_alias(cols, 'email', ['email', 'EMAIL', '邮箱', '电子邮件']):
        s += 3

    return s


def _match_row_fields(row: Dict[str, Any], keywords: Dict[str, Any]) -> int:
    """统计匹配字段数。"""
    count = 0
    for k, v in keywords.items():
        if v is None:
            continue
        for rk, rv in row.items():
            if str(rk).lower() in [k, k.upper()] or rk == k:
                # 简单相等或包含匹配
                sv = str(rv or '').strip()
                if sv and (sv == str(v) or str(v) in sv):
                    count += 1
                    break
    return count


def _map_row_to_profile(row: Dict[str, Any], table: str) -> Dict[str, Any]:
    """从任意来源行映射到 profile 结构。"""
    def g(canonical_key: str, *names):
        candidates = _get_aliases(canonical_key, list(names))
        for n in candidates:
            if n in row and row[n]:
                return row[n]
        for n in candidates:
            ln = str(n).lower()
            for k, v in row.items():
                if str(k).lower() == ln and v:
                    return v
        return None

    phone_val = g('phone', '手机号', '手机', 'phone', 'PHONE')
    email_val = g('email', '邮箱', '电子邮件', 'email', 'EMAIL')
    rel_name = g('relative_name', '直系亲属姓名', 'relative_name', 'RELATIVE_NAME')
    rel_phone = g('relative_phone', '直属手机号', '直系亲属手机号', '亲属手机号', 'relative_phone', 'RELATIVE_PHONE')
    rel_type = g('relationship', '直属关系', '直系亲属关系', '亲属关系', '关系', 'relationship', 'RELATIONSHIP')

    # 构造来源信息：仅存储表名字符串，展示时由 API 格式化

    data = {
        'id_card': g('id_card', '身份证号', '身份证', 'id_card', 'ID_CARD'),
        'name': g('name', '姓名', '名字', 'name', 'NAME'),
        'gender': g('gender', '性别', 'gender', 'GENDER'),
        'native_place': g('native_place', '籍贯', 'native_place', 'NATIVE_PLACE'),
        'birth_date': g('birth_date', '出生日期', 'birth_date', 'BIRTH_DATE'),
        # 统一使用简单字符串数组以与主表 schema 保持一致
        'phones': ([_normalize_phone(phone_val)] if phone_val else []),
        'emails': ([str(email_val).strip()] if email_val else []),
        'qqs': [q for q in filter(None, [g('qq', 'qq', 'QQ')])],
        'weibo_uids': [u for u in filter(None, [g('weibo_uid', 'uid', 'weibo_uid', 'WEIBO_UID')])],
        'company': g('company', '单位名称', '公司', 'company', 'COMPANY'),
        'position': g('position', '职位', '部门', 'position', 'POSITION'),
        'spouse_name': g('spouse_name', '配偶姓名', 'spouse_name', 'SPOUSE_NAME'),
        'spouse_phone': g('spouse_phone', '配偶手机号', 'spouse_phone', 'SPOUSE_PHONE'),
        'relatives_names': ([rel_name] if rel_name else []),
        'relatives_phones': ([_normalize_phone(rel_phone)] if rel_phone else []),
        'relatives_types': ([str(rel_type).strip()] if rel_type else []),
        'relatives_relations': (_rel_add_relation([], rel_name, rel_type) if rel_name and rel_type else []),
        'data_sources': [table]
    }
    # 若提供了身份证号，补全缺失的籍贯/性别/生日
    id_val = data.get('id_card')
    if id_val and isinstance(id_val, str):
        code = id_val[:6]
        if (not data.get('native_place')) and code and code.isdigit() and len(code) == 6:
            np = lookup_native_place_from_code(code)
            if np:
                data['native_place'] = np
        if not data.get('gender'):
            gdr = _infer_gender_from_id(id_val)
            if gdr:
                data['gender'] = gdr
        if not data.get('birth_date'):
            bd = _infer_birth_from_id(id_val)
            if bd:
                data['birth_date'] = bd
    return data


def scan_all_tables_for_subject(keywords: Dict[str, Any], limit_per_table: int = SCAN_LIMIT_PER_TABLE) -> Optional[Dict[str, Any]]:
    """在所有表中执行关键词查询，聚合所有命中行并合并为单个 profile。
    为避免超时：
    - 仅在可能相关的列上匹配（如 id_card/phone/qq/name/weibo_uid 等）
    - 限制每张表返回的记录数
    - 限制扫描的表数量
    - 为会话设置语句执行超时
    """
    conn = get_db()
    # 为当前会话设置语句超时，避免慢表阻塞
    try:
        with conn.cursor() as _c:
            _c.execute(f"SET statement_timeout = {SCAN_STATEMENT_TIMEOUT_MS}")
    except Exception:
        # 忽略设置失败，继续执行
        pass

    cols_map = _columns_for_search(conn)
    combined: Optional[Dict[str, Any]] = None
    tables_scanned = 0
    start_ts = time.time()

    # 使用动态别名，确保能命中配偶与亲属手机号等列
    phone_aliases = _get_aliases('phone', ['phone', 'PHONE', '手机号', '手机', '电话'])
    spouse_phone_aliases = _get_aliases('spouse_phone', ['spouse_phone', '配偶手机号'])
    relatives_phone_aliases = _get_aliases('relatives_phones', ['直系亲属手机号', '亲属手机号', '直属手机号'])
    name_aliases = _get_aliases('name', ['name', 'NAME', '姓名', '名字'])
    id_aliases = _get_aliases('id_card', ['id_card', 'ID_CARD', '身份证', '身份证号'])
    weibo_aliases = _get_aliases('weibo_uid', ['weibo_uid', 'WEIBO_UID', 'uid', 'UID'])
    email_aliases = _get_aliases('email', ['email', 'EMAIL', '邮箱', '电子邮件'])
    key_patterns: Dict[str, List[str]] = {
        'id_card': list(set(id_aliases)),
        'phone': list(set(phone_aliases + spouse_phone_aliases + relatives_phone_aliases)),
        'qq': ['qq', 'QQ'],
        'name': list(set(name_aliases)),
        'weibo_uid': list(set(weibo_aliases)),
        'email': list(set(email_aliases))
    }

    # 依据优先级对表排序，先扫更可能命中者
    sorted_items = sorted(
        cols_map.items(),
        key=lambda kv: _table_priority_score(kv[0], kv[1], keywords),
        reverse=True
    )
    for full_table, cols in sorted_items:
        # 总时间预算控制，避免长时间阻塞导致 worker 超时
        if (time.time() - start_ts) * 1000 >= SCAN_TOTAL_TIME_BUDGET_MS:
            break
        if tables_scanned >= SCAN_MAX_TABLES:
            break
        schema, table = full_table.split('.')
        where_clauses: List[str] = []
        params: List[Any] = []

        # 仅在匹配相关列时才构造条件
        for k, v in keywords.items():
            if v is None:
                continue
            # 自由文本模式：在该表所有列上做 LIKE
            if k == 'general':
                matched_cols = cols[:]
                patterns = []
            else:
                patterns = key_patterns.get(k, [])
                matched_cols = [col for col in cols if any(p == col for p in patterns)]
            if not matched_cols:
                # 退化为包含关系匹配列名
                lc_patterns = [p.lower() for p in patterns]
                matched_cols = [col for col in cols if any(lp in col.lower() for lp in lc_patterns)]
            for col in matched_cols:
                if k in ('id_card', 'qq', 'weibo_uid'):
                    # 保持等值匹配
                    where_clauses.append(f"CAST({col} AS TEXT) = %s")
                    params.append(str(v))
                elif k == 'phone':
                    # 对手机号进行规范化，忽略非数字字符，并支持可选前导86
                    norm = _normalize_phone(str(v))
                    if norm:
                        where_clauses.append(f"regexp_replace(CAST({col} AS TEXT), '[^0-9]', '', 'g') = %s")
                        params.append(norm)
                        where_clauses.append(f"regexp_replace(CAST({col} AS TEXT), '[^0-9]', '', 'g') = %s")
                        params.append(f"86{norm}")
                elif k == 'email':
                    # 邮箱大小写不敏感的等值匹配
                    where_clauses.append(f"LOWER(CAST({col} AS TEXT)) = LOWER(%s)")
                    params.append(str(v))
                else:
                    where_clauses.append(f"LOWER(CAST({col} AS TEXT)) LIKE LOWER(%s)")
                    params.append(f"%{str(v)}%")

        if not where_clauses:
            continue

        sql = f"SELECT * FROM {schema}.{table} WHERE " + " OR ".join(where_clauses) + " LIMIT %s"
        params.append(limit_per_table)

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
                for r in rows:
                    prof = _map_row_to_profile(r, full_table)
                    combined = _merge_profile(combined, prof)
            tables_scanned += 1
        except Exception:
            # 跳过异常表或慢表
            continue
    return combined


def scan_all_tables_for_subject_multi(keywords: Dict[str, Any], limit_per_table: int = SCAN_LIMIT_PER_TABLE) -> List[Dict[str, Any]]:
    """跨表扫描，按身份证号分组返回多条 profile。
    - 当源行缺少身份证号时跳过（避免跨人误合并）
    - 同一身份证的多源数据使用 _merge_profile 合并为一条
    """
    conn = get_db()
    try:
        with conn.cursor() as _c:
            _c.execute(f"SET statement_timeout = {SCAN_STATEMENT_TIMEOUT_MS}")
    except Exception:
        pass

    cols_map = _columns_for_search(conn)
    profiles_by_id: Dict[str, Dict[str, Any]] = {}
    tables_scanned = 0
    start_ts = time.time()

    phone_aliases = _get_aliases('phone', ['phone', 'PHONE', '手机号', '手机', '电话'])
    spouse_phone_aliases = _get_aliases('spouse_phone', ['spouse_phone', '配偶手机号'])
    relatives_phone_aliases = _get_aliases('relatives_phones', ['直系亲属手机号', '亲属手机号', '直属手机号'])
    name_aliases = _get_aliases('name', ['name', 'NAME', '姓名', '名字'])
    id_aliases = _get_aliases('id_card', ['id_card', 'ID_CARD', '身份证', '身份证号'])
    weibo_aliases = _get_aliases('weibo_uid', ['weibo_uid', 'WEIBO_UID', 'uid', 'UID'])
    key_patterns: Dict[str, List[str]] = {
        'id_card': list(set(id_aliases)),
        'phone': list(set(phone_aliases + spouse_phone_aliases + relatives_phone_aliases)),
        'qq': ['qq', 'QQ'],
        'name': list(set(name_aliases)),
        'weibo_uid': list(set(weibo_aliases))
    }

    sorted_items = sorted(
        cols_map.items(),
        key=lambda kv: _table_priority_score(kv[0], kv[1], keywords),
        reverse=True
    )
    for full_table, cols in sorted_items:
        if (time.time() - start_ts) * 1000 >= SCAN_TOTAL_TIME_BUDGET_MS:
            break
        if tables_scanned >= SCAN_MAX_TABLES:
            break
        schema, table = full_table.split('.')
        where_clauses: List[str] = []
        params: List[Any] = []

        for k, v in keywords.items():
            if v is None:
                continue
            patterns = key_patterns.get(k, [])
            matched_cols = [col for col in cols if any(p == col for p in patterns)]
            if not matched_cols:
                lc_patterns = [p.lower() for p in patterns]
                matched_cols = [col for col in cols if any(lp in col.lower() for lp in lc_patterns)]
            for col in matched_cols:
                if k in ('id_card', 'qq', 'weibo_uid'):
                    where_clauses.append(f"CAST({col} AS TEXT) = %s")
                    params.append(str(v))
                elif k == 'phone':
                    norm = _normalize_phone(str(v))
                    if norm:
                        where_clauses.append(f"regexp_replace(CAST({col} AS TEXT), '[^0-9]', '', 'g') = %s")
                        params.append(norm)
                        where_clauses.append(f"regexp_replace(CAST({col} AS TEXT), '[^0-9]', '', 'g') = %s")
                        params.append(f"86{norm}")
                else:
                    where_clauses.append(f"LOWER(CAST({col} AS TEXT)) LIKE LOWER(%s)")
                    params.append(f"%{str(v)}%")

        if not where_clauses:
            continue
        sql = f"SELECT * FROM {schema}.{table} WHERE " + " OR ".join(where_clauses) + " LIMIT %s"
        params.append(limit_per_table)

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
                for r in rows:
                    prof = _map_row_to_profile(r, full_table)
                    id_card = (prof.get('id_card') or '').strip()
                    if not id_card:
                        continue  # 仅对有身份证的记录进行分组聚合
                    existing = profiles_by_id.get(id_card)
                    profiles_by_id[id_card] = _merge_profile(existing, prof)
            tables_scanned += 1
        except Exception:
            continue

    return list(profiles_by_id.values())


def find_profile(query_key: str, query_value: str) -> Optional[Dict[str, Any]]:
    """查询主表，若不存在则扫描各表并写入后返回。"""
    conn = get_db()
    qk = query_key.lower()
    qv = (query_value or '').strip()
    if qk == 'phone':
        qv = _normalize_phone(qv) or qv

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if qk == 'id':
            cur.execute("SELECT * FROM profile WHERE id=%s", (qv,))
        elif qk == 'id_card':
            cur.execute("SELECT * FROM profile WHERE id_card=%s", (qv,))
        elif qk == 'phone':
            # 同时匹配规范化后的手机号（移除非数字、可选前导86）
            qv86 = f"86{qv}"
            cur.execute(
                """
                SELECT * FROM profile
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements(phones) AS p
                    WHERE p->>'number'=%s OR p->>'number'=%s
                )
                OR EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(phones) AS t
                    WHERE regexp_replace(t, '[^0-9]', '', 'g')=%s OR regexp_replace(t, '[^0-9]', '', 'g')=%s
                )
                OR regexp_replace(COALESCE(spouse_phone,''), '[^0-9]', '', 'g')=%s OR regexp_replace(COALESCE(spouse_phone,''), '[^0-9]', '', 'g')=%s
                OR EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(relatives_phones) AS rp
                    WHERE regexp_replace(rp, '[^0-9]', '', 'g')=%s OR regexp_replace(rp, '[^0-9]', '', 'g')=%s
                )
                """,
                (qv, qv86, qv, qv86, qv, qv86, qv, qv86)
            )
        elif qk == 'qq':
            cur.execute(
                """
                SELECT * FROM profile
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements(qqs) AS q WHERE q->>'qq'=%s
                )
                OR EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(qqs) AS q WHERE q=%s
                )
                """,
                (qv, qv)
            )
        elif qk == 'email':
            cur.execute(
                """
                SELECT * FROM profile
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(emails) AS e WHERE LOWER(e) = LOWER(%s)
                )
                """,
                (qv,)
            )
        elif qk in ('weibo', 'weibo_uid', 'uid'):
            cur.execute(
                """
                SELECT * FROM profile
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(weibo_uids) AS u WHERE u=%s
                )
                """,
                (qv,)
            )
        else:
            # 使用 TRIM 等值匹配，避免姓名存在前后空格导致的漏查
            cur.execute("SELECT * FROM profile WHERE LOWER(TRIM(name))=LOWER(%s)", (qv,))

        rec = cur.fetchone()
        if rec:
            return dict(rec)

    # 若无记录则扫描所有表
    keywords = {
        'name': qv if qk == 'name' else None,
        'id_card': qv if qk == 'id_card' else None,
        'phone': qv if qk == 'phone' else None,
        'qq': qv if qk == 'qq' else None,
        'weibo_uid': qv if qk in ('weibo', 'weibo_uid', 'uid') else None,
        'email': qv if qk == 'email' else None,
    }
    prof = scan_all_tables_for_subject(keywords)
    if prof:
        # 写入前尝试按多特征在主表寻找候选并合并，避免重复创建
        ds = (prof.get('data_sources') or [None])
        candidate = _find_existing_profile_candidate(prof)
        if candidate:
            merged = _merge_profile(candidate, prof)
            if merged:
                merged['id'] = candidate.get('id')
                saved = upsert_profile(merged, source_table=ds[0] if ds else None)
            else:
                # 不可合并（如身份证冲突），直接返回候选
                saved = dict(candidate)
        else:
            saved = upsert_profile(prof, source_table=ds[0] if ds else None)
        return saved
    return None


def expand_search_profile(query_key: str, query_value: str) -> Optional[Dict[str, Any]]:
    """扩展搜索：手动触发，聚合跨表结果；若发现新数据则与主表合并更新。"""
    # 聚合跨表数据
    prof = scan_all_tables_for_subject({query_key: query_value})
    if not prof:
        return None

    # 若主表已有记录，先读取并与新数据合并，再写回
    existing = find_profile(query_key, query_value)
    merged = _merge_profile(existing, prof)
    if not merged:
        return None
    # 写回主表
    ds = (prof.get('data_sources') or [None])
    saved = upsert_profile(merged, source_table=ds[0] if ds else None)

    # 自动创建并维护配偶与亲属的关联记录
    spouse_name = saved.get('spouse_name')
    spouse_phone = saved.get('spouse_phone')
    if spouse_name or spouse_phone:
        spouse_profile = {
            'id_card': None,
            'name': spouse_name,
            'phones': ([{'type': '主要', 'number': spouse_phone}] if spouse_phone else []),
            'relatives_relations': [{'name': saved.get('name'), 'relation': '配偶'}]
        }
        update_bidirectional_relations(saved, spouse_profile)
        upsert_profile(spouse_profile)

    for rel in (saved.get('relatives_relations') or []):
        rname = rel.get('name')
        rphone = None
        for nm, ph in zip(saved.get('relatives_names') or [], saved.get('relatives_phones') or []):
            if nm == rname:
                rphone = ph
                break
        relative_profile = {
            'id_card': None,
            'name': rname,
            'phones': ([{'type': '主要', 'number': rphone}] if rphone else []),
            'relatives_relations': [{'name': saved.get('name'), 'relation': _reverse_relationship(rel.get('relation'), saved.get('gender'), None)}]
        }
        update_bidirectional_relations(saved, relative_profile)
        upsert_profile(relative_profile)

    return saved

def lookup_native_place_from_code(code: str) -> Optional[str]:
    """根据身份证前六位代码查找籍贯名称。"""
    if not code or not code.isdigit() or len(code) != 6:
        return None
    conn = get_db()
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT name FROM region_code_map WHERE code=%s", (code,))
            r = cur.fetchone()
            return r[0] if r else None
        except Exception:
            return None


def _infer_gender_from_id(id_card: str) -> Optional[str]:
    """从身份证号推断性别（奇数男，偶数女）。"""
    s = (id_card or '').strip()
    if len(s) == 18 and s[:-1].isdigit():
        try:
            num = int(s[16])
            return '男' if num % 2 == 1 else '女'
        except Exception:
            return None
    return None


def _infer_birth_from_id(id_card: str) -> Optional[str]:
    """从身份证号提取生日 YYYY-MM-DD。"""
    s = (id_card or '').strip()
    if len(s) == 18 and s[:-1].isdigit():
        y = s[6:10]
        m = s[10:12]
        d = s[12:14]
        try:
            yyyy = int(y); mm = int(m); dd = int(d)
            if 1 <= mm <= 12 and 1 <= dd <= 31:
                return f"{yyyy:04d}-{mm:02d}-{dd:02d}"
        except Exception:
            return None
    return None


# ---------------------------
# Relationships (bidirectional)
# ---------------------------

def _reverse_relationship(rel: str, subject_gender: Optional[str], other_gender: Optional[str]) -> str:
    rel = (rel or '').strip()
    if rel in ('配偶', '妻子', '丈夫'):
        return '配偶'
    if rel in ('父亲', '爸爸', '爹', '父亲(直系)'):
        return '儿子' if subject_gender == '男' else '女儿'
    if rel in ('母亲', '妈妈', '娘', '母亲(直系)'):
        return '儿子' if subject_gender == '男' else '女儿'
    if rel in ('儿子', '女儿', '孩子'):
        return '父亲' if other_gender == '男' else '母亲'
    if rel in ('兄弟', '哥哥', '弟弟'):
        return '兄弟' if subject_gender == '男' else '兄弟'
    if rel in ('姐妹', '姐姐', '妹妹'):
        return '姐妹'
    # 公婆/岳父母
    if rel in ('公公', '岳父'):
        return '儿媳' if subject_gender == '女' else '女婿'
    if rel in ('婆婆', '岳母'):
        return '儿媳' if subject_gender == '女' else '女婿'
    if rel in ('儿媳', '女婿'):
        return '公公/岳父' if other_gender == '男' else '婆婆/岳母'
    return rel or '亲属'


def update_bidirectional_relations(a: Dict[str, Any], b: Dict[str, Any]) -> None:
    """维护 A 与 B 的双向关系：
    - 配偶：仅写入双方的 spouse 字段，不写入 relatives_* 数组
    - 公婆/岳父母：根据 A 的父母关系与 A 的性别，为 B 增加相应直系亲属关系
    """
    # A 与 B 的配偶关系（不写入 relatives_*）
    if a.get('spouse_name') and (b.get('name') == a.get('spouse_name')):
        # 设置双方配偶字段
        a['spouse_name'] = b.get('name') or a.get('spouse_name')
        b['spouse_name'] = a.get('name') or b.get('spouse_name')
        # 互相回填配偶手机号（若缺失，取对方主号码）
        if not a.get('spouse_phone'):
            a_main_phone = None
            for p in (b.get('phones') or []):
                if isinstance(p, dict) and p.get('number'):
                    a_main_phone = _normalize_phone(p.get('number'))
                    break
                elif isinstance(p, str):
                    a_main_phone = _normalize_phone(p)
                    break
            if a_main_phone:
                a['spouse_phone'] = a_main_phone
        if not b.get('spouse_phone'):
            b_main_phone = None
            for p in (a.get('phones') or []):
                if isinstance(p, dict) and p.get('number'):
                    b_main_phone = _normalize_phone(p.get('number'))
                    break
                elif isinstance(p, str):
                    b_main_phone = _normalize_phone(p)
                    break
            if b_main_phone:
                b['spouse_phone'] = b_main_phone

    # 若 B 是配偶，则为 B 增加对应的公婆/岳父母
    a_gender = a.get('gender')
    if b.get('name') == a.get('spouse_name'):
        for name, rtype in zip(a.get('relatives_names') or [], a.get('relatives_types') or []):
            if rtype in ('父亲', '爸爸', '母亲', '妈妈'):
                if rtype in ('父亲', '爸爸'):
                    rev = '公公' if a_gender == '男' else '岳父'
                else:
                    rev = '婆婆' if a_gender == '男' else '岳母'
                b['relatives_names'] = _json_add_unique(b.get('relatives_names'), name)
                b['relatives_types'] = _json_add_unique(b.get('relatives_types'), rev)
                # 为 B 回填对应父母手机号（按 A 的亲属姓名匹配）
                rphone = None
                for nm, ph in zip(a.get('relatives_names') or [], a.get('relatives_phones') or []):
                    if nm == name:
                        rphone = ph
                        break
                if rphone:
                    b['relatives_phones'] = _json_add_unique(b.get('relatives_phones'), _normalize_phone(rphone))
                b['relatives_relations'] = _rel_add_relation(b.get('relatives_relations'), name, rev)

    # 若 B 是 A 的父母（C），且 A 有配偶，则为 C 增加对配偶的“儿媳/女婿”关系
    if a.get('spouse_name') and b.get('name') in (a.get('relatives_names') or []):
        # 通过 A 性别推断配偶性别：A 男→配偶 女（儿媳）；A 女→配偶 男（女婿）
        spouse_relation = '儿媳' if a_gender == '男' else '女婿' if a_gender == '女' else '儿媳/女婿'
        b['relatives_names'] = _json_add_unique(b.get('relatives_names'), a.get('spouse_name'))
        b['relatives_types'] = _json_add_unique(b.get('relatives_types'), spouse_relation)
        # 为 C 回填配偶（B）的手机号，优先使用 A 的 spouse_phone
        if a.get('spouse_phone'):
            b['relatives_phones'] = _json_add_unique(b.get('relatives_phones'), _normalize_phone(a.get('spouse_phone')))
        b['relatives_relations'] = _rel_add_relation(b.get('relatives_relations'), a.get('spouse_name'), spouse_relation)


# ---------------------------
# Compatibility helpers for API
# ---------------------------

def _map_profile_to_api_result(rec: Dict[str, Any]) -> Dict[str, Any]:
    """将单条 profile 记录映射为前端显示结构。"""
    phones = rec.get('phones') or []
    qqs = rec.get('qqs') or []
    # 标准化数据来源，确保包含中文名与日期
    raw_sources = rec.get('data_sources') or []
    formatted_sources: List[Dict[str, Any]] = []
    for s in raw_sources:
        if isinstance(s, dict):
            t = s.get('table') or s.get('source') or ''
            meta = get_data_source_meta([t]).get(t, {'chinese': (t.split('.')[-1] if t else None), 'date': None, 'count': None})
            d = meta.get('date')
            dstr = d if isinstance(d, str) else (d.isoformat() if isinstance(d, (datetime, date)) else None)
            formatted_sources.append({'table': t, 'chinese': meta.get('chinese'), 'date': dstr, 'count': meta.get('count')})
        elif isinstance(s, str):
            t = s
            meta = get_data_source_meta([t]).get(t, {'chinese': t.split('.')[-1], 'date': None, 'count': None})
            d = meta.get('date')
            dstr = d if isinstance(d, str) else (d.isoformat() if isinstance(d, (datetime, date)) else None)
            formatted_sources.append({'table': t, 'chinese': meta.get('chinese'), 'date': dstr, 'count': meta.get('count')})
    # 关系字段：优先从对象数组 relatives_relations 取第一个 relation，其次回退到 relatives_types
    rel_obj_list = rec.get('relatives_relations') or []
    spouse_words = {'配偶', '妻子', '丈夫'}
    rel_value = None
    rel_name_for_api = None
    rel_phone_for_api = None
    # 优先选择非配偶的关系
    for r in rel_obj_list:
        if isinstance(r, dict) and r.get('relation') and r.get('relation') not in spouse_words:
            rel_value = r.get('relation')
            rel_name_for_api = r.get('name')
            break
    # 根据选中的姓名匹配对应手机号
    if rel_name_for_api:
        for nm, ph in zip(rec.get('relatives_names') or [], rec.get('relatives_phones') or []):
            if nm == rel_name_for_api:
                rel_phone_for_api = ph
                break

    # 生日统一为字符串，避免 JSON 序列化问题
    _bd = rec.get('birth_date')
    if isinstance(_bd, (datetime, date)):
        bd_str = _bd.isoformat()
    else:
        bd_str = _bd if (_bd is None or isinstance(_bd, str)) else str(_bd)

    return {
        'id': rec.get('id'),
        'name': rec.get('name'),
        'gender': rec.get('gender'),
        'native_place': rec.get('native_place'),
        'birth_date': bd_str,
        'phones': phones,
        'phone': phones[0] if phones else None,
        'emails': rec.get('emails'),
        'email': (rec.get('emails') or [None])[0],
        'qqs': qqs,
        'qq': qqs[0] if qqs else None,
        'weibo_uids': rec.get('weibo_uids'),
        'weibo_uid': (rec.get('weibo_uids') or [None])[0],
        'id_card': rec.get('id_card'),
        'company': rec.get('company'),
        'position': rec.get('position'),
        'address': None,
        'spouse_name': rec.get('spouse_name'),
        'spouse_phone': rec.get('spouse_phone'),
        'relative_name': rel_name_for_api if rel_name_for_api is not None else (rec.get('relatives_names') or [None])[0],
        'relative_phone': rel_phone_for_api if rel_phone_for_api is not None else (rec.get('relatives_phones') or [None])[0],
        'relationship': rel_value if rel_value is not None else (([t for t in (rec.get('relatives_types') or []) if t not in spouse_words] or [None])[0]),
        'ai_confidence': rec.get('ai_confidence'),
        'formatted_data_sources': formatted_sources
    }


def _find_profiles_from_main_table(query_key: str, query_value: str, limit: int = 50) -> List[Dict[str, Any]]:
    """直接在主表按身份证号唯一聚合，返回可能多条记录（如重名）。"""
    conn = get_db()
    qk = query_key.lower()
    qv = (query_value or '').strip()
    if qk == 'phone':
        qv = _normalize_phone(qv) or qv

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if qk == 'id':
            cur.execute("SELECT * FROM profile WHERE id=%s LIMIT %s", (qv, limit))
        elif qk == 'id_card':
            cur.execute("SELECT * FROM profile WHERE id_card=%s LIMIT %s", (qv, limit))
        elif qk == 'phone':
            qv86 = f"86{qv}"
            cur.execute(
                """
                SELECT * FROM profile
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements(phones) AS p
                    WHERE p->>'number'=%s OR p->>'number'=%s
                )
                OR EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(phones) AS t
                    WHERE regexp_replace(t, '[^0-9]', '', 'g')=%s OR regexp_replace(t, '[^0-9]', '', 'g')=%s
                )
                OR regexp_replace(COALESCE(spouse_phone,''), '[^0-9]', '', 'g')=%s OR regexp_replace(COALESCE(spouse_phone,''), '[^0-9]', '', 'g')=%s
                OR EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(relatives_phones) AS rp
                    WHERE regexp_replace(rp, '[^0-9]', '', 'g')=%s OR regexp_replace(rp, '[^0-9]', '', 'g')=%s
                )
                LIMIT %s
                """,
                (qv, qv86, qv, qv86, qv, qv86, qv, qv86, limit)
            )
        elif qk == 'qq':
            cur.execute(
                """
                SELECT * FROM profile
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements(qqs) AS q WHERE q->>'qq'=%s
                )
                OR EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(qqs) AS q WHERE q=%s
                )
                LIMIT %s
                """,
                (qv, qv, limit)
            )
        elif qk == 'email':
            # 邮箱大小写不敏感匹配
            cur.execute(
                """
                SELECT * FROM profile
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(emails) AS e WHERE LOWER(e)=LOWER(%s)
                )
                LIMIT %s
                """,
                (qv, limit)
            )
        elif qk in ('weibo', 'weibo_uid', 'uid'):
            cur.execute(
                """
                SELECT * FROM profile
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(weibo_uids) AS u WHERE u=%s
                )
                LIMIT %s
                """,
                (qv, limit)
            )
        else:
            # 使用 TRIM 等值匹配，避免姓名存在前后空格导致的漏查
            cur.execute("SELECT * FROM profile WHERE LOWER(TRIM(name))=LOWER(%s) LIMIT %s", (qv, limit))

        return [dict(r) for r in (cur.fetchall() or [])]


def find_customer_info(query_key: str, query_value: str, limit: int = 50) -> List[Dict[str, Any]]:
    """返回搜索结果，支持多条记录（如重名或多号映射）。优先按主键 id 查询。"""
    # 先直接从主表找可能多条匹配
    recs = _find_profiles_from_main_table(query_key, query_value, limit)
    if not recs:
        # 若主表没有任何匹配：
        # - 姓名查询：跨表扫描并按身份证号生成多条主表记录
        # - 其他查询：沿用单条聚合逻辑
        qkl = query_key.lower()
        if qkl == 'name':
            profs = scan_all_tables_for_subject_multi({'name': query_value})
            for p in profs:
                ds = (p.get('data_sources') or [None])
                candidate = _find_existing_profile_candidate(p)
                if candidate:
                    merged = _merge_profile(candidate, p)
                    if merged:
                        merged['id'] = candidate.get('id')
                        upsert_profile(merged, source_table=ds[0] if ds else None)
                    else:
                        # 身份证冲突则跳过合并，避免误写
                        pass
                else:
                    upsert_profile(p, source_table=ds[0] if ds else None)
            recs = _find_profiles_from_main_table(query_key, query_value, limit)
        elif qkl == 'general':
            # 自由文本扫描：跨所有列做 LIKE 聚合
            prof = scan_all_tables_for_subject({'general': query_value})
            if prof:
                ds = (prof.get('data_sources') or [None])
                candidate = _find_existing_profile_candidate(prof)
                if candidate:
                    merged = _merge_profile(candidate, prof)
                    if merged:
                        merged['id'] = candidate.get('id')
                        saved = upsert_profile(merged, source_table=ds[0] if ds else None)
                    else:
                        saved = dict(candidate)
                else:
                    saved = upsert_profile(prof, source_table=ds[0] if ds else None)
                # 直接返回写入后的主表记录（含生成的唯一 id）
                recs = [saved]
        else:
            prof = scan_all_tables_for_subject({query_key: query_value})
            if prof:
                ds = (prof.get('data_sources') or [None])
                candidate = _find_existing_profile_candidate(prof)
                if candidate:
                    merged = _merge_profile(candidate, prof)
                    if merged:
                        merged['id'] = candidate.get('id')
                        saved = upsert_profile(merged, source_table=ds[0] if ds else None)
                    else:
                        saved = dict(candidate)
                else:
                    saved = upsert_profile(prof, source_table=ds[0] if ds else None)
                recs = [saved]
            else:
                # 后备：手机号查询无命中时，尝试写入基础档案（含归属地）
                qkl_norm = query_key.lower()
                if qkl_norm == 'phone':
                    try:
                        norm = _normalize_phone(query_value)
                        # 仅处理合法的中国手机号（11位且以1开头）
                        if norm and len(norm) == 11 and norm.startswith('1'):
                            # 延迟导入，避免模块加载循环
                            from app.services.validation_service import fetch_phone_attribution
                            attr = fetch_phone_attribution(norm) or {}
                            base_profile = {
                                'id_card': None,
                                'name': None,
                                'phones': [{
                                    'type': '其他',
                                    'number': norm,
                                    'attribution': {
                                        'province': attr.get('province'),
                                        'city': attr.get('city'),
                                        'carrier': attr.get('carrier'),
                                        'area_code': attr.get('area_code'),
                                        'postcode': attr.get('postcode'),
                                    }
                                }],
                                'data_sources': ['validation.phone_attribution']
                            }
                            candidate = _find_existing_profile_candidate(base_profile)
                            if candidate:
                                merged = _merge_profile(candidate, base_profile)
                                if merged:
                                    merged['id'] = candidate.get('id')
                                    saved = upsert_profile(merged, source_table='validation.phone_attribution')
                                else:
                                    saved = dict(candidate)
                            else:
                                saved = upsert_profile(base_profile, source_table='validation.phone_attribution')
                            recs = [saved]
                    except Exception:
                        # 若外部查询失败或不可用则保持空结果
                        pass

    return [_map_profile_to_api_result(r) for r in recs][:limit]


def add_customer_info(customer_data: Dict[str, Any], _unused: Any) -> Dict[str, Any]:
    return upsert_profile(customer_data)


def check_database_health() -> Dict[str, Any]:
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM profile")
            total = cur.fetchone()[0]
        return {
            'status': 'healthy',
            'engine': 'postgresql',
            'profile_rows': total
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


# ---------------------------
# Additional compatibility endpoints for existing API
# ---------------------------

def update_customer_info(customer_id: str, update_data: Dict[str, Any], _unused: Any = None) -> Dict[str, Any]:
    """更新 profile 表中指定 id 的记录。
    仅允许更新主表字段，不涉及源表。返回更新后的完整记录。
    """
    if not customer_id:
        raise ValidationError("id is required")
    conn = get_db()

    # 允许更新的字段
    fields = {
        'name': update_data.get('name'),
        'gender': update_data.get('gender'),
        'native_place': update_data.get('native_place'),
        'birth_date': update_data.get('birth_date'),
        'phones': update_data.get('phones'),
        'emails': update_data.get('emails'),
        'qqs': update_data.get('qqs'),
        'weibo_uids': update_data.get('weibo_uids'),
        'company': update_data.get('company'),
        'position': update_data.get('position'),
        'spouse_name': update_data.get('spouse_name'),
        'spouse_phone': update_data.get('spouse_phone'),
        'relatives_names': update_data.get('relatives_names'),
        'relatives_phones': update_data.get('relatives_phones'),
        'relatives_types': update_data.get('relatives_types'),
        'data_sources': update_data.get('data_sources'),
        'ai_confidence': update_data.get('ai_confidence'),
    }

    # 规范化
    if fields['phones'] is not None:
        # 兼容两种形态：
        # 1) 纯字符串数组 -> 规范化为11位手机号字符串
        # 2) 对象数组（包含 number 或中文键“手机号”）-> 保留对象结构，仅规范化内部号码
        normalized_phones = []
        for p in (fields['phones'] or []):
            if isinstance(p, dict):
                obj = dict(p)
                # 仅规范化并保持标准键 number；不写中文冗余键
                num = obj.get('number') or obj.get('手机号')
                norm = _normalize_phone(num) if num is not None else None
                if norm:
                    obj['number'] = norm
                # 如果 attribution 存在，原样保留
                normalized_phones.append(obj)
            else:
                norm = _normalize_phone(p)
                if norm:
                    normalized_phones.append(norm)
        fields['phones'] = normalized_phones
    if fields['emails'] is not None:
        fields['emails'] = [e.strip() for e in (fields['emails'] or []) if e]
    if fields['qqs'] is not None:
        normalized_qqs: List[Dict[str, Any]] = []
        for q in (fields['qqs'] or []):
            if isinstance(q, dict):
                obj = dict(q)
                num = obj.get('qq') or obj.get('number')
                norm = _normalize_qq(num) if num is not None else None
                if norm:
                    obj['qq'] = norm
                    obj.pop('number', None)
                    normalized_qqs.append(obj)
            else:
                norm = _normalize_qq(q)
                if norm:
                    normalized_qqs.append({'qq': norm})
        fields['qqs'] = normalized_qqs
    if fields['weibo_uids'] is not None:
        fields['weibo_uids'] = [str(u).strip() for u in (fields['weibo_uids'] or []) if u]
    if fields['spouse_phone'] is not None:
        fields['spouse_phone'] = _normalize_phone(fields['spouse_phone'])
    if fields['relatives_phones'] is not None:
        fields['relatives_phones'] = [p for p in map(_normalize_phone, fields['relatives_phones'] or []) if p]
    if fields['relatives_names'] is not None:
        fields['relatives_names'] = [n.strip() for n in (fields['relatives_names'] or []) if n]
    if fields['relatives_types'] is not None:
        fields['relatives_types'] = [t.strip() for t in (fields['relatives_types'] or []) if t]

    sets = []
    params = []
    for k, v in fields.items():
        if v is None:
            continue
        if k in ('phones','emails','qqs','weibo_uids','relatives_names','relatives_phones','relatives_types','data_sources','ai_confidence'):
            sets.append(f"{k}=%s")
            params.append(Json(v))
        else:
            sets.append(f"{k}=%s")
            params.append(v)

    if not sets:
        # 无更新内容，返回原记录
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM profile WHERE id_card=%s", (customer_id,))
            rec = cur.fetchone()
            if not rec:
                raise ValidationError("record not found")
            return dict(rec)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        sql = "UPDATE profile SET " + ", ".join(sets) + " WHERE id=%s RETURNING *"
        params.append(customer_id)
        cur.execute(sql, params)
        rec = cur.fetchone()
        if not rec:
            raise ValidationError("record not found")
        return dict(rec)


def delete_customer_info(customer_id: str, _unused: Any = None) -> Dict[str, Any]:
    """删除指定 id 的主表记录。"""
    if not customer_id:
        raise ValidationError("id is required")
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM profile WHERE id=%s", (customer_id,))
        deleted = cur.rowcount
    return {"deleted": deleted}


def fetch_source_detail(table: str, subject: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
    """查询指定源表的详情，按照 subject 进行模糊匹配。"""
    if not table:
        raise ValidationError("table is required")
    conn = get_db()
    # 解析 schema.table
    if '.' in table:
        schema, tname = table.split('.', 1)
    else:
        schema, tname = 'public', table

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 为当前会话设置语句超时，避免慢表阻塞（来源详情单表查询适当提高超时）
        try:
            cur.execute(f"SET statement_timeout = {SOURCE_DETAIL_STATEMENT_TIMEOUT_MS}")
        except Exception:
            pass
        # 获取列
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            """,
            (schema, tname)
        )
        cols = [r['column_name'] for r in (cur.fetchall() or [])]
        if not cols:
            return []

        where: List[str] = []
        params: List[Any] = []

        # 动态别名：优先在相关列上精确匹配以提升命中与性能
        phone_aliases = _get_aliases('phone', ['phone', 'PHONE', '手机号', '手机', '电话'])
        spouse_phone_aliases = _get_aliases('spouse_phone', ['spouse_phone', '配偶手机号'])
        relatives_phone_aliases = _get_aliases('relatives_phones', ['直系亲属手机号', '亲属手机号', '直属手机号'])
        id_aliases = _get_aliases('id_card', ['id_card', 'ID_CARD', '身份证', '身份证号'])
        name_aliases = _get_aliases('name', ['name', 'NAME', '姓名', '名字'])
        weibo_aliases = _get_aliases('weibo_uid', ['weibo_uid', 'WEIBO_UID', 'uid', 'UID'])
        email_aliases = _get_aliases('email', ['email', 'EMAIL', '邮箱', '电子邮件'])
        qq_aliases: List[str] = ['qq', 'QQ']

        def _match_cols(all_cols: List[str], patterns: List[str]) -> List[str]:
            matched = [c for c in all_cols if any(p == c for p in patterns)]
            if not matched:
                lp = [p.lower() for p in patterns]
                matched = [c for c in all_cols if any(l in c.lower() for l in lp)]
            return matched

        # 统一将数组参数展开
        expanded_subject: Dict[str, List[str]] = {}
        for sk, sv in subject.items():
            if sv is None:
                continue
            if isinstance(sv, list):
                expanded_subject[sk] = [str(v).strip() for v in sv if str(v or '').strip()]
            else:
                s = str(sv or '').strip()
                if s:
                    expanded_subject[sk] = [s]

        # 精准匹配优先，按键构造条件
        for sk, vals in expanded_subject.items():
            for s in vals:
                if not s:
                    continue
                if sk in ('phone', 'phones'):
                    patterns = list(set(phone_aliases + spouse_phone_aliases + relatives_phone_aliases))
                    matched_cols = _match_cols(cols, patterns)
                    norm = _normalize_phone(s)
                    if norm and matched_cols:
                        # 先尝试索引友好的等值查询（避免触发正则导致的全表扫描）。
                        eq_where: List[str] = []
                        eq_params: List[Any] = []
                        for col in matched_cols:
                            eq_where.append(f"CAST({col} AS TEXT) = %s")
                            eq_params.append(norm)
                            eq_where.append(f"CAST({col} AS TEXT) = %s")
                            eq_params.append(f"86{norm}")
                        eq_sql = f"SELECT * FROM {schema}.{tname} WHERE " + " OR ".join(eq_where) + " LIMIT %s"
                        eq_params.append(limit)
                        try:
                            cur.execute("SET LOCAL statement_timeout = 5000")
                        except Exception:
                            pass
                        try:
                            cur.execute(eq_sql, eq_params)
                            eq_rows = cur.fetchall() or []
                            if eq_rows:
                                return [dict(r) for r in eq_rows]
                        except Exception:
                            # 等值查询失败则继续回退到正则/LIKE
                            pass

                        # 优先依据索引是否存在来决定是否回退到正则（有 phone 的 btree 索引时避免正则）
                        has_phone_bt_index = False
                        try:
                            cur.execute(
                                """
                                SELECT 1 FROM pg_indexes
                                WHERE schemaname=%s AND tablename=%s
                                  AND (
                                    indexdef LIKE '%%USING btree (phone%%' OR
                                    indexdef LIKE '%%USING btree (qq, phone%%'
                                  )
                                LIMIT 1
                                """,
                                (schema, tname),
                            )
                            has_phone_bt_index = (cur.fetchone() is not None)
                        except Exception:
                            has_phone_bt_index = False

                        allow_regex_fallback = not has_phone_bt_index
                        if allow_regex_fallback:
                            # 次要判断：如果能读取到估算行数且非常大，也避免正则
                            try:
                                cur.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = %s::regclass", (f"{schema}.{tname}",))
                                rr = cur.fetchone()
                                if rr and rr[0] and rr[0] > 5000000:
                                    allow_regex_fallback = False
                            except Exception:
                                pass

                        if allow_regex_fallback:
                            for col in matched_cols:
                                where.append(f"regexp_replace(CAST({col} AS TEXT), '[^0-9]', '', 'g') = %s")
                                params.append(norm)
                                where.append(f"regexp_replace(CAST({col} AS TEXT), '[^0-9]', '', 'g') = %s")
                                params.append(f"86{norm}")
                        else:
                            # 超大表不再添加正则条件，避免超时；保持 where 为空以返回空结果或继续匹配其他键。
                            pass
                    else:
                        # 回退：在所有列做 LIKE
                        for col in cols:
                            where.append(f"LOWER(CAST({col} AS TEXT)) LIKE LOWER(%s)")
                            params.append(f"%{s}%")
                elif sk == 'id_card':
                    matched_cols = _match_cols(cols, id_aliases)
                    if matched_cols:
                        for col in matched_cols:
                            where.append(f"CAST({col} AS TEXT) = %s")
                            params.append(s)
                    else:
                        for col in cols:
                            where.append(f"LOWER(CAST({col} AS TEXT)) LIKE LOWER(%s)")
                            params.append(f"%{s}%")
                elif sk in ('qq', 'qqs'):
                    matched_cols = _match_cols(cols, qq_aliases)
                    if matched_cols:
                        for col in matched_cols:
                            where.append(f"CAST({col} AS TEXT) = %s")
                            params.append(s)
                    else:
                        for col in cols:
                            where.append(f"LOWER(CAST({col} AS TEXT)) LIKE LOWER(%s)")
                            params.append(f"%{s}%")
                elif sk in ('weibo_uid',):
                    matched_cols = _match_cols(cols, weibo_aliases)
                    if matched_cols:
                        for col in matched_cols:
                            where.append(f"CAST({col} AS TEXT) = %s")
                            params.append(s)
                    else:
                        for col in cols:
                            where.append(f"LOWER(CAST({col} AS TEXT)) LIKE LOWER(%s)")
                            params.append(f"%{s}%")
                elif sk in ('email', 'name'):
                    patterns = email_aliases if sk == 'email' else name_aliases
                    matched_cols = _match_cols(cols, patterns)
                    target_cols = matched_cols if matched_cols else cols
                    for col in target_cols:
                        where.append(f"LOWER(CAST({col} AS TEXT)) LIKE LOWER(%s)")
                        params.append(f"%{s}%")
                else:
                    # 其他键统一回退到模糊匹配
                    for col in cols:
                        where.append(f"LOWER(CAST({col} AS TEXT)) LIKE LOWER(%s)")
                        params.append(f"%{s}%")

        # 若没有任何过滤条件，不返回任意记录，直接空结果（避免大表无条件 LIMIT 扫描）
        if not where:
            return []

        sql = f"SELECT * FROM {schema}.{tname} WHERE " + " OR ".join(where) + " LIMIT %s"
        params.append(limit)
        try:
            cur.execute(sql, params)
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]
        except Exception as e:
            try:
                logger.error(f"fetch_source_detail failed for {schema}.{tname}: {e}; sql={sql}; params={params}")
            except Exception:
                pass
            raise DatabaseError(f"Failed to query source table {schema}.{tname}: {e}")


_DATA_SOURCE_META_CACHE: Dict[str, Dict[str, Any]] = {}
_DATA_SOURCE_CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}

def _load_data_source_config() -> Dict[str, Dict[str, Any]]:
    """加载 config/data_source.json 并缓存，返回 {table_without_schema: {name, date}}。

    - 若文件不存在或解析失败，返回空字典。
    - 仅在首次调用时读取磁盘，随后走内存缓存。
    """
    global _DATA_SOURCE_CONFIG_CACHE
    if _DATA_SOURCE_CONFIG_CACHE:
        return _DATA_SOURCE_CONFIG_CACHE
    try:
        base_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../'))
        cfg_path = os.path.join(base_dir, 'config', 'data_source.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
            # 规范化为 {key: {name, date}}
            if isinstance(data, dict):
                _DATA_SOURCE_CONFIG_CACHE = {str(k): (v if isinstance(v, dict) else {}) for k, v in data.items()}
            else:
                _DATA_SOURCE_CONFIG_CACHE = {}
    except Exception:
        _DATA_SOURCE_CONFIG_CACHE = {}
    return _DATA_SOURCE_CONFIG_CACHE

def _sync_data_source_config_with_db_tables(full_table_names: List[str]) -> None:
    """将数据库中检测到的表同步到 config/data_source.json：

    - 对于配置中不存在的表（按不含schema的短名），新增条目：
      { "name": 中文名或短表名, "date": 日期或 None }
    - 中文名与日期优先取自 `public.data_source` 表；不可用则回退。
    - 不覆盖已有条目，确保用户可手动维护。
    """
    try:
        if not full_table_names:
            return
        cfg = _load_data_source_config()
        # 预取数据库元信息（按完整表名）
        metas = get_data_source_meta(full_table_names)
        updated = False
        for ft in full_table_names:
            short = ft.split('.')[-1]
            if short not in cfg:
                m = metas.get(ft) or {}
                cfg[short] = {
                    'name': (m.get('chinese') or short),
                    'date': m.get('date')
                }
                updated = True
        if updated:
            # 写回文件（原子性：先写临时文件再替换）
            base_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../'))
            cfg_path = os.path.join(base_dir, 'config', 'data_source.json')
            tmp_path = cfg_path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=4)
            os.replace(tmp_path, cfg_path)
            # 刷新内存缓存
            global _DATA_SOURCE_CONFIG_CACHE
            _DATA_SOURCE_CONFIG_CACHE = cfg
    except Exception:
        # 任何异常均不影响主流程
        pass

def get_data_source_meta(tables: List[str]) -> Dict[str, Dict[str, Any]]:
    """返回数据来源元信息 {table: {chinese, date, count}}，优先使用配置文件。

    - 参数 `tables` 使用完整表名（如 `public.loans_80384`）。
    - 优先从 `config/data_source.json` 读取中文名与日期（key 为不含 schema 的表名）。
    - 其次尝试查询 `public.data_source` 表以补充缺失信息与记录数。
    - 返回中的 `date` 为字符串（通常为 `YYYY-MM-DD`）。
    """
    result: Dict[str, Dict[str, Any]] = {}
    req = [str(t) for t in (tables or [])]
    missing = [t for t in req if t not in _DATA_SOURCE_META_CACHE]

    # 先加载配置文件，尽可能填充中文名与日期
    if missing:
        cfg = _load_data_source_config()
        for t in list(missing):
            short = t.split('.')[-1]
            cfg_entry = cfg.get(short)
            if cfg_entry:
                _DATA_SOURCE_META_CACHE[t] = {
                    'chinese': cfg_entry.get('name') or short,
                    'date': cfg_entry.get('date'),
                    'count': None
                }
        # 更新缺失列表，仅留下尚未通过配置填充的项
        missing = [t for t in req if t not in _DATA_SOURCE_META_CACHE]

    if missing:
        conn = get_db()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # 使用 ANY 数组匹配，避免构造长 IN 列表
                cur.execute(
                    'SELECT tables, date, "Chinese" FROM public.data_source WHERE tables = ANY(%s)',
                    (missing,)
                )
                rows: List[Dict[str, Any]] = cur.fetchall() or []
                for r in rows:
                    key = str(r.get('tables'))
                    dt = r.get('date')
                    if isinstance(dt, (datetime, date)):
                        dstr = dt.isoformat()
                    else:
                        dstr = str(dt) if dt else None
                    # 计算来源表的行数（缓存一次即可）
                    count_val: Optional[int] = None
                    try:
                        # 仅当表名合法时才执行计数
                        if key and '.' in key:
                            schema, tname = key.split('.', 1)
                            cur.execute(f'SELECT COUNT(*) FROM {schema}.{tname}')
                            _c = cur.fetchone()
                            count_val = int(_c[0]) if _c and _c[0] is not None else None
                    except Exception:
                        # 计数失败则忽略，不影响其他元信息
                        count_val = None
                    # 合并：若已从配置写入中文/日期，保留配置优先；否则使用数据库值
                    existing = _DATA_SOURCE_META_CACHE.get(key)
                    if existing:
                        _DATA_SOURCE_META_CACHE[key] = {
                            'chinese': existing.get('chinese') or r.get('Chinese') or key.split('.')[-1],
                            'date': existing.get('date') or dstr,
                            'count': count_val if count_val is not None else existing.get('count')
                        }
                    else:
                        _DATA_SOURCE_META_CACHE[key] = {
                            'chinese': r.get('Chinese') or key.split('.')[-1],
                            'date': dstr,
                            'count': count_val
                        }
            except Exception:
                # 如果 data_source 表不存在或查询失败，继续使用降级信息
                for t in missing:
                    _DATA_SOURCE_META_CACHE.setdefault(
                        t,
                        {'chinese': t.split('.')[-1], 'date': None, 'count': None}
                    )

    for t in req:
        if t in _DATA_SOURCE_META_CACHE:
            result[t] = _DATA_SOURCE_META_CACHE[t]
        else:
            result[t] = {'chinese': t.split('.')[-1], 'date': None, 'count': None}
    return result
def get_schema_columns_cached(ttl_secs: int = 3600, refresh: bool = False, limit: Optional[int] = None) -> Dict[str, List[str]]:
    """获取列枚举，支持内存缓存与文件回退。

    - 优先尝试数据库实时枚举，失败则回退到本地文件
    - 使用内存缓存减少重复调用，可通过 refresh 强制刷新
    - 可选 limit 限制返回的表数量
    """
    now = time.time()
    if (not refresh) and _SCHEMA_CACHE.get('columns_by_table') and (now - float(_SCHEMA_CACHE.get('timestamp') or 0)) < float(ttl_secs):
        data = _SCHEMA_CACHE['columns_by_table']
        # 应用 limit（若提供）
        if limit is not None:
            keys = list(data.keys())[: int(limit)]
            return {k: data[k] for k in keys}
        return data
    # 尝试数据库枚举
    data: Dict[str, List[str]] = {}
    try:
        data = list_all_table_columns(limit=limit)
    except Exception:
        # 数据库不可用时返回空结构
        data = {}
        if limit is not None:
            data = {}
    # 写入内存缓存（不再写入文件）
    _SCHEMA_CACHE['timestamp'] = now
    _SCHEMA_CACHE['columns_by_table'] = data
    # 刷新动态别名
    try:
        global _DYNAMIC_ALIASES
        _DYNAMIC_ALIASES = _build_dynamic_aliases(data)
    except Exception:
        pass
    # 同步新表到配置文件，方便用户手动维护中文与日期
    try:
        _sync_data_source_config_with_db_tables(list(data.keys()))
    except Exception:
        pass
    return data

def get_aliases_map() -> Dict[str, List[str]]:
    """返回当前动态别名映射（含默认别名并去重排序）。"""
    _ensure_dynamic_aliases_loaded()
    result: Dict[str, List[str]] = {}
    for k in SCHEMA_ALIAS_PATTERNS.keys():
        result[k] = _get_aliases(k, [])
    return result