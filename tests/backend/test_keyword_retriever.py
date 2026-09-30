"""keyword 检索测试：命中、零命中、README 排除、排序、截断、来源安全、低相关门槛。

- 分段与 IDF/覆盖度排序用代表性固定 fixture 回归（违纪处分种类）；
- 仓库真实语料另做只读集成回归（知识库缺失时自动跳过）；
- 全程不写知识库、不访问网络。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import REPO_ROOT
from app.services.rag_service import RAGService, REFUSAL_MESSAGE
from app.services.retriever import KeywordRetriever, RetrieverUnavailable

DOC_A = """# 选课管理办法

第一条 学生应当在规定时间内登录教务系统完成选课，逾期未选课按学校通知处理。

第二条 选课时间安排在每学期第一周，补选与退选以教务处通知为准。
"""

DOC_B = """# 考试违规处理办法

考生不得携带手机等电子设备进入考场，违规的按考试违规处理。
"""

README = """# 说明

这段选课内容不应被检索到，因为 README 会被排除。
"""

# 取自 knowledge_base/cleaned/10.大连大学学生违纪管理规定.md 的真实片段（固定回归用）
DISCIPLINE_DOC = """# 大连大学学生违纪管理规定(修订)

（校发 [2022]55号）

# 第一章 总 则

第一条 为贯彻国家教育方针，建立健全育人机制，维护学校正常的教学、工作和生活秩序，维护学生的合法权益，保障学生身心健康。

第五条 学校对违纪学生给予纪律处分，坚持教育与惩戒相结合，应当与学生违法、违规、违纪行为的性质和过错的严重程度相适应。

# 第二章 处分的种类和运用

第六条学校对违纪学生的处理，视其情节，给予相应的纪律

处分。纪律处分的种类分为：

（一）警告；（二）严重警告；（三）记过；（四）留校察看；（五）开除学籍。

第七条 除开除学籍处分以外，纪律处分应设置处分期限。警告、严重警告的处分期限为 6 个月；记过和留校察看的处分期限为 12 个月。

第十三条 违反国家法律、法规，受到公安、司法部门处罚的，视情节轻重，给予警告以上处分。
"""

EDUCATION_DOC = """# 育人工作问答

学校通过管理实现教育目标，如何在日常管理中落实育人要求，是各部门都要思考的问题。

如何把育人目标落实到课堂，如何实现全过程育人，需要任课教师持续探索。

课堂上如何实现思政元素与专业内容结合，是教学改革的重要方向。

如何实现学生自我管理，如何实现班级自治，辅导员需要给出具体办法。

德育工作如何实现家校协同，如何实现信息共享，是常见的问题。

育人成效如何衡量，如何实现可量化的评价，仍在探索中。
"""

KIND_TERMS = ("警告", "严重警告", "记过", "留校察看", "开除学籍")


def write_corpus(root: Path, *docs: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for index, text in enumerate(docs, 1):
        (root / f"文档{index}.md").write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge_base" / "cleaned"
    root.mkdir(parents=True)
    (root / "选课管理办法.md").write_text(DOC_A, encoding="utf-8")
    (root / "考试违规处理办法.md").write_text(DOC_B, encoding="utf-8")
    (root / "README.md").write_text(README, encoding="utf-8")
    return root


@pytest.fixture
def discipline_dir(tmp_path: Path) -> Path:
    return write_corpus(tmp_path / "discipline_kb", DISCIPLINE_DOC, DOC_A, DOC_B)


class _FakeLLM:
    def __init__(self):
        self.calls: list[list[dict]] = []

    def chat(self, messages):
        self.calls.append(messages)
        return "模型回答"


# ------------------------------------------------------------ 基础行为


def test_basic_hit_and_source_safety(kb_dir):
    retriever = KeywordRetriever(kb_dir)
    results = retriever.search("选课时间")
    assert results
    top = results[0]
    assert "选课管理办法.md" in top.source
    assert "README" not in top.source
    # 来源不含盘符 / 反斜杠
    assert ":" not in top.source
    assert "\\" not in top.source
    assert top.score > 0
    assert "选课" in top.text
    assert top.title == "选课管理办法"


def test_zero_match_returns_empty(kb_dir):
    retriever = KeywordRetriever(kb_dir)
    assert retriever.search("火星探测器维护周期") == []


def test_readme_excluded(kb_dir):
    retriever = KeywordRetriever(kb_dir)
    # 只出现在 README 里的句子不应命中
    assert retriever.search("不应被检索到") == []


def test_ranking_prefers_more_matches(kb_dir):
    retriever = KeywordRetriever(kb_dir)
    results = retriever.search("选课")
    assert results
    assert "选课管理办法.md" in results[0].source
    scores = [item.score for item in results]
    assert scores == sorted(scores, reverse=True)


def test_top_k_is_bounded(kb_dir):
    retriever = KeywordRetriever(kb_dir, top_k=1)
    assert len(retriever.search("选课")) == 1
    retriever = KeywordRetriever(kb_dir, top_k=999)
    assert len(retriever.search("选课")) <= 10


def test_snippet_is_bounded(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    long_paragraph = "选课" + "内容" * 600  # 远超 100 字
    (root / "长文档.md").write_text(f"# 长文档\n\n{long_paragraph}\n", encoding="utf-8")
    retriever = KeywordRetriever(root, snippet_max_chars=100)
    results = retriever.search("选课")
    assert results
    snippet = results[0].text
    assert "选课" in snippet
    assert len(snippet) <= 100
    assert snippet.endswith("…")


def test_snippet_keeps_match_at_paragraph_end(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    paragraph = "开头" * 300 + "选课补办流程"  # 命中在长段落末尾
    (root / "长文档.md").write_text(f"# 长文档\n\n{paragraph}\n", encoding="utf-8")
    retriever = KeywordRetriever(root, snippet_max_chars=100)

    results = retriever.search("补办流程")
    assert results
    snippet = results[0].text
    assert "补办流程" in snippet
    assert len(snippet) <= 100
    assert snippet.startswith("…")  # 窗口截取自段落中后部


# ------------------------------------------------------------ 分段与排序回归


def test_discipline_kinds_are_in_top_results(discipline_dir):
    retriever = KeywordRetriever(discipline_dir)
    results = retriever.search("学生违纪处分有哪些种类？")
    assert results
    union = " ".join(item.text for item in results[:5])
    for term in KIND_TERMS:
        assert term in union, term
    # "处分种类"的列举段本身应进入前五，并包含完整五种处分
    assert any(all(term in item.text for term in KIND_TERMS) for item in results[:5])


def test_adjacent_list_stays_with_its_intro(discipline_dir):
    retriever = KeywordRetriever(discipline_dir)
    results = retriever.search("处分种类")
    assert results
    kinds = next((item for item in results if "警告" in item.text and "开除学籍" in item.text), None)
    assert kinds is not None
    # "种类分为："与（一）…（五）列表在同一个片段里，没有被拆散
    assert "种类分为" in kinds.text
    assert "（五）开除学籍" in kinds.text


def test_low_relevance_gate_rejects_off_topic_query(tmp_path):
    root = write_corpus(tmp_path / "kb", DISCIPLINE_DOC, DOC_A, EDUCATION_DOC)
    assert KeywordRetriever(root).search("量子纠缠如何实现超光速通信？") == []


def test_generic_word_only_match_is_gated(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    (root / "通用词.md").write_text(
        "# 通用词\n\n学生应当遵守学校纪律，学生要好好学习，学生要尊敬师长。\n", encoding="utf-8"
    )
    (root / "目标文档.md").write_text(
        "# 目标文档\n\n考试作弊的认定与处理按照学校规定执行。\n", encoding="utf-8"
    )
    retriever = KeywordRetriever(root)
    results = retriever.search("学生考试作弊处理细则")
    sources = {item.source for item in results}
    assert sources == {"目标文档.md"}  # 只命中"学生"的通用段落被门槛过滤


def test_off_topic_query_refuses_without_model(tmp_path):
    root = write_corpus(tmp_path / "kb", DISCIPLINE_DOC, DOC_A, EDUCATION_DOC)
    llm = _FakeLLM()
    service = RAGService(KeywordRetriever(root), llm, prompt="p", retrieval_mode="keyword")
    result = service.answer("量子纠缠如何实现超光速通信？")
    assert result.answer == REFUSAL_MESSAGE
    assert result.sources == []
    assert llm.calls == []


# ------------------------------------------------------------ 真实语料集成回归（只读，缺库跳过）


requires_repo_corpus = pytest.mark.skipif(
    not (REPO_ROOT / "knowledge_base" / "cleaned").is_dir(),
    reason="仓库知识库目录不存在",
)


@requires_repo_corpus
def test_real_corpus_discipline_kinds_in_top5():
    retriever = KeywordRetriever(REPO_ROOT / "knowledge_base" / "cleaned")
    results = retriever.search("学生违纪处分有哪些种类？")
    assert results
    union = " ".join(item.text for item in results[:5])
    for term in KIND_TERMS:
        assert term in union, term


@requires_repo_corpus
def test_real_corpus_off_topic_query_is_refused():
    retriever = KeywordRetriever(REPO_ROOT / "knowledge_base" / "cleaned")
    assert retriever.search("量子纠缠如何实现超光速通信？") == []


@requires_repo_corpus
def test_real_corpus_common_queries_still_hit():
    retriever = KeywordRetriever(REPO_ROOT / "knowledge_base" / "cleaned")
    for query, expected in (
        ("选课时间是怎么规定的？", "选课"),
        ("考试作弊怎么处理", "考试违规"),
        ("怎么申请奖学金", "奖学金"),
    ):
        results = retriever.search(query)
        assert results, query
        assert any(expected in item.source or expected in item.title for item in results), query


# ------------------------------------------------------------ 异常路径


def test_missing_directory_raises_503(tmp_path):
    retriever = KeywordRetriever(tmp_path / "not-exists")
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_empty_directory_returns_empty(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    retriever = KeywordRetriever(empty)
    assert retriever.search("选课") == []


def test_directory_listing_failure_raises_503(kb_dir, monkeypatch):
    def broken_rglob(self, pattern):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "rglob", broken_rglob)
    retriever = KeywordRetriever(kb_dir, top_k=1)
    retriever._docs = None
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_all_files_unreadable_raises_503(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    (root / "坏文件.md").write_bytes(b"\xff\xfe\x00\xff")
    retriever = KeywordRetriever(root)
    with pytest.raises(RetrieverUnavailable):
        retriever.search("选课")


def test_partially_unreadable_files_are_skipped(kb_dir):
    (kb_dir / "坏文件.md").write_bytes(b"\xff\xfe\x00\xff")
    retriever = KeywordRetriever(kb_dir)
    results = retriever.search("选课时间")
    assert results  # 正常文件仍可检索


def test_empty_query_terms_return_empty(kb_dir):
    retriever = KeywordRetriever(kb_dir)
    assert retriever.search("   ") == []


def test_concurrent_first_search_loads_index_once(kb_dir):
    import threading

    retriever = KeywordRetriever(kb_dir)
    results: list[int] = []
    lock = threading.Lock()

    def run():
        found = retriever.search("选课")
        with lock:
            results.append(len(found))

    threads = [threading.Thread(target=run) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(count > 0 for count in results)
    assert retriever.search("选课") is not None
