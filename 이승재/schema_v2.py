"""레시피 검색·대체/생략 여부·재료 사용 통계를 위한 온톨로지 명세.

유일한 입력: 전처리/recipes_graph_prepared_v2.jsonl
이 파일은 설계 명세다. 데이터 변환이나 DB 제약 생성을 실행하지 않는다.
nullable 필드는 JSON에서 null을 허용하며 Neo4j에서는 속성 부재로 표현된다.
unique는 요구하는 식별 규칙이며 실제 제약/적재 검증은 구현 단계에서 적용한다.
"""

SCHEMA_VERSION = "2.0"

NODE_SCHEMA = {
    "Recipe": {
        "meaning": "출처에서 수집한 개별 레시피 문서",
        "properties": {
            "recipe_uid": "STRING",
            "title": "STRING",
            "source": "STRING",
            "source_url": "STRING",
            "servings": "STRING",
        },
        "required": ["recipe_uid", "title", "source", "source_url"],
        "unique": ["recipe_uid"],
        "nullable": ["servings"],
        "description": {
            "recipe_uid": "recipe.recipe_uid 그대로 사용. 같은 제목이나 Dish라고 병합하지 않음",
            "title": "recipe.title 그대로 보존. 임의로 음식명1·음식명2로 개명하지 않음",
            "source": "recipe.source의 출처 이름",
            "source_url": "recipe.source_url. 사용자에게 개별 레시피를 안내하는 링크",
            "servings": "recipe.servings. 재료 수량이 어느 인분 기준인지 보존. 미지정이면 null",
        },
    },
    "Dish": {
        "meaning": "여러 Recipe가 공유하는 정규화된 음식 개념",
        "properties": {"name": "STRING"},
        "required": ["name"],
        "unique": ["name"],
        "nullable": [],
        "description": {
            "name": (
                "recipe.title에서 추출한 후보를 승인된 음식 Alias로 정규화한 대표명. "
                "예: 닭도리탕과 닭볶음탕을 닭볶음탕으로 통일. 제목의 모든 수식어를 "
                "일괄 제거하지 않으며 음식 구분에 필요한 표현은 유지"
            ),
        },
    },
    "Ingredient": {
        "meaning": "여러 레시피에서 공유하는 정규화된 재료 개념",
        "properties": {"name": "STRING", "name_normalized": "STRING"},
        "required": ["name", "name_normalized"],
        "unique": ["name_normalized"],
        "nullable": [],
        "description": {
            "name": "ingredient.name 또는 승인된 Alias의 표시용 대표 재료명",
            "name_normalized": (
                "ingredient.name_normalized를 검사한 뒤 승인된 Alias로 정규화한 식별 이름. "
                "대파 또는 쪽파 같은 미분리 표현을 하나의 재료로 등록하지 않음. "
                "비슷한 이름·상하위 개념이라는 이유만으로 병합하지 않음"
            ),
        },
    },
}

RELATION_SCHEMA = {
    "VARIANT_OF": {
        "source": "Recipe",
        "target": "Dish",
        "meaning": "해당 개별 레시피가 대표 음식의 한 조리법임",
        "properties": {},
        "validation_rules": [
            "단일 음식 레시피 범위에서 Recipe당 0~1개",
            "입력 dish가 null이면 recipe.title만으로 음식 후보를 추출하고 Alias/ER 적용",
            "제목으로 확정할 수 없거나 여러 음식이 함께 등장하면 연결 보류",
            "Dish를 확정하지 못해도 유효한 재료 포함 관계는 생성 가능",
        ],
    },
    "CONTAINS": {
        "source": "Recipe",
        "target": "Ingredient",
        "meaning": "레시피에 기재된 개별 재료 사용 항목의 기본 재료 또는 첫 선택지",
        "properties": {
            "item_id": "STRING",
            "role": "STRING",
            "group": "STRING",
            "quantity": "STRING",
            "unit": "STRING",
            "preparation": "STRING",
            "is_required": "BOOLEAN",
            "alternative_mode": "STRING",
        },
        "required": ["item_id", "role", "alternative_mode"],
        "unique": ["item_id"],
        "nullable": ["group", "quantity", "unit", "preparation", "is_required"],
        "enum": {
            "role": ["food", "seasoning", "unknown"],
            "alternative_mode": ["none", "replacement", "either_or", "unresolved"],
        },
        "defaults": {"role": "unknown", "is_required": None},
        "description": {
            "item_id": (
                "components[].component.component_uid 그대로 사용. 예: "
                "10000recipe:6876357:component:001. 값에 component가 남아 있어도 "
                "Component 노드를 생성한다는 뜻은 아님"
            ),
            "role": "component.role. 레시피 문맥에서 food=일반 재료, seasoning=양념, unknown=미상",
            "group": "component.group. 양념·밑간 등 사용 구역. 미지정이면 null",
            "quantity": "component.quantity 그대로 복사. 1/2·2~3·약간을 숫자로 강제 변환하지 않음",
            "unit": "component.unit 그대로 복사. 없는 단위를 추정하거나 임의 환산하지 않음",
            "preparation": "component.preparation. 다진·삶은 등 재료 검색 결과 해석에 필요한 상태",
            "is_required": (
                "true=필수라는 명시적 판단, false=생략 가능이라는 명시적 판단, "
                "null/속성 부재=판단 없음. 입력에 키가 없으면 null. "
                "either_or에서는 개별 기본 재료가 아니라 해당 선택 항목 전체의 필요 여부"
            ),
            "alternative_mode": (
                "none=파일에 대체 정보가 기록되지 않음; replacement=기본/대체 방향 있음; "
                "either_or=대등한 선택이며 첫 선택지를 기본 연결로 표현; unresolved=미해결. "
                "none은 대체 불가능을 뜻하지 않음"
            ),
        },
        "validation_rules": [
            "검증된 하나의 입력 Component는 기본 CONTAINS 정확히 하나로 변환",
            "item_id는 정확히 하나의 Recipe와 하나의 기본 Ingredient를 식별",
            "같은 Recipe와 Ingredient 사이에도 item_id가 다르면 별도 관계로 유지",
            "같은 재료라고 그룹·수량이 다른 관계를 합치거나 덮어쓰지 않음",
            "is_required 누락을 true 또는 false로 자동 변경하지 않음",
            "기본 재료가 단일 개체로 확정되지 않으면 해당 항목만 보류",
            "기본 재료가 확정되었지만 대체만 불명확하면 CONTAINS는 유지하고 mode=unresolved",
            "none에는 SUBSTITUTE가 없어야 하고 replacement/either_or에는 검증된 SUBSTITUTE가 하나 이상 있어야 함",
            "유일한 대체 후보가 보류되면 none으로 바꾸지 않고 unresolved로 기록",
        ],
    },
    "SUBSTITUTE": {
        "source": "Recipe",
        "target": "Ingredient",
        "meaning": "해당 레시피의 특정 사용 항목에 대한 대체 재료 또는 대등한 선택지",
        "properties": {
            "for_item_id": "STRING",
            "condition": "STRING",
            "evidence": "STRING",
        },
        "required": ["for_item_id", "evidence"],
        "nullable": ["condition"],
        "description": {
            "for_item_id": "부모 component.component_uid를 복사. 대체 대상 CONTAINS.item_id와 일치",
            "condition": "alternatives[].relation.condition이 있을 때만 보존. 현재 없으면 null",
            "evidence": (
                "alternatives[].relation.evidence에 이미 기록된 근거. "
                "LLM 보완 시에도 이 prepared 파일에 들어 있는 문구만 사용"
            ),
        },
        "validation_rules": [
            "같은 Recipe에서 for_item_id와 일치하는 CONTAINS가 정확히 하나 존재해야 함",
            "replacement/either_or 구분은 참조한 CONTAINS.alternative_mode에서 읽음",
            "한 item_id에 여러 대체재를 연결할 수 있으나 각각 독립적인 선택지여야 함",
            "기본과 대체 Ingredient가 ER 후 같아지면 해당 대체 관계는 보류",
            "같은 Recipe·for_item_id·대체 Ingredient·condition·evidence의 완전 중복만 제거",
            "여러 재료를 함께 써야 하는 복합 대체를 독립적인 대체 관계들로 펼치지 않음",
            "대등한 선택에서 기본 연결은 저장 관례이며 우선순위나 더 높은 필수성을 뜻하지 않음",
            "대체 관계는 이 레시피에만 유효. 역방향·전역·연쇄 대체를 자동 추론하지 않음",
            "for_item_id 참조 무결성은 적재 코드에서 검사. 문자열 속성 자체가 DB 외래키는 아님",
        ],
    },
}

# 그래프 속성으로 적재하지 않고 item_id별 외부 검토 기록에서 사용하는 코드.
# 기존 파일의 세 코드는 보존한다. 뒤의 세 코드는 v2 변환 검사에서 추가 가능하다.
QUALITY_FLAG_CODES = [
    "POSSIBLE_DUPLICATE_COMPONENT",
    "AMBIGUOUS_ALTERNATIVE",
    "COMPOUND_ALTERNATIVE",
    "AMBIGUOUS_INGREDIENT",
    "SELF_ALTERNATIVE",
    "MISSING_ALTERNATIVE_EVIDENCE",
]

SOURCE_MAPPING = {
    "Recipe": "recipe에서 NODE_SCHEMA.Recipe에 정의한 필드만 복사",
    "Dish": "recipe.title에서 음식 후보 추출 후 승인된 음식 Alias 적용. 불명확하면 생략",
    "Ingredient": "components[].ingredient 및 components[].alternatives[].ingredient",
    "VARIANT_OF": "Recipe와 확정된 Dish를 연결",
    "CONTAINS": "components[].component의 선택 필드 + 부모 recipe + 같은 항목의 ingredient",
    "SUBSTITUTE": "각 alternatives[].ingredient + relation + 부모 component_uid + 부모 recipe",
}

PROCESSING_RULES = [
    "입력은 recipes_graph_prepared_v2.jsonl 하나뿐. raw/cleaned/steps를 다시 읽거나 조인하지 않음",
    "Recipe UID는 prepared 값 보존. 이전 실험의 밑줄 UID로 임의 변경하지 않음",
    "metadata·수량·단위·손질·기존 재료값은 Python이 옮기며 LLM에 전체 재출력시키지 않음",
    "Dish 후보는 recipe.title에서 규칙/승인 사전으로 우선 처리하고 필요한 제목만 LLM 사용",
    "대체/생략 보완은 prepared 내부 raw_name·detail·evidence·alternatives에 있는 정보로만 판단",
    "prepared에 근거가 없으면 LLM의 조리 상식으로 필수 여부나 대체재를 만들지 않음",
    "품질 경고는 검토 요청이며 자동 삭제 명령이 아님. 빈 목록도 의미 정확성을 보장하지 않음",
    "오류는 해당 사용 항목 또는 대체 관계만 보류하고 다른 유효한 관계는 유지",
    "components가 비어 있는 Recipe는 메타데이터만 보존하고 재료 검색·통계의 모집단에서 제외",
    "관계 식별/중복/참조/허용 자료형/enum/대체 일관성은 Python에서 검사",
    "Dish/Ingredient Alias 변경 시 모든 관련 노드와 관계 참조를 재연결하고 재검증",
    "현재 prepared에 없는 조리 본문 정보까지 완전하게 포착했다고 주장하지 않음",
]

STATISTICS_RULES = {
    "recipe_usage_count": "CONTAINS를 연결한 Ingredient별 COUNT(DISTINCT Recipe.recipe_uid)",
    "item_usage_count": "Ingredient별 고유 CONTAINS.item_id 개수. 반복 사용이므로 레시피 수와 다를 수 있음",
    "alternative_recipe_count": "SUBSTITUTE로 제시된 Ingredient별 고유 Recipe 수. 기본 재료 사용 횟수에 합산하지 않음",
    "either_or_count": "대등한 선택 항목은 실제 사용 확정이 아니라 기재된 선택지의 빈도로 별도 집계",
    "required_count": "is_required=true만 집계. null은 미상으로 별도 보고",
    "optional_count": "is_required=false인 항목만 집계. 대체 가능성과 생략 가능성을 혼동하지 않음",
    "amount_sum": "현재 목표에서 제외. 서로 다른 단위·인분·정성 수량을 무조건 합산하지 않음",
}
