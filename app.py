"""Run from the repository root: python -m streamlit run app.py."""
from neo4j.exceptions import DriverError, Neo4jError
import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

import recipe_graph as graph


st.set_page_config(page_title="오늘의 레시피", page_icon=":material/restaurant:", layout="wide")
st.title("오늘의 레시피")
st.caption("음식과 재료로 찾고, 재료의 양부터 조리 순서까지 확인하세요.")


@st.cache_resource(max_entries=2, on_release=lambda driver: driver.close())
def get_driver(settings):
    return graph.open_driver(settings)


@st.cache_data(ttl=300, max_entries=4, show_spinner=False)
def get_catalog(settings):
    return graph.load_catalog(get_driver(settings), settings.database)


@st.cache_data(ttl=60, max_entries=128, show_spinner=False)
def find_recipes(settings, keyword, group, required, excluded, limit):
    return graph.search_recipes(get_driver(settings), settings.database, keyword, group, required, excluded, limit)


@st.cache_data(ttl=300, max_entries=128, show_spinner=False)
def get_recipe(settings, recipe_uid):
    return graph.load_recipe(get_driver(settings), settings.database, recipe_uid)


# Local .streamlit/secrets.toml and Cloud Secrets use the same st.secrets API.
keys = ("NEO4J_URI", "NEO4J_USER", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE")
try:
    settings = graph.ConnectionSettings.from_mapping({key: st.secrets[key] for key in keys if key in st.secrets})
except StreamlitSecretNotFoundError:
    st.warning("Secrets 파일을 읽을 수 없습니다. .streamlit/secrets.toml 파일과 TOML 형식을 확인하세요.")
    st.info("프로젝트 루트에서 실행하세요. Cloud 배포 시에는 앱 설정의 Secrets에 접속 정보를 입력하세요.")
    st.stop()
except ValueError as error:
    st.warning(str(error))
    st.info("로컬은 .streamlit/secrets.toml, 배포 환경은 Streamlit 앱 설정의 Secrets에 접속 정보를 입력하세요.")
    st.stop()

with st.sidebar:
    st.header("데이터 연결")
    if st.button("데이터 새로고침", icon=":material/refresh:"):
        # Data-only invalidation; keep the thread-safe connection pool alive.
        get_catalog.clear()
        find_recipes.clear()
        get_recipe.clear()
        st.session_state.pop("results", None)
        st.session_state.pop("selected_recipe", None)

try:
    with st.spinner("레시피 목록을 준비하는 중…"):
        catalog = get_catalog(settings)
except (DriverError, Neo4jError, OSError) as error:
    st.error(graph.public_error(error))
    st.button("다시 연결", key="retry_connection")
    st.stop()

st.sidebar.success("Neo4j Aura 연결됨", icon=":material/check_circle:")
with st.container(horizontal=True):
    st.metric("레시피", f"{catalog['recipe_count']:,}개", border=True)
    st.metric("재료", f"{catalog['ingredient_count']:,}개", border=True)

with st.form("recipe_search"):
    keyword = st.text_input("음식 이름", placeholder="예: 김치찌개, 닭볶음탕", key="keyword", max_chars=100)
    group = st.selectbox("음식 분류", ["전체", *catalog["groups"]], key="group")
    left, right = st.columns(2)
    included = left.text_input("꼭 들어갈 재료", placeholder="예: 두부, 김치", key="included", max_chars=200)
    excluded = right.text_input("제외할 재료", placeholder="예: 소고기", key="excluded", max_chars=200)
    st.caption("재료는 쉼표로 구분하세요. 저장된 재료명과 정확히 일치하는 항목을 찾습니다.")
    limit = st.selectbox("결과 수", [10, 20, 50], key="limit")
    submitted = st.form_submit_button("레시피 찾기", type="primary", icon=":material/search:", key="search")

if submitted:
    required_terms = graph.parse_ingredients(included)
    excluded_terms = graph.parse_ingredients(excluded)
    st.session_state["results"] = []
    st.session_state.pop("selected_recipe", None)
    st.session_state["search_error"] = ""
    overlap = set(required_terms) & set(excluded_terms)
    if overlap:
        st.session_state["search_error"] = "포함·제외 재료가 겹칩니다: " + ", ".join(sorted(overlap))
    else:
        try:
            with st.spinner("조건에 맞는 레시피를 찾는 중…"):
                st.session_state["results"] = find_recipes(
                    settings, keyword, "" if group == "전체" else group,
                    required_terms, excluded_terms, limit,
                )
        except (DriverError, Neo4jError, OSError) as error:
            st.session_state["search_error"] = graph.public_error(error)

if "results" not in st.session_state:
    st.info("검색 조건을 입력하고 ‘레시피 찾기’를 누르세요. 조건 없이 검색하면 조회수 순으로 보여드립니다.")
    st.stop()
if st.session_state.get("search_error"):
    st.error(st.session_state["search_error"])
    st.stop()
results = st.session_state["results"]
if not results:
    st.info("조건에 맞는 레시피가 없습니다. 재료명을 확인하거나 검색 조건을 줄여보세요.")
    st.stop()

st.subheader(f"검색 결과 {len(results)}개")
st.caption("원본 조회수 순으로 표시합니다. 제외 조건은 DB에 기록된 재료에만 적용됩니다.")
columns = {"title": "레시피", "dish_group": "분류", "dish_type": "음식", "cooking_time": "조리 시간", "views": "조회수"}
st.dataframe(pd.DataFrame(results)[list(columns)].rename(columns=columns), hide_index=True)
by_uid = {row["recipe_uid"]: row for row in results}
selected = st.selectbox("상세 레시피 선택", list(by_uid), format_func=lambda uid: by_uid[uid]["title"], key="selected_recipe")

try:
    detail = get_recipe(settings, selected)
except (DriverError, Neo4jError, OSError) as error:
    st.error(graph.public_error(error))
    st.stop()
recipe = detail["recipe"]
if not recipe:
    st.info("레시피가 변경되었거나 삭제되었습니다. 데이터를 새로고침하세요.")
    st.stop()

with st.container(border=True):
    st.subheader(recipe["title"])
    st.caption(" · ".join(str(recipe.get(key) or "정보 없음") for key in ("servings", "cooking_time", "difficulty")))
    source_url = graph.safe_source_url(recipe.get("source_url"))
    if source_url:
        st.link_button("원본 레시피 보기", source_url, icon=":material/open_in_new:")
    st.markdown("**재료와 분량**")
    ingredients = detail["ingredients"]
    if ingredients:
        table = []
        for item in ingredients:
            preparation = item.get("preparation") or []
            table.append({
                "재료": item.get("name"), "수량": item.get("quantity"), "단위": item.get("unit"),
                "구분": item.get("source_group"),
                "손질": ", ".join(str(x) for x in preparation) if isinstance(preparation, list) else str(preparation),
                "원문": item.get("raw"),
            })
        st.dataframe(pd.DataFrame(table), hide_index=True)
    else:
        st.info("등록된 재료 정보가 없습니다. 원본 레시피를 확인하세요.")
    st.markdown("**조리 순서**")
    if recipe.get("cooking_method"):
        st.text(recipe["cooking_method"])
    else:
        st.info("등록된 조리 순서가 없습니다. 원본 레시피를 확인하세요.")
