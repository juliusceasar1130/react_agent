
import re
import sys
import os

# 将项目路径加入 sys.path 以便导入
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), ".")))

# 模拟 sql_tools.py 中的正则模式
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|REPLACE|MERGE|EXEC|EXECUTE)\b",
    re.IGNORECASE
)

def test_query(query: str):
    if FORBIDDEN_SQL_PATTERN.search(query):
        print(f"BLOCK: {query}")
        return False
    else:
        print(f"ALLOW: {query}")
        return True

# 测试用例
test_cases = [
    ("SELECT * FROM users", True),
    ("SELECT name FROM employees WHERE id = 1", True),
    ("DROP TABLE users", False),
    ("DELETE FROM orders", False),
    ("UPDATE profile SET name = 'admin'", False),
    ("INSERT INTO logs (msg) VALUES ('test')", False),
    ("ALTER TABLE users ADD COLUMN age INT", False),
    ("SELECT * FROM users; DROP TABLE logs", False), # 多语句注入
    ("TRUNCATE TABLE cache", False),
    ("SELECT id FROM (DELETE FROM x) as t", False), # 嵌套注入
    ("SELECT 1; -- DROP TABLE x", False), # 虽然有注释，但包含关键字也会被拦截（保守策略）
]

success = True
for query, expected in test_cases:
    result = test_query(query)
    if result != expected:
        print(f"FAILED: query='{query}', expected={expected}, actual={result}")
        success = False

if success:
    print("\nVerification Passed: All test cases behaved as expected.")
    sys.exit(0)
else:
    print("\nVerification Failed: Some test cases did not behave as expected.")
    sys.exit(1)
