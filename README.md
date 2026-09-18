# 레시피 검색 · Streamlit + Neo4j Aura

## 지금 실행

1. 저장소 루트의 `.streamlit/secrets.toml`에 접속 정보를 입력합니다.
   처음 설정한다면 `.streamlit/secrets.toml.example`을 복사해 값을 채웁니다.

   ```toml
   NEO4J_URI = "neo4j+ssc://YOUR_INSTANCE.databases.neo4j.io"
   NEO4J_USER = "YOUR_USER"
   NEO4J_PASSWORD = "YOUR_PASSWORD"
   NEO4J_DATABASE = "YOUR_DATABASE"
   ```

   현재 연결한 인스턴스의 DB 이름은 `11769529`입니다. `neo4j`로 설정하면 DatabaseNotFound가 발생합니다.
   URI는 Aura에서 받은 값을 사용합니다. 앱의 비밀번호는 로컬 `secrets.toml` 또는 Cloud Secrets에서 관리합니다.
   앱은 `.env`에서 연결 정보를 읽지 않습니다. 파일을 처음 만든 뒤에는 실행 중인 Streamlit을 재시작하세요.

2. 실행합니다.

   ```powershell
   .venv/Scripts/python.exe -m streamlit run app.py
   ```

   새 환경이라면 먼저 `python -m pip install -r deploy/requirements.txt`를 실행하고,
   `python -m streamlit run app.py`로 시작합니다.

3. `http://localhost:8501`에서 음식·분류·포함/제외 재료로 검색합니다.

## Cloud 배포

1. 앱 파일을 GitHub에 올립니다. `.env`와 실제 `secrets.toml`은 제외합니다.
2. [Streamlit Community Cloud](https://share.streamlit.io/) → **Create app** → 저장소/브랜치 선택.
3. **Main file path: `deploy/app.py`**, **Python: 3.12**.
4. **Advanced settings → Secrets**에 `.streamlit/secrets.toml.example` 형식으로 실제 접속 정보를 입력합니다.
5. **Deploy** 후 음식 검색과 상세 보기를 확인합니다.

`deploy/app.py`는 루트 `app.py`를 실행하는 진입점입니다. 같은 폴더의 가벼운
`requirements.txt`를 사용해 노트북용 torch/Jupyter까지 설치하지 않도록 했습니다.
Cloud는 진입점 폴더의 의존성 파일을 먼저 찾고, 같은 폴더에서는 `uv.lock`을
`requirements.txt`보다 먼저 사용합니다.
([공식 의존성 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies),
[Secrets 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management))

## 연결 구조와 현재 기능

```text
사용자 → Streamlit app.py → Neo4j Python Driver → Aura
DishGroup -HAS_TYPE-> DishType -HAS_DISH-> Dish -INGREDIENT-> Ingredient
```

- 실제 Aura에서는 `Dish` 하나가 개별 레시피이며 `recipe_uid`로 식별됩니다.
- 검색: 제목/음식 이름 부분 일치, 음식 분류, 포함 재료 전체 일치, 제외 재료 미포함.
- 재료 검색은 `Ingredient.name_normalized`와 정확히 일치합니다. `파`가 `대파`로 자동 확장되지 않습니다.
- 정렬: 원본 조회수 내림차순. AI 추천 점수가 아닙니다.
- 상세: 수량·단위·손질·재료 원문, 조리 순서, 원본 링크.
- DB에는 조회만 수행합니다. 모든 입력은 Cypher 매개변수로 전달합니다.
- 데이터 목록/상세는 5분, 검색은 1분 캐시합니다. 사이드바에서 새로고침할 수 있습니다.
- 앱의 연결 정보는 `st.secrets`로 읽습니다. 로컬은 `.streamlit/secrets.toml`, 배포 환경은 Cloud Secrets를 사용합니다.
- 지식그래프 품질 평가가 끝나도 검색/추천 품질 검증은 별도로 필요합니다.

## 벡터 임베딩 완료 후

현재 앱은 벡터/LLM 없이 실행됩니다. 연결 확인 시점에는 벡터 인덱스가 없었습니다.
팀원에게 다음을 전달받은 뒤 `recipe_graph.py`의 검색 함수 옆에 벡터 검색을 추가합니다.

| 필요한 정보 | 예시 / 확인 사항 |
|---|---|
| 임베딩 모델 | 정확한 공급자·모델 이름, 쿼리 임베딩도 동일 모델 사용 |
| 벡터 차원 | 인덱스 차원과 쿼리 벡터 차원이 같아야 함 |
| 인덱스 이름 / 상태 | 실제 생성한 이름, `ONLINE` |
| 노드 / 벡터 속성 | 실제 라벨과 속성 이름, `recipe_uid`로 상세 연결 가능 여부 |
| 임베딩 입력 내용 | 제목만인지, 재료·조리법 포함인지 |

현재 검색은 그대로 유지하고 자연어 검색을 추가한 뒤,
샘플 질문의 상위 결과와 재료 조건 준수 여부를 검증합니다.

## 검증

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_recipe_app.py
# 실제 Aura 읽기 전용 통합 검사까지 실행
$env:TEST_AURA = "1"
.venv/Scripts/python.exe -m unittest discover -s tests -p test_recipe_app.py
```

화면은 `app.py`, DB 연결/조회는 `recipe_graph.py`, 배포 의존성은 `deploy/requirements.txt`에서 관리합니다.
