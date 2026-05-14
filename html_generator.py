#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 보고서 생성기
DART 수집 데이터를 HTML 템플릿 플레이스홀더에 채워 넣음

플레이스홀더 목록:
  [N]                - 순번
  [발주처명]          - 발주처 회사명
  [프로젝트명]        - 계약/프로젝트명
  [예상규모]          - 계약금액(억원)
  [CM사]             - CM사명 (없으면 "-")
  [설계사]            - 설계사명 (없으면 "-")
  [발주처_출처URL]    - 발주처 출처 링크
  [규모_출처URL]      - 계약금액 출처 링크
  [CM사명]            - CM사명
  [CM_출처URL]        - CM사 출처 링크
  [설계사명]          - 설계사명
  [설계사_출처URL]    - 설계사 출처 링크
  [AI 요약 내용 3~5줄] - AI 분석 요약
"""

import re
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Optional


class HtmlReportGenerator:

    def __init__(self, template_path: str, output_dir: str = "output"):
        self.template_path = template_path
        self.output_dir    = output_dir
        os.makedirs(output_dir, exist_ok=True)

        with open(template_path, "r", encoding="utf-8") as f:
            self.template_html = f.read()
        print(f"[HTML] 템플릿 로드: {template_path}")

    # ----------------------------------------------------------
    # 단일 수주 카드 블록 치환
    # ----------------------------------------------------------
    def _fill_card(self, card_html: str, item: dict, seq: int) -> str:
        """카드 블록의 플레이스홀더를 실제 데이터로 치환"""
        source_url  = item.get("source_url", "#")
        client_name = item.get("client_name") or item.get("corp_name", "-")
        project     = item.get("project_name") or item.get("report_nm", "-")
        amount      = item.get("contract_amount", "-")
        ai_summary  = item.get("ai_summary", "AI 요약 준비 중")
        cm_name     = item.get("cm_name", "-")
        design_name = item.get("design_name", "-")

        amount_str  = f"{amount:,.1f}" if isinstance(amount, (int, float)) else str(amount)

        replacements = {
            "[N]":                   str(seq),
            "[발주처명]":             client_name,
            "[프로젝트명]":           project,
            "[예상규모]":             amount_str,
            "[CM사]":                 cm_name,
            "[설계사]":               design_name,
            "[발주처_출처URL]":       source_url,
            "[규모_출처URL]":         source_url,
            "[CM사명]":               cm_name,
            "[CM_출처URL]":           source_url,
            "[설계사명]":             design_name,
            "[설계사_출처URL]":       source_url,
            "[AI 요약 내용 3~5줄]":   ai_summary,
        }

        result = card_html
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        return result

    # ----------------------------------------------------------
    # 섹션별 카드 반복 블록 처리
    # ----------------------------------------------------------
    def _find_card_template(self, section_html: str) -> Optional[str]:
        """
        템플릿 HTML에서 반복 카드 블록 탐지
        [발주처명] 플레이스홀더가 포함된 최소 div 블록을 반환
        """
        soup = BeautifulSoup(section_html, "html.parser")
        for tag in soup.find_all(class_="nc-card"):
            return str(tag.parent)  # 카드 wrapper 반환
        return None

    # ----------------------------------------------------------
    # 전체 보고서 생성
    # ----------------------------------------------------------
    def generate(
        self,
        dart_data:    list[dict],
        report_date:  Optional[str] = None,
        output_name:  Optional[str] = None,
    ) -> str:
        """
        dart_data : DartCrawler.run() 반환값
        returns   : 생성된 HTML 파일 경로
        """
        if report_date is None:
            report_date = datetime.now().strftime("%Y년 %m월 %d일")
        if output_name is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            output_name = f"weekly_report_{ts}.html"

        html = self.template_html

        # ── 날짜 치환 ──────────────────────────────────────────
        html = html.replace("2026년 5월 13일", report_date)
        html = html.replace("2026.05.12", datetime.now().strftime("%Y.%m.%d"))

        # ── 수주건수 치환 ──────────────────────────────────────
        html = html.replace(
            "수주정보 건수",
            f"수주정보 건수: {len(dart_data)}건"
        )

        # ── 섹션별 데이터 분배 ─────────────────────────────────
        # 섹션 분류 키워드 매핑 (필요시 확장)
        section_map = {
            "sec-1": ["전자", "반도체", "부품", "디스플레이"],
            "sec-2": ["화학", "에너지", "배터리", "정유"],
            "sec-3": ["통신", "IT", "소프트웨어", "데이터"],
            "sec-4": ["LX", "LG"],
            "sec-5": ["CR", "크레인"],
            "sec-6": ["GMP", "제약", "바이오"],
            "sec-7": ["생산", "공장", "제조"],
            "sec-8": ["DC", "데이터센터"],
            "sec-9": ["플랜트", "설비"],
        }

        # 섹션 분류
        section_data: dict[str, list] = {k: [] for k in section_map}
        unclassified = []

        for item in dart_data:
            keyword_text = (
                item.get("corp_name", "") + " " +
                item.get("report_nm", "") + " " +
                (item.get("project_name") or "") + " " +
                (item.get("client_name") or "")
            )
            classified = False
            for sec_id, keywords in section_map.items():
                if any(kw in keyword_text for kw in keywords):
                    section_data[sec_id].append(item)
                    classified = True
                    break
            if not classified:
                unclassified.append(item)

        # 미분류는 sec-1에 추가
        section_data["sec-1"].extend(unclassified)

        # ── 카드 블록 반복 생성 ────────────────────────────────
        # 플레이스홀더 카드를 실제 데이터 카드로 교체
        soup = BeautifulSoup(html, "html.parser")

        global_seq = 1
        for sec_id, items in section_data.items():
            section = soup.find(id=sec_id)
            if not section:
                continue
            if not items:
                continue

            # 기존 nc-card 플레이스홀더 찾기
            sample_cards = section.find_all(class_="nc-card")
            if not sample_cards:
                continue

            # 부모 wrapper 찾기
            card_wrapper_parent = sample_cards[0].find_parent()
            if not card_wrapper_parent:
                continue

            # 기존 카드 제거
            for card in sample_cards:
                wrapper = card.find_parent()
                if wrapper and wrapper != card_wrapper_parent:
                    wrapper.decompose()
                else:
                    card.decompose()

            # 실제 데이터로 새 카드 생성
            for item in items:
                card_html = CARD_TEMPLATE.format(
                    seq         = global_seq,
                    client_name = item.get("client_name") or item.get("corp_name", "-"),
                    project     = item.get("project_name") or item.get("report_nm", "-"),
                    amount      = (f"{item['contract_amount']:,.1f}"
                                   if isinstance(item.get("contract_amount"), (int, float))
                                   else "-"),
                    cm_name     = item.get("cm_name", "-"),
                    design_name = item.get("design_name", "-"),
                    source_url  = item.get("source_url", "#"),
                    ai_summary  = item.get("ai_summary", "요약 준비 중"),
                )
                new_tag = BeautifulSoup(card_html, "html.parser")
                card_wrapper_parent.append(new_tag)
                global_seq += 1

        # ── 파일 저장 ──────────────────────────────────────────
        output_path = os.path.join(self.output_dir, output_name)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

        print(f"[HTML] 보고서 생성 완료: {output_path}")
        return output_path


# ── 카드 HTML 템플릿 ──────────────────────────────────────────
CARD_TEMPLATE = """
<div class="nc-card">
  <div class="nc-header">{project}</div>
  <div class="nc-body">
    <div class="nc-field">
      <span class="nc-label">발주처명</span>
      <span class="nc-value">{client_name}
        <a class="nc-src" href="{source_url}" target="_blank">출처</a>
      </span>
    </div>
    <div class="nc-field">
      <span class="nc-label">예상 규모</span>
      <span class="nc-value">{amount} 억 원
        <a class="nc-src" href="{source_url}" target="_blank">출처</a>
      </span>
    </div>
    <div class="nc-field">
      <span class="nc-label">CM사</span>
      <span class="nc-value">{cm_name}
        <a class="nc-src" href="{source_url}" target="_blank">출처</a>
      </span>
    </div>
    <div class="nc-field">
      <span class="nc-label">설계사</span>
      <span class="nc-value">{design_name}
        <a class="nc-src" href="{source_url}" target="_blank">출처</a>
      </span>
    </div>
    <div class="nc-field">
      <span class="nc-label">AI 요약</span>
      <span class="nc-value">{ai_summary}</span>
    </div>
  </div>
</div>
"""


if __name__ == "__main__":
    # 테스트 더미 데이터
    dummy_data = [
        {
            "corp_name":        "삼성전자",
            "report_nm":        "단일판매·공급계약체결",
            "rcept_dt":         "20260512",
            "client_name":      "Apple Inc.",
            "project_name":     "갤럭시 S 시리즈 부품 공급 계약",
            "contract_amount":  5200.0,
            "source_url":       "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260512000001",
            "ai_summary":       "삼성전자가 Apple사에 스마트폰 부품을 공급하는 계약을 체결함.\n계약금액 5,200억원 규모.\n공급 기간은 2026년 6월부터 2027년 5월까지.",
        },
        {
            "corp_name":        "현대건설",
            "report_nm":        "수주공시",
            "rcept_dt":         "20260511",
            "client_name":      "한국전력공사",
            "project_name":     "북방계통 변전소 신설공사",
            "contract_amount":  3800.0,
            "source_url":       "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260511000002",
            "ai_summary":       "현대건설이 한국전력으로부터 변전소 신설공사를 수주.\n계약금액 3,800억원.\n2026년 7월 착공 예정.",
        },
    ]

    gen = HtmlReportGenerator(
        template_path="report_r5_팀색상_맨위로.html",
        output_dir="output"
    )
    path = gen.generate(dummy_data)
    print(f"생성 파일: {path}")
