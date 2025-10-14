from flask import jsonify

def success(data=None, status: int = 200, **extra):
    """构造统一成功响应。支持附加字段（例如 from_cache、results 等）。"""
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    # 合并附加字段（避免覆盖关键字段）
    for k, v in extra.items():
        if k not in payload:
            payload[k] = v
    return jsonify(payload), status

def error_response(error: str, message: str, status: int, **extra):
    """构造统一错误响应，支持附加字段（例如 status 等）。"""
    payload = {"error": error, "message": message}
    for k, v in extra.items():
        if k not in payload:
            payload[k] = v
    return jsonify(payload), status