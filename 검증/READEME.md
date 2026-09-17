
## 데이터 품질 검증

검증 스크립트 실행:
```bash
uv run python .\validate_recipes.py "..\전처리\recipes_dish_final3.jsonl"

=== Recipe Graph Data Quality Report ===
Recipes                : 3886
Components             : 38754
Alternatives           : 162
Unique recipe_uid      : 3886
Unique component_uid   : 38754
Unique dishes          : 1372
Unique ingredients     : 5189
JSON parse errors      : 0
Errors                 : 0
Warnings               : 0

RESULT: PASS

검증 결과 요약
전체 Recipe: 3,886개
전체 Component: 38,754개
Alternative 관계: 162개
고유 Dish: 1,372개
고유 Ingredient: 5,189개
JSON 파싱 오류: 0건
데이터 검증 오류: 0건
경고: 0건
