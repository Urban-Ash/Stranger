import os
import sys
import re
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

# 设置日志
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """数据验证异常"""
    pass

class Utils:
    """工具函数类"""
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """验证手机号格式是否正确
        
        Args:
            phone: 手机号字符串
        
        Returns:
            bool: 验证结果
        
        Raises:
            ValidationError: 验证失败时抛出异常
        """
        if not phone:
            raise ValidationError("手机号不能为空")
        
        # 中国大陆手机号正则：以1开头的11位数字
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, phone):
            raise ValidationError(f"手机号格式不正确: {phone}")
        
        return True
    
    @staticmethod
    def validate_id_card(id_card: Optional[str] = None) -> bool:
        """验证身份证号码格式是否正确
        
        Args:
            id_card: 身份证号码字符串，可选
        
        Returns:
            bool: 验证结果
        
        Raises:
            ValidationError: 验证失败时抛出异常
        """
        # 身份证号码可以为空
        if id_card is None:
            return True
        
        if not id_card:
            raise ValidationError("身份证号码不能为空字符串")
        
        # 中国大陆身份证正则：18位，前17位是数字，最后一位可以是数字或X/x
        pattern = r'^[1-9]\d{5}(18|19|20)\d{2}((0[1-9])|(1[0-2]))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx]$'
        if not re.match(pattern, id_card):
            raise ValidationError(f"身份证号码格式不正确: {id_card}")
        
        # 加权因子
        factors = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        # 校验码对应值
        check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
        
        # 计算校验码
        sum_value = 0
        for i in range(17):
            sum_value += int(id_card[i]) * factors[i]
        check_code_index = sum_value % 11
        expected_check_code = check_codes[check_code_index]
        
        # 检查校验码是否正确
        actual_check_code = id_card[17]
        if actual_check_code.upper() != expected_check_code:
            raise ValidationError(f"身份证号码校验失败: {id_card}")
        
        return True
    
    @staticmethod
    def clean_input(value: Any) -> Any:
        """清理输入数据，防止注入攻击
        
        Args:
            value: 输入数据，可以是字符串、字典、列表等
        
        Returns:
            Any: 清理后的数据
        """
        if value is None:
            return None
        
        if isinstance(value, str):
            # 移除HTML标签
            value = re.sub(r'<[^>]*>', '', value)
            # 转义特殊字符
            # 移除可能的JavaScript代码
            value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.DOTALL)
            # 移除SQL注入相关字符
            value = re.sub(r'(--|#|;)', '', value)
            # 移除多余空格
            value = ' '.join(value.split())
            return value.strip()
        
        elif isinstance(value, dict):
            return {k: Utils.clean_input(v) for k, v in value.items()}
        
        elif isinstance(value, list):
            return [Utils.clean_input(item) for item in value]
        
        # 其他类型保持不变
        return value
    
    @staticmethod
    def format_datetime(dt: Optional[datetime] = None, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
        """格式化日期时间
        
        Args:
            dt: 日期时间对象，如果为None则使用当前时间
            format_str: 格式化字符串
        
        Returns:
            str: 格式化后的日期时间字符串
        """
        if dt is None:
            dt = datetime.now()
        
        try:
            return dt.strftime(format_str)
        except Exception as e:
            logger.error(f"日期时间格式化失败: {e}")
            return str(dt)
    
    @staticmethod
    def parse_datetime(date_str: str, format_str: Optional[str] = None) -> Optional[datetime]:
        """解析日期时间字符串
        
        Args:
            date_str: 日期时间字符串
            format_str: 格式化字符串，如果为None则尝试多种常见格式
        
        Returns:
            Optional[datetime]: 解析后的日期时间对象，如果解析失败则返回None
        """
        if not date_str:
            return None
        
        if format_str:
            try:
                return datetime.strptime(date_str, format_str)
            except ValueError:
                logger.warning(f"无法按照指定格式解析日期时间: {date_str}")
                return None
        
        # 尝试多种常见格式
        common_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d %H:%M',
            '%Y/%m/%d',
            '%d-%m-%Y %H:%M:%S',
            '%d-%m-%Y %H:%M',
            '%d-%m-%Y',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d/%m/%Y'
        ]
        
        for fmt in common_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        logger.warning(f"无法解析日期时间: {date_str}")
        return None
    
    @staticmethod
    def calculate_age(birth_date: Union[str, datetime]) -> Optional[int]:
        """计算年龄
        
        Args:
            birth_date: 出生日期，可以是字符串或datetime对象
        
        Returns:
            Optional[int]: 年龄，如果计算失败则返回None
        """
        if isinstance(birth_date, str):
            birth_date = Utils.parse_datetime(birth_date)
            if birth_date is None:
                return None
        
        today = datetime.now()
        age = today.year - birth_date.year
        
        # 检查是否已经过了生日
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return max(0, age)  # 确保年龄不为负数
    
    @staticmethod
    def merge_dicts(*dicts: Dict) -> Dict:
        """合并多个字典
        
        Args:
            *dicts: 要合并的字典
        
        Returns:
            Dict: 合并后的字典
        """
        result = {}
        for d in dicts:
            if d:
                result.update(d)
        return result
    
    @staticmethod
    def flatten_dict(d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """将嵌套字典展平
        
        Args:
            d: 嵌套字典
            parent_key: 父键
            sep: 分隔符
        
        Returns:
            Dict: 展平后的字典
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(Utils.flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # 对于列表，可以选择不同的处理方式，这里简化处理
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)

    @staticmethod
    def parse_comma_list(text: Optional[str]) -> Optional[List[str]]:
        """解析逗号分隔的字符串为字符串数组，去空格与空项。
        空值返回 None，便于与 QueryString 区分是否提供该参数。
        """
        if text is None:
            return None
        s = str(text).strip()
        if not s:
            return None
        return [v.strip() for v in s.split(',') if v.strip()]

    @staticmethod
    def normalize_profile_for_api(rec: Dict[str, Any]) -> Dict[str, Any]:
        """兼容前端字段：补充 id，并将单值 phone/qq 转为数组字段。
        不修改原始记录，仅返回副本。
        """
        if not isinstance(rec, dict):
            return rec
        r = dict(rec)
        # 输出 id 作为唯一标识；若不存在则回退到 id_card
        rid = r.get('id') or r.get('id_card')
        if rid:
            r.setdefault('id', rid)
        # 将单值兼容为数组字段
        if ('phone' in r) and ('phones' not in r) and r.get('phone'):
            r['phones'] = [r['phone']]
        if ('qq' in r) and ('qqs' not in r) and r.get('qq'):
            r['qqs'] = [r['qq']]
        return r
    def safe_get(data: Dict, path: str, default: Any = None, sep: str = '.') -> Any:
        """安全地从嵌套字典中获取值
        
        Args:
            data: 嵌套字典
            path: 键路径，如 'user.profile.name'
            default: 默认值
            sep: 分隔符
        
        Returns:
            Any: 获取的值或默认值
        """
        if not data:
            return default
        
        keys = path.split(sep)
        current = data
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError, IndexError):
            return default
    
    @staticmethod
    def retry(max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
        """重试装饰器
        
        Args:
            max_retries: 最大重试次数
            delay: 重试间隔（秒）
            exceptions: 捕获的异常类型
        
        Returns:
            function: 装饰后的函数
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            logger.warning(f"尝试 {attempt + 1}/{max_retries} 失败，{delay} 秒后重试: {e}")
                            import time
                            time.sleep(delay * (2 ** attempt))  # 指数退避
                        else:
                            logger.error(f"尝试 {max_retries} 次后仍然失败: {e}")
                            raise last_exception
            
            return wrapper
        
        return decorator
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """计算两个文本的相似度（简化版，使用编辑距离）
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
        
        Returns:
            float: 相似度得分（0-1）
        """
        # 编辑距离算法（Levenshtein距离）
        def levenshtein_distance(s1, s2):
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            
            # 空字符串的情况
            if len(s2) == 0:
                return len(s1)
            
            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            
            return previous_row[-1]
        
        # 计算编辑距离
        distance = levenshtein_distance(text1, text2)
        
        # 计算相似度（归一化到0-1）
        max_length = max(len(text1), len(text2))
        if max_length == 0:
            return 1.0  # 两个空字符串是完全相似的
        
        similarity = 1 - (distance / max_length)
        return similarity
    
    @staticmethod
    def mask_sensitive_info(data: Dict, sensitive_fields: List[str] = None) -> Dict:
        """屏蔽敏感信息
        
        Args:
            data: 包含敏感信息的数据
            sensitive_fields: 敏感字段列表
        
        Returns:
            Dict: 屏蔽敏感信息后的数据
        """
        if not sensitive_fields:
            sensitive_fields = ['password', 'id_card', 'credit_card', 'phone', 'email']
        
        if not data:
            return data
        
        masked_data = {}
        for key, value in data.items():
            if isinstance(value, dict):
                masked_data[key] = Utils.mask_sensitive_info(value, sensitive_fields)
            elif isinstance(value, list):
                masked_data[key] = [Utils.mask_sensitive_info(item, sensitive_fields) if isinstance(item, dict) else item for item in value]
            else:
                # 检查键是否包含敏感字段
                key_lower = key.lower()
                if any(sensitive_field in key_lower for sensitive_field in sensitive_fields):
                    # 对不同类型的敏感信息进行不同的屏蔽处理
                    if 'password' in key_lower:
                        masked_data[key] = '******'
                    elif 'id_card' in key_lower and isinstance(value, str):
                        masked_data[key] = value[:6] + '******' + value[-4:] if len(value) >= 14 else '******'
                    elif 'phone' in key_lower and isinstance(value, str):
                        masked_data[key] = value[:3] + '****' + value[-4:] if len(value) >= 11 else '******'
                    elif 'email' in key_lower and isinstance(value, str) and '@' in value:
                        parts = value.split('@')
                        masked_data[key] = parts[0][:2] + '****' + '@' + parts[1]
                    else:
                        masked_data[key] = '******'
                else:
                    masked_data[key] = value
        
        return masked_data
    
    @staticmethod
    def safe_convert(value: Any, target_type: type, default: Any = None) -> Any:
        """安全地转换数据类型
        
        Args:
            value: 要转换的值
            target_type: 目标类型
            default: 转换失败时的默认值
        
        Returns:
            Any: 转换后的值或默认值
        """
        if value is None:
            return default
        
        try:
            if target_type == int:
                # 处理字符串类型的数字
                if isinstance(value, str):
                    # 移除可能的千位分隔符
                    value = value.replace(',', '')
                return int(value)
            elif target_type == float:
                # 处理字符串类型的浮点数
                if isinstance(value, str):
                    # 移除可能的千位分隔符
                    value = value.replace(',', '')
                return float(value)
            elif target_type == bool:
                # 特殊处理布尔值
                if isinstance(value, str):
                    return value.lower() in ('true', 'yes', '1', 'y')
                return bool(value)
            elif target_type == str:
                return str(value)
            else:
                return target_type(value)
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"无法将 {value} 转换为 {target_type.__name__} 类型，使用默认值 {default}")
            return default

# 创建工具类实例
utils = Utils()

# 导出常用函数供直接使用
validate_phone = utils.validate_phone
validate_id_card = utils.validate_id_card
clean_input = utils.clean_input
format_datetime = utils.format_datetime
parse_datetime = utils.parse_datetime
calculate_age = utils.calculate_age
merge_dicts = utils.merge_dicts
flatten_dict = utils.flatten_dict
safe_get = utils.safe_get
retry = utils.retry
calculate_similarity = utils.calculate_similarity
mask_sensitive_info = utils.mask_sensitive_info
safe_convert = utils.safe_convert
parse_comma_list = utils.parse_comma_list
normalize_profile_for_api = utils.normalize_profile_for_api