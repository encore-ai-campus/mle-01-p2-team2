"""Read-only queries for the verified Aura recipe graph.

DishGroup -HAS_TYPE-> DishType -HAS_DISH-> Dish -INGREDIENT-> Ingredient.
One Dish is one recipe, identified by recipe_uid (not schema_v3_final.py).
"""
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit

from neo4j import GraphDatabase, Query
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable, SessionExpired


@dataclass(frozen=True)
class ConnectionSettings:
    uri: str
    user: str
    password: str = field(repr=False)
    database: str = "neo4j"

    @classmethod
    def from_sources(cls, *sources: Mapping):
        values = {}
        for source in sources:
            values.update(source)
            # Both names identify the same setting; resolve aliases per layer.
            if "NEO4J_USER" in source or "NEO4J_USERNAME" in source:
                values["NEO4J_USER"] = source.get("NEO4J_USER") or source.get("NEO4J_USERNAME") or ""
                values.pop("NEO4J_USERNAME", None)
        return cls.from_mapping(values)

    @classmethod
    def from_mapping(cls, values: Mapping):
        uri = str(values.get("NEO4J_URI") or "").strip()
        user = str(values.get("NEO4J_USER") or values.get("NEO4J_USERNAME") or "").strip()
        password = str(values.get("NEO4J_PASSWORD") or "")
        missing = [key for key, value in (("NEO4J_URI", uri), ("NEO4J_USER", user), ("NEO4J_PASSWORD", password)) if not value]
        if missing:
            raise ValueError("연결 설정을 입력하세요: " + ", ".join(missing))
        if urlsplit(uri).scheme not in {"neo4j+s", "neo4j+ssc", "bolt+s", "bolt+ssc", "neo4j", "bolt"}:
            raise ValueError("NEO4J_URI에 Neo4j 접속 주소를 입력하세요.")
        return cls(uri, user, password, str(values.get("NEO4J_DATABASE") or "neo4j").strip())


def parse_ingredients(value: str) -> list[str]:
    return list(dict.fromkeys(part.strip().lower() for part in value.split(",") if part.strip()))


def safe_source_url(value: str | None) -> str:
    try:
        parsed = urlsplit(value or "")
        return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""
    except ValueError:
        return ""


def public_error(error: Exception) -> str:
    """Never show a driver exception containing connection details to visitors."""
    if isinstance(error, AuthError):
        return "DB 인증에 실패했습니다. NEO4J_USER와 NEO4J_PASSWORD를 확인하세요."
    if isinstance(error, Neo4jError) and "DatabaseNotFound" in (error.code or ""):
        return "DB 이름이 맞지 않습니다. NEO4J_DATABASE를 실제 데이터베이스 이름으로 설정하세요."
    if isinstance(error, (ServiceUnavailable, SessionExpired)):
        return "DB에 연결할 수 없습니다. Aura 실행 상태와 네트워크 연결을 확인한 뒤 다시 시도하세요."
    return "데이터를 불러오지 못했습니다. DB 권한과 데이터 구조를 확인한 뒤 다시 시도하세요."


def read_query(driver, database: str, query: str, **params) -> list[dict]:
    records, _, _ = driver.execute_query(
        Query(query, timeout=20), parameters_=params,
        database_=database, routing_="r",
    )
    return [record.data() for record in records]


def open_driver(settings: ConnectionSettings):
    driver = GraphDatabase.driver(
        settings.uri, auth=(settings.user, settings.password),
        connection_timeout=10, connection_acquisition_timeout=15,
        max_transaction_retry_time=3, max_connection_pool_size=10,
    )
    try:
        # A plain verify_connectivity() can probe the wrong home database.
        read_query(driver, settings.database, "RETURN 1 AS connected")
    except Exception:
        driver.close()
        raise
    return driver


def load_catalog(driver, database: str) -> dict:
    rows = read_query(driver, database, """
        CALL () { MATCH (d:Dish) RETURN count(d) AS recipe_count }
        CALL () { MATCH (i:Ingredient) RETURN count(i) AS ingredient_count }
        CALL () {
            MATCH (g:DishGroup) WITH g ORDER BY g.name
            RETURN collect(g.name) AS groups
        }
        RETURN recipe_count, ingredient_count, groups
    """)
    return rows[0]


def search_recipes(driver, database: str, keyword: str, group: str,
                   required: list[str], excluded: list[str], limit: int) -> list[dict]:
    if not 1 <= limit <= 50:
        raise ValueError("검색 결과 수는 1~50개여야 합니다.")
    return read_query(driver, database, """
        MATCH (g:DishGroup)-[:HAS_TYPE]->(t:DishType)-[:HAS_DISH]->(d:Dish)
        WHERE ($group = '' OR g.name = $group)
          AND ($keyword = '' OR toLower(d.title) CONTAINS $keyword
               OR toLower(t.name) CONTAINS $keyword)
          AND all(term IN $required WHERE EXISTS {
              MATCH (d)-[:INGREDIENT]->(i:Ingredient)
              WHERE toLower(i.name_normalized) = term
          })
          AND none(term IN $excluded WHERE EXISTS {
              MATCH (d)-[:INGREDIENT]->(i:Ingredient)
              WHERE toLower(i.name_normalized) = term
          })
        RETURN DISTINCT d.recipe_uid AS recipe_uid, d.title AS title,
               g.name AS dish_group, t.name AS dish_type,
               d.servings AS servings, d.cooking_time AS cooking_time,
               d.difficulty AS difficulty, coalesce(d.views, 0) AS views
        ORDER BY views DESC, recipe_uid
        LIMIT $limit
    """, keyword=keyword.strip().lower(), group=group,
        required=required, excluded=excluded, limit=limit)


def load_recipe(driver, database: str, recipe_uid: str) -> dict:
    rows = read_query(driver, database, """
        MATCH (d:Dish {recipe_uid: $recipe_uid})
        RETURN d { .recipe_uid, .title, .servings, .cooking_time,
                   .difficulty, .source_url, .cooking_method } AS recipe
    """, recipe_uid=recipe_uid)
    if not rows:
        return {"recipe": None, "ingredients": []}
    ingredients = read_query(driver, database, """
        MATCH (:Dish {recipe_uid: $recipe_uid})-[r:INGREDIENT]->(i:Ingredient)
        RETURN i.name_normalized AS name, r.quantity AS quantity, r.unit AS unit,
               r.source_group AS source_group, r.raw AS raw,
               r.preparation AS preparation, r.amount_text AS amount_text
        ORDER BY r.source_group, toInteger(split(r.usage_key, '|')[2]), r.usage_key
    """, recipe_uid=recipe_uid)
    return {"recipe": rows[0]["recipe"], "ingredients": ingredients}
