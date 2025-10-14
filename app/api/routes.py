from flask import Blueprint, request
import logging
from typing import Any, Dict

# 创建蓝图
api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)

# 导入数据库相关服务
from app.models.database import (
    get_db, find_customer_info,
    add_customer_info, update_customer_info, delete_customer_info,
    DatabaseError, ValidationError, check_database_health,
    fetch_source_detail, get_data_source_meta, get_schema_columns_cached, get_aliases_map,
    expand_search_profile, find_profile, lookup_native_place_from_code
)
from app.utils.utils import parse_comma_list, normalize_profile_for_api
from app.services.ai_service import ai_service, AIServiceError
from app.services.validation_service import fetch_phone_attribution, fetch_qq_profile, validate_id_structure, ValidationServiceError, fetch_weibo_profile
from app.api.response import success, error_response

# 搜索客户信息
@api_bp.route('/search', methods=['GET'])
def search_customer():
    try:
        query_value = request.args.get('query', '').strip()
        # 分页与排序
        page = max(int(request.args.get('page', '1') or '1'), 1)
        page_size = max(int(request.args.get('page_size', request.args.get('max_results', '50')) or '50'), 1)
        sort_key = (request.args.get('sort') or '').strip().lower()
        sort_order = (request.args.get('order', 'asc') or 'asc').strip().lower()
        max_results = page * page_size
        expand_flag = (request.args.get('expand', '0') or '0').strip().lower() in ('1','true','yes')
        if not query_value:
            return error_response("Bad Request", "Query parameter is required", 400)

        # 根据查询值自动识别查询字段
        def _detect_query_key(val: str) -> str:
            import re
            s = val.strip()
            # 识别微博UID：URL模式 https://weibo.com/u/<uid>
            m = re.search(r"https?://weibo\.com/u/(\d{5,20})", s)
            if m:
                return 'weibo_uid'
            # 先身份证（18位，末尾可X）
            if re.fullmatch(r"\d{17}[\dXx]", s):
                return 'id_card'
            # 归一化数字，兼容+86/空格/短横线/括号等
            digits = re.sub(r"\D", "", s)
            # 86前缀手机号
            if len(digits) >= 12 and digits.startswith('86'):
                digits_norm = digits[-11:]
            else:
                digits_norm = digits
            # 中国手机号（11位且1开头）
            if re.fullmatch(r"1\d{10}", digits_norm or ''):
                return 'phone'
            # Email（简单验证）
            if re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", s):
                return 'email'
            # QQ：5-12位纯数字（避免误把非11位数字当手机号）
            if re.fullmatch(r"\d{5,12}", digits or ''):
                return 'qq'
            return 'name'

        # 支持查询模式覆盖（如自由文本扫描）
        mode = (request.args.get('mode') or '').strip().lower()
        if mode in ('general', 'text', 'free'):
            qk = 'general'
        else:
            qk = _detect_query_key(query_value)
            # 若为微博URL，规范化查询值为UID
            if qk == 'weibo_uid':
                import re
                m = re.search(r"https?://weibo\.com/u/(\d{5,20})", query_value)
                if m:
                    query_value = m.group(1)
        raw_results = find_customer_info(qk, query_value, max_results)

        # 可选扩展：若已有主表命中，则按 id_card 触发跨表聚合并写回，再读取最新结果
        if expand_flag and raw_results:
            try:
                for r in raw_results:
                    rid = (r.get('id_card') or '').strip()
                    if rid:
                        expand_search_profile('id_card', rid)
                raw_results = find_customer_info(qk, query_value, max_results)
            except Exception as e:
                logger.warning(f"扩展搜索失败，回退到原结果: {e}")

        results = [normalize_profile_for_api(r) for r in raw_results]
        # 排序（允许按 name / id_card / birth_date / company）
        if sort_key in ('name','id_card','birth_date','company'):
            results.sort(key=lambda r: (str(r.get(sort_key) or '').lower()))
            if sort_order == 'desc':
                results.reverse()
        # 分页切片
        start = (page - 1) * page_size
        end = start + page_size
        page_items = results[start:end]
        return success(page_items, from_cache=False, results=page_items, page=page, page_size=page_size, total=len(results))
    except ValidationError as e:
        return error_response("Validation Error", str(e), 400)
    except DatabaseError:
        # 数据库不可用或慢时返回503，避免在成功结构中夹带错误细节
        return error_response("Service Unavailable", "Database temporarily unavailable or slow.", 503)
    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        return error_response("Internal Server Error", "Failed to search customer information", 500)

# 添加客户
@api_bp.route('/customer', methods=['POST'])
def add_customer():
    try:
        customer_data = request.get_json()
        if not customer_data:
            return error_response("Bad Request", "Request body is required", 400)
        # 直接写入主表
        result = add_customer_info(customer_data, None)
        # 输出唯一标识 id（若不存在则回退到 id_card）
        rid = result.get('id') or result.get('id_card')
        if rid:
            result['id'] = rid
        return success(result, status=201)
    except ValidationError as e:
        return error_response("Validation Error", str(e), 400)
    except DatabaseError:
        # 后端存储不可用或过慢，统一返回503
        return error_response("Service Unavailable", "Database temporarily unavailable or slow.", 503)
    except Exception as e:
        logger.error(f"添加客户失败: {e}")
        return error_response("Internal Server Error", "Failed to add customer information", 500)

# 更新客户
@api_bp.route('/customer/<customer_id>', methods=['PUT'])
def update_customer(customer_id: str):
    try:
        update_data = request.get_json()
        if not update_data:
            return error_response("Bad Request", "Request body is required", 400)
        # 以 id 为唯一键更新
        result = update_customer_info(customer_id, update_data, None)
        # 输出唯一标识 id（若不存在则回退到 id_card）
        rid = result.get('id') or result.get('id_card')
        if rid:
            result['id'] = rid
        return success(result)
    except ValidationError as e:
        return error_response("Validation Error", str(e), 400)
    except DatabaseError:
        return error_response("Service Unavailable", "Database temporarily unavailable or slow.", 503)
    except Exception as e:
        logger.error(f"更新客户失败: {e}")
        return error_response("Internal Server Error", "Failed to update customer information", 500)

# 删除客户
@api_bp.route('/customer/<customer_id>', methods=['DELETE'])
def delete_customer(customer_id: str):
    try:
        # 以 id 为唯一键删除
        result = delete_customer_info(customer_id, None)
        return success(result)
    except ValidationError as e:
        return error_response("Validation Error", str(e), 400)
    except DatabaseError:
        return error_response("Service Unavailable", "Database temporarily unavailable or slow.", 503)
    except Exception as e:
        logger.error(f"删除客户失败: {e}")
        return error_response("Internal Server Error", "Failed to delete customer information", 500)

# 指标接口（AI disabled / 分析 removed）
@api_bp.route('/metrics', methods=['GET'])
def get_metrics():
    try:
        db_health = check_database_health()
        metrics = {
            "cache": {"status": "removed"},
            "database": db_health,
            "api": {"endpoints": {"search": "active", "customer": "active", "analyze": "removed", "ai": "disabled"}}
        }
        return success(metrics)
    except Exception as e:
        logger.error(f"获取指标失败: {e}")
        return error_response("Internal Server Error", "Failed to get metrics", 500)

# 来源详情查询
@api_bp.route('/source_detail', methods=['GET'])
def source_detail():
    try:
        table = (request.args.get('table') or '').strip()
        if not table:
            return error_response("Bad Request", "table is required", 400)
        # 主体标识
        subject = {
            'id_card': (request.args.get('id_card') or '').strip() or None,
            'phone': (request.args.get('phone') or '').strip() or None,
            'phones': request.args.get('phones'),
            'qq': (request.args.get('qq') or '').strip() or None,
            'qqs': request.args.get('qqs'),
            'weibo_uid': (request.args.get('weibo_uid') or '').strip() or None,
            'email': (request.args.get('email') or '').strip() or None,
            'name': (request.args.get('name') or '').strip() or None,
        }
        # 解析数组参数（逗号分隔）
        for k in ['phones', 'qqs']:
            subject[k] = parse_comma_list(subject.get(k))

        records = fetch_source_detail(table, subject, limit=int(request.args.get('limit', '50')))
        meta = get_data_source_meta([table]).get(table, {})
        return success(
            {"table": table, "chinese": meta.get('chinese') or table, "date": meta.get('date'), "records": records},
            table=table, chinese=meta.get('chinese') or table, date=meta.get('date'), records=records
        )
    except ValidationError as e:
        return error_response("Validation Error", str(e), 400)
    except DatabaseError:
        # 统一返回503以表示后端存储暂不可用
        return error_response("Service Unavailable", "Database temporarily unavailable or slow.", 503)
    except Exception as e:
        logger.error(f"来源详情查询失败: {e}", exc_info=True)
        return error_response("Internal Server Error", "Failed to get source detail", 500)

@api_bp.route('/ai/assess_confidence', methods=['POST'])
def assess_confidence():
    """触发AI置信度评估并保存到 profile.ai_confidence。
    请求体应包含：
      - subject: 查询到的完整信息JSON（用于评估）
      - id_card: 作为主键保存到对应 profile 记录（可从 subject 中推断）
    返回：最新的 profile 映射结果（兼容前端字段）。
    """
    try:
        payload = request.get_json() or {}
        subject = payload.get('subject') or {}
        # 以 id 为主键，允许从 subject/payload 中获取；若缺失则回退到 id_card
        primary_id = (payload.get('id') or subject.get('id') or '').strip()
        id_card = (payload.get('id_card') or subject.get('id_card') or '').strip()
        if not primary_id and not id_card:
            return error_response("Bad Request", "id or id_card is required", 400)
        if not primary_id:
            primary_id = id_card

        # 在发送给AI前，对现有数据进行校验并汇总校验结果
        validations: Dict[str, Any] = {}

        try:
            # 身份证结构校验
            code = (subject.get('id_card') or '').strip()
            if code:
                try:
                    validations['id_card'] = validate_id_structure(code)
                except ValidationServiceError as e:
                    validations['id_card'] = {'error': str(e), 'id_card': code}
            # 手机归属地校验（支持 phones 数组与单个 phone）
            phones = []
            p_single = (subject.get('phone') or '').strip()
            if p_single:
                phones.append(p_single)
            for p in subject.get('phones') or []:
                if isinstance(p, dict):
                    num = str(p.get('number') or p.get('phone') or '').strip()
                    if num:
                        phones.append(num)
                elif isinstance(p, str) and p.strip():
                    phones.append(p.strip())
            phone_results = []
            for num in phones[:5]:  # 限制数量避免过多外部调用
                try:
                    phone_results.append(fetch_phone_attribution(num))
                except ValidationServiceError as e:
                    phone_results.append({'number': num, 'error': str(e)})
                except Exception as e:
                    phone_results.append({'number': num, 'error': f'{e}'})
            if phone_results:
                validations['phones'] = phone_results
            # QQ 昵称与头像（支持 qqs 数组与单个 qq）
            qqs = []
            q_single = (subject.get('qq') or '').strip()
            if q_single:
                qqs.append(q_single)
            for q in subject.get('qqs') or []:
                if isinstance(q, dict):
                    num = str(q.get('qq') or q.get('number') or '').strip()
                    if num:
                        qqs.append(num)
                elif isinstance(q, str) and q.strip():
                    qqs.append(q.strip())
            qq_results = []
            for q in qqs[:5]:
                try:
                    qq_results.append(fetch_qq_profile(q))
                except ValidationServiceError as e:
                    qq_results.append({'qq': q, 'error': str(e)})
                except Exception as e:
                    qq_results.append({'qq': q, 'error': f'{e}'})
            if qq_results:
                validations['qqs'] = qq_results
            # 微博 UID 校验（支持 weibo_uids 数组与单个 weibo_uid）
            weibo_uids = []
            w_single = (subject.get('weibo_uid') or '').strip()
            if w_single:
                weibo_uids.append(w_single)
            for w in subject.get('weibo_uids') or []:
                if isinstance(w, dict):
                    uid = str(w.get('uid') or w.get('weibo_uid') or '').strip()
                    if uid:
                        weibo_uids.append(uid)
                elif isinstance(w, str) and w.strip():
                    weibo_uids.append(w.strip())
            weibo_results = []
            for u in weibo_uids[:5]:
                try:
                    weibo_results.append(fetch_weibo_profile(u))
                except ValidationServiceError as e:
                    weibo_results.append({'uid': u, 'error': str(e)})
                except Exception as e:
                    weibo_results.append({'uid': u, 'error': f'{e}'})
            if weibo_results:
                validations['weibo_uids'] = weibo_results
        except Exception as e:
            logger.warning(f"预校验阶段发生异常，继续AI评估（忽略校验）：{e}")

        # 合并校验结果后调用AI评估
        enriched_subject = dict(subject)
        enriched_subject['validations'] = validations
        result = ai_service.assess_confidence(enriched_subject)
        # 规范化保存结构：JSONB，包含 level/percentage/report/provider/model
        update_data = { 'ai_confidence': {
            'level': result.get('level'),
            'percentage': result.get('percentage'),
            'report': result.get('report'),
            'provider': result.get('provider'),
            'model': result.get('model')
        } }
        saved = update_customer_info(primary_id, update_data, None)
        # 输出唯一标识 id（若不存在则回退到 id_card）
        rid = saved.get('id') or saved.get('id_card')
        if rid:
            saved['id'] = rid
        return success(saved)
    except AIServiceError as e:
        return error_response("AI Service Error", str(e), 500)
    except ValidationError as e:
        return error_response("Validation Error", str(e), 400)
    except Exception as e:
        logger.error(f"置信度评估失败: {e}", exc_info=True)
        return error_response("Internal Server Error", "Failed to assess confidence", 500)
# 架构自省：列枚举与别名
@api_bp.route('/schema_introspect', methods=['GET'])
def schema_introspect():
    try:
        refresh = (request.args.get('refresh', '0') or '0').strip().lower() in ('1','true','yes')
        limit = request.args.get('limit')
        limit_int = int(limit) if (limit and limit.isdigit()) else None
        include_aliases = (request.args.get('include_aliases', '1') or '1').strip().lower() in ('1','true','yes')

        columns_by_table = get_schema_columns_cached(ttl_secs=int(request.args.get('ttl', '3600')), refresh=refresh, limit=limit_int)
        aliases = get_aliases_map() if include_aliases else {}
        summary = {
            'table_count': len(columns_by_table),
            'column_count': sum(len(v or []) for v in columns_by_table.values()),
        }
        from app.api.response import success
        return success({
            'columns_by_table': columns_by_table,
            'aliases': aliases,
            'summary': summary
        }, columns_by_table=columns_by_table, aliases=aliases, summary=summary)
    except ValidationError as e:
        from app.api.response import error_response
        return error_response("Validation Error", str(e), 400)
    except DatabaseError:
        from app.api.response import error_response
        return error_response("Service Unavailable", "Database temporarily unavailable or slow.", 503)
    except Exception as e:
        logger.error(f"架构自省失败: {e}", exc_info=True)
        from app.api.response import error_response
        return error_response("Internal Server Error", "Failed to introspect schema", 500)

# 数据验证：手机号归属地
@api_bp.route('/validate/phone', methods=['GET'])
def validate_phone():
    try:
        number = (request.args.get('number') or '').strip()
        if not number:
            return error_response("Bad Request", "number is required", 400)
        write_flag = (request.args.get('write', '1') or '1').strip().lower() in ('1','true','yes')
        id_card_arg = (request.args.get('id_card') or '').strip() or None
        # 可选用于合并的手机号（来自当前卡片上下文）
        merge_phone_raw = (request.args.get('merge_phone') or '').strip()
        # 归一化手机号：保留末尾11位数字（兼容+86/空格/短横线）
        import re
        digits = re.sub(r"\D", "", number)
        if len(digits) >= 12 and digits.startswith('86'):
            digits = digits[-11:]
        # 优先使用数据库中已存在的归属地信息，避免重复查询
        result = None
        from_db = False
        used_id_card = None
        used_id = None
        try:
            prof = None
            if id_card_arg:
                prof = find_profile('id_card', id_card_arg)
            if not prof:
                prof = find_profile('phone', digits)
            if prof and (prof.get('id') or prof.get('id_card')):
                used_id = prof.get('id') or prof.get('id_card')
                used_id_card = prof.get('id_card')
                phones = prof.get('phones') or []
                for p in phones:
                    if isinstance(p, dict):
                        num = str(p.get('number') or '').strip()
                        num_norm = re.sub(r"\D", "", num)
                        if len(num_norm) >= 12 and num_norm.startswith('86'):
                            num_norm = num_norm[-11:]
                        if num_norm == digits:
                            attr = p.get('attribution') or {}
                            # 兼容旧中文键（归属地/运营商/区号/邮编）
                            if not any(attr.get(k) for k in ('province','city','carrier','area_code','postcode')):
                                loc = (p.get('归属地') or '').strip()
                                carrier = p.get('运营商')
                                area = p.get('区号')
                                post = p.get('邮编')
                                prov = None
                                city = None
                                if loc:
                                    parts = [s for s in re.split(r"\s+", loc) if s]
                                    if len(parts) >= 1:
                                        prov = parts[0]
                                    if len(parts) >= 2:
                                        city = parts[1]
                                attr = {
                                    'province': prov,
                                    'city': city,
                                    'carrier': carrier,
                                    'area_code': area,
                                    'postcode': post,
                                }
                            # 若至少有一项有效信息，则直接返回表中数据
                            if any(attr.get(k) for k in ('province','city','carrier','area_code','postcode')):
                                result = {
                                    'number': digits,
                                    'province': attr.get('province'),
                                    'city': attr.get('city'),
                                    'carrier': attr.get('carrier'),
                                    'area_code': attr.get('area_code'),
                                    'postcode': attr.get('postcode'),
                                    'raw_excerpt': None
                                }
                                from_db = True
                                break
        except Exception:
            result = None
            from_db = False
        # 若数据库无足够信息，则调用在线查询服务
        if result is None:
            result = fetch_phone_attribution(digits)
        updated = None
        # used_id_card 可能已在读取数据库时确定
        if write_flag:
            try:
                # 确定要更新的 profile
                prof = None
                if id_card_arg:
                    prof = find_profile('id_card', id_card_arg)
                if not prof:
                    prof = find_profile('phone', digits)
                if prof and (prof.get('id') or prof.get('id_card')):
                    used_id = prof.get('id') or prof.get('id_card')
                    used_id_card = prof.get('id_card')
                    phones = prof.get('phones') or []
                    # 统一匹配逻辑：对象的 number 或纯字符串
                    changed = False
                    new_phones = []
                    found = False
                    for p in phones:
                        if isinstance(p, dict):
                            num = str(p.get('number') or '').strip()
                            num_norm = re.sub(r"\D", "", num)
                            if len(num_norm) >= 12 and num_norm.startswith('86'):
                                num_norm = num_norm[-11:]
                            if num_norm == digits:
                                # 写入 attribution（仅当缺失或有变更）
                                attr_old = p.get('attribution') or {}
                                attr_new = {
                                    'province': result.get('province'),
                                    'city': result.get('city'),
                                    'carrier': result.get('carrier'),
                                    'area_code': result.get('area_code'),
                                    'postcode': result.get('postcode'),
                                }
                                # 写入中文展示字段
                                p = dict(p)
                                p['number'] = digits
                                # 保持 attribution 对象（便于服务端检索与复用）
                                if attr_old != attr_new:
                                    p['attribution'] = attr_new
                                    changed = True
                                found = True
                                new_phones.append(p)
                            else:
                                new_phones.append(p)
                        else:
                            s = str(p)
                            s_norm = re.sub(r"\D", "", s)
                            if len(s_norm) >= 12 and s_norm.startswith('86'):
                                s_norm = s_norm[-11:]
                            if s_norm == digits:
                                # 替换为带 attribution 的对象
                                new_phones.append({
                                    'type': '主要',
                                    'number': digits,
                                    'attribution': {
                                        'province': result.get('province'),
                                        'city': result.get('city'),
                                        'carrier': result.get('carrier'),
                                        'area_code': result.get('area_code'),
                                        'postcode': result.get('postcode'),
                                    }
                                })
                                # 只有在原来不是对象或缺少 attribution 时算变更
                                changed = True
                                found = True
                            else:
                                new_phones.append(p)
                    # 若列表中不存在该号码，则追加到末尾
                    if not found:
                        new_phones = list(new_phones or phones)
                        new_phones.append({
                            'type': '其他',
                            'number': digits,
                            'attribution': {
                                'province': result.get('province'),
                                'city': result.get('city'),
                                'carrier': result.get('carrier'),
                                'area_code': result.get('area_code'),
                                'postcode': result.get('postcode'),
                            }
                        })
                        changed = True
                    if changed:
                        saved = update_customer_info(used_id, {'phones': new_phones}, None)
                        updated = {'phones': True}
                    else:
                        updated = {'phones': False}
                else:
                    # 主表无记录或缺少唯一键：创建基础档案并写入当前号码归属地
                    base_profile = {
                        'id_card': id_card_arg or (prof.get('id_card') if isinstance(prof, dict) else None),
                        'name': (prof.get('name') if isinstance(prof, dict) else None),
                        'phones': [{
                            'type': '其他',
                            'number': digits,
                            'attribution': {
                                'province': result.get('province'),
                                'city': result.get('city'),
                                'carrier': result.get('carrier'),
                                'area_code': result.get('area_code'),
                                'postcode': result.get('postcode'),
                            }
                        }]
                    }
                    try:
                        saved = add_customer_info(base_profile, None)
                        used_id = saved.get('id') or saved.get('id_card')
                        used_id_card = saved.get('id_card')
                        updated = {'phones': True}
                    except Exception:
                        updated = None
            except Exception as e:
                logger.warning(f"写入手机号归属地失败：{e}")

        # 统一成功结构
        payload = {
            'number': result.get('number'),
            'province': result.get('province'),
            'city': result.get('city'),
            'carrier': result.get('carrier'),
            'area_code': result.get('area_code'),
            'postcode': result.get('postcode'),
            'raw_excerpt': result.get('raw_excerpt'),
            'updated': updated,
            'id_card': used_id_card,
            'id': used_id,
            'from_db': from_db
        }
        return success(payload, **payload)
    except ValidationServiceError as e:
        return error_response("Validation Error", str(e), 400)
    except Exception as e:
        logger.error(f"手机号归属地查询失败: {e}", exc_info=True)
        return error_response("Internal Server Error", "Failed to validate phone attribution", 500)

# 数据验证：QQ信息
@api_bp.route('/validate/qq', methods=['GET'])
def validate_qq():
    try:
        qq_raw = (request.args.get('qq') or '').strip()
        if not qq_raw:
            return error_response("Bad Request", "qq is required", 400)
        write_flag = (request.args.get('write', '1') or '1').strip().lower() in ('1','true','yes')
        id_card_arg = (request.args.get('id_card') or '').strip() or None
        # 可选用于合并的手机号（来自当前卡片上下文）
        merge_phone_raw = (request.args.get('merge_phone') or '').strip()
        import re
        qq = re.sub(r"\D", "", qq_raw)
        if not re.fullmatch(r"\d{5,12}", qq or ""):
            return error_response("Bad Request", "qq format invalid", 400)
        # 归一化待合并手机号
        merge_phone_digits = None
        try:
            if merge_phone_raw:
                mp = re.sub(r"\D", "", merge_phone_raw)
                if len(mp) >= 12 and mp.startswith('86'):
                    mp = mp[-11:]
                if re.fullmatch(r"1\d{10}", mp or ""):
                    merge_phone_digits = mp
        except Exception:
            merge_phone_digits = None

        # 优先使用主表已有昵称与头像，避免重复查询
        result = None
        from_db = False
        used_id = None
        try:
            prof = None
            if id_card_arg:
                prof = find_profile('id_card', id_card_arg)
            if not prof:
                prof = find_profile('qq', qq)
            if prof and (prof.get('id') or prof.get('id_card')):
                used_id = prof.get('id') or prof.get('id_card')
                qqs = prof.get('qqs') or []
                for item in qqs:
                    if isinstance(item, dict):
                        num = str(item.get('qq') or item.get('number') or '').strip()
                        num = re.sub(r"\D", "", num)
                        if num == qq:
                            name = item.get('name')
                            logo = item.get('logo') or f"http://q1.qlogo.cn/g?b=qq&nk={qq}&s=40"
                            if name or logo:
                                result = {"qq": qq, "name": name, "logo": logo}
                                from_db = True
                                break
        except Exception:
            pass

        # 若库中缺少昵称，则调用外部接口获取
        if result is None or not result.get('name'):
            fetched = fetch_qq_profile(qq)
            # 补齐logo（即使昵称已命中）
            if result is None:
                result = fetched
            else:
                result = {"qq": qq, "name": fetched.get('name') or result.get('name'), "logo": result.get('logo') or fetched.get('logo')}

        updated = None
        if write_flag:
            try:
                prof = None
                if id_card_arg:
                    prof = find_profile('id_card', id_card_arg)
                if not prof:
                    prof = find_profile('qq', qq)
                if prof and (prof.get('id') or prof.get('id_card')):
                    # 统一使用主键 id，若缺失则回退到 id_card
                    used_id = used_id or prof.get('id') or prof.get('id_card')
                    qqs = prof.get('qqs') or []
                    changed = False
                    new_qqs = []
                    found = False
                    for item in qqs:
                        if isinstance(item, dict):
                            num = re.sub(r"\D", "", str(item.get('qq') or item.get('number') or ''))
                            if num == qq:
                                obj = dict(item)
                                obj['qq'] = qq
                                obj.pop('number', None)
                                # 仅当新增昵称或头像发生变化时写入
                                if obj.get('name') != result.get('name'):
                                    obj['name'] = result.get('name')
                                    changed = True
                                if obj.get('logo') != result.get('logo'):
                                    obj['logo'] = result.get('logo')
                                    changed = True
                                new_qqs.append(obj)
                                found = True
                            else:
                                new_qqs.append(item)
                        else:
                            s = re.sub(r"\D", "", str(item))
                            if s == qq:
                                # 将纯字符串项升级为对象
                                new_qqs.append({"qq": qq, "name": result.get('name'), "logo": result.get('logo')})
                                changed = True
                                found = True
                            else:
                                new_qqs.append(item)
                    if not found:
                        new_qqs = list(new_qqs or qqs)
                        new_qqs.append({"qq": qq, "name": result.get('name'), "logo": result.get('logo')})
                        changed = True
                    if changed and used_id:
                        saved = update_customer_info(used_id, {'qqs': new_qqs}, None)
                        updated = {'qqs': True}
                    else:
                        updated = {'qqs': False}
                else:
                    # 优先尝试根据待合并手机号合并到现有记录
                    merged = False
                    if merge_phone_digits:
                        try:
                            prof2 = find_profile('phone', merge_phone_digits)
                            if prof2 and (prof2.get('id') or prof2.get('id_card')):
                                used_id = prof2.get('id') or prof2.get('id_card')
                                arr = prof2.get('qqs') or []
                                arr = list(arr)
                                arr.append({"qq": qq, "name": result.get('name'), "logo": result.get('logo')})
                                saved = update_customer_info(used_id, { 'qqs': arr }, None)
                                updated = {'qqs': True}
                                merged = True
                        except Exception:
                            pass
                    if not merged:
                        # 找不到主表记录或无法合并：创建基础档案并写入当前QQ信息
                        base_profile = {
                            'id_card': id_card_arg or (prof.get('id_card') if isinstance(prof, dict) else None),
                            'name': (result.get('name') or (prof.get('name') if isinstance(prof, dict) else None)),
                            'qqs': [{
                                'qq': qq,
                                'name': result.get('name'),
                                'logo': result.get('logo')
                            }]
                        }
                        try:
                            saved = add_customer_info(base_profile, None)
                            used_id = saved.get('id') or saved.get('id_card')
                            updated = {'qqs': True}
                        except Exception:
                            updated = None
            except Exception as e:
                logger.warning(f"写入QQ信息失败：{e}")
        payload = {
            "qq": result.get('qq'),
            "name": result.get('name'),
            "logo": result.get('logo'),
            "updated": updated,
            "id": used_id,
            "from_db": from_db
        }
        return success(payload, **payload)
    except ValidationServiceError as e:
        return error_response("Validation Error", str(e), 400)
    except Exception as e:
        logger.error(f"QQ信息查询失败: {e}", exc_info=True)
        return error_response("Internal Server Error", "Failed to validate QQ info", 500)

# 数据验证：微博UID
@api_bp.route('/validate/weibo', methods=['GET'])
def validate_weibo():
    try:
        uid_raw = (request.args.get('uid') or request.args.get('weibo_uid') or '').strip()
        if not uid_raw:
            return error_response("Bad Request", "uid is required", 400)
        import re
        uid = re.sub(r"\D", "", uid_raw)
        if not re.fullmatch(r"\d{5,20}", uid or ""):
            return error_response("Bad Request", "uid format invalid", 400)

        write_flag = (request.args.get('write', '1') or '1').strip().lower() in ('1','true','yes')
        id_card_arg = (request.args.get('id_card') or '').strip() or None

        # 抓取主页信息
        info = fetch_weibo_profile(uid)

        # 可选写入：将 weibo_uids 写入主表（字符串数组）
        updated = None
        used_id = None
        if write_flag:
            try:
                prof = None
                if id_card_arg:
                    prof = find_profile('id_card', id_card_arg)
                if not prof:
                    prof = find_profile('weibo_uid', uid)
                if prof and (prof.get('id') or prof.get('id_card')):
                    used_id = prof.get('id') or prof.get('id_card')
                    arr = prof.get('weibo_uids') or []
                    arr = [str(x).strip() for x in arr if x]
                    if uid not in arr:
                        arr.append(uid)
                        update_customer_info(used_id, { 'weibo_uids': arr }, None)
                        updated = { 'weibo_uids': True }
                    else:
                        updated = { 'weibo_uids': False }
                else:
                    updated = { 'weibo_uids': None }
            except Exception as e:
                logger.warning(f"写入weibo_uids失败: {e}")
                updated = { 'weibo_uids': None }

        payload = {
            'uid': info.get('uid') or uid,
            'name': info.get('name'),
            'gender': info.get('gender'),
            'avatar': info.get('avatar'),
            'fans': info.get('fans'),
            'follows': info.get('follows'),
            'rpz': info.get('rpz'),
            'posts': info.get('posts'),
            'updated': updated,
            'id': used_id
        }
        return success(payload, **payload)
    except ValidationServiceError as e:
        return error_response("Validation Error", str(e), 400)
    except Exception as e:
        logger.error(f"微博UID查询失败: {e}", exc_info=True)
        return error_response("Internal Server Error", "Failed to validate Weibo UID", 500)

# 数据验证：身份证号
@api_bp.route('/validate/id_card', methods=['GET'])
def validate_id_card():
    try:
        code = (request.args.get('id_card') or '').strip()
        if not code:
            return error_response("Bad Request", "id_card is required", 400)
        write_flag = (request.args.get('write', '1') or '1').strip().lower() in ('1','true','yes')

        # 结构校验与字段解析
        result = validate_id_structure(code)
        address_code = result.get('address_code')
        birth_raw = result.get('birth') or ''
        # 籍贯名称映射
        native_place = lookup_native_place_from_code(address_code) if address_code else None

        # 出生日期格式化 YYYY-MM-DD
        birth_fmt = None
        if birth_raw and len(birth_raw) == 8:
            birth_fmt = f"{birth_raw[0:4]}-{birth_raw[4:6]}-{birth_raw[6:8]}"

        # 从主表读取现有信息用于一致性比较
        existing = None
        try:
            existing = find_profile('id_card', code)
        except Exception:
            existing = None
        existing_gender = (existing or {}).get('gender')
        existing_native = (existing or {}).get('native_place')
        existing_birth = (existing or {}).get('birth_date')
        if hasattr(existing_birth, 'isoformat'):
            existing_birth = existing_birth.isoformat()

        consistency = {
            'gender': (existing_gender == result.get('gender')) if existing is not None else None,
            'native_place': (existing_native == native_place) if existing is not None else None,
            'birth_date': (existing_birth == birth_fmt) if existing is not None else None,
        }

        updated = None
        saved = None
        created = False
        if write_flag and result.get('valid'):
            try:
                if existing is None:
                    # 无记录：自动插入 profile 基础信息
                    saved = add_customer_info({
                        'id_card': code,
                        'gender': result.get('gender'),
                        'native_place': native_place,
                        'birth_date': birth_fmt,
                    }, None)
                    created = True
                    updated = {
                        'gender': bool(result.get('gender')),
                        'native_place': bool(native_place),
                        'birth_date': bool(birth_fmt),
                    }
                else:
                    # 仅在不一致时更新对应字段（优先使用主键 id，回退到 id_card）
                    update_data: Dict[str, Any] = {}
                    if result.get('gender') is not None and existing_gender != result.get('gender'):
                        update_data['gender'] = result.get('gender')
                    if native_place is not None and existing_native != native_place:
                        update_data['native_place'] = native_place
                    if birth_fmt is not None and existing_birth != birth_fmt:
                        update_data['birth_date'] = birth_fmt

                    if update_data:
                        used_id = (existing.get('id') or existing.get('id_card') or code)
                        saved = update_customer_info(used_id, update_data, None)
                        updated = {
                            'gender': 'gender' in update_data,
                            'native_place': 'native_place' in update_data,
                            'birth_date': 'birth_date' in update_data,
                        }
                    else:
                        updated = {
                            'gender': False,
                            'native_place': False,
                            'birth_date': False,
                        }
            except Exception as e:
                logger.warning(f"写入profile失败（保持结果返回）：{e}")

        payload = {
            'id_card': result.get('id_card'),
            'address_code': address_code,
            'native_place': native_place,
            'birth': result.get('birth'),
            'birth_date': birth_fmt,
            'gender': result.get('gender'),
            'valid': result.get('valid'),
            'consistency': consistency,
            'updated': updated,
            'created': created,
            'error': result.get('error')
        }
        return success(payload, **payload)
    except Exception as e:
        logger.error(f"身份证校验失败: {e}", exc_info=True)
        return error_response("Internal Server Error", "Failed to validate id card", 500)