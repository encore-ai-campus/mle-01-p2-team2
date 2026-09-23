"""레시피 검색과 답변 생성을 담당하는 애플리케이션 로직."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 768
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
VECTOR_INDEX_NAME = "dish_embedding_index"

VECTOR_SEARCH_QUERY = f"""
CALL db.index.vector.queryNodes(
    '{VECTOR_INDEX_NAME}',
    $k,
    $query_embedding
)
YIELD node, score
OPTIONAL MATCH (node)-[:INGREDIENT]->(ingredient:Ingredient)
WITH node, score, collect(ingredient.name_normalized) AS ingredients
RETURN node.recipe_uid AS recipe_uid,
       node.title AS title,
       node.dish_group AS dish_group,
       node.dish_type AS dish_type,
       node.difficulty AS difficulty,
       node.source_url AS source_url,
       node.cooking_method AS cooking_method,
       ingredients,
       score AS similarity
ORDER BY similarity DESC
"""


@lru_cache(maxsize=1)
def load_resources():
    """임베더, LLM, Neo4j 드라이버를 한 번만 초기화한다."""
    from neo4j import GraphDatabase
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    embedder = OpenAIEmbeddings(
        model=EMBED_MODEL,
        dimensions=EMBED_DIM,
    )

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_CHAT_MODEL", "gpt-5.6-luna"),
    )

    neo4j_uri = os.getenv("NEO4J_URI")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not all((neo4j_uri, neo4j_user, neo4j_password)):
        raise RuntimeError(
            "NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD를 .env에 설정해야 합니다."
        )

    driver = GraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password),
    )
    driver.verify_connectivity()

    return embedder, llm, driver


def search_recipes(query: str, k: int = 5, resources=None):
    """사용자 질문과 가까운 레시피를 Neo4j 벡터 인덱스에서 검색한다."""
    embedder, _, driver = resources or load_resources()
    query_vector = embedder.embed_query(query)

    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(
            VECTOR_SEARCH_QUERY,
            k=k,
            query_embedding=query_vector,
        )
        records = [record.data() for record in result]

    return graph_records_to_results(records)


def graph_records_to_results(records: list[dict[str, Any]]) -> dict[str, list[list[Any]]]:
    """Neo4j 벡터 검색 결과를 기존 Streamlit 표시 형식으로 변환한다."""
    documents = []
    metadatas = []

    for record in records:
        ingredients = [
            ingredient
            for ingredient in record.get("ingredients", [])
            if ingredient
        ]
        ingredients_text = ", ".join(ingredients)

        documents.append(
            "\n".join(
                [
                    f"요리명: {record.get('title', '')}",
                    f"대분류: {record.get('dish_group', '')}",
                    f"요리 종류: {record.get('dish_type', '')}",
                    f"난이도: {record.get('difficulty', '')}",
                    f"재료: {ingredients_text}",
                    f"조리 방법: {record.get('cooking_method', '')}",
                ]
            )
        )

        metadatas.append(
            {
                "recipe_uid": record.get("recipe_uid"),
                "title": record.get("title"),
                "dish_group": record.get("dish_group"),
                "dish_type": record.get("dish_type"),
                "difficulty": record.get("difficulty"),
                "source_url": record.get("source_url"),
                "similarity": record.get("similarity"),
            }
        )

    return {
        "documents": [documents],
        "metadatas": [metadatas],
    }


def build_context(documents: list[str]) -> str:
    """검색된 문서 목록을 답변 프롬프트용 문자열로 변환한다."""
    return "\n\n".join(
        f"[레시피 {index + 1}]\n{document}"
        for index, document in enumerate(documents or [])
    )


def generate_answer(query: str, results: dict[str, Any], llm=None) -> str:
    """검색 결과를 근거로 최종 답변을 생성한다."""
    if llm is None:
        _, llm, _ = load_resources()

    documents = results.get("documents", [[]])[0]
    context = build_context(documents)

    messages = [
        SystemMessage(
            content="""
너는 레시피 추천 챗봇이다.

반드시 검색된 레시피 정보를 바탕으로 답변한다.

사용자의 조건에 적합한 레시피를 추천하고,
추천 이유와 주요 재료, 조리 방법을 이해하기 쉽게 설명한다.

검색 결과에 없는 내용을 임의로 만들어내지 않는다.
적절한 레시피를 찾을 수 없다면 찾지 못했다고 말한다.
"""
        ),
        HumanMessage(
            content=f"""
사용자 질문:
{query}

검색된 레시피:
{context}
"""
        ),
    ]

    response = llm.invoke(messages)
    return response.content


def ask(query: str, k: int = 5, resources=None) -> dict[str, Any]:
    """Neo4j 벡터 검색으로 답변하고, 향후 Text-to-Cypher를 연결할 진입점."""
    active_resources = resources or load_resources()
    results = search_recipes(query, k=k, resources=active_resources)
    answer = generate_answer(query, results, llm=active_resources[1])

    return {
        "answer": answer,
        "results": results,
        "mode": "neo4j_vector",
    }
