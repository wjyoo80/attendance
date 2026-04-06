# 📋 온라인 출석부

Flask 기반 온라인 출석 관리 시스템입니다.

## 비밀번호

| 역할 | 비밀번호 |
|------|----------|
| 일반 사용자 | `1234` |
| 관리자 | `admin1234` |

> `app.py` 상단의 `PASSWORDS` 딕셔너리에서 변경하세요.

## 로컬 실행

```bash
pip install flask
python app.py
# → http://localhost:5000 접속
```

## 데이터 저장 위치

`data/` 폴더 안에 연도별 JSON 파일로 저장됩니다.

```
data/
  2025.json
  2026.json
```

JSON 구조:
```json
{
  "year": 2025,
  "classes": {
    "중1": ["홍길동", "김철수"],
    "고1": ["이영희"]
  },
  "attendance": {
    "2025-09-01": {
      "중1": ["홍길동"],
      "고1": ["이영희"]
    }
  }
}
```

---

## 🌐 무료 호스팅 방법

### 방법 1: Render.com (추천 ⭐)

1. [render.com](https://render.com) 가입
2. GitHub에 이 프로젝트 올리기
3. New → Web Service → GitHub 연결
4. 설정:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
5. 배포 완료 → 무료 URL 발급

`requirements.txt`에 gunicorn 추가 필요:
```
flask>=3.0.0
gunicorn>=21.0.0
```

**단점**: 15분 비활성 시 슬립 (첫 요청 느림)

---

### 방법 2: Railway.app

1. [railway.app](https://railway.app) 가입 (GitHub 로그인)
2. New Project → Deploy from GitHub
3. 자동 감지 후 배포
4. `Procfile` 생성 필요:

```
web: gunicorn app:app
```

월 $5 크레딧 무료 제공.

---

### 방법 3: PythonAnywhere (초보자 추천)

1. [pythonanywhere.com](https://pythonanywhere.com) 무료 가입
2. Files 탭에서 파일 업로드
3. Web 탭 → Add a new web app → Flask 선택
4. WSGI 설정 파일에서 앱 경로 지정
5. Reload → 완료

무료 플랜: `username.pythonanywhere.com` 도메인 제공  
**단점**: 외부 API 호출 제한 있음 (이 앱은 해당 없음)

---

### 방법 4: Fly.io

```bash
# fly CLI 설치 후
fly launch
fly deploy
```

소규모 앱 무료 티어 제공.

---

### 데이터 영속성 주의사항

Render, Railway 등 무료 플랜은 **파일 시스템이 재배포 시 초기화**될 수 있습니다.  
데이터를 안전하게 보존하려면:

- **PythonAnywhere**: 파일이 유지됨 (추천)
- **Render**: 유료 Disk 옵션 추가 필요
- 또는 SQLite / 외부 DB (예: Supabase 무료 플랜) 로 마이그레이션 권장
