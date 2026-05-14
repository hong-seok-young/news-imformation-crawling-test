#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주간 수주정보 리포트 - 메인 실행 파일
실행 순서:
  1. DART 수주공시 크롤링
  2. AI 분석 (cm사, 설계사, 요약)
  3. HTML 보고서 생성
  4. (선택) 이메일 발송
"""

import os
import sys
import json
from datetime import datetime

from dart_crawler   import DartCrawler
from ai_analyzer    import AiAnalyzer
from html_generator import HtmlReportGenerator


def main():
    print("=" * 60)
    print("  주간 수주정보 리포트 생성 시작")
    print(f"  실행시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ── 환경변수 읽기 ──────────────────────────────────────────
    DART_API_KEY   = os.environ["DART_API_KEY"]
    AI_API_KEY     = os.environ["AI_API_KEY"]
    AI_PROVIDER    = os.getenv("AI_PROVIDER", "openai")   # openai | claude
    AI_MODEL       = os.getenv("AI_MODEL", "")            # 빈값이면 기본모델
    OUTPUT_DIR     = os.getenv("OUTPUT_DIR", "output")
    DAYS_BACK      = int(os.getenv("DAYS_BACK", "7"))
    TEMPLATE_PATH  = os.getenv("TEMPLATE_PATH", "template/report_r5_팀색상_맨위로.html")

    # ── STEP 1: DART 크롤링 ────────────────────────────────────
    print("\n[STEP 1] DART 수주공시 크롤링...")
    crawler   = DartCrawler(api_key=DART_API_KEY)
    dart_data = crawler.run(days_back=DAYS_BACK)

    if not dart_data:
        print("⚠️  수집된 수주공시 없음. 종료합니다.")
        sys.exit(0)

    # 중간 결과 저장 (디버그용)
    with open(f"{OUTPUT_DIR}/dart_raw.json", "w", encoding="utf-8") as f:
        json.dump(dart_data, f, ensure_ascii=False, indent=2)

    # ── STEP 2: AI 분석 ────────────────────────────────────────
    print(f"\n[STEP 2] AI 분석 ({AI_PROVIDER}/{AI_MODEL or '기본모델'})...")
    analyzer     = AiAnalyzer(
        api_key  = AI_API_KEY,
        provider = AI_PROVIDER,
        model    = AI_MODEL or None,
    )
    analyzed_data = analyzer.analyze_batch(dart_data, delay=0.8)

    # 분석 결과 저장
    with open(f"{OUTPUT_DIR}/dart_analyzed.json", "w", encoding="utf-8") as f:
        json.dump(analyzed_data, f, ensure_ascii=False, indent=2)

    # ── STEP 3: HTML 보고서 생성 ───────────────────────────────
    print("\n[STEP 3] HTML 보고서 생성...")
    report_date = datetime.now().strftime("%Y년 %m월 %d일")
    output_name = f"weekly_report_{datetime.now().strftime('%Y%m%d')}.html"

    generator   = HtmlReportGenerator(
        template_path = TEMPLATE_PATH,
        output_dir    = OUTPUT_DIR,
    )
    html_path = generator.generate(
        dart_data   = analyzed_data,
        report_date = report_date,
        output_name = output_name,
    )

    print(f"\n✅ 보고서 생성 완료: {html_path}")

    # ── STEP 4: (선택) 이메일 발송 ────────────────────────────
    SEND_EMAIL = os.getenv("SEND_EMAIL", "false").lower() == "true"
    if SEND_EMAIL:
        print("\n[STEP 4] 이메일 발송...")
        from mailer import Mailer
        mailer = Mailer(
            smtp_host = os.environ["SMTP_HOST"],
            smtp_port = int(os.getenv("SMTP_PORT", "587")),
            username  = os.environ["SMTP_USER"],
            password  = os.environ["SMTP_PASS"],
        )
        recipients = os.environ["EMAIL_TO"].split(",")
        mailer.send(
            to_list   = recipients,
            subject   = f"[주간 수주리포트] {report_date}",
            html_path = html_path,
        )
        print(f"✅ 이메일 발송 완료 → {recipients}")

    print("\n" + "=" * 60)
    print("  전체 파이프라인 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
