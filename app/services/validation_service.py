import logging
import re
from typing import Dict, Any, Optional

import os
import requests
from .crawler import get_crawler, CrawlerError

logger = logging.getLogger(__name__)


class ValidationServiceError(Exception):
    pass




def _strip_html(text: str) -> str:
    try:
        # 粗略去除HTML标签并压缩空白
        s = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
        s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
        s = re.sub(r"<[^>]+>", " ", s)
        s = re.sub(r"&nbsp;", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s
    except Exception:
        return text


def validate_id_structure(id_card: str) -> Dict[str, Any]:
    """校验18位中国居民身份证结构并解析关键字段。
    返回：{"id_card": str, "valid": bool, "error": Optional[str],
          "address_code": str, "birth": str, "gender": str}
    说明：本函数不做行政区划名称映射，仅返回前六位地址码。
    """
    import re
    from datetime import datetime

    s = (id_card or '').strip().upper()
    result: Dict[str, Any] = {
        "id_card": s,
        "valid": False,
        "error": None,
        "address_code": None,
        "birth": None,
        "gender": None,
    }

    # 基本格式
    if not re.fullmatch(r"\d{17}[\dX]", s):
        result["error"] = "格式不正确，应为18位数字，末位可为X"
        return result

    addr = s[:6]
    birth = s[6:14]
    seq = s[14:17]
    result["address_code"] = addr
    result["birth"] = birth
    try:
        result["gender"] = "男" if int(seq) % 2 == 1 else "女"
    except Exception:
        result["gender"] = None

    # 出生日期有效
    try:
        dob = datetime.strptime(birth, "%Y%m%d").date()
        from datetime import date
        if dob.year < 1900 or dob > date.today():
            raise ValueError()
    except Exception:
        result["error"] = "出生日期无效"
        return result

    # 校验码
    WEIGHTS = [7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
    CHECK_MAP = ['1','0','X','9','8','7','6','5','4','3','2']
    try:
        total = sum(int(s[i]) * WEIGHTS[i] for i in range(17))
        expected = CHECK_MAP[total % 11]
        if s[17] != expected:
            result["error"] = f"校验码不匹配，应为{expected}"
            return result
    except Exception:
        result["error"] = "校验码计算失败"
        return result

    result["valid"] = True
    return result


def fetch_phone_attribution(number: str, timeout: int = 8) -> Dict[str, Any]:
    """查询手机号归属地信息。
    优先使用 360 的 JSON 接口，其次淘宝 JSONP，最后回退 ip138 解析。
    返回结构：{"number": str, "province": Optional[str], "city": Optional[str], "carrier": Optional[str], "raw_excerpt": Optional[str]}
    """
    # 归一化：去除非数字，去掉+86前缀
    digits = re.sub(r"\D", "", number or "")
    if len(digits) >= 12 and digits.startswith('86'):
        digits = digits[-11:]
    if not re.fullmatch(r"1\d{10}", digits or ""):
        raise ValidationServiceError("手机号格式不正确，需为11位以1开头的数字")

    # 1) 360 手机号归属地接口（JSON）
    try:
        crawler = get_crawler()
        resp = crawler.get(
            "https://cx.shouji.360.cn/phonearea.php",
            params={"number": digits},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and int(data.get("code", 1)) == 0:
            d = data.get("data") or {}
            province = d.get("province") or None
            city = d.get("city") or None
            sp = d.get("sp") or None
            # 运营商标准化
            carrier_map = {
                "移动": "中国移动",
                "联通": "中国联通",
                "电信": "中国电信"
            }
            carrier = carrier_map.get(sp or "", sp)
            # 额外尝试通过 ip138 获取区号/邮编
            area_code = None
            postcode = None
            try:
                url = f"https://www.ip138.com/mobile.asp"
                r2 = _http_get(url, params={"mobile": digits, "action": "mobile"}, headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                }, timeout=10.0)
                r2.raise_for_status()
                plain2 = _strip_html(r2.text or "")
                m_area = re.search(r"区号[:：]\s*(\d{3,4})", plain2)
                if m_area:
                    area_code = m_area.group(1)
                m_post = re.search(r"邮编[:：]\s*(\d{6})", plain2)
                if m_post:
                    postcode = m_post.group(1)
            except Exception:
                pass
            # 若仍缺失，尝试 apihz.cn 免费接口补充
            if not area_code or not postcode:
                try:
                    r3 = _http_get(
                        "https://cn.apihz.cn/api/ip/shouji.php",
                        params={"id": "88888888", "key": "88888888", "phone": digits},
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=8.0
                    )
                    r3.raise_for_status()
                    j3 = r3.json()
                    if int(j3.get("code", 0)) == 200:
                        area_code = area_code or (j3.get("quhao") or None)
                        postcode = postcode or (j3.get("youbian") or None)
                except Exception:
                    pass
            return {
                "number": digits,
                "province": province,
                "city": city,
                "carrier": carrier,
                "area_code": area_code,
                "postcode": postcode,
                "raw_excerpt": None
            }
    except (Exception, CrawlerError) as e:
        logger.debug(f"360归属地查询失败，尝试回退: {e}")

    # 2) 淘宝号段（JSONP 文本）
    try:
        crawler = get_crawler()
        resp = crawler.get(
            "https://tcc.taobao.com/cc/json/mobile_tel_segment.htm",
            params={"tel": digits},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp.raise_for_status()
        # 淘宝文本通常为 GBK，需要显式编码；若失败则用默认
        try:
            resp.encoding = resp.apparent_encoding or 'gbk'
        except Exception:
            resp.encoding = resp.encoding or 'utf-8'
        text = resp.text or ""
        # __GetZoneResult_ = {telString:"15004751221",province:"内蒙古",catName:"中国移动",carrier:"移动"}
        province = None
        city = None
        carrier = None
        m_prov = re.search(r"province\s*:\s*\"([^\"]+)\"", text)
        if m_prov:
            province = m_prov.group(1)
        m_car = re.search(r"catName\s*:\s*\"([^\"]+)\"", text)
        if m_car:
            carrier = m_car.group(1)
        # 淘宝返回通常不含城市
        if province or carrier:
            # 淘宝不含区号/邮编，尝试 apihz.cn 补充
            area_code = None
            postcode = None
            try:
                r3 = get_crawler().get(
                    "https://cn.apihz.cn/api/ip/shouji.php",
                    params={"id": "88888888", "key": "88888888", "phone": digits},
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                r3.raise_for_status()
                j3 = r3.json()
                if int(j3.get("code", 0)) == 200:
                    area_code = j3.get("quhao") or None
                    postcode = j3.get("youbian") or None
            except Exception:
                pass
            return {
                "number": digits,
                "province": province,
                "city": city,
                "carrier": carrier,
                "area_code": area_code,
                "postcode": postcode,
                "raw_excerpt": None
            }
    except Exception as e:
        logger.debug(f"淘宝号段查询失败，尝试回退: {e}")

    # 3) ip138 网页解析作为最后回退
    try:
        url = f"https://www.ip138.com/mobile.asp"
        resp = _http_get(url, params={"mobile": digits, "action": "mobile"}, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        }, timeout=10.0)
        resp.raise_for_status()
        text = resp.text or ""
        plain = _strip_html(text)

        province: Optional[str] = None
        city: Optional[str] = None
        carrier: Optional[str] = None

        # 归属地/运营商多样式匹配
        loc_patterns = [
            r"归属地[:：]\s*([\u4e00-\u9fa5A-Za-z]+)\s*([\u4e00-\u9fa5A-Za-z]+)?",
            r"卡号归属地[:：]\s*([\u4e00-\u9fa5A-Za-z]+)\s*([\u4e00-\u9fa5A-Za-z]+)?",
            r"所在地[:：]\s*([\u4e00-\u9fa5A-Za-z]+)\s*([\u4e00-\u9fa5A-Za-z]+)?"
        ]
        for pat in loc_patterns:
            m = re.search(pat, plain)
            if m:
                province = m.group(1)
                city = (m.group(2) or "").strip() or None
                break

        carrier_patterns = [
            r"运营商[:：]\s*([\u4e00-\u9fa5A-Za-z0-9]+)",
            r"卡类型[:：]\s*([\u4e00-\u9fa5A-Za-z0-9]+)",
            r"网络类型[:：]\s*([\u4e00-\u9fa5A-Za-z0-9]+)"
        ]
        for pat in carrier_patterns:
            m = re.search(pat, plain)
            if m:
                carrier = m.group(1)
                break

        excerpt = None
        # 区号/邮编
        m_area = re.search(r"区号[:：]\s*(\d{3,4})", plain)
        area_code = m_area.group(1) if m_area else None
        m_post = re.search(r"邮编[:：]\s*(\d{6})", plain)
        postcode = m_post.group(1) if m_post else None
        if not province and not carrier:
            m2 = re.search(r"(归属地[\s\S]{0,60}|运营商[\s\S]{0,60})", plain)
            if m2:
                excerpt = m2.group(1)

        return {
            "number": digits,
            "province": province,
            "city": city,
            "carrier": carrier,
            "area_code": area_code,
            "postcode": postcode,
            "raw_excerpt": excerpt
        }
    except Exception as e:
        logger.warning(f"请求ip138失败: {e}")
        raise ValidationServiceError("查询手机号归属地失败")


def fetch_qq_info(qq: str, timeout: int = 8) -> Dict[str, Any]:
    """查询QQ号相关信息（来源：bugpk接口）。
    返回结构：按接口原始字段转发（success/msg/data/...）。
    """
    if not re.fullmatch(r"\d{5,12}", qq or ""):
        raise ValidationServiceError("QQ号格式不正确，需为5-12位数字")

    url = f"https://api.bugpk.com/api/qq_info?qq={qq}"
    try:
        resp = _http_get(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        }, timeout=float(timeout))
        resp.raise_for_status()
        try:
            data = resp.json()
        except Exception:
            # 回退为文本并包装
            text = resp.text or ""
            data = {"success": False, "msg": "非JSON响应", "raw": text}
    except Exception as e:
        logger.warning(f"请求QQ接口失败: {e}")
        raise ValidationServiceError("查询QQ信息失败")

    # 直接返回原结构，前端再格式化
    return data


def fetch_qq_profile(qq: str, timeout: int = 8) -> Dict[str, Any]:
    """获取QQ昵称与头像。
    - 昵称来源：users.qzone.qq.com cgi_get_portrait（JSONP）
    - 头像：直接构造 qlogo URL（无需HTTP查询）
    返回：{"qq": str, "name": Optional[str], "logo": str}
    """
    digits = re.sub(r"\D", "", str(qq or ""))
    if not re.fullmatch(r"\d{5,12}", digits or ""):
        raise ValidationServiceError("QQ号格式不正确，需为5-12位数字")

    name: Optional[str] = None
    # 头像URL（固定规则）
    logo = f"http://q1.qlogo.cn/g?b=qq&nk={digits}&s=40"

    # 昵称接口（JSONP），尝试解析为JSON
    try:
        resp = get_crawler().get(
            "https://users.qzone.qq.com/fcg-bin/cgi_get_portrait.fcg",
            params={"uins": digits},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp.raise_for_status()
        # 设置编码，常见为GBK
        try:
            resp.encoding = resp.apparent_encoding or 'gbk'
        except Exception:
            resp.encoding = resp.encoding or 'utf-8'
        text = (resp.text or '').strip()
        # 去掉回调包装
        import json, re as _re
        inner = _re.sub(r"^[^(]*\(", "", text)
        inner = _re.sub(r"\)\s*;?\s*$", "", inner)
        data = None
        try:
            data = json.loads(inner)
        except Exception:
            data = None
        if isinstance(data, dict):
            # 可能键为字符串QQ号或不带引号；统一尝试字符串键
            arr = data.get(digits)
            if isinstance(arr, list):
                # 新结构示例：["http://qlogo2...", 4945, -1, 0, 0, 0, "昵称", 0]
                # 旧结构示例：[..., ..., "昵称", ...]
                for idx in (6, 2):
                    if idx < len(arr):
                        n = arr[idx]
                        if isinstance(n, str) and n.strip():
                            name = n.strip()
                            break
                # 再次兜底：取数组中最后一个非URL的非空字符串
                if not name:
                    strs = [s for s in arr if isinstance(s, str)]
                    for s in reversed(strs):
                        t = s.strip()
                        if t and not t.lower().startswith('http'):
                            name = t
                            break
        if not name:
            # 文本兜底解析：提取第一组方括号内的数组并尝试索引 6/2
            m = _re.search(r"\[\s*[^\]]*?\]", inner)
            if m:
                raw = m.group(0).strip('[]')
                # 简易分割（昵称通常不含逗号），去引号和空白
                parts = [p.strip().strip('"') for p in raw.split(',')]
                for idx in (6, 2):
                    if idx < len(parts) and parts[idx] and not parts[idx].lower().startswith('http'):
                        name = parts[idx]
                        break
                if not name:
                    # 取最后一个非URL字符串
                    for p in reversed(parts):
                        if p and not p.lower().startswith('http'):
                            name = p
                            break
    except (Exception, CrawlerError) as e:
        logger.debug(f"获取QQ昵称失败，返回空昵称: {e}")

    return {"qq": digits, "name": name, "logo": logo}


def fetch_weibo_profile(uid: str, timeout: int = 10) -> Dict[str, Any]:
    """抓取微博用户主页，解析头像、性别、用户名与统计信息。
    来源：`https://weibo.com/u/<uid>`（公开主页）。
    返回：{
      "uid": str, "name": Optional[str], "gender": Optional[str],
      "avatar": Optional[str], "fans": Optional[int], "follows": Optional[int],
      "rpz": Optional[int], "posts": Optional[int]
    }
    """
    digits = re.sub(r"\D", "", str(uid or ""))
    if not re.fullmatch(r"\d{5,20}", digits or ""):
        raise ValidationServiceError("微博UID格式不正确，需为5-20位数字")

    url = f"https://weibo.com/u/{digits}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    html = ""
    try:
        resp = _http_get(url, headers=headers, timeout=float(timeout))
        resp.raise_for_status()
        try:
            resp.encoding = resp.apparent_encoding or resp.encoding or 'utf-8'
        except Exception:
            resp.encoding = resp.encoding or 'utf-8'
        html = (resp.text or '')
    except Exception as e:
        logger.warning(f"请求微博主页失败: {e}")
        html = ""

    import re as _re
    def _text_between(pattern: str) -> Optional[str]:
        m = _re.search(pattern, html, _re.S | _re.I)
        if not m:
            return None
        s = m.group(1)
        s = _re.sub(r"<[^>]+>", "", s)
        return (s or '').strip() or None

    name = _text_between(r"<div[^>]*class=\"[^\"]*ProfileHeader_name[^\"]*\"[^>]*>(.*?)</div>")

    gender = None
    if _re.search(r"xlink:href=\"#woo_svg_female\"", html):
        gender = "女"
    elif _re.search(r"xlink:href=\"#woo_svg_male\"", html):
        gender = "男"

    avatar = None
    block_m = _re.search(r"<div[^>]*class=\"[^\"]*ProfileHeader_avatar2[^\"]*\"[^>]*>(.*?)</div>", html, _re.S | _re.I)
    block = block_m.group(1) if block_m else html
    img_m = _re.search(r"<img[^>]*src=\"([^\"]+)\"", block, _re.I)
    if img_m:
        avatar = img_m.group(1)
    else:
        style_m = _re.search(r"background-image\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)", block, _re.I)
        if style_m:
            avatar = style_m.group(1)

    def _num_for(label: str) -> Optional[int]:
        m = _re.search(rf"<span[^>]*>\s*(\d+)\s*</span>\s*{label}", html, _re.I)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
        return None
    fans = _num_for("粉丝")
    follows = _num_for("关注")
    rpz = _num_for("转评赞")

    posts = None
    pm = _re.search(r"全部微博（(\d+)）", html)
    if pm:
        try:
            posts = int(pm.group(1))
        except Exception:
            posts = None

    # 如果HTML抓取失败或关键字段为空，尝试移动端JSON接口兜底
    if not name or not avatar or fans is None or follows is None:
        try:
            m_resp = get_crawler().get(
                "https://m.weibo.cn/profile/info",
                params={"uid": digits},
                headers={
                    "Referer": f"https://m.weibo.cn/profile/{digits}",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/plain, */*"
                }
            )
            m_resp.raise_for_status()
            j = m_resp.json()
            u = (j.get("data") or {}).get("user") or {}
            name = name or (u.get("screen_name") or None)
            g = u.get("gender")
            if not gender and isinstance(g, str):
                gender = "男" if g.lower() == 'm' else ("女" if g.lower() == 'f' else None)
            avatar = avatar or (u.get("profile_image_url") or u.get("avatar_hd") or None)
            fans = fans if fans is not None else (u.get("followers_count") or None)
            follows = follows if follows is not None else (u.get("follow_count") or None)
            posts = posts if posts is not None else (u.get("statuses_count") or None)
        except Exception:
            pass

    return {
        "uid": digits,
        "name": name,
        "gender": gender,
        "avatar": avatar,
        "fans": fans,
        "follows": follows,
        "rpz": rpz,
        "posts": posts
    }
def _http_get(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> requests.Response:
    """轻量化HTTP GET封装：使用requests直接请求，统一超时与UA。
    不做重试与复杂节流，以简化实现；异常由调用方捕获。
    """
    base_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "User-Agent": headers.get("User-Agent") if headers and headers.get("User-Agent") else (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
        )
    }
    if headers:
        base_headers.update(headers)
    resp = requests.get(url, params=params, headers=base_headers, timeout=timeout)
    return resp