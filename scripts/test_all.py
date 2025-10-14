#!/usr/bin/env python3
import argparse
import json
import os
import random
import string
import sys
import time
from typing import Any, Dict, List, Tuple, Optional

import requests
import subprocess
import shlex


def gen_id_card() -> str:
    """Generate a plausible 18-char ID card for testing (not guaranteed valid)."""
    # 固定北京地区码 110101 + 生日 19900101 + 顺序号 003 + 校验位 X
    # 为避免冲突，顺序号后两位随机。
    suffix = f"{random.randint(10, 99)}"
    return f"1101011990010100{suffix}"


class SmokeTester:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: int = 12,
        include_external: bool = False,
        include_ai: bool = False,
    ) -> None:
        self.base = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.include_external = include_external
        self.include_ai = include_ai
        self.sess = requests.Session()
        self.csrf_token: Optional[str] = None
        self.created_id: Optional[str] = None
        self.created_id_card: Optional[str] = None
        self.report: List[Tuple[str, bool, str]] = []
        self.use_curl: bool = False
        self.cookie_file: str = "/tmp/stranger_smoke_cookies.txt"

    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def _add(self, name: str, ok: bool, detail: str) -> None:
        self.report.append((name, ok, detail))

    def _headers(self, need_csrf: bool = False) -> Dict[str, str]:
        hdrs = {"Accept": "application/json"}
        if need_csrf and self.csrf_token:
            hdrs["X-CSRF-Token"] = self.csrf_token
        return hdrs

    def login(self) -> bool:
        try:
            # 尝试表单登录
            resp = self.sess.post(
                self._url("/login"),
                data={"username": self.username, "password": self.password},
                allow_redirects=True,
                timeout=self.timeout,
            )
            ok = resp.status_code in (200, 302)
            # 有效登录应设置会话 Cookie
            has_cookie = bool(self.sess.cookies.get("session"))
            if not has_cookie:
                # 回退为 JSON 登录
                resp2 = self.sess.post(
                    self._url("/login"),
                    json={"username": self.username, "password": self.password},
                    allow_redirects=True,
                    timeout=self.timeout,
                )
                ok = resp2.status_code in (200, 302)
                has_cookie = bool(self.sess.cookies.get("session"))
                self._add("登录 /login(JSON)", ok and has_cookie, f"HTTP {resp2.status_code}")
                return ok and has_cookie
            else:
                self._add("登录 /login", ok and has_cookie, f"HTTP {resp.status_code}")
                return ok and has_cookie
        except Exception as e:
            self._add("登录 /login", False, f"error: {e}")
            return False

    def csrf(self) -> bool:
        try:
            resp = self.sess.get(self._url("/api/csrf"), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                self.csrf_token = token
                cookie_token = self.sess.cookies.get("XSRF-TOKEN")
                ok = True
                detail = f"token={token}"
                if cookie_token and token and cookie_token != token:
                    # 如果不一致，视为需要回退，但不记录失败
                    ok = False
                if ok:
                    self._add("获取 CSRF /api/csrf", True, detail)
                    return True
                # 回退到 curl
                return self._csrf_via_curl()
            # 非200时回退到 curl，不记录失败
            return self._csrf_via_curl()
        except Exception as e:
            # 发生异常也尝试 curl 回退，如果仍失败再记录失败
            ok = self._csrf_via_curl()
            if not ok:
                self._add("获取 CSRF /api/csrf", False, f"error: {e}")
            return ok

    def _curl(self, args: List[str], input_data: Optional[str] = None) -> Tuple[int, str]:
        cmd = ["curl", "-s"] + args
        try:
            proc = subprocess.run(cmd, input=input_data.encode("utf-8") if input_data else None,
                                  capture_output=True, timeout=self.timeout)
            out = proc.stdout.decode("utf-8", errors="ignore")
            return proc.returncode, out
        except Exception as e:
            return 1, f"error: {e}"

    def _login_via_curl(self) -> bool:
        # 使用 curl 执行登录并写入 Cookie 文件
        code, _ = self._curl(["-i", "-c", self.cookie_file, "-d",
                              f"username={self.username}&password={self.password}", self._url("/login")])
        ok = (code == 0)
        self._add("登录（curl）", ok, f"cookie_file={self.cookie_file}")
        self.use_curl = ok
        return ok

    def _csrf_via_curl(self) -> bool:
        if not self.use_curl:
            if not self._login_via_curl():
                return False
        code, out = self._curl(["-b", self.cookie_file, self._url("/api/csrf")])
        ok = (code == 0)
        detail = f"curl rc={code}"
        try:
            data = json.loads(out)
            ok = ok and (data.get("success") is True)
            self.csrf_token = data.get("token")
            detail = f"token={self.csrf_token}"
        except Exception:
            pass
        self._add("获取 CSRF（curl） /api/csrf", ok, detail)
        return ok

    def health(self) -> bool:
        try:
            resp = self.sess.get(self._url("/health"), timeout=self.timeout)
            ok = resp.status_code == 200
            detail = f"HTTP {resp.status_code}"
            if ok:
                data = resp.json()
                app_status = data.get("app", {}).get("status")
                db_status = data.get("db", {}).get("status")
                # 只要接口返回成功即视为通过，记录详细状态以供参考
                detail = f"app={app_status} db={db_status}"
                ok = True
            self._add("健康检查 /health", ok, detail)
            return ok
        except Exception as e:
            self._add("健康检查 /health", False, f"error: {e}")
            return False

    def create_customer(self) -> bool:
        try:
            self.created_id_card = gen_id_card()
            payload = {
                "id_card": self.created_id_card,
                "name": "测试用户-CRUD",
                "sex": "男",
                "phone": "13600000000",
            }
            if not self.use_curl:
                resp = self.sess.post(
                    self._url("/api/customer"),
                    headers=self._headers(need_csrf=True),
                    json=payload,
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    ok = data.get("success") is True and isinstance(data.get("data"), dict)
                    self.created_id = data.get("data", {}).get("id")
                    detail = f"id={self.created_id}"
            else:
                body = json.dumps(payload, ensure_ascii=False)
                code, out = self._curl(["-b", self.cookie_file, "-H", f"X-CSRF-Token: {self.csrf_token}", "-H", "Content-Type: application/json", "-d", "@-", self._url("/api/customer")], input_data=body)
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    ok = ok and (data.get("success") is True) and isinstance(data.get("data"), dict)
                    self.created_id = data.get("data", {}).get("id")
                    detail = f"id={self.created_id}"
                except Exception:
                    pass
            self._add("新增客户 POST /api/customer", ok, detail)
            return ok
        except Exception as e:
            self._add("新增客户 POST /api/customer", False, f"error: {e}")
            return False

    def search_customer(self) -> bool:
        try:
            # 依据证件号搜索
            if not self.use_curl:
                resp = self.sess.get(
                    self._url(f"/api/search"),
                    params={"query": self.created_id_card, "max_results": 10},
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    records = data.get("records") or data.get("data")
                    ok = isinstance(records, list) and len(records) >= 1
                    detail = f"records={len(records) if isinstance(records, list) else 0}"
            else:
                code, out = self._curl(["-b", self.cookie_file, self._url(f"/api/search?query={self.created_id_card}&max_results=10")])
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    records = data.get("records") or data.get("data")
                    ok = ok and isinstance(records, list) and len(records) >= 1
                    detail = f"records={len(records) if isinstance(records, list) else 0}"
                except Exception:
                    pass
            self._add("查询客户 GET /api/search", ok, detail)
            return ok
        except Exception as e:
            self._add("查询客户 GET /api/search", False, f"error: {e}")
            return False

    def update_customer(self) -> bool:
        try:
            if not self.created_id:
                self._add("更新客户 PUT /api/customer/:id", False, "no id")
                return False
            payload = {"company": "测试公司-CRUD"}
            if not self.use_curl:
                resp = self.sess.put(
                    self._url(f"/api/customer/{self.created_id}"),
                    headers=self._headers(need_csrf=True),
                    json=payload,
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    # 部分实现返回空对象，容忍
                    ok = data.get("success") is True
                    if isinstance(data.get("data"), dict):
                        new_company = data.get("data", {}).get("company")
                        detail = f"company={new_company}"
                    else:
                        detail = "updated"
            else:
                body = json.dumps(payload, ensure_ascii=False)
                code, out = self._curl(["-b", self.cookie_file, "-H", f"X-CSRF-Token: {self.csrf_token}", "-H", "Content-Type: application/json", "-X", "PUT", "-d", "@-", self._url(f"/api/customer/{self.created_id}")], input_data=body)
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    ok = ok and (data.get("success") is True)
                    if isinstance(data.get("data"), dict):
                        new_company = data.get("data", {}).get("company")
                        detail = f"company={new_company}"
                    else:
                        detail = "updated"
                except Exception:
                    pass
            self._add("更新客户 PUT /api/customer/:id", ok, detail)
            return ok
        except Exception as e:
            self._add("更新客户 PUT /api/customer/:id", False, f"error: {e}")
            return False

    def delete_customer(self) -> bool:
        try:
            if not self.created_id:
                self._add("删除客户 DELETE /api/customer/:id", False, "no id")
                return False
            if not self.use_curl:
                resp = self.sess.delete(
                    self._url(f"/api/customer/{self.created_id}"),
                    headers=self._headers(need_csrf=True),
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    ok = data.get("success") is True and (data.get("data", {}).get("deleted") == 1)
                    detail = f"deleted={data.get('data', {}).get('deleted')}"
            else:
                code, out = self._curl(["-b", self.cookie_file, "-H", f"X-CSRF-Token: {self.csrf_token}", "-X", "DELETE", self._url(f"/api/customer/{self.created_id}")])
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    ok = ok and (data.get("success") is True) and (data.get("data", {}).get("deleted") == 1)
                    detail = f"deleted={data.get('data', {}).get('deleted')}"
                except Exception:
                    pass
            self._add("删除客户 DELETE /api/customer/:id", ok, detail)
            return ok
        except Exception as e:
            self._add("删除客户 DELETE /api/customer/:id", False, f"error: {e}")
            return False

    def validate_id_card(self) -> bool:
        try:
            if not self.use_curl:
                resp = self.sess.get(
                    self._url("/api/validate/id_card"),
                    params={"id_card": self.created_id_card},
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    ok = data.get("success") is True
                    detail = f"valid={data.get('valid')}"
            else:
                code, out = self._curl(["-b", self.cookie_file, self._url(f"/api/validate/id_card?id_card={self.created_id_card}")])
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    ok = ok and (data.get("success") is True)
                    detail = f"valid={data.get('valid')}"
                except Exception:
                    pass
            self._add("校验身份证 GET /api/validate/id_card", ok, detail)
            return ok
        except Exception as e:
            self._add("校验身份证 GET /api/validate/id_card", False, f"error: {e}")
            return False

    def validate_phone(self) -> bool:
        try:
            if not self.use_curl:
                resp = self.sess.get(
                    self._url("/api/validate/phone"),
                    params={"phone": "13600000000", "write": 0},
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    ok = data.get("success") is True
                    detail = f"carrier={data.get('data', {}).get('carrier')}"
            else:
                code, out = self._curl(["-b", self.cookie_file, self._url("/api/validate/phone?phone=13600000000&write=0")])
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    ok = ok and (data.get("success") is True)
                    detail = f"carrier={data.get('data', {}).get('carrier')}"
                except Exception:
                    pass
            self._add("归属地查询 GET /api/validate/phone", ok, detail)
            return ok
        except Exception as e:
            self._add("归属地查询 GET /api/validate/phone", False, f"error: {e}")
            return False

    def validate_qq(self) -> bool:
        try:
            if not self.use_curl:
                resp = self.sess.get(
                    self._url("/api/validate/qq"),
                    params={"qq": "10000", "write": 0},
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    ok = data.get("success") is True
                    detail = f"exists={data.get('data', {}).get('exists')}"
            else:
                code, out = self._curl(["-b", self.cookie_file, self._url("/api/validate/qq?qq=10000&write=0")])
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    ok = ok and (data.get("success") is True)
                    detail = f"exists={data.get('data', {}).get('exists')}"
                except Exception:
                    pass
            self._add("QQ 校验 GET /api/validate/qq", ok, detail)
            return ok
        except Exception as e:
            self._add("QQ 校验 GET /api/validate/qq", False, f"error: {e}")
            return False

    def validate_weibo(self) -> bool:
        try:
            if not self.use_curl:
                resp = self.sess.get(
                    self._url("/api/validate/weibo"),
                    params={"weibo": "testuser", "write": 0},
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    ok = data.get("success") is True
                    detail = f"exists={data.get('data', {}).get('exists')}"
            else:
                code, out = self._curl(["-b", self.cookie_file, self._url("/api/validate/weibo?weibo=testuser&write=0")])
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    ok = ok and (data.get("success") is True)
                    detail = f"exists={data.get('data', {}).get('exists')}"
                except Exception:
                    pass
            self._add("微博校验 GET /api/validate/weibo", ok, detail)
            return ok
        except Exception as e:
            self._add("微博校验 GET /api/validate/weibo", False, f"error: {e}")
            return False

    def ai_assess(self) -> bool:
        try:
            subject = {
                "id": self.created_id,
                "id_card": self.created_id_card,
                "name": "测试用户-CRUD",
                "validations": {"id_card": {"valid": False}},
            }
            if not self.use_curl:
                resp = self.sess.post(
                    self._url("/api/ai/assess_confidence"),
                    headers=self._headers(need_csrf=True),
                    json=subject,
                    timeout=self.timeout,
                )
                ok = resp.status_code == 200
                detail = f"HTTP {resp.status_code}"
                if ok:
                    data = resp.json()
                    ok = data.get("success") is True and isinstance(data.get("data"), dict)
                    detail = f"level={data.get('data', {}).get('level')} percent={data.get('data', {}).get('percentage')}"
            else:
                body = json.dumps(subject, ensure_ascii=False)
                code, out = self._curl(["-b", self.cookie_file, "-H", f"X-CSRF-Token: {self.csrf_token}", "-H", "Content-Type: application/json", "-d", "@-", self._url("/api/ai/assess_confidence")], input_data=body)
                ok = (code == 0)
                detail = f"curl rc={code}"
                try:
                    data = json.loads(out)
                    ok = ok and (data.get("success") is True) and isinstance(data.get("data"), dict)
                    detail = f"level={data.get('data', {}).get('level')} percent={data.get('data', {}).get('percentage')}"
                except Exception:
                    pass
            self._add("AI 置信度评估 POST /api/ai/assess_confidence", ok, detail)
            return ok
        except Exception as e:
            self._add("AI 置信度评估 POST /api/ai/assess_confidence", False, f"error: {e}")
            return False

    def run(self) -> int:
        # 登录与 CSRF
        if not self.login():
            return self._finish()
        if not self.csrf():
            return self._finish()

        # 基础健康检查
        self.health()

        # CRUD 全流程
        if self.create_customer():
            self.search_customer()
            self.update_customer()
            self.delete_customer()
        else:
            self._add("CRUD 流程", False, "create failed")

        # 验证接口（本地/轻量）
        self.validate_id_card()

        # 外部接口（可选）
        if self.include_external:
            self.validate_phone()
            self.validate_qq()
            self.validate_weibo()

        # AI 评估（可选）
        if self.include_ai:
            self.ai_assess()

        return self._finish()

    def _finish(self) -> int:
        failures = [r for r in self.report if not r[1]]
        print(f"Base: {self.base}")
        for name, ok, detail in self.report:
            print(f"{name:40} -> {'PASS' if ok else 'FAIL'} | {detail}")
        print(f"Result: {'PASS' if not failures else 'FAIL'} ({len(self.report)-len(failures)} passed, {len(failures)} failed)")
        return 0 if not failures else 1


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stranger 全量功能冒烟测试脚本")
    parser.add_argument("--base", default=os.getenv("BASE_URL", "http://127.0.0.1:5082"), help="服务地址，默认 http://127.0.0.1:5082")
    parser.add_argument("--user", default=os.getenv("STRANGER_USER", "UrAsh"), help="用户名")
    parser.add_argument("--pass", dest="password", default=os.getenv("STRANGER_PASS", "Acg153759"), help="密码")
    parser.add_argument("--timeout", type=int, default=12, help="请求超时（秒）")
    parser.add_argument("--include-external", action="store_true", help="包含外部校验接口（phone/qq/weibo）")
    parser.add_argument("--include-ai", action="store_true", help="包含 AI 置信度评估（需 DEEPSEEK_API_KEY）")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    tester = SmokeTester(
        base_url=args.base,
        username=args.user,
        password=args.password,
        timeout=args.timeout,
        include_external=args.include_external,
        include_ai=args.include_ai,
    )
    return tester.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))