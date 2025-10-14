import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CrawlerError(Exception):
    """爬虫模块通用异常，占位与统一异常类型。"""
    pass


def get_crawler() -> requests.Session:
    """返回一个带重试、默认超时与代理支持的 requests 会话。
    可通过环境变量配置：
    - CRAWLER_TIMEOUT（默认 8 秒）
    - CRAWLER_RETRIES（默认 3 次）
    - CRAWLER_BACKOFF（默认 0.5 指数退避系数）
    - HTTP_PROXY/HTTPS_PROXY 或 CRAWLER_HTTP_PROXY/CRAWLER_HTTPS_PROXY
    """
    try:
        default_timeout = float(os.getenv("CRAWLER_TIMEOUT", os.getenv("REQUEST_TIMEOUT", "8")))
        retries = int(os.getenv("CRAWLER_RETRIES", "3"))
        backoff = float(os.getenv("CRAWLER_BACKOFF", "0.5"))

        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        })

        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        s.mount("https://", adapter)
        s.mount("http://", adapter)

        http_proxy = os.getenv("CRAWLER_HTTP_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        https_proxy = os.getenv("CRAWLER_HTTPS_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or http_proxy
        if http_proxy or https_proxy:
            s.proxies.update({
                "http": http_proxy,
                "https": https_proxy,
            })
        s.trust_env = True

        _orig_get = s.get
        _orig_post = s.post

        def _with_default_timeout(fn):
            def _inner(url, *args, **kwargs):
                if "timeout" not in kwargs:
                    kwargs["timeout"] = default_timeout
                return fn(url, *args, **kwargs)
            return _inner

        s.get = _with_default_timeout(_orig_get)
        s.post = _with_default_timeout(_orig_post)
        return s
    except Exception as e:
        raise CrawlerError(f"init crawler failed: {e}")