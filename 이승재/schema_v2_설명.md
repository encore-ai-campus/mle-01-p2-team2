# 레시피 온톨로지 2 0

입력은 `전처리/recipes_graph_prepared_v2.jsonl` 하나다. 첨부한 v1.0의 명세 형식에 맞춰
`schema_v2.py`를 작성했다. 데이터 파일명에 있는 v2, 내부 schema_version 1.0, 새 온톨로지
버전 2.0은 서로 다른 버전 식별자다. 입력 데이터 자체를 수정하거나 이미 변환한 것은 아니다.

## 노드와 관계

```text
Recipe ──VARIANT_OF──→ Dish
       ├─CONTAINS────→ Ingredient
       └─SUBSTITUTE──→ Ingredient
```

Recipe는 출처별 개별 문서, Dish는 닭볶음탕 같은 대표 음식, Ingredient는 정규화된 재료다.
닭도리탕·닭볶음탕은 승인된 Alias로 하나의 Dish에 연결하되 Recipe의 UID와 제목은 유지한다.
Dish 후보는 이 파일의 recipe.title로만 추출한다. 분류가 불명확하면 연결을 만들지 않는다.

## 축소한 부분

| 기존 | v2.0 처리 | 이유 |
|---|---|---|
| Component 노드 | 제거, CONTAINS 관계로 이동 | 사용 정보는 관계 속성으로 충분 |
| HAS_COMPONENT와 INGREDIENT | CONTAINS 하나로 통합 | 기본 검색 경로 단순화 |
| ALTERNATIVE | Recipe → SUBSTITUTE → Ingredient | 기본 항목은 for_item_id로 식별 |
| component_uid | CONTAINS.item_id로 값 그대로 보존 | 반복 재료와 대체 대상 구별 |
| index | 그래프에서 제거 | 사용 항목 식별은 item_id로 가능 |
| raw_name와 기본 evidence | 입력 파일에 보존, 그래프에서는 제외 | 중복 저장을 줄이고 필요 시 item_id로 prepared 내부 조회 |
| detail | 그래프에서 제외 | 보완 판단 시 prepared의 값만 참조 |
| quality_flags | 그래프에서 제외, 항목별 검토 기록에 보존 | 경고 코드와 요리 관계 의미를 분리 |
| Recipe.description·cooking_time·difficulty·views | 그래프에서 제외 | 현재 검색·대체·재료 빈도 목표에 필수 아님 |
| 대체재 quantity·unit·preparation·raw_name | 그래프에서 제외 | 현재 파일에 대체재 수량/손질 정보가 없고 간소화 대체 검색에 불필요 |
| Dish.name_normalized | 추가하지 않음 | 승인된 대표 name 자체를 유일 식별 이름으로 사용 |

Recipe.servings는 수량의 인분 기준을 잃지 않기 위해 유지한다.
대체 관계의 evidence는 방향과 선택 의미를 검토할 수 있도록 이 파일의 값만 유지한다.
CONTAINS.alternative_mode를 유지하므로 대체 관계가 없어도 none과 unresolved를 구분할 수 있다.
SUBSTITUTE에 mode를 중복 저장하지 않는다.

## 현재 파일과의 대응

- 9,985개 Recipe, 91,781개 입력 Component, 588개 대체 후보가 있다.
- Dish는 모두 null이다. title만으로 후보를 생성한 뒤 Alias/ER을 적용한다.
- is_required=false는 445개다. 해당 키가 없는 91,336개는 null/미상이며 true로 채우지 않는다.
- 재료가 없는 430개 레시피는 메타데이터 보존 대상으로 두고 재료 검색·통계에서 제외한다.
- 1,994개 사용 항목에 품질 경고가 있다. 모두 버리지 않고 경고 내용에 따라 항목/관계만 검토한다.
- '또는/혹은/ / ' 패턴으로 찾은 복합 이름 후보가 11개 있다. 패턴 일치가 오류 확정은 아니며
  복합 표현을 단일 Ingredient로 자동 등록하지 않는다.

이 숫자는 파일 구조·필드 집계 결과다. 음식 의미의 정확성이나 누락까지 사람이 검수한 결과는 아니다.

## 예시

```text
(Recipe {recipe_uid: "10000recipe:6876357", title: "닭볶음탕 진짜진짜 황금레시피 알려 드려요~~^^"})
  -[:VARIANT_OF]-> (Dish {name: "닭볶음탕"})

(Recipe)
  -[:CONTAINS {
      item_id: "10000recipe:6876357:component:001",
      role: "food", group: "[재료]", quantity: "1", unit: "마리",
      preparation: null, is_required: null, alternative_mode: "none"
    }]-> (Ingredient {name: "닭", name_normalized: "닭"})
```

다음은 구조 설명용 예시이며 실제 파일에서 검증된 관계를 뜻하지 않는다.

```text
(Recipe)
  -[:CONTAINS {item_id: "r1:item:001", alternative_mode: "replacement"}]-> (버터)
(Recipe)
  -[:SUBSTITUTE {for_item_id: "r1:item:001", condition: null,
                 evidence: "버터 대신 식용유를 사용해도 된다"}]-> (식용유)
```

대체 관계는 동일 Recipe의 item_id를 가리켜야 한다. for_item_id는 문자열 속성이므로
DB가 자동으로 외래키처럼 보장하지 않는다. 적재 코드가 해당 CONTAINS 존재 여부를 검사한다.
동일 Recipe와 Ingredient라도 item_id가 다르면 관계를 유지한다. 대등한 선택의 기본 연결은
저장 순서일 뿐 실제로 그 재료를 사용했다거나 더 권장한다는 뜻이 아니다.

## Python과 LLM의 역할

Python은 필드 복사, ID 보존, 승인된 Alias 적용, 기본 관계 생성, 자료형·관계 일관성 검사를 맡는다.
LLM은 필요한 제목의 Dish 후보 추출과 prepared 안에 남은 모호한 대체/생략 표현 해석만 맡는다.
raw 파일이나 steps를 다시 읽지 않는다. 입력에 없는 사실은 미상으로 남긴다.
LLM 응답은 판단 변경분만 받고 기존 수량·단위·재료 사용 정보를 다시 출력시키지 않는다.

이 명세는 스키마 설계만 제공한다. v1.0 실험 코드와 결과는 별도로 유지되며 v2.0 변환·적재는 아직 실행하지 않았다.
