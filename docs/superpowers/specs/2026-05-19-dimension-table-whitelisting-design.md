# Dimension Table Whitelisting Design Spec

## Goal
Solve the dimension table truncation contradiction in the SQL Agent by implementing an AST-based dynamic whitelisting mechanism. This allows small, critical dimension tables (e.g., dictionaries) to return fully to the LLM for fuzzy matching, while keeping strict safeguards for massive fact tables to prevent OOM and context window exhaustion.

## Scope
- `backend/app/config.py`
- `backend/app/agent/tools/sql_tools.py`
- `.env`

*(Note: `sql_tools_local.py` will not be modified as it is out of scope for this update per user decision).*

## Architecture & Components

### 1. Configuration Layer (`.env` & `config.py`)
- **`.env` variables**:
  - `DIMENSION_TABLES`: A comma-separated string of table names considered as dimensions (e.g., `'process_areas,car_models,colors'`).
  - `DIMENSION_RESULT_HARD_LIMIT`: An integer representing the lenient truncation limit for dimension tables (e.g., `300`).
- **`config.py`**:
  - Add `dimension_tables` (`List[str]`) and `dimension_result_hard_limit` (`int`) to the `Settings` class.
  - Implement a `field_validator` for `dimension_tables` to parse the comma-separated string from the environment into a clean list of lowercase strings.

### 2. AST Parsing Module (`sql_tools.py`)
- **Dependency**: Utilize `sqlglot` to parse the SQL Abstract Syntax Tree safely without regex or substring flaws.
- **`_extract_table_names(query: str) -> set[str]`**:
  - Parse the query using `sqlglot.parse_one(..., error_level=sqlglot.ErrorLevel.IGNORE)`.
  - Extract all `sqlglot.exp.Table` nodes.
  - Return a set of lowercase table names.
  - Exception handling: If parsing fails entirely, catch the exception and return an empty set `set()` (fail-safe to strict mode).
- **`_is_pure_dimension_query(query: str) -> bool`**:
  - Extract the set of tables.
  - If the set is empty, return `False`.
  - Check `issubset` against `settings.dimension_tables`. If true, the query only touches dimension tables.

### 3. Dynamic Truncation Logic (`sql_tools.py`)
- In the `sql_db_query` execution flow, replace the static `hard_limit` lookup:
  ```python
  is_dim = _is_pure_dimension_query(query)
  hard_limit = (
      settings.dimension_result_hard_limit
      if is_dim
      else settings.sql_result_hard_limit
  )
  ```
- The existing limit-check and system warning string generation will natively adopt the newly calculated `hard_limit`.

## Data Flow
1. LLM generates SQL -> `sql_db_query` tool.
2. Tool executes SQL and normalizes dates -> `cleaned_result`.
3. Tool estimates row count -> `estimated_rows`.
4. AST Parser evaluates `query` -> determines if `is_dim`.
5. Tool sets `hard_limit` based on `is_dim`.
6. If `estimated_rows >= hard_limit`, result is truncated and system warning is appended.
7. Else, result is returned fully.

## Error Handling
- **AST Parsing Failure**: Gracefully falls back to returning `set()`, which forces `_is_pure_dimension_query` to return `False`, keeping the restrictive 30-row limit (Fact Table protection remains intact).
- **Empty Config**: If `DIMENSION_TABLES` is empty, the whitelist is empty, and all queries default to the strict limit.

## Testing & Verification
- Unit test or manual verification that `SELECT * FROM process_areas` returns >30 rows.
- Verification that `SELECT * FROM vehicle_tracking JOIN process_areas` triggers the 30-row limit.
- Verification that `SELECT process_areas_id FROM vehicle_tracking` (column name spoofing) triggers the 30-row limit.
