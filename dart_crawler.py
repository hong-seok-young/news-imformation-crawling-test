#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DART OpenDART API 수주공시 크롤러
- 단일판매·공급계약체결 공시 수집
- 계약금액, 발주처, 프로젝트명 파싱
"""

import requests
import urllib3
import json
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class DartCrawler:
    BASE_API   = "https://opendart.fss.or.kr/api"
    BASE_DART  = "https://dart.fss.or.kr"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://dart.fss.or.kr/",
        })

    # ----------------------------------------------------------
    # 1) 공시 목록 조회
    # ----------------------------------------------------------
    def get_disclosure_list(
        self,
        days_back: int = 7,
        report_type: str = "B",          # B = 주요사항보고
        page_count: int = 100,
    ) -> list[dict]:
        """OpenDART API로 최근 N일 공시 목록 반환"""
        end_de   = datetime.now().strftime("%Y%m%d")
        start_de = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

        params = {
            "crtfc_key":   self.api_key,
            "pblntf_ty":   report_type,
            "bgn_de":      start_de,
            "end_de":      end_de,
            "page_no":     1,
            "page_count":  page_count,
        }

        try:
            resp = self.session.get(
                f"{self.BASE_API}/list.json",
                params=params, timeout=20, verify=False
            )
            data = resp.json()
        except Exception as e:
            print(f"[DART] 목록 조회 오류: {e}")
            return []

        if data.get("status") != "000":
            print(f"[DART] API 오류: {data.get('message','')}")
            return []

        items = data.get("list", [])
        print(f"[DART] 조회된 공시: {len(items)}건 ({start_de}~{end_de})")
        return items

    # ----------------------------------------------------------
    # 2) 수주 관련 공시 필터링
    # ----------------------------------------------------------
    def filter_order_disclosures(self, items: list[dict]) -> list[dict]:
        """수주·계약 관련 공시만 필터링"""
        KEYWORDS = [
            "단일판매", "공급계약", "수주", "계약체결",
            "납품계약", "서비스계약", "유지보수계약",
        ]
        result = []
        for item in items:
            report_nm = item.get("report_nm", "")
            if any(kw in report_nm for kw in KEYWORDS):
                result.append(item)
        print(f"[DART] 수주 관련 필터링: {len(result)}건")
        return result

    # ----------------------------------------------------------
    # 3) 공시 원문 상세 파싱
    # ----------------------------------------------------------
    def parse_disclosure_detail(self, rcept_no: str) -> dict:
        """
        공시 원문 HTML 파싱
        → 계약금액 / 발주처 / 계약내용 / 계약기간 추출
        """
        url = f"{self.BASE_DART}/dsaf001/main.do?rcpNo={rcept_no}"
        try:
            resp = self.session.get(url, timeout=20, verify=False)
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  [파싱오류] {rcept_no}: {e}")
            return {}

        # iframe src 찾기 (공시 본문은 iframe 내부)
        iframe = soup.find("iframe", id="ifrViewer")
        if not iframe:
            return self._parse_from_html(soup, rcept_no)

        iframe_src = iframe.get("src", "")
        if not iframe_src.startswith("http"):
            iframe_src = self.BASE_DART + iframe_src

        try:
            resp2 = self.session.get(iframe_src, timeout=20, verify=False)
            soup2 = BeautifulSoup(resp2.text, "html.parser")
            return self._parse_from_html(soup2, rcept_no)
        except Exception as e:
            print(f"  [iframe 파싱오류] {rcept_no}: {e}")
            return {}

    def _parse_from_html(self, soup: BeautifulSoup, rcept_no: str) -> dict:
        """HTML에서 핵심 필드 추출"""
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        result = {
            "rcept_no": rcept_no,
            "contract_amount": None,   # 계약금액 (억원)
            "client_name":     None,   # 발주처명
            "project_name":    None,   # 프로젝트/계약명
            "contract_period": None,   # 계약기간
            "description":     None,   # 계약내용 요약
            "source_url":      f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
        }

        for i, line in enumerate(lines):
            # ── 계약금액 ──────────────────────────────────────
            if "계약금액" in line:
                amount_match = re.search(
                    r"([\d,]+)\s*(원|백만원|억원|천만원|조원)?", line
                )
                if amount_match:
                    raw = amount_match.group(1).replace(",", "")
                    unit = amount_match.group(2) or "원"
                    val  = int(raw)
                    # 억원 단위로 통일
                    if unit == "원":          val = round(val / 1e8, 1)
                    elif unit == "백만원":    val = round(val / 100,  1)
                    elif unit == "천만원":    val = round(val / 10,   1)
                    elif unit == "조원":      val = val * 10000
                    result["contract_amount"] = val

            # ── 발주처 / 계약상대방 ───────────────────────────
            if any(kw in line for kw in ["발주처", "계약상대방", "매출처", "공급받는자"]):
                if i + 1 < len(lines):
                    candidate = lines[i + 1]
                    if len(candidate) > 2 and len(candidate) < 60:
                        result["client_name"] = candidate

            # ── 계약내용 / 프로젝트명 ────────────────────────
            if any(kw in line for kw in ["계약내용", "공급품목", "납품품목", "서비스명"]):
                if i + 1 < len(lines):
                    result["project_name"] = lines[i + 1][:80]

            # ── 계약기간 ──────────────────────────────────────
            if "계약기간" in line or "납기" in line:
                date_match = re.search(
                    r"(\d{4})[.\-/년](\d{1,2})[.\-/월](\d{1,2})", line
                )
                if date_match:
                    result["contract_period"] = date_match.group(0)

        return result

    # ----------------------------------------------------------
    # 4) 전체 파이프라인 실행
    # ----------------------------------------------------------
    def run(self, days_back: int = 7) -> list[dict]:
        """
        메인 실행:
        공시목록 수집 → 필터링 → 상세파싱 → 결과 반환
        """
        print("=" * 50)
        print("[DART 수주공시 크롤러 시작]")
        print("=" * 50)

        # ① 목록 조회
        items = self.get_disclosure_list(days_back=days_back)
        if not items:
            return []

        # ② 수주 관련만 필터
        orders = self.filter_order_disclosures(items)
        if not orders:
            print("[DART] 수주 공시 없음")
            return []

        # ③ 상세 파싱
        results = []
        for idx, item in enumerate(orders[:30], 1):   # 최대 30건
            rcept_no   = item.get("rcept_no", "")
            corp_name  = item.get("corp_name", "")
            report_nm  = item.get("report_nm", "")
            rcept_dt   = item.get("rcept_dt", "")

            print(f"  [{idx:02d}] {corp_name} | {report_nm} | {rcept_dt}")

            detail = self.parse_disclosure_detail(rcept_no)
            merged = {
                "corp_name":    corp_name,
                "report_nm":    report_nm,
                "rcept_dt":     rcept_dt,
                "rcept_no":     rcept_no,
                **detail,
            }
            results.append(merged)
            time.sleep(0.5)   # 서버 부하 방지

        print(f"\n[DART] 파싱 완료: {len(results)}건")
        return results


# ----------------------------------------------------------
# 직접 실행 테스트
# ----------------------------------------------------------
if __name__ == "__main__":
    import os

    API_KEY = os.getenv("DART_API_KEY", "YOUR_DART_API_KEY_HERE")
    crawler = DartCrawler(api_key=API_KEY)
    data    = crawler.run(days_back=7)

    print("\n=== 수집 결과 샘플 ===")
    for d in data[:3]:
        print(json.dumps(d, ensure_ascii=False, indent=2))
