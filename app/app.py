import os
import sys
import logging
from flask import Flask, render_template, send_from_directory, session, redirect, url_for, request, make_response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from flask_compress import Compress
from app.utils.utils import ValidationError

# 设置项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 配置日志
from config.config import config_manager
log_level = config_manager.get('LOG_LEVEL', 'INFO')
log_file = config_manager.get('LOG_FILE', 'app.log')

logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 数据库连接
from app.models.database import get_db, DatabaseError, create_indexes

# 创建Flask应用
def create_app():
    """创建Flask应用实例"""
    app = Flask(__name__, 
                template_folder=os.path.join(project_root, 'templates'),
                static_folder=os.path.join(project_root, 'static'))
    
    # 配置应用
    app.config.update(config_manager.get_flask_config())
    # 安全的会话Cookie配置
    try:
        env = (config_manager.get('FLASK_ENV') or 'development').lower()
        app.config.update({
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
            'SESSION_COOKIE_SECURE': env == 'production'
        })
    except Exception:
        # 忽略配置错误以避免阻断开发环境
        pass
    
    # 启用CORS（按配置收敛来源）
    CORS(app, origins=config_manager.get('CORS_ORIGINS'))

    # 启用响应压缩（默认对JSON/text等开启）
    Compress(app)

    # 接入限流（基于客户端地址），使用纯内存存储。
    storage_uri = "memory://"
    logger.info("Rate limiter storage: in-memory")

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[config_manager.get('RATE_LIMIT', '60 per minute')],
        storage_uri=storage_uri
    )
    limiter.init_app(app)
    
    # 注册API路由
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # 应用启动时初始化数据库连接
    # 使用全局标志确保初始化只执行一次
    db_initialized = False
    @app.before_request
    def init_database():
        """应用启动时初始化数据库连接"""
        nonlocal db_initialized
        if not db_initialized:
            db_initialized = True
            try:
                # 测试数据库连接并创建必要索引
                db = get_db()
                try:
                    create_indexes(db)
                    logger.info("数据库索引初始化完成")
                except Exception as ie:
                    logger.warning(f"创建索引失败（忽略继续运行）: {ie}")
                logger.info("数据库连接初始化成功")
            except DatabaseError as e:
                logger.error(f"数据库连接初始化失败: {e}")

    # 登录访问控制（除登录页、健康检查、静态与PWA资源外，必须登录）
    @app.before_request
    def require_login():
        if not config_manager.get('AUTH_ENABLED', True):
            return None
        path = request.path or '/'
        # 放行的路径
        if (
            path == '/login' or
            path == '/health' or
            path == '/manifest.json' or
            path == '/sw.js' or
            path.startswith('/i18n/') or
            path.startswith('/static/') or
            path.startswith('/icons/') or
            path.startswith('/favicon')
        ):
            return None
        if session.get('logged_in'):
            return None
        # 未登录：API返回401，页面重定向到登录页
        if path.startswith('/api/'):
            from app.api.response import error_response
            return error_response("Unauthorized", "Please login to access API", 401)
        return redirect(url_for('login'))

    # CSRF 防护：对 API 的写操作检查令牌
    @app.before_request
    def csrf_protect():
        try:
            if not config_manager.get('CSRF_ENABLED', True):
                return None
            method = (request.method or 'GET').upper()
            path = request.path or '/'
            if path.startswith('/api/') and method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                token = request.headers.get('X-CSRF-Token') or request.cookies.get('XSRF-TOKEN')
                sess_token = session.get('csrf_token')
                if (not token) or (not sess_token) or (token != sess_token):
                    from app.api.response import error_response
                    return error_response("CSRF Failed", "Invalid or missing CSRF token", 403)
        except Exception:
            # 避免因异常影响其他请求
            return None
    
    # 全局错误处理
    @app.errorhandler(Exception)
    def handle_exception(e):
        """全局异常处理，统一为 {error, message} 结构"""
        from app.api.response import error_response
        if isinstance(e, HTTPException):
            return error_response(e.name, e.description, e.code)
        elif isinstance(e, ValidationError):
            logger.warning(f"参数校验错误: {str(e)}")
            return error_response("Validation Error", str(e), 400)
        elif isinstance(e, DatabaseError):
            logger.error(f"数据库错误: {str(e)}")
            return error_response("Service Unavailable", "Database temporarily unavailable or slow.", 503)
        else:
            logger.error(f"未预期的错误: {str(e)}")
            return error_response("Internal Server Error", "An unexpected error occurred", 500)
    
    # 添加根路径路由
    @app.route('/')
    def home():
        """应用根路径，渲染前端页面"""
        return render_template('index.html')

    # 登录页与登录处理
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return render_template('login.html')
        # 支持表单与JSON
        form = request.form or {}
        payload = request.get_json(silent=True) or {}
        username = (form.get('username') or payload.get('username') or '').strip()
        password = (form.get('password') or payload.get('password') or '').strip()
        cfg_user = (config_manager.get('AUTH_USERNAME') or 'admin')
        cfg_pass = config_manager.get('AUTH_PASSWORD')
        cfg_hash = config_manager.get('AUTH_PASSWORD_HASH')
        valid = False
        try:
            if cfg_hash:
                from werkzeug.security import check_password_hash
                valid = (username == cfg_user) and check_password_hash(cfg_hash, password)
            else:
                valid = (username == cfg_user) and (cfg_pass is not None) and (password == cfg_pass)
        except Exception:
            valid = False
        if not valid:
            # 传递可翻译的错误键，文本留空由前端 i18n 渲染
            return render_template('login.html', error_key='login_error_invalid_credentials', error='')
        session['logged_in'] = True
        session['user'] = username
        # 生成并设置 CSRF 令牌（同时通过 Cookie 暴露给前端）
        try:
            import secrets
            tok = session.get('csrf_token') or secrets.token_hex(32)
            session['csrf_token'] = tok
        except Exception:
            tok = None
        resp = make_response(redirect(url_for('home')))
        if tok:
            # JS 可读取，为前端附加到请求头
            env = (config_manager.get('FLASK_ENV') or 'development').lower()
            resp.set_cookie('XSRF-TOKEN', tok, httponly=False, samesite='Lax', secure=(env == 'production'))
        return resp

    @app.route('/logout', methods=['GET'])
    def logout():
        session.clear()
        return redirect(url_for('login'))

    # PWA: 以根路径提供 service worker 与 manifest
    @app.route('/sw.js')
    def service_worker():
        return send_from_directory(app.static_folder, 'sw.js')

    @app.route('/manifest.json')
    def manifest():
        from flask import jsonify
        import json
        # 要求显式传入语言参数
        lang = request.args.get('lang')
        if not lang:
            return jsonify({"error": "missing_lang", "message": "lang query parameter is required"}), 400

        # 仅使用外部 JSON 提供的 PWA 元信息，不再使用任何内置后备
        json_path = os.path.join(app.static_folder, 'i18n', f'{lang}.json')
        if not os.path.exists(json_path):
            return jsonify({"error": "not_found", "message": "language json not found"}), 404
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            pwa = ((data.get('meta') or {}).get('pwa')) or None
            if not pwa:
                return jsonify({"error": "missing_pwa_meta", "message": "meta.pwa not provided in language json"}), 400
        except Exception as e:
            logger.error(f"读取语言JSON失败: {e}")
            return jsonify({"error": "internal_error", "message": "failed to read language json"}), 500

        # 语言代码校验并映射 manifest 的 lang 字段
        lang_map = {
            'zh': 'zh-CN',
            'zh-TW': 'zh-TW',
            'en': 'en',
            'ja': 'ja',
            'ko': 'ko'
        }
        if lang not in lang_map:
            return jsonify({"error": "unsupported_lang", "message": "unsupported language code"}), 400
        manifest_lang = lang_map[lang]

        # 构建完整的 manifest（固定结构 + 语言 JSON 的 pwa 字段）
        manifest_json = {
            "id": "stranger.app",
            "lang": manifest_lang,
            "dir": "ltr",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#0b0c10",
            "theme_color": "#4FC3F7",
            "icons": [
                {
                    "src": "/static/icons/icon.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any maskable"
                }
            ],
            "categories": ["productivity", "utilities"],
            "prefer_related_applications": False,
            "name": pwa.get('name'),
            "short_name": pwa.get('short_name'),
            "description": pwa.get('description'),
            "shortcuts": pwa.get('shortcuts')
        }

        response = jsonify(manifest_json)
        response.headers['Content-Type'] = 'application/manifest+json'
        return response

    # 简易 CSRF 令牌获取端点（登录后可用）
    @app.route('/api/csrf', methods=['GET'])
    def get_csrf_token():
        from flask import jsonify
        tok = session.get('csrf_token')
        if not tok:
            return jsonify({"success": False, "error": "csrf_not_set"}), 400
        return jsonify({"success": True, "token": tok})

    # i18n：列出可用语言（基于static/i18n目录JSON自动生成）
    @app.route('/i18n/list')
    def i18n_list():
        from flask import jsonify
        import json
        dir_path = os.path.join(app.static_folder, 'i18n')
        items = []
        try:
            if os.path.exists(dir_path):
                for name in os.listdir(dir_path):
                    if name.endswith('.json'):
                        code = name[:-5]
                        native_label = code
                        try:
                            with open(os.path.join(dir_path, name), 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                native_label = (data.get('meta') or {}).get('native_label') or native_label
                        except Exception:
                            pass
                        items.append({"code": code, "native_label": native_label})
        except Exception as e:
            logger.warning(f"读取语言列表失败: {e}")
        # 仅返回在 static/i18n 中发现的语言（完全外部化）
        return jsonify(items)

    # i18n：返回指定语言的JSON内容
    @app.route('/i18n/<lang>.json')
    def i18n_json(lang: str):
        from flask import jsonify
        import json
        dir_path = os.path.join(app.static_folder, 'i18n')
        file_path = os.path.join(dir_path, f'{lang}.json')
        if not os.path.exists(file_path):
            return jsonify({"error": "not_found", "message": "language json not found"}), 404
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except Exception as e:
            logger.error(f"读取语言JSON失败: {e}")
            return jsonify({"error": "internal_error", "message": "failed to read language json"}), 500
    
    # 健康检查端点
    @app.route('/health')
    def health_check():
        """应用健康检查端点"""
        from app.models.database import check_database_health
        from app.api.response import success, error_response
        try:
            db_health = check_database_health()
            return success({
                "status": "healthy",
                "application": {
                    "name": config_manager.get('APP_NAME', 'Stranger Database Query System'),
                    "version": config_manager.get('APP_VERSION', '2.0.0'),
                    "environment": config_manager.get('FLASK_ENV', 'development')
                },
                "database": db_health
            })
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return error_response("Internal Server Error", "Health check failed", 500, status="unhealthy")
    
    # 安全响应头
    @app.after_request
    def set_security_headers(response):
        try:
            # 基本安全头
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
            response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
            response.headers['Permissions-Policy'] = "geolocation=(), camera=(), microphone=()"
            # 严格 CSP：无内联脚本/事件处理器
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "manifest-src 'self'; "
                "worker-src 'self'"
            )
            response.headers['Content-Security-Policy'] = csp
        except Exception:
            pass
        return response

    return app

# 创建应用实例
app = create_app()