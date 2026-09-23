import streamlit as st

from agent import ask


st.set_page_config(
    page_title="레시피 추천 챗봇",
    page_icon="🍳",
)

st.title("🍳 레시피 추천 챗봇")

st.write(
    "원하는 재료나 음식 조건을 입력하면 "
    "레시피를 찾아 추천해드립니다."
)


if "messages" not in st.session_state:
    st.session_state.messages = []


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


query = st.chat_input(
    "예: 닭고기로 만들 수 있는 매콤한 요리 추천해줘"
)

if query:
    st.session_state.messages.append({
        "role": "user",
        "content": query,
    })

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("레시피를 찾고 있습니다..."):
            result = ask(query, k=3)

        answer = result["answer"]
        results = result["results"]

        st.markdown(answer)

        with st.expander("검색된 레시피 보기"):
            for index, metadata in enumerate(results["metadatas"][0]):
                st.write(
                    f"**{index + 1}. "
                    f"{metadata.get('title', '제목 없음')}**"
                )

                st.write(
                    "종류:",
                    metadata.get("dish_type", "정보 없음"),
                )

                st.write(
                    "난이도:",
                    metadata.get("difficulty", "정보 없음"),
                )

                st.write(
                    "유사도:",
                    metadata.get("similarity", "정보 없음"),
                )

                if metadata.get("source_url"):
                    st.write(metadata["source_url"])

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
    })
