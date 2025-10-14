import logging
import json
from typing import List, Dict, Any, Optional

from openai import OpenAI

from config.config import config_manager

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    pass


class AIService:
    """DeepSeek-based AI service implemented via OpenAI SDK."""

    def __init__(self) -> None:
        cfg = config_manager.get_deepseek_config()
        self.api_key: str = cfg.get("api_key", "")
        self.base_url: str = cfg.get("api_url", "https://api.deepseek.com")
        self.model: str = cfg.get("model", "deepseek-chat")

        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY is not configured. AI features will be disabled.")
            self.enabled = False
            self.client: Optional[OpenAI] = None
        else:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            self.enabled = True
            logger.info("DeepSeek AI client initialized successfully.")

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """Generic chat completion wrapper.
        Returns content string when stream=False; returns the raw stream iterator when stream=True.
        """
        if not self.enabled or not self.client:
            raise AIServiceError("DeepSeek API key not configured or client not initialized.")

        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            **({"max_tokens": max_tokens} if max_tokens else {})
        )

        if stream:
            return response
        return response.choices[0].message.content

    def enhance_customer_data(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use DeepSeek to analyze and enhance customer data.
        Returns a concise AI summary for UI display; keep structure simple for robustness.
        """
        if not isinstance(customer_data, dict):
            raise AIServiceError("customer_data must be a JSON object.")
        if not self.enabled:
            raise AIServiceError("AI service disabled: missing DEEPSEEK_API_KEY.")

        system_prompt = "You are a helpful assistant for CRM data enrichment."
        user_prompt = (
            "Analyze and enhance the following customer data. "
            "Provide a concise summary (<=120 words), potential data corrections, and recommended tags.\n\n"
            f"Data: {json.dumps(customer_data, ensure_ascii=False)}\n\n"
            "Return plain text, with short bullet points."
        )

        content = self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            temperature=0.3,
        )

        return {
            "ai_summary": content,
            "model": self.model,
            "provider": "deepseek",
        }

    def assess_confidence(self, subject_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess data confidence (高/中/低) with percentage and full report.
        Input: all queried information as JSON.
        Output JSON structure:
          {
            "level": "高|中|低",
            "percentage": 0-100,
            "report": "full text",
            "model": str,
            "provider": "deepseek"
          }
        """
        if not isinstance(subject_data, dict):
            raise AIServiceError("subject_data must be a JSON object.")
        if not self.enabled:
            raise AIServiceError("AI service disabled: missing DEEPSEEK_API_KEY.")

        system_prompt = (
            "你是一名资深 OSINT（公开来源情报）分析师，在本 OSINT 信息检索平台上执行证据驱动的置信度评估。"
            "评估需以来源可追溯性、交叉验证、一致性与时效性为核心，并清晰标注不确定性与风险。"
        )
        user_prompt = (
            "请基于以下主体的聚合数据与平台预校验结果（位于 validations 字段）进行 OSINT 置信度评估：\n"
            f"数据JSON：{json.dumps(subject_data, ensure_ascii=False)}\n\n"
            "评估方法与维度：\n"
            "1) 来源谱系与证据权重：标注数据来源类型（官方/第三方/社交/泄露/推断）、可验证性与覆盖度；\n"
            "2) 时效性与变更迹象：识别数据时间戳、最近变更、过期或失效线索；\n"
            "3) 结构与一致性校验：身份证格式/地区码、手机号归属、邮箱域名与MX、亲属/公司等字段间的一致性与交叉印证；\n"
            "4) 矛盾与伪造信号：重复/冲突字段、异常模式、生成式伪造迹象；\n"
            "5) 风险与合规提示：PII敏感度、可能的数据泄露源、误用风险与建议；\n"
            "6) 结论：给出置信度等级（高/中/低）与百分比（0-100），并明确关键证据与主要不确定性。\n\n"
            "返回格式：\n"
            "第一行：等级（高/中/低）+ 空格 + 百分比整数；\n"
            "随后多行：详细分析报告（不少于150字），包含：\n"
            "- 证据摘要（来源类型与权重）；\n"
            "- 交叉验证结果与时效性；\n"
            "- 主要不确定性与风险；\n"
            "- 建议的进一步核验步骤（如需要）。"
        )

        content = self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            temperature=0.2,
        )

        # 解析第一行的等级与百分比
        level_map = {"高": "高", "中": "中", "低": "低"}
        level = "中"
        percentage = 60
        report = content.strip() if isinstance(content, str) else str(content)
        first_line = report.splitlines()[0] if report else ""
        import re
        m = re.search(r"(高|中|低)[^\d]*(\d{1,3})", first_line)
        if m:
            level = level_map.get(m.group(1), "中")
            try:
                percentage = max(0, min(100, int(m.group(2))))
            except Exception:
                percentage = 60

        return {
            "level": level,
            "percentage": percentage,
            "report": report,
            "model": self.model,
            "provider": "deepseek",
        }


# Global service instance
ai_service = AIService()