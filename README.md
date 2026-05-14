# 📊 주간 수주정보 리포트 자동화

## 폴더 구조
```
project-root/
├── .github/
│   └── workflows/
│       └── weekly_report.yml      ← GitHub Actions 스케줄 트리거
│
├── template/
│   └── report_r5_팀색상_맨위로.html  ← 원본 HTML 템플릿
│
├── output/                         ← 생성된 보고서 저장 폴더
│   ├── weekly_report_20260514.html
│   └── dart_analyzed.json
│
├── dart_crawler.py    ← DART 공시 수집
├── ai_analyzer.py     ← AI 분석 (GPT/Claude)
├── html_generator.py  ← HTML 템플릿 채우기
├── mailer.py          ← 이메일 발송
├── main.py            ← 전체 파이프라인
├── requirements.txt
└── README.md
```

## GitHub Secrets 설정
Settings → Secrets and variables → Actions → New repository secret

| Secret 이름    | 값 예시                        | 설명              |
|---------------|-------------------------------|-------------------|
| DART_API_KEY  | abc123def456...               | OpenDART API키    |
| AI_API_KEY    | sk-...                        | OpenAI or Claude  |
| AI_PROVIDER   | openai                        | openai / claude   |
| AI_MODEL      | gpt-4o-mini                   | 모델명 (선택)     |
| SMTP_HOST     | smtp.gmail.com                | SMTP 서버         |
| SMTP_PORT     | 587                           | SMTP 포트         |
| SMTP_USER     | your@gmail.com                | 발신 이메일       |
| SMTP_PASS     | xxxx xxxx xxxx xxxx           | Gmail 앱 비밀번호 |
| EMAIL_TO      | a@co.kr,b@co.kr               | 수신자 (,구분)    |

## 실행 스케줄
- 매주 수요일 오전 9시 (KST)
- 수동 실행: Actions 탭 → Run workflow

## DART API 키 발급
1. https://opendart.fss.or.kr 접속
2. 회원가입 → 인증키 신청
3. 즉시 발급 (무료)
