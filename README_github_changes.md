# README_github.md 변경 설명

이 문서는 기존 `README.md`를 보존한 상태에서 새로 작성한 `README_github.md`의 변경 내용을 설명합니다.

## 파일 처리 원칙

| 파일 | 처리 |
|---|---|
| `README.md` | 원본 유지, 수정하지 않음 |
| `README_github.md` | 기존 README 내용과 평가 반영 내용을 통합한 문서 |
| `README_github_changes.md` | README를 어디에, 어떻게, 왜 수정했는지 설명하는 문서 |

## 1. 프로젝트 구조와 경로 정리

기존 README에서 실제 폴더와 맞지 않는 경로를 현재 저장소 구조에 맞게 수정했습니다.

```text
기존: /input/recipes_10000_cleaned.jsonl
변경: data/processed/recipes_10000_cleaned.jsonl
```

실제 프로젝트의 주요 경로도 명확히 표시했습니다.

- `app.py`
- `recipe_graph.py`
- `data/raw/`
- `data/processed/`
- `notebooks/`
- `image/`
- `기록 보관용/`

### 수정 이유

GitHub에서 README를 읽는 사람이 실제 파일을 바로 찾고 데이터 처리 과정을 재현할 수 있도록 하기 위해서입니다.

## 2. 현재 운영 스키마와 설계 스키마 구분

현재 `app.py`와 `recipe_graph.py`는 다음 구조를 사용합니다.

```text
DishGroup → DishType → Dish → Ingredient
```

현재 운영 관계는 다음과 같습니다.

```text
HAS_TYPE
HAS_DISH
INGREDIENT
```

현재 `Dish`는 개별 레시피이며 `recipe_uid`로 식별합니다.

반면 `기록 보관용/schema_v3_final.py`는 다음 구조를 제안합니다.

```text
DishGroup → DishType → Dish
                              └─ CONTAINS → Ingredient
                              └─ SUBSTITUTE → Ingredient
```

v3에서는 `Recipe` 노드를 제거하고 여러 레시피의 상세 정보를 `Dish.recipes_json`에 저장합니다.

### 수정 이유

현재 운영 DB 구조와 향후 적용을 검토 중인 v3 설계안이 다르기 때문입니다.
두 구조를 구분하지 않으면 현재 구현된 기능과 향후 계획이 혼동될 수 있습니다.

## 3. 제거된 616건의 사유별 통계

### 산출 방법

`data/processed/recipes_10000_cleaned.jsonl` 9,997건과 `data/processed/recipes_classified_cleaned.jsonl` 9,381건을 `recipe_uid` 기준으로 비교했습니다.

```text
9,997 - 9,381 = 616건
```

### 대표 사유별 통계

사유가 겹치는 레코드는 하나의 대표 사유로 분류했습니다.

| 대표 제거 사유 | 건수 |
|---|---:|
| `graph_eligible=False`이며 재료·조리 과정이 없는 레코드 | 430 |
| 재료는 있으나 조리 과정이 없는 레코드 | 137 |
| 조리 과정과 재료가 모두 없는 레코드 | 37 |
| 제목·재료·조리 과정이 모두 없고 `graph_eligible=False`인 레코드 | 12 |
| 합계 | 616 |

### 필드별 진단

한 레코드가 여러 조건에 동시에 해당할 수 있으므로 아래 수치는 합산하지 않습니다.

| 진단 조건 | 건수 |
|---|---:|
| `cooking_method` 없음 | 616 |
| `ingredients_clean` 없음 | 479 |
| `graph_eligible=False` | 442 |
| `title` 없음 | 12 |

### 수정 이유

기존 README에는 616건이 제거되었다는 결과만 있고 제거 사유별 근거가 없었습니다.
사유별 통계를 추가해 데이터 품질과 필터링 기준을 확인할 수 있도록 했습니다.

## 4. INGREDIENT 관계 생성 방식

현재 `INGREDIENT` 관계는 LLM이 직접 생성하는 방식이 아닙니다.
전처리 데이터의 정형 필드를 Python으로 변환해 생성합니다.

주요 입력 필드는 다음과 같습니다.

- `ingredients_clean`
- `seasonings_clean`
- `name_normalized`
- `amount_text`
- `unit_normalized`
- `preparation`
- `item_type`
- `group`

이 값들은 재료명, 수량, 단위, 손질법, 재료 역할 등의 관계 속성으로 저장됩니다.

### 수정 이유

현재 그래프 적재 방식이 정형 필드 기반이라는 점을 명시해 어떤 데이터가 자동으로 관계로 변환되는지 설명하기 위해서입니다.

## 5. 비정형 텍스트 기반 확장 계획

설명·조리 과정 같은 비정형 텍스트에서 다음 정보를 추가 추출하는 작업을 향후 과제로 정리했습니다.

- 조리 행위와 조리 순서
- 조리도구
- 대체 재료
- 대체 조건

LLM 활용 원칙:

- 정형 필드는 Python으로 원본 값을 그대로 복사
- LLM은 비정형 텍스트에서 후보와 근거만 추출
- 원문에 없는 정보는 생성하지 않음
- `evidence`, 추출 방식, 신뢰도, 검토 상태 보존
- 중복 관계와 근거 누락 검증
- 일부 샘플에 대한 사람 검수 수행

### 수정 이유

현재 구현 범위와 향후 확장 범위를 구분하기 위해서입니다.
현재는 재료 관계가 중심이며 조리도구·대체 재료·조리 행위의 그래프화는 추가 개발이 필요한 영역입니다.

## 6. 시각화별 Cypher 쿼리 추가

`README_github.md`에 다음 네 가지 시각화를 재현할 수 있는 Cypher 쿼리를 추가했습니다.

1. 전체 계층 구조
2. 특정 레시피의 분류와 재료
3. 특정 재료를 사용하는 레시피
4. 공통 재료 기반 레시피 추천

쿼리는 현재 운영 스키마인 `DishGroup -HAS_TYPE-> DishType -HAS_DISH-> Dish -INGREDIENT-> Ingredient`를 기준으로 작성했습니다.

### 수정 이유

이미지만 제공하면 다른 사람이 같은 결과를 재현하기 어렵습니다.
조회 쿼리를 함께 제공하면 Neo4j Browser나 애플리케이션에서 결과를 다시 확인할 수 있습니다.

현재 저장소에 시각화 원본 쿼리가 별도 파일로 관리되고 있지 않아, 현재 스키마 기준의 재현용 Cypher를 README에 정리했습니다.

향후에는 다음과 같이 쿼리를 별도 파일로 관리하는 것을 권장합니다.

```text
queries/
├─ visualization_01_full_graph.cypher
├─ visualization_02_recipe_detail.cypher
├─ visualization_03_ingredient_recipes.cypher
└─ visualization_04_common_ingredients.cypher
```

## 7. 벡터 검색 설명 정리

벡터 검색은 `notebooks/백터임베딩.ipynb`와 `기록 보관용/벡터 기반/`에 있는 실험 기능으로 분류했습니다.

현재 기본 `app.py`는 키워드, 분류, 포함·제외 재료 기반 검색을 제공하며 벡터 검색 챗봇이 기본 화면에 통합된 상태는 아닙니다.

### 수정 이유

README에서 벡터 검색이 이미 운영 화면에 통합된 것처럼 보이지 않도록 현재 구현과 실험 기능을 구분하기 위해서입니다.

## 8. GitHub 업로드 전 확인 사항

- `README.md`는 원본으로 유지
- `README_github.md`를 GitHub 대표 README로 사용할지 결정
- `README_github_changes.md`는 문서 변경 설명용으로 함께 업로드 가능
- 실제 Neo4j 접속 정보와 OpenAI API 키는 업로드하지 않음
- `.env`, `.streamlit/secrets.toml`, `.venv`, `__pycache__`는 제외
- 시각화 쿼리를 향후 `queries/` 폴더로 분리하면 재현성이 더 좋아짐
