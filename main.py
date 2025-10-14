#!/usr/bin/env python3
import os
import sys
import logging
from app.app import create_app

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_project():
    """设置项目环境"""
    # 添加项目根目录到Python路径
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.append(project_root)
    
    # 确保配置目录存在
    config_dir = os.path.join(project_root, 'config')
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        logger.warning(f"Config directory created at: {config_dir}")

def main():
    """主入口函数"""
    try:
        # 设置项目环境
        setup_project()
        
        # 创建Flask应用
        app = create_app()
        
        # 获取配置的主机和端口
        host = app.config.get('HOST', '0.0.0.0')
        port = app.config.get('PORT', 8080)
        debug = app.config.get('DEBUG', False)
        
        logger.info(f"Starting server on {host}:{port} (debug={debug})")
        
        # 启动服务器
        app.run(host=host, port=port, debug=debug)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()