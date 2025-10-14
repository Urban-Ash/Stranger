import os
import logging
from typing import Any, Dict
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 合并后的配置管理器，实现原config_manager.py的全部功能
class ConfigManager:
    """配置管理器：统一管理应用程序的配置信息"""
    _instance = None
    _config_cache: Dict[str, Any] = {}
    _initialized = False
    _env_specific_config: Dict[str, Dict[str, Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            load_dotenv()
            self._init_env_config_classes()
            self._load_config()

    def _init_env_config_classes(self) -> None:
        base_config: Dict[str, Any] = {
            'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
            'FLASK_HOST': os.getenv('FLASK_HOST', '0.0.0.0'),
            'FLASK_PORT': int(os.getenv('FLASK_PORT', 5000)),
            'FLASK_DEBUG': os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
            'LOG_FORMAT': os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'),
            'API_RATE_LIMIT': os.getenv('API_RATE_LIMIT', '100 per hour'),
            'MAX_QUERY_RESULTS': int(os.getenv('MAX_QUERY_RESULTS', '50')),
            'CACHE_TIMEOUT': int(os.getenv('CACHE_TIMEOUT', '300')),
            'CORS_ORIGINS': os.getenv('CORS_ORIGINS', '*').split(',')
        }

        dev_config = base_config.copy()
        dev_config.update({'FLASK_DEBUG': True, 'LOG_LEVEL': 'DEBUG'})

        prod_config = base_config.copy()
        prod_config.update({'FLASK_DEBUG': False, 'LOG_LEVEL': 'WARNING', 'API_RATE_LIMIT': '50 per hour'})

        test_config = base_config.copy()
        test_config.update({'TESTING': True})

        self._env_specific_config = {
            'development': dev_config,
            'production': prod_config,
            'testing': test_config,
            'default': dev_config
        }

    def _load_config(self) -> None:
        # 加载环境默认值
        current_env = os.getenv('FLASK_ENV', 'development')
        env_config = self._env_specific_config.get(current_env, self._env_specific_config['default'])
        self._config_cache.update(env_config)
        # 使用环境变量覆盖（dotenv 已在 __init__ 加载）
        self._load_env_config()
        # 不再读取 config.json，统一改为使用环境变量管理
        logger.info("Configuration loaded from environment (dotenv), config.json disabled")

    def _load_env_config(self) -> None:
        # 已移除Mongo相关环境项

        # 移除Redis相关环境项

        self._config_cache['FLASK_APP'] = os.getenv('FLASK_APP', self._config_cache.get('FLASK_APP', 'run.py'))
        self._config_cache['FLASK_ENV'] = os.getenv('FLASK_ENV', self._config_cache.get('FLASK_ENV', 'development'))
        self._config_cache['FLASK_DEBUG'] = os.getenv('FLASK_DEBUG', str(self._config_cache.get('FLASK_DEBUG'))).lower() == 'true'
        self._config_cache['SECRET_KEY'] = os.getenv('SECRET_KEY', self._config_cache.get('SECRET_KEY', 'dev_key_change_in_production'))

        self._config_cache['DEEPSEEK_API_KEY'] = os.getenv('DEEPSEEK_API_KEY', self._config_cache.get('DEEPSEEK_API_KEY', ''))
        self._config_cache['DEEPSEEK_API_URL'] = os.getenv('DEEPSEEK_API_URL', self._config_cache.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/chat/completions'))
        self._config_cache['DEEPSEEK_MODEL'] = os.getenv('DEEPSEEK_MODEL', self._config_cache.get('DEEPSEEK_MODEL', 'deepseek-chat'))

        self._config_cache['LOG_LEVEL'] = os.getenv('LOG_LEVEL', self._config_cache.get('LOG_LEVEL', 'INFO'))
        self._config_cache['LOG_FILE'] = os.getenv('LOG_FILE', self._config_cache.get('LOG_FILE', 'app.log'))

        self._config_cache['APP_NAME'] = os.getenv('APP_NAME', self._config_cache.get('APP_NAME', 'Stranger Database Query System'))
        self._config_cache['APP_VERSION'] = os.getenv('APP_VERSION', self._config_cache.get('APP_VERSION', '2.0.0'))
        self._config_cache['MAX_RESULTS'] = int(os.getenv('MAX_RESULTS', str(self._config_cache.get('MAX_RESULTS', '50'))))

        self._config_cache['CSRF_ENABLED'] = os.getenv('CSRF_ENABLED', str(self._config_cache.get('CSRF_ENABLED', 'True'))).lower() == 'true'
        self._config_cache['RATE_LIMIT'] = os.getenv('RATE_LIMIT', self._config_cache.get('RATE_LIMIT', '100/hour'))

        # 数据库连接（PG_*）从环境加载
        self._config_cache['PG_HOST'] = os.getenv('PG_HOST', self._config_cache.get('PG_HOST', 'localhost'))
        self._config_cache['PG_PORT'] = int(os.getenv('PG_PORT', str(self._config_cache.get('PG_PORT', '5432'))))
        self._config_cache['PG_DATABASE'] = os.getenv('PG_DATABASE', self._config_cache.get('PG_DATABASE', 'stranger'))
        self._config_cache['PG_USER'] = os.getenv('PG_USER', self._config_cache.get('PG_USER', 'postgres'))
        self._config_cache['PG_PASSWORD'] = os.getenv('PG_PASSWORD', self._config_cache.get('PG_PASSWORD', 'postgres'))

        # 认证相关（可选）
        self._config_cache['AUTH_ENABLED'] = os.getenv('AUTH_ENABLED', 'true').lower() in ('1','true','yes')
        self._config_cache['AUTH_USERNAME'] = os.getenv('AUTH_USERNAME', self._config_cache.get('AUTH_USERNAME', 'admin'))
        self._config_cache['AUTH_PASSWORD'] = os.getenv('AUTH_PASSWORD', self._config_cache.get('AUTH_PASSWORD', 'admin'))
        self._config_cache['AUTH_PASSWORD_HASH'] = os.getenv('AUTH_PASSWORD_HASH', self._config_cache.get('AUTH_PASSWORD_HASH', ''))

    def get(self, key: str, default: Any = None) -> Any:
        return self._config_cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config_cache[key] = value

    # 已移除：MongoDB配置

    # 移除：Redis配置方法

    def get_flask_config(self) -> Dict[str, Any]:
        return {
            'SECRET_KEY': self.get('SECRET_KEY'),
            'DEBUG': self.get('FLASK_DEBUG'),
            'ENV': self.get('FLASK_ENV'),
            'HOST': self.get('FLASK_HOST', '0.0.0.0'),
            'PORT': self.get('FLASK_PORT', 5000),
            'LOG_LEVEL': self.get('LOG_LEVEL'),
            'LOG_FORMAT': self.get('LOG_FORMAT'),
            'CORS_ORIGINS': self.get('CORS_ORIGINS')
        }

    def get_deepseek_config(self) -> Dict[str, Any]:
        return {
            'api_key': self.get('DEEPSEEK_API_KEY'),
            'api_url': self.get('DEEPSEEK_API_URL'),
            'model': self.get('DEEPSEEK_MODEL')
        }

    def get_log_config(self) -> Dict[str, Any]:
        return {
            'level': self.get('LOG_LEVEL'),
            'file': self.get('LOG_FILE'),
            'format': self.get('LOG_FORMAT')
        }

    def get_cache_config(self) -> Dict[str, Any]:
        return {
            'memory_cache_size': self.get('CACHE_MEMORY_SIZE', 1000),
            'default_ttl': self.get('CACHE_TIMEOUT', 300),
            'cleanup_interval': self.get('CACHE_CLEANUP_INTERVAL', 300)
        }

    def refresh(self) -> None:
        self._load_config()
        logger.info("Configuration refreshed")

    def get_all(self) -> Dict[str, Any]:
        return self._config_cache.copy()

# 全局配置管理器实例
# merged: config_manager is defined below in this file
config_manager = ConfigManager()

# 配置映射 - 保持向后兼容性
config = {
    'development': type('DevelopmentConfig', (), {}),
    'production': type('ProductionConfig', (), {}),
    'testing': type('TestingConfig', (), {}),
    'default': type('DevelopmentConfig', (), {})
}

# 为了保持向后兼容性，提供Config类
class Config:
    # 动态加载配置
    @classmethod
    def __getattr__(cls, name):
        # 尝试直接从配置管理器获取配置
        value = config_manager.get(name)
        if value is not None:
            return value
        # 如果配置不存在，尝试映射命名约定
        mapping = {
            'FLASK_HOST': 'HOST',
            'FLASK_PORT': 'PORT',
            'LOG_LEVEL': 'LOG_LEVEL',
            'LOG_FORMAT': 'LOG_FORMAT',
            'API_RATE_LIMIT': 'RATE_LIMIT',
            'MAX_QUERY_RESULTS': 'MAX_RESULTS'
        }
        if name in mapping:
            return config_manager.get(mapping[name])
        # 如果还是没有找到，返回一些合理的默认值
        defaults = {
            'SECRET_KEY': 'dev-secret-key-change-in-production',
            'FLASK_HOST': '0.0.0.0',
            'FLASK_PORT': 5000,
            'FLASK_DEBUG': False,
            # 移除Mongo默认值
            'LOG_LEVEL': 'INFO',
            'LOG_FORMAT': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            'API_RATE_LIMIT': '100 per hour',
            'MAX_QUERY_RESULTS': 50,
            'REDIS_URL': 'redis://localhost:6379/0',
            'CACHE_TIMEOUT': 300,
            'CORS_ORIGINS': ['*']
        }
        return defaults.get(name)

class DevelopmentConfig(Config):
    @classmethod
    def __getattr__(cls, name):
        if name == 'FLASK_DEBUG':
            return True
        if name == 'LOG_LEVEL':
            return 'DEBUG'
        return super().__getattr__(name)

class ProductionConfig(Config):
    @classmethod
    def __getattr__(cls, name):
        if name == 'FLASK_DEBUG':
            return False
        if name == 'LOG_LEVEL':
            return 'WARNING'
        if name == 'API_RATE_LIMIT':
            return '50 per hour'
        return super().__getattr__(name)

class TestingConfig(Config):
    @classmethod
    def __getattr__(cls, name):
        if name == 'TESTING':
            return True
        # 移除Mongo测试配置
        return super().__getattr__(name)

config['development'] = DevelopmentConfig
config['production'] = ProductionConfig
config['testing'] = TestingConfig
config['default'] = DevelopmentConfig

# 从config_manager加载环境变量
def load_dotenv():
    """加载环境变量的兼容方法"""
    pass

# 获取当前环境
def get_current_config():
    """获取当前环境的配置"""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])