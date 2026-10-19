"""LangChain retriever adapter around the existing dimension retrieval function."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field


class PaperRetriever(BaseRetriever):
    """Convert retrieved parent blocks into LangChain Documents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    contest_id: str = ""
    rubric_id: str = ""
    review_id: str = ""
    dimension_code: str = ""
    section_types: tuple[str, ...] = ()
    retrieve_fn: Callable[..., Any] | None = Field(default=None, exclude=True)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Any = None,
    ) -> list[Document]:
        if self.retrieve_fn is None:
            raise ValueError("必须注入 retrieve_fn 后才能使用 PaperRetriever")

        result = self.retrieve_fn(
            query,
            contest_id=self.contest_id,
            rubric_id=self.rubric_id,
            review_id=self.review_id,
            dimension_code=self.dimension_code,
            section_types=self.section_types,
        )
        parents = result.parents
        if result.status == "证据不足" or not parents:
            return []

        return [
            Document(
                page_content=parent.content,
                metadata={
                    "parent_id": parent.parent_id,
                    "section_type": parent.section_type,
                    "chunk_ids": parent.chunk_ids,
                    "review_id": getattr(parent, "review_id", self.review_id),
                },
            )
            for parent in parents
        ]
