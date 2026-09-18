# 1.프로젝트 소개 
저희는 레시피를 모르는 사람들이나 요리를 못하는 사람들에게 요리와 친해지길 바래 라는 생각으로 시작하게 되었습니다
갑자기 요리가 하고 싶어질 때 무스무슨 재료가 있는데 요리가 될까 마땅히 생각이 되지 않을 때 쓰면 좋을거 같다
레시피를 지식그래프 끼리 이어서 어느 재료가 들어가고 어느 재료가 있는지에 대해서 TextToCyper를 통해서 지식그래프 연결 streamlit 배포

# 2. 데이터 수집
데이터 출처 : https://www.10000recipe.com/?srsltid=AU7gw4UhddDc4BJV765zxpv9xQGpsVjtGPPoE04yhK4cuFGsWaxjiK5c
원본 데이터 : recipes_10000.jsonl
최초 수집 건 수 : 10,000건

# 3. 데이터 전처리 / 정재
음식명 정규화
ex) 닭 볶음탕 , 닭도리탕 , 닭볶음탕 , 
재료명 정규화
ex) 달걀 , 계란
수량 단위 처리 
ex) 소금 약간 , 조금 , 큰 술 , 작은 술
대체 재료 처리
ex) 닭가슴살 -> 닭다리삼 , 간장 또는 국간장 
dish_group / dish_type 분류
대분류 , 중분류로 큰 틀과 중간틀 작은틀로 잡음
누락값 
원본 데이터: 10,000건
     ↓
JSON 파싱 오류 / 필수 정보 누락 / 음식 분류 불가 데이터 제거
     ↓
그래프 적재 대상: 9,558건
# 4. 데이터 구조
    "recipe_uid": "10000recipe_6912220",
    "source_id": "6912220",
    title, : 입맛 떨어질 때 쫄깃한...
    source_url : "https://www.10000recipe.com/rec..
    description : 삶은 계란 남은 걸로 양념해서 비벼 먹었...
    servings : 2인분
    더 있지만 여기서 줄임
    
# 5 그래프 스키마 / 온톨로지 
https://github.com/encore-ai-campus/mle-01-p2-team2/blob/main/image/%EC%98%A8%ED%86%A8%EB%A1%9C%EC%A7%80.png?raw=true

| Source Node | Relation | Target Node | 의미 |
|---|---|---|---|
| Recipe | VARIANT_OF | Dish | 레시피가 어떤 음식의 변형인지 |
| Recipe | HAS_COMPONENT | Component | 레시피가 어떤 재료 구성을 가지는지 |
| Component | INGREDIENT | Ingredient | 구성 요소가 어떤 실제 재료인지 |
| Component | ALTERNATIVE | Ingredient | 대체 가능한 재료 |
