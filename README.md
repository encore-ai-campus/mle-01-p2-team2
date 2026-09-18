# 🍳 레시피 지식그래프 기반 요리 검색 서비스

요리를 해보고 싶지만 어떤 음식을 만들 수 있을지 떠올리기 어려운 사람을 위한 레시피 검색 프로젝트입니다.

사용자가 음식명, 음식 분류, 가지고 있는 재료 또는 제외하고 싶은 재료를 입력하면 Neo4j 지식그래프에 연결된 레시피를 검색할 수 있습니다. 레시피를 음식 분류·레시피·재료 사이의 관계로 표현하고, Streamlit 화면에서 검색 결과와 상세 조리 정보를 제공합니다.

추가로 레시피 문서를 임베딩하여 Neo4j 벡터 인덱스에서 의미적으로 가까운 레시피를 찾는 벡터 검색 모듈도 구현했습니다.

~~~text
Python · Neo4j · Cypher · Streamlit · OpenAI Embeddings · Vector Search
~~~

## 1. 프로젝트 소개

이 프로젝트는 다음과 같은 상황을 해결하기 위해 시작했습니다.

- 요리를 처음 시작해 어떤 레시피를 선택해야 할지 모를 때
- 냉장고에 있는 재료로 만들 수 있는 음식을 찾고 싶을 때
- 특정 재료를 반드시 포함하거나 제외한 레시피를 찾고 싶을 때
- 비슷한 재료를 사용하는 다른 레시피를 추천받고 싶을 때

레시피를 단순한 문서 목록으로 저장하지 않고 다음과 같은 그래프로 연결했습니다.

~~~text
대분류(DishGroup)
        ↓ HAS_TYPE
중분류(DishType)
        ↓ HAS_DISH
레시피(Dish)
        ↓ INGREDIENT
재료(Ingredient)
~~~

이를 통해 특정 레시피의 재료를 조회하거나, 특정 재료를 사용하는 레시피를 역으로 탐색할 수 있습니다.

## 2. 프로젝트 구조

~~~text
원본 레시피 데이터
        ↓
JSON 파싱 및 전처리
        ↓
대분류·중분류 생성
        ↓
Neo4j 지식그래프 구축
        ↓
레시피 임베딩 및 벡터 인덱스 구축
        ↓
Streamlit 검색 서비스
~~~

주요 파일은 다음과 같습니다.

| 경로 | 역할 |
|---|---|
| app.py | Streamlit 검색·상세 레시피·통계 화면 |
| recipe_graph.py | Neo4j 연결 및 Cypher 조회 함수 |
| /대분류,중분류+neo4j 적재.ipynb | 대분류·중분류 생성 및 그래프 적재 |
| /백터임베딩.ipynb | 레시피 임베딩 생성, Neo4j 적재, 벡터 인덱스 생성 |
| app.py | 질의 임베딩 기반 벡터 검색 및 답변 생성 |
| image/온톨로지.png | 그래프 스키마 이미지 |
| image/visualisation1.svg | 대분류 → 중분류 → 레시피 → 재료 예시 |
| image/visualisation2.svg | 특정 레시피의 분류와 재료 예시 |
| image/visualisation3.svg | 특정 재료를 사용하는 레시피 예시 |
| image/visualisation4.svg | 공통 재료 기반 레시피 추천 예시 |

## 3. 데이터 수집

데이터 출처는 [만개의레시피](https://www.10000recipe.com/)입니다.

| 항목 | 내용 |
|---|---|
| 원본 데이터 | recipes_10000.jsonl |
| 최초 수집 건수 | 10,000건 |
| JSON 파싱 후 유효 데이터 | 9,997건 |
| 제외 데이터 | 파싱할 수 없는 JSON 3건 |

대분류·중분류 및 Neo4j 적재 노트북은 /input/recipes_10000_cleaned.jsonl을 입력으로 사용하며, 해당 파일에서 실제로 읽은 레시피 수는 9,997건입니다.

## 4. 데이터 전처리 및 정제

전처리 단계에서는 레시피를 그래프와 검색에 사용할 수 있도록 원본 필드를 정리했습니다.

### 주요 전처리 항목

- 음식명 및 재료명 정규화
- 일반 재료와 양념 분리
- 수량·단위·범위 표현 정리
- 손질 방법과 원문 재료 정보 보존
- 인분 및 조리 시간의 최소·최대값 추출
- 조리 단계 정렬 및 cooking_method 문자열 생성
- 그래프 적재 가능 여부를 나타내는 graph_eligible 관리
- 제목, 조리법, 재료가 없는 레코드 필터링

정제된 재료 데이터는 다음과 같은 형태로 그래프 적재에 사용됩니다.

~~~json
{
  "name_normalized": "마늘",
  "amount_text": "5쪽",
  "amount_min": 5.0,
  "amount_max": 5.0,
  "unit_normalized": "쪽",
  "preparation": ["다진"]
}
~~~

재료명 정규화와 수량 파싱은 그래프 적재 노트북의 입력 단계에서 이미 만들어진 ingredients_clean, seasonings_clean 필드를 사용합니다. 대분류,중분류+neo4j 적재.ipynb 자체는 이 필드를 다시 정규화하지 않고 그래프 행으로 변환합니다.

### 데이터 감소 결과

~~~text
최초 수집 데이터       10,000건
        ↓ JSON 파싱
분류 노트북 입력         9,997건
        ↓ 대분류·중분류 생성
분류 결과                9,997건
        ↓ 유효 레시피 필터,데이터를 뽑을 수 없는 값 삭제
최종 정제 데이터         9,381건
        ↓ 분류 누락 1건 제외
Neo4j Dish 적재 대상     9,380건
~~~

분류 노트북의 최종 필터 조건은 다음과 같습니다.

~~~text
graph_eligible == True
title 값 존재
cooking_method 값 존재
ingredients_clean 값 존재
~~~

노트북 실행 결과는 다음과 같습니다.

| 단계 | 건수 |
|---|---:|
| 노트북 입력 | 9,997 |
| LLM 분류 성공 | 9,982 |
| LLM 분류 실패 | 15 |
| 최종 정제 JSONL | 9,381 |
| Neo4j Dish 적재 대상 | 9,380 |

약 600건 정도는 파일이 형식이 이상하거나 , url 만 있는것만 다수 하여서 삭제

## 5. 대분류 및 중분류 생성

### 대분류(dish_group)

LLM의 구조화된 출력으로 생성하며, 다음 21개 범주 중 하나를 선택합니다.

~~~text
국, 찌개, 탕, 전골, 조림, 볶음, 구이, 찜,
튀김, 전/부침, 무침, 샐러드, 밥, 죽, 면/국수,
절임/장아찌, 소스/양념, 빵/베이킹, 디저트, 음료, 기타
~~~

대분류는 조리 과정 중 일부 단계가 아니라 최종적으로 완성되는 음식의 형태를 기준으로 결정합니다.

~~~text
김치찌개   → 찌개
닭볶음탕   → 탕
갈비찜     → 찜
오징어볶음 → 볶음
미역국     → 국
~~~

### 중분류(dish_type)

중분류는 레시피의 대표 음식명을 생성합니다. 제목, 설명, 정제된 재료명, 조리 과정을 참고하며 광고성·부가 표현은 제거합니다.

~~~text
돼지고기 김치찌개 맛내는 비법
→ 돼지고기김치찌개

엄마의 레시피, 소고기 미역국 끓이는 법
→ 소고기미역국

오징어 볶음, 향과 맛이 일품! 백종원 오징어 볶음
→ 오징어볶음
~~~

분류 입력에는 제목, 설명, 정제된 재료명·양념명, 조리 과정이 사용됩니다. 조리 과정이 6단계를 초과하면 앞 4단계와 마지막 2단계만 사용하며, 입력 텍스트는 최대 2,500자로 제한합니다.

## 6. 데이터 구조

최종 레시피 데이터는 다음과 같은 기본 정보를 포함합니다.

~~~json
{
  "recipe_uid": "10000recipe_6912220",
  "source": "10000recipe",
  "source_id": "6912220",
  "source_url": "https://www.10000recipe.com/recipe/...",
  "title": "레시피 제목",
  "description": "레시피 설명",
  "servings": "2인분",
  "cooking_time": "30분 이내",
  "difficulty": "초급",
  "ingredients_clean": [],
  "seasonings_clean": [],
  "steps": [],
  "graph_eligible": true,
  "is_collection": false,
  "dish_group": "볶음",
  "dish_type": "제육볶음",
  "cooking_method": "1. ...\n2. ..."
}
~~~

그래프 적재용 Dish 노드에는 다음 속성을 저장합니다.

~~~text
recipe_uid
title
views
servings
cooking_time
difficulty
source_url
cooking_method
~~~

## 7. 그래프 스키마 / 온톨로지

레시피 지식그래프의 전체 구조는 다음과 같습니다.

<p align="center">
  <img src="image/온톨로지.png" alt="레시피 지식그래프 온톨로지" width="700">
</p>

~~~text
(DishGroup)-[:HAS_TYPE]->(DishType)-[:HAS_DISH]->(Dish)
(Dish)-[:INGREDIENT]->(Ingredient)
~~~

## 8. 노드 설명

| 노드 | 식별 속성 | 주요 속성 |
|---|---|---|
| DishGroup | name | 음식 대분류명 |
| DishType | key | key, name |
| Dish | recipe_uid | 제목, 조회수, 인분, 조리시간, 난이도, 출처 URL, 조리방법 |
| Ingredient | name_normalized | 정규화된 재료명 |

DishType 식별자는 중분류 이름만 사용하지 않고 다음과 같이 대분류와 조합합니다.

~~~text
dish_type_key = dish_group + "::" + dish_type
~~~

이를 통해 서로 다른 대분류에 같은 중분류명이 존재하더라도 그래프에서 충돌하지 않습니다.

## 9. 관계 설명

| 관계 | 방향 | 설명 |
|---|---|---|
| HAS_TYPE | DishGroup → DishType | 대분류에 속한 중분류 |
| HAS_DISH | DishType → Dish | 중분류에 속한 레시피 |
| INGREDIENT | Dish → Ingredient | 레시피에 사용된 재료 또는 양념 |

INGREDIENT 관계에는 다음 사용 정보를 저장합니다.

~~~text
usage_key
quantity
unit
preparation
role
raw
amount_text
source_group
~~~

role은 일반 재료인 경우 food, 양념인 경우 seasoning으로 저장합니다.

## 10. Neo4j 적재 결과

### 노드 및 관계 수

| 항목 | 개수 |
|---|---:|
| DishGroup | 21 |
| DishType | 4,646 |
| Dish | 9,380 |
| Ingredient | 10,751 |
| HAS_TYPE | 4,646 |
| HAS_DISH | 9,380 |
| INGREDIENT | 90,129 |

DishType의 4,646개는 단순한 중분류 문자열 수가 아니라 dish_group::dish_type 복합 키 기준의 그래프 노드 수입니다.

### 적재 방식

Neo4j 적재는 다음 순서로 수행합니다.

1. DishGroup, DishType, Dish, Ingredient 고유 제약 조건 생성
2. 대분류 노드 적재
3. 중분류 노드 적재
4. 레시피 노드 적재
5. 재료 노드 적재
6. HAS_TYPE, HAS_DISH, INGREDIENT 관계 적재
7. 예상 개수와 실제 개수 비교
8. 레시피별 분류·재료 연결 검증

사용하는 고유 제약 조건은 다음과 같습니다.

~~~text
Dish.recipe_uid UNIQUE
DishGroup.name UNIQUE
DishType.key UNIQUE
Ingredient.name_normalized UNIQUE
~~~

## 11. 임베딩 및 벡터 검색

임베딩은 /백터임베딩.ipynb에서 별도로 수행합니다.

### 임베딩 생성

각 레시피에 대해 다음 정보를 하나의 문서로 결합합니다.

~~~text
요리명
음식 분류
음식 종류
설명
재료
양념
조리법
~~~

| 항목 | 설정 |
|---|---|
| 임베딩 모델 | text-embedding-3-large |
| 임베딩 차원 | 768 |
| 임베딩 문서 수 | 9,381 |
| 배치 크기 | 100 |
| 백업 파일 | /recipe_vectors_backup.pkl |

확인된 백업 파일에는 문서 9,381개, 메타데이터 9,381개, 임베딩 벡터 9,381개가 저장되어 있으며, 각 벡터의 차원은 768입니다.

### Neo4j 벡터 인덱스

임베딩 적재 코드는 레시피 노드에 embedding 속성을 저장하고 다음 벡터 인덱스를 생성합니다.

~~~cypher
CREATE VECTOR INDEX dish_embedding_index IF NOT EXISTS
FOR (d:Dish) ON (d.embedding)
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 768,
        `vector.similarity_function`: 'cosine'
    }
}
~~~


## 12. 그래프 질의 시각화

### 12.1 대분류 → 중분류 → 레시피 → 재료

그래프의 전체 계층 구조와 연결 관계를 한 장에 표현했습니다.

<p align="center">
  <img src="image/visualisation1.svg" alt="대분류에서 재료까지의 그래프 구조" width="850">
</p>

### 12.2 특정 레시피의 분류와 재료

하나의 레시피가 어느 대분류·중분류에 속하고, 어떤 재료와 연결되는지 확인할 수 있습니다.

<p align="center">
  <img src="image/visualisation2.svg" alt="특정 레시피의 분류와 재료" width="850">
</p>

### 12.3 특정 재료를 사용하는 레시피

특정 재료 노드에서 연결된 여러 레시피를 역방향으로 탐색할 수 있습니다.

<p align="center">
  <img src="image/visualisation3.svg" alt="특정 재료를 사용하는 레시피" width="850">
</p>

### 12.4 공통 재료 기반 레시피 추천

여러 레시피가 공유하는 재료를 중심으로 유사한 요리 후보를 탐색할 수 있습니다.

<p align="center">
  <img src="image/visualisation4.svg" alt="공통 재료 기반 레시피 추천" width="850">
</p>

## 13. Streamlit 서비스 기능

현재 app.py에서 제공하는 화면은 다음과 같습니다.

### 요리 찾기

- 음식명 검색
- 대분류 선택
- 반드시 포함할 재료 입력
- 제외할 재료 입력
- 결과 개수 선택
- 레시피별 제목, 분류, 음식명, 조리시간, 조회수 확인
- 선택한 레시피의 재료·수량·단위·손질법·조리 순서 확인
- 원본 레시피 링크 이동

### 요리 통계

- 전체 노드 수
- 전체 관계 수
- 전체 레시피 수
- 전체 재료 수
- 대분류별 레시피 수
- 자주 등장하는 재료와 사용률


## 14. 실행 방법

### 14.1 의존성 설치

~~~bash
uv sync
~~~

### 14.2 Neo4j 연결 설정

.streamlit/secrets.toml.example을 복사하여 .streamlit/secrets.toml을 만들고 실제 연결 정보를 입력합니다.

~~~toml
NEO4J_URI = "neo4j+ssc://YOUR_INSTANCE.databases.neo4j.io"
NEO4J_USER = "YOUR_USER"
NEO4J_PASSWORD = "YOUR_PASSWORD"
NEO4J_DATABASE = "neo4j"
~~~

실제 비밀번호가 포함된 secrets.toml은 저장소에 커밋하지 않습니다.

### 14.3 Streamlit 실행

프로젝트 루트에서 실행합니다.

~~~bash
python -m streamlit run app.py
~~~

브라우저에서 표시되는 Streamlit 화면을 통해 레시피 검색과 그래프 통계를 확인할 수 있습니다.

## 15. 검증 및 주의사항

- 그래프 적재 노트북 기준 Dish 적재 대상은 9,380건입니다.
- recipes_classified_cleaned.jsonl 9,381건과 Neo4j Dish 9,380건은 분류 누락 1건 때문에 차이가 납니다.
- graph_eligible은 최종 필터 조건으로 사용되지만, 이 노트북은 is_collection을 별도의 필터 조건으로 직접 사용하지 않습니다.
- 9,558건은 현재 저장소 코드와 노트북 출력에서 확인되지 않으므로 공식 결과 수치로 사용하지 않습니다.
- 벡터 검색을 사용하려면 Dish.embedding 속성과 dish_embedding_index가 실제 Neo4j 인스턴스에 생성되어 있어야 합니다.
- Neo4j 접속 정보와 OpenAI API 키는 코드나 README에 직접 기록하지 않습니다.

## 16. 기대 효과 및 개선 방향

### 기대 효과

- 재료 중심의 레시피 탐색
- 음식 분류와 재료 관계를 한눈에 확인
- 특정 재료를 포함하거나 제외한 레시피 검색
- 임베딩 기반 의미 유사 레시피 추천
- 그래프 구조를 활용한 재료·레시피 탐색

### 개선 방향

- Streamlit 검색 화면과 벡터 추천 모듈 통합
- 자연어 질문을 Cypher로 변환하는 Text-to-Cypher 흐름 연결
- 재료 대체 관계를 별도의 그래프 관계로 모델링
- 전처리 제거 사유별 통계 추가
- 임베딩 및 벡터 인덱스 배포 자동화
- 레시피별 품질 점검 및 분류 누락 자동 보정
