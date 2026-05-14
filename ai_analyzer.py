#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 분석기
- OpenAI GPT 또는 Anthropic Claude 선택 가능
- 공시 텍스트 → CM사/설계사/요약 추출
"""

import json
import os
import time
from typing import Optional


class AiAnalyzer:
    """
    AI API로 DART 공시 데이터를 분석
    provider: "openai" | "claude"
    """

    def __init__(self, api_key: str, provider: str = "openai", model: str = None):
        self.api_key  = api_key
        self.provider = provider.lower()

        if self.provider == "openai":
            self.model = model or "gpt-4o-mini"
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            except ImportError:
                raise ImportError("pip install openai 필요")

        elif self.provider == "claude":
            self.model = model or "claude-3-5-haiku-20241022"
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError("pip install anthropic 필요")

        else:
            raise ValueError(f"지원하지 않는 provider: {provider}")

        print(f"[AI] 분석기 초기화: {self.provider} / {self.model}")

    # ----------------------------------------------------------
    # 공시 단건 분석
    # ----------------------------------------------------------
    def analyze_disclosure(self, item: dict) -> dict:
        """
        공시 정보 딕셔너리를 받아 AI 분석 결과 추가 후 반환
        추가 필드: ai_summary, cm_name, design_name
        """
        corp_name   = item.get("corp_name", "")
        report_nm   = item.get("report_nm", "")
        client_name = item.get("client_name") or ""
        project     = item.get("project_name") or ""
        amount      = item.get("contract_amount", "")
        source_url  = item.get("source_url", "")

        prompt = f"""
다음은 DART 공시 정보입니다. 아래 JSON 형식으로만 응답하세요.

## 공시 정보
- 공시기업: {corp_name}
- 공시유형: {report_nm}
- 발주처:   {client_name}
- 내용:     {project}
- 계약금액: {amount}억원
- 출처:     {source_url}

## 응답 형식 (JSON만, 설명 없이)
{{
  "cm_name":    "CM사명 (없으면 null)",
  "design_name":"설계사명 (없으면 null)",
  "ai_summary": "3~5줄 요약. 핵심만 간결하게."
}}

규칙:
- CM사와 설계사는 공시 내용에 명시된 경우만 기재, 아니면 null
- ai_summary는 한국어로, 줄바꿈은 \\n 사용
- JSON 외 다른 텍스트 절대 포함 금지
"""

        try:
            result_text = self._call_api(prompt)
            # JSON 파싱
            result_text = result_text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            parsed = json.loads(result_text)
        except Exception as e:
            print(f"  [AI 분석 오류] {corp_name}: {e}")
            parsed = {
                "cm_name":    None,
                "design_name": None,
                "ai_summary": f"{corp_name}의 {report_nm} 공시입니다."
            }

        return {**item, **parsed}

    # ----------------------------------------------------------
    # 배치 분석
    # ----------------------------------------------------------
    def analyze_batch(self, items: list[dict], delay: float = 1.0) -> list[dict]:
        """여러 공시 일괄 분석 (rate limit 방지 delay)"""
        results = []
        for idx, item in enumerate(items, 1):
            corp = item.get("corp_name", "")
            print(f"  [AI {idx:02d}/{len(items):02d}] {corp} 분석 중...")
            analyzed = self.analyze_disclosure(item)
            results.append(analyzed)
            if idx < len(items):
                time.sleep(delay)
        print(f"[AI] 배치 분석 완료: {len(results)}건")
        return results

    # ----------------------------------------------------------
    # API 호출 (OpenAI / Claude 분기)
    # ----------------------------------------------------------
    def _call_api(self, prompt: str) -> str:
        if self.provider == "openai":
            resp = self.client.chat.completions.create(
                model    = self.model,
                messages = [{"role": "user", "content": prompt}],
                temperature = 0.2,
                max_tokens  = 500,
            )
            return resp.choices[0].message.content

        elif self.provider == "claude":
            resp = self.client.messages.create(
                model      = self.model,
                max_tokens = 500,
                messages   = [{"role": "user", "content": prompt}],
            )
            return resp.content[0].text


if __name__ == "__main__":
    # 테스트
    analyzer = AiAnalyzer(
        api_key  = os.getenv("AI_API_KEY", "YOUR_KEY"),
        provider = os.getenv("AI_PROVIDER", "openai"),
    )

    dummy = [{
        "corp_name":       "현대건설",
        "report_nm":       "단일판매·공급계약체결",
        "client_name":     "한국전력공사",
        "project_name":    "북방계통 변전소 신설공사",
        "contract_amount": 3800.0,
        "source_url":      "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260511000002",
    }]

    results = analyzer.analyze_batch(dummy)
    print(json.dumps(results, ensure_ascii=False, indent=2))
