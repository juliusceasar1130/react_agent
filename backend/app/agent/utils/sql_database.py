"""
SQLDatabase 扩展工具

修改时间: 2026-04-12 Asia/Shanghai
主要修改内容:
- 新增支持 PostgreSQL 物化视图的 SQLDatabase 封装
- 新增业务分析库 search_path 的 engine_args 构造函数
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_community.utilities import SQLDatabase
from sqlalchemy import MetaData, create_engine, inspect


def build_postgres_search_path_engine_args(search_path: str) -> dict[str, Any]:
    """为 PostgreSQL 引擎构造 search_path 参数。"""
    cleaned_search_path = ",".join(
        part.strip() for part in search_path.split(",") if part.strip()
    )
    if not cleaned_search_path:
        return {}
    return {
        "connect_args": {
            "options": f"-csearch_path={cleaned_search_path}",
        }
    }


class MaterializedViewSQLDatabase(SQLDatabase):
    """支持把 PostgreSQL 物化视图纳入可用对象集合的 SQLDatabase。"""

    def __init__(
        self,
        engine,
        schema: Optional[str] = None,
        metadata: Optional[MetaData] = None,
        ignore_tables: Optional[list[str]] = None,
        include_tables: Optional[list[str]] = None,
        sample_rows_in_table_info: int = 3,
        indexes_in_table_info: bool = False,
        custom_table_info: Optional[dict] = None,
        view_support: bool = False,
        max_string_length: int = 300,
        lazy_table_reflection: bool = False,
    ) -> None:
        self._engine = engine
        self._schema = schema
        self._inspector = inspect(self._engine)

        all_tables = list(self._inspector.get_table_names(schema=schema))
        if view_support:
            all_tables += self._inspector.get_view_names(schema=schema)
            get_materialized_view_names = getattr(
                self._inspector,
                "get_materialized_view_names",
                None,
            )
            if callable(get_materialized_view_names):
                all_tables += get_materialized_view_names(schema=schema)
        self._all_tables = set(all_tables)

        self._include_tables = set(include_tables) if include_tables else set()
        if self._include_tables:
            missing_tables = self._include_tables - self._all_tables
            if missing_tables:
                raise ValueError(
                    f"include_tables {missing_tables} not found in database"
                )

        self._ignore_tables = set(ignore_tables) if ignore_tables else set()
        if self._ignore_tables:
            missing_tables = self._ignore_tables - self._all_tables
            if missing_tables:
                raise ValueError(
                    f"ignore_tables {missing_tables} not found in database"
                )

        usable_tables = self.get_usable_table_names()
        self._usable_tables = set(usable_tables) if usable_tables else self._all_tables

        if not isinstance(sample_rows_in_table_info, int):
            raise TypeError("sample_rows_in_table_info must be an integer")

        self._sample_rows_in_table_info = sample_rows_in_table_info
        self._indexes_in_table_info = indexes_in_table_info

        self._custom_table_info = custom_table_info
        if self._custom_table_info:
            if not isinstance(self._custom_table_info, dict):
                raise TypeError(
                    "table_info must be a dictionary with table names as keys and the "
                    "desired table info as values"
                )
            intersection = set(self._custom_table_info).intersection(self._all_tables)
            self._custom_table_info = {
                table: self._custom_table_info[table]
                for table in self._custom_table_info
                if table in intersection
            }

        self._max_string_length = max_string_length
        self._view_support = view_support

        self._metadata = metadata or MetaData()
        if not lazy_table_reflection:
            self._metadata.reflect(
                views=view_support,
                bind=self._engine,
                only=list(self._usable_tables),
                schema=self._schema,
            )

    @classmethod
    def from_uri(
        cls,
        database_uri,
        engine_args: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "MaterializedViewSQLDatabase":
        _engine_args = engine_args or {}
        return cls(create_engine(database_uri, **_engine_args), **kwargs)
