"""최종 설계 명세 v3.0 — 실행용 적재 코드가 아님.

DishGroup(찌개) → DishType(김치찌개) → Dish(참치김치찌개).
Recipe 노드는 만들지 않는다. Dish는 여러 레시피가 공유하는 음식 개념이다.
레시피 상세는 Dish.recipes_json 문자열 안에 recipe_uid별로 저장한다.
CONTAINS/SUBSTITUTE.recipe_uid로 해당 음식의 레시피별 재료를 구분한다.
이 파일은 이전에 잘못 작성한 'Dish = 개별 레시피' V3 명세를 대체한다.
Ingredient는 공유 노드, 사용량과 원문 정보는 CONTAINS 관계 속성이다.
필요성 상/중/하는 설계 기여도이며 required(값 필수)와는 다르다.
nullable은 JSON에서는 null/누락, Neo4j에서는 속성 부재로 표현한다.
이 명세는 데이터 검증 완료나 DB 마이그레이션 완료를 의미하지 않는다.
"""

SCHEMA_VERSION = "3.0"


def field(type_, meaning, need, required=False):
    """명세 작성 보조 함수. 반환된 중첩 dict를 DB 속성으로 저장하지 않는다."""
    return {"type": type_, "한국어해석": meaning, "필요성": need,
            "required": required, "nullable": not required}


NODE_SCHEMA = {
    # 한국어해석: 음식군 대분류. 예: 찌개.
    # 필요성: 상 — 사용자가 선택한 탐색 시작점.
    "DishGroup": {
        "한국어해석": "음식군 대분류", "필요성": "상",
        "unique": ["group_id"],
        "properties": {
            "group_id": field("STRING", "분류 사전의 안정적인 대분류 ID", "상", True),
            "name": field("STRING", "대분류 대표명. 예: 찌개", "상", True),
        },
    },
    # 한국어해석: 같은 음식군 안에서 구분되는 중분류. 예: 김치찌개.
    # 필요성: 상 — 세부 음식 개념들을 묶는 기준.
    "DishType": {
        "한국어해석": "음식 중분류", "필요성": "상",
        "unique": ["type_id"],
        "properties": {
            "type_id": field("STRING", "분류 사전의 안정적인 중분류 ID", "상", True),
            "name": field("STRING", "중분류 대표명. 예: 김치찌개", "상", True),
        },
    },
    # 한국어해석: 여러 원본 레시피가 공유하는 음식 개념. 예: 참치김치찌개.
    # 필요성: 상 — 같은 음식의 여러 레시피를 모아 탐색·비교.
    "Dish": {
        "한국어해석": "공유 음식 개념", "필요성": "상",
        "unique": ["dish_id"],
        "properties": {
            "dish_id": field("STRING", "승인된 음식 사전의 안정적인 음식 ID", "상", True),
            "name": field("STRING", "공유 대표 음식명. 예: 참치김치찌개", "상", True),
            "recipes_json": field("STRING", "recipe_uid를 키로 하는 레시피 상세 객체를 JSON 직렬화한 문자열", "상", True),
        },
    },
    # 한국어해석: 여러 Dish가 공유하는 정규화된 단일 재료.
    # 필요성: 상 — 공통/차이 재료 비교, 재료별 검색 및 집계.
    "Ingredient": {
        "한국어해석": "공유 재료 개념", "필요성": "상",
        "unique": ["name_normalized"],
        "properties": {
            "name": field("STRING", "화면 표시용 대표 재료명", "상", True),
            "name_normalized": field("STRING", "승인된 정규화 재료 식별명", "상", True),
        },
    },
}

# 한국어해석: recipes_json을 파싱한 뒤 각 recipe_uid에 대응하는 값의 명세.
# 필요성: 상 — 레시피를 노드로 만들지 않고 제목·본문·출처를 보존.
# 이 필드들은 Dish의 개별 Neo4j 속성이 아니라 JSON 문자열 내부 필드다.
RECIPE_METADATA_SCHEMA = {
    "한국어해석": "음식에 속한 개별 원본 레시피 상세", "필요성": "상",
    "key": "recipe_uid: 출처+원본 ID. 예: 10000recipe:6876357",
    "properties": {
        "title": field("STRING", "원본 레시피 제목", "상", True),
        "source": field("STRING", "출처 이름", "상", True),
        "source_url": field("STRING", "원문 레시피 링크", "상", True),
        "variant_label": field("STRING", "백종원식 등 원문에 명시된 변형 표시명", "중"),
        "servings": field("STRING", "수량의 기준 인분", "상"),
        "cooking_time": field("STRING", "원문 조리 시간", "중"),
        "steps": field("LIST<STRING>", "순서를 보존한 원문 조리 단계", "중"),
        "description": field("STRING", "원문 소개", "하"),
        "difficulty": field("STRING", "원문 난이도", "하"),
        "views": field("INTEGER", "수집 시점 조회수", "하"),
        "ingredient_data_status": field("STRING", "complete/partial/missing: 재료 목록 처리 완전성", "상", True),
    },
    "enum": {"ingredient_data_status": ["complete", "partial", "missing"]},
}

RELATION_SCHEMA = {
    # 한국어해석: 대분류에 중분류가 속한다. 필요성: 상.
    "HAS_TYPE": {
        "source": "DishGroup", "target": "DishType",
        "한국어해석": "대분류의 하위 음식 유형", "필요성": "상",
        "properties": {},
        "cardinality": "DishGroup 1 : DishType N. 각 DishType의 부모는 정확히 1개",
    },
    # 한국어해석: 중분류에 공유 음식 개념이 속한다. 필요성: 상.
    "HAS_DISH": {
        "source": "DishType", "target": "Dish",
        "한국어해석": "중분류에 속한 세부 음식", "필요성": "상",
        "properties": {},
        "cardinality": "DishType 1 : Dish N. 분류 확정 Dish의 부모는 정확히 1개",
    },
    # 한국어해석: 해당 Dish에 기재된 재료 사용 항목. 필요성: 상.
    "CONTAINS": {
        "source": "Dish", "target": "Ingredient",
        "한국어해석": "특정 레시피의 기본 재료 사용 항목", "필요성": "상",
        "unique": ["item_id"],
        "properties": {
            "recipe_uid": field("STRING", "출발 Dish.recipes_json 안의 레시피 키 참조", "상", True),
            "item_id": field("STRING", "원본 재료 항목의 안정적인 고유 ID", "상", True),
            "index": field("INTEGER", "원문 재료 항목의 1부터 시작하는 순번", "중", True),
            "raw_text": field("STRING", "항목의 수량·단위를 포함한 원문", "상", True),
            "quantity": field("STRING", "수량 문자열. 1/2·약간 등 그대로 보존", "상"),
            "unit": field("STRING", "원문 단위. 임의 환산하지 않음", "상"),
            "group": field("STRING", "양념/육수/밑간 등 원문 사용 구역", "중"),
            "preparation": field("STRING", "다진/삶은 등 손질 상태", "중"),
            "detail": field("STRING", "다른 필드에 담기지 않은 원문 조건", "중"),
            "role": field("STRING", "food/seasoning/unknown. 문맥상 역할", "하", True),
            "is_required": field("BOOLEAN", "명시적 필수 true, 생략 가능 false, 미상 null", "중"),
            "required_evidence": field("STRING", "필수/생략 판정의 원문 근거. 섹션명도 가능", "중"),
            "alternative_mode": field("STRING", "none/replacement/either_or/unresolved", "중", True),
        },
        "enum": {
            "role": ["food", "seasoning", "unknown"],
            "alternative_mode": ["none", "replacement", "either_or", "unresolved"],
        },
        "defaults": {"role": "unknown", "alternative_mode": "none"},
    },
    # 한국어해석: 특정 Dish의 특정 사용 항목에만 유효한 대체 선택지.
    # 필요성: 중 — 원문 근거가 있을 때 재료 선택 안내에 도움.
    "SUBSTITUTE": {
        "source": "Dish", "target": "Ingredient",
        "한국어해석": "레시피 문맥에 한정된 대체 재료", "필요성": "중",
        "unique": ["substitute_id"],
        "properties": {
            "recipe_uid": field("STRING", "출발 Dish.recipes_json 안의 레시피 키 참조", "상", True),
            "substitute_id": field("STRING", "원본 대체 선택지의 안정적인 고유 ID", "상", True),
            "for_item_id": field("STRING", "같은 Dish·같은 recipe_uid의 CONTAINS.item_id 참조", "상", True),
            "raw_text": field("STRING", "대체재의 원문 표현", "중", True),
            "evidence": field("STRING", "대체/선택을 명시한 원문 구절", "상", True),
            "condition": field("STRING", "대체가 가능한 조건", "중"),
            "quantity": field("STRING", "원문에 별도로 제시된 대체재 수량", "중"),
            "unit": field("STRING", "대체재 단위", "중"),
            "preparation": field("STRING", "대체재 손질 상태", "중"),
        },
    },
}

CLASSIFICATION_RULES = [
    "본 분류의 예시는 찌개 → 김치찌개 → 참치김치찌개. 레시피를 분류 노드로 만들지 않음",
    "분류 사전의 ID/정의/상하위 매핑을 먼저 확정. 이름만으로 부모를 추정하지 않음",
    "백종원식/전주식 표기는 원문 근거가 있을 때만 variant_label에 저장",
    "같은 음식의 여러 레시피는 동일 Dish.recipes_json의 서로 다른 키로 저장",
    "단일 음식 범위에서 recipe_uid는 전체 Dish 중 정확히 하나에만 소속",
    "음식 자체를 확정할 수 없거나 여러 음식이 섞인 레시피는 외부 보류 기록으로 보존",
    "Dish는 확정됐으나 상위 분류만 불명확하면 HAS_DISH만 보류하고 외부 검토",
    "기존 3886개 레시피/1372개 Dish는 과거 관측값이며 새 추출 결과의 고정 목표 개수가 아님",
]

VALIDATION_RULES = [
    "unique 표시는 요구사항이다. 실제 DB 제약과 적재 검사 구현은 별도",
    "동일 Dish-Ingredient 사이에도 item_id가 다르면 별도 CONTAINS 유지",
    "CONTAINS.item_id는 전역에서 하나의 Dish·recipe_uid·기본 Ingredient에만 대응",
    "모든 CONTAINS/SUBSTITUTE.recipe_uid는 출발 Dish.recipes_json의 키로 존재",
    "index는 recipe_uid 내부에서 양의 정수이며 중복 금지. 보류 항목 때문에 순번이 비어 있을 수 있음",
    "재료명 자체와 문맥의 수량·손질·그룹을 구분. 대파 또는 쪽파를 단일 재료로 만들지 않음",
    "SUBSTITUTE.for_item_id는 같은 Dish·recipe_uid의 CONTAINS 정확히 하나를 참조. 적재 코드가 검사",
    "none에는 SUBSTITUTE 없음. replacement/either_or에는 검증된 SUBSTITUTE 1개 이상",
    "미해결 대체는 unresolved. none은 대체 불가능이 아니라 대체 정보 미기록",
    "either_or의 첫 선택지는 저장 관례이며 사용 확정·권장 순위를 뜻하지 않음",
    "복합 대체(A 대신 B+C)는 독립 선택지로 분해하지 않고 unresolved 및 원문 보존",
    "대체재의 수량을 기본재에서 자동 복사하지 않음. 기본재와 같은 대체 노드 연결 보류",
    "대체 가능을 생략 가능으로 해석하지 않음. is_required 값이 있으면 근거도 필수",
    "is_required=false 항목 제거만으로 조리 가능한 간소화 레시피라고 보장하지 않음",
    "원본 재료 목록 전 항목 매핑 성공 시 complete, 일부 보류 시 partial, 목록 없으면 missing",
    "complete는 처리 완전성 표시이며 음식 의미를 사람 검수했다는 뜻이 아님",
    "노드에 재료 객체 배열을 저장하지 않음. 관계 속성으로 표현",
    "steps는 recipes_json 내부의 순서 있는 문자열 배열. CookingMethod 노드는 만들지 않음",
    "미상값은 null/부재. 빈 문자열·0·false로 미상을 대신하지 않음",
]

DISPLAY_AND_STATISTICS = {
    "간단표시": "Dish와 recipe_uid를 선택해 재료명·수량·단위만 표시. 재료 임의 제거 금지",
    "상세표시": "같은 recipe_uid의 전체 항목·그룹·손질·원문·대체재 및 JSON 내부 조리 단계 표시",
    "실제간소화레시피": "같은 음식의 별도 원본이면 같은 Dish에 새 recipe_uid와 관계 추가",
    "recipe_count": "recipes_json을 파싱한 키 개수. 재료 관계가 없는 레시피도 포함",
    "item_count": "recipe_uid별 CONTAINS 관계 수: 재료 사용 항목 수",
    "ingredient_count": "recipe_uid별 연결된 고유 Ingredient 수: 중복 제거 재료 종류 수",
    "optional_count": "is_required=false인 항목 수. null은 미상",
    "usage_count": "Ingredient별 count(DISTINCT CONTAINS.recipe_uid). SUBSTITUTE는 별도 집계",
    "either_or": "기본 사용 확정 빈도가 아닌 기재 선택지 빈도로 표시",
    "비교": "같은 Dish의 recipe_uid별 재료 집합·수량 비교. Dish 간 음식 비교도 가능",
    "수량합계": "단위·인분·반복 용도가 다른 수량을 자동 합산하지 않음",
    "카운트저장": "조회 시 계산. 저장 캐시 사용 시 데이터 변경마다 갱신 필요",
}

RAW_EXTRACTION_RULES = [
    "새 작업의 입력은 선택한 raw 스냅샷. 기존 v2의 prepared-only 제한을 승계하지 않음",
    "raw 파일·원본 ID·원문 위치를 외부 추적 기록에 보존",
    "공백 정리 시에도 1/2, 2~3, 괄호 조건 등 의미 있는 기호와 단계 경계를 보존",
    "메타데이터는 Python으로 복사. 수량·단위·단계 순서를 LLM에 전체 재작성시키지 않음",
    "분류는 승인된 사전 우선, 모호한 항목만 LLM 후보 추출 후 검사",
    "재료는 원문 사용 항목별 분리 후 승인된 Alias 적용. 비슷하다는 이유로 병합 금지",
    "원문에서 대체/필수 근거를 추출. 없는 근거를 조리 상식으로 생성하지 않음",
    "형식·식별·관계 참조 및 원문 보존 검사 후 소량 샘플 검토, 이후 전체 변환",
    "quality_flags는 항목 ID별 외부 검토 기록에 저장. 그래프 필수 속성에서 제외",
]

V2_COMPARISON = {
    "Recipe": "독립 노드 제거. 레시피 상세는 Dish.recipes_json에 recipe_uid별 저장",
    "Dish": "공유 음식 개념 유지. dish_id로 식별하며 개별 레시피 수만큼 노드를 만들지 않음",
    "VARIANT_OF": "제거. DishGroup-HAS_TYPE-DishType-HAS_DISH-Dish로 분류",
    "Ingredient": "공유 재료 개념 유지",
    "CONTAINS": "출발 노드를 공유 Dish로 변경. recipe_uid 추가로 레시피별 재료 구분",
    "SUBSTITUTE": "공유 Dish에서 출발. recipe_uid와 for_item_id로 대체 대상 명시",
    "CookingMethod": "추가하지 않음. 조리법은 Dish.recipes_json 내부 steps",
    "quality_flags": "v2처럼 외부 검토 기록으로 유지",
    "입력": "기존 prepared 전용에서 raw 기반 재추출로 변경",
}

# 한국어해석: JSON 속성과 그래프 관계 사이의 일관성 관리. 필요성: 상.
JSON_STORAGE_RULES = [
    "recipes_json은 UTF-8 JSON 객체의 문자열. 키는 비어 있지 않은 고유 recipe_uid",
    "중복 JSON 키를 조용히 덮어쓰지 말고 파싱 단계에서 거부",
    "레시피 값은 RECIPE_METADATA_SCHEMA에 맞는 객체. 알 수 없는 선택 필드는 null/생략",
    "Dish가 소유한 레시피의 상세를 입력 전체 기준으로 모아 직렬화. 증분 적재 시 기존 키 보존",
    "Neo4j는 JSON 내부 필수 필드·레시피 전역 유일성·참조를 자동 보장하지 않으므로 적재기가 검사",
    "레시피 추가·수정·삭제 시 recipes_json과 해당 recipe_uid의 재료/대체 관계를 함께 갱신",
    "동시 갱신은 직렬화 또는 잠금/재시도로 덮어쓰기 유실 방지. 실제 정책은 적재기에 구현",
    "제목·조회수·시간 필터는 프로그램에서 JSON 파싱 후 처리. 기본 속성 인덱스로 내부 필드 검색 불가",
    "재료 없는 레시피 목록은 관계에서 추론하지 말고 JSON 키에서 조회",
    "JSON에는 재료 목록을 중복 저장하지 않음. 기본 재료/대체재는 관계가 기준",
    "레시피별 상세 출력은 JSON 메타데이터와 recipe_uid로 필터한 관계를 프로그램에서 조합",
    "unique 및 필요성 표기는 명세일 뿐 제약을 생성하지 않음. 필요성 상도 원문 미상값 추정 금지",
]

# 한국어해석: 가상 데이터로 구조만 보여주는 예시. 실제 추출 결과가 아님.
# 필요성: 중 — 같은 Dish/Ingredient를 공유하면서 레시피별 수량이 유지됨을 확인.
EXAMPLE_RECIPES = {
    "demo:r1": {
        "title": "간단 참치김치찌개", "source": "demo",
        "source_url": "https://example.com/r1", "servings": "2인분",
        "steps": ["원문 조리 단계 예시"], "ingredient_data_status": "complete",
    },
    "demo:r2": {
        "title": "진한 참치김치찌개", "source": "demo",
        "source_url": "https://example.com/r2", "servings": "3인분",
        "ingredient_data_status": "complete",
    },
}

# recipes_json 실제 값은 json.dumps(EXAMPLE_RECIPES, ensure_ascii=False)로 생성.
EXAMPLE_CONTAINS = [
    {"dish_id": "dish:tuna_kimchi_jjigae", "ingredient": "김치",
     "properties": {"recipe_uid": "demo:r1", "item_id": "demo:r1:item:001",
                    "index": 1, "quantity": "200", "unit": "g",
                    "raw_text": "김치 200g", "role": "unknown", "alternative_mode": "none"}},
    {"dish_id": "dish:tuna_kimchi_jjigae", "ingredient": "김치",
     "properties": {"recipe_uid": "demo:r2", "item_id": "demo:r2:item:001",
                    "index": 1, "quantity": "300", "unit": "g",
                    "raw_text": "김치 300g", "role": "unknown", "alternative_mode": "none"}},
]

# 한국어해석: 특정 음식의 레시피 하나에 기재된 재료 목록 조회. 필요성: 상.
# $dish_id와 $recipe_uid는 실행 시 전달하는 파라미터다.
EXAMPLE_CYPHER = """
MATCH (d:Dish {dish_id: $dish_id})-[c:CONTAINS]->(i:Ingredient)
WHERE c.recipe_uid = $recipe_uid
RETURN i.name AS ingredient, c.item_id AS item_id,
       c.quantity AS quantity, c.unit AS unit, c.raw_text AS raw_text
ORDER BY c.index
"""
