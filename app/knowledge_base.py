"""A small, read-only IT SOP source for the Day 3 tool-boundary example."""

from dataclasses import asdict, dataclass
import re


@dataclass(frozen=True)
class KnowledgeBaseArticle:
    article_id: str
    title: str
    content: str


DEFAULT_ARTICLES = (
    KnowledgeBaseArticle(
        article_id="SOP-001",
        title="VPN 無法連線",
        content="確認網路連線後，重新啟動 VPN 用戶端。若仍失敗，記錄錯誤訊息並建立工單。",
    ),
    KnowledgeBaseArticle(
        article_id="SOP-002",
        title="忘記密碼",
        content="使用者必須透過公司自助入口完成密碼重設。IT 人員不得在聊天中索取密碼。",
    ),
    KnowledgeBaseArticle(
        article_id="SOP-003",
        title="筆電無法開機",
        content="確認電源與充電器連接狀態。若電源燈沒有反應，建立硬體支援工單。",
    ),
)


class MockKnowledgeBase:
    """Searches a fixed local SOP set without reading external documents."""

    def __init__(self, articles: tuple[KnowledgeBaseArticle, ...] = DEFAULT_ARTICLES) -> None:
        self.articles = articles

    def search(self, query: str) -> list[dict[str, str]]:
        normalized_query = query.casefold().strip()
        if not normalized_query:
            return []

        terms = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", normalized_query)
        matches = []
        for article in self.articles:
            searchable = f"{article.title}\n{article.content}".casefold()
            if any(term in searchable for term in terms):
                matches.append(asdict(article))
        return matches
