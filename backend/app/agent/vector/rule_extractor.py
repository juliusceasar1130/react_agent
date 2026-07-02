import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ExtractionContext:
    """提取任务上下文，保存会话状态、中间提取产物及最终输出结果"""
    def __init__(self, message_id: str, db_session):
        self.message_id = message_id
        self.db = db_session
        
        # 流程控制
        self.is_rejected = False
        self.reject_reason = ""
        
        # 原始数据（从 DB 自动加载）
        self.target_message = None     # 目标 assistant 消息
        self.history_messages = []     # 精准回溯还原的上下文历史链
        
        # 待输出至 LLM 的提炼素材（中间产物）
        self.raw_user_query = ""       # 用户原始提问
        self.extracted_sql = ""        # 提取出的单个成功 SQL
        self.tool_result = ""          # 该 SQL 的执行返回结果
        self.domain = "general"        # 业务技能域

class BaseFilter:
    """过滤器基类"""
    def execute(self, context: ExtractionContext) -> bool:
        raise NotImplementedError


class SafetyWarningFilter(BaseFilter):
    """安全过滤器：阻止恶意 DDL/DML 或带安全警告拦截的 SQL 存入"""
    def execute(self, context: ExtractionContext) -> bool:
        from backend.app.config import settings
        if not settings.rule_extractor_safety_enabled:
            return True

        target_content = (context.target_message.content or "").upper() if context.target_message else ""
        tool_res = (context.tool_result or "").upper()
        
        # 1. 检查 SQL 关键字拦截
        blocked_keywords = settings.rule_extractor_blocked_keywords
        for kw in blocked_keywords:
            if kw in target_content:
                context.reject_reason = f"SafetyWarningFilter: 含有违规关键字 {kw}"
                return False
                
        # 2. 检查结果返回的拦截器标记
        warning_markers = settings.rule_extractor_warning_markers
        for marker in warning_markers:
            if marker in tool_res:
                context.reject_reason = f"SafetyWarningFilter: 包含安全警告标记: {marker}"
                return False
                
        return True


class EmptyResultFilter(BaseFilter):
    """空结果集过滤器：丢弃最终执行成功但没有返回任何实质数据的 SQL 案例"""
    def execute(self, context: ExtractionContext) -> bool:
        from backend.app.config import settings
        if not settings.rule_extractor_empty_result_enabled:
            return True

        res_str = (context.tool_result or "").strip()
        if not res_str:
            context.reject_reason = "EmptyResultFilter: 结果为空白文本"
            return False

        # 如果包含多步结果标识，仅检验最后一步的结果
        if "[Step " in res_str:
            steps = res_str.split("[Step ")
            last_step = steps[-1].strip()
            # 去除类似 "N Result]\n" 的行头
            lines = last_step.split("\n", 1)
            if len(lines) > 1:
                res_str = lines[1].strip()
            else:
                res_str = ""

        if not res_str:
            context.reject_reason = "EmptyResultFilter: 最后一步结果为空白文本"
            return False

        try:
            data = json.loads(res_str)
            if isinstance(data, list) and len(data) == 0:
                context.reject_reason = "EmptyResultFilter: 最后一步结果为结构化空列表 []"
                return False
            if isinstance(data, dict) and len(data) == 0:
                context.reject_reason = "EmptyResultFilter: 最后一步结果为结构化空字典 {}"
                return False
        except Exception:
            if len(res_str) < 2:
                context.reject_reason = "EmptyResultFilter: 最后一步结果为非结构化无意义短文本"
                return False

        return True


class SqlStepFilter(BaseFilter):
    """SQL 步骤校验器：提取单步或多步执行成功的 SQL 序列"""
    def execute(self, context: ExtractionContext) -> bool:
        from backend.app.config import settings

        msg = context.target_message
        if not msg or not msg.tool_calls:
            context.reject_reason = "SqlStepFilter: 目标消息没有工具调用"
            return False

        try:
            tool_calls = json.loads(msg.tool_calls)
            tool_results = json.loads(msg.tool_results) if msg.tool_results else {}
        except Exception as e:
            context.reject_reason = f"SqlStepFilter: 序列化解析错误 {e}"
            return False

        # 过滤并找出所有 sql_db_query 工具调用
        sql_calls = [tc for tc in tool_calls if tc.get("name") == "sql_db_query"]

        if not sql_calls:
            context.reject_reason = "SqlStepFilter: 没有调用 sql_db_query 工具"
            return False

        # 计算最大步数：单步模式启用时强制为 1，否则使用配置上限
        max_steps = 1 if settings.rule_extractor_single_sql_enabled else settings.rule_extractor_max_sql_steps

        # 过滤出执行成功的 SQL 调用记录（过滤掉结果包含 ERROR 或 EXCEPTION 的调用）
        valid_sql_calls = []
        for sc in sql_calls:
            call_id = sc.get("id")
            result_content = tool_results.get(call_id) or ""

            if not result_content:
                continue
            if "ERROR:" in result_content.upper() or "EXCEPTION:" in result_content.upper():
                # 属于执行失败或报错步骤，跳过
                continue
            valid_sql_calls.append((sc, result_content))

        if not valid_sql_calls:
            context.reject_reason = "SqlStepFilter: 没有执行成功的 SQL 工具调用"
            return False

        if len(valid_sql_calls) > max_steps:
            context.reject_reason = f"SqlStepFilter: 包含多个 SQL 工具调用 (成功次数 {len(valid_sql_calls)} 超过上限 {max_steps}，舍弃)"
            return False

        # 提取 SQL 文本并拼装
        extracted_sqls = []
        extracted_results = []

        for idx, (call, res_content) in enumerate(valid_sql_calls):
            args = call.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass

            sql_query = args.get("query") if isinstance(args, dict) else ""
            if not sql_query:
                context.reject_reason = f"SqlStepFilter: 无法解析第 {idx + 1} 步的 query 参数"
                return False

            extracted_sqls.append(sql_query)
            extracted_results.append(res_content)

        # 组装存储格式
        if len(extracted_sqls) == 1:
            context.extracted_sql = extracted_sqls[0]
            context.tool_result = extracted_results[0]
        else:
            # 多步拼接
            joined_sql = []
            joined_res = []
            for idx, (sql, res) in enumerate(zip(extracted_sqls, extracted_results)):
                joined_sql.append(f"-- Step {idx + 1}\n{sql.strip()};")
                joined_res.append(f"[Step {idx + 1} Result]\n{res.strip()}")
            context.extracted_sql = "\n\n".join(joined_sql)
            context.tool_result = "\n\n".join(joined_res)

        return True


from backend.app.crud import get_messages_by_session

class TopologyBacktrackFilter(BaseFilter):
    """精准拓扑回溯过滤器：还原多轮对话并拼装完整意图"""
    def execute(self, context: ExtractionContext) -> bool:
        from backend.app.config import settings

        target = context.target_message
        if not target:
            context.reject_reason = "TopologyBacktrackFilter: 上下文中目标消息为空"
            return False
            
        # 1. 加载当前会话的所有历史消息
        all_messages = get_messages_by_session(context.db, target.session_id)
        if not all_messages:
            context.reject_reason = "TopologyBacktrackFilter: 未能获取会话消息历史"
            return False
            
        # 2. 找到当前 target_message 在历史列表中的位置
        try:
            target_idx = -1
            for idx, m in enumerate(all_messages):
                if m.id == target.id:
                    target_idx = idx
                    break
            if target_idx == -1:
                # 如果 id 找不到，备用方案：按内容匹配
                for idx, m in enumerate(all_messages):
                    if m.content == target.content and m.created_at == target.created_at:
                        target_idx = idx
                        break
        except Exception:
            target_idx = len(all_messages) - 1
            
        if target_idx == -1:
            context.reject_reason = "TopologyBacktrackFilter: 无法定位当前消息在会话历史中的位置"
            return False
            
        # 3. 开始精准向上追溯
        history = []
        curr_idx = target_idx
        
        # 将最终这条回复加入临时追踪链
        history.insert(0, all_messages[curr_idx])
        
        # 向上寻找它的触发 User 消息
        curr_idx -= 1
        if curr_idx < 0:
            context.reject_reason = "TopologyBacktrackFilter: 会话缺少 User 提问"
            return False
            
        prev_msg = all_messages[curr_idx]
        history.insert(0, prev_msg)
        
        # 4. 判断 prev_msg（紧邻的 User 消息）是否是对澄清提问（AskUserQuestion）的回复
        # 仅当 backtrack_enabled 且 max_turns >= 2 时才尝试进行澄清链回溯
        if settings.rule_extractor_backtrack_enabled and settings.rule_extractor_backtrack_max_turns >= 2:
            if prev_msg.role == "user" and prev_msg.tool_results:
                try:
                    results = json.loads(prev_msg.tool_results)
                except Exception:
                    results = {}
                    
                # 检查 results 中是否含有 AskUserQuestion 的 key
                # 拓扑咬合：如果包含这个 key，说明该 user 答案是回复上级澄清问答卡片的
                ask_user_ids = list(results.keys())
                
                if ask_user_ids:
                    # 进一步向上寻找产生该 ask_user_id 的 Assistant 澄清消息卡片
                    clarify_idx = curr_idx - 1
                    found_clarify = False
                    
                    while clarify_idx >= 0:
                        potential_clarify = all_messages[clarify_idx]
                        if potential_clarify.role == "assistant" and potential_clarify.tool_calls:
                            try:
                                calls = json.loads(potential_clarify.tool_calls)
                            except Exception:
                                calls = []
                            
                            # 匹配 tool call id
                            if any(c.get("id") == ask_user_ids[0] for c in calls):
                                # 找到了澄清卡片，插入追踪链中
                                history.insert(0, potential_clarify)
                                found_clarify = True
                                
                                # 接着再向上抓取触发该澄清提问的“原始 User 提问”
                                orig_user_idx = clarify_idx - 1
                                if orig_user_idx >= 0:
                                    history.insert(0, all_messages[orig_user_idx])
                                break
                        clarify_idx -= 1
                        
                    if not found_clarify:
                        # 拓扑链断层，退回到普通单轮
                        pass
                        
        # 保存消息历史链
        context.history_messages = history
        
        # 5. 拼装语义意图，供 LLM 后续消解指代
        # 格式化形式为：原始问题 [澄清提问: xxx -> 澄清回答: yyy]
        if len(history) >= 4:
            orig_query = history[0].content
            clarify_q = history[1].content
            clarify_a = history[2].content
            
            # 过滤可能存在的前置澄清修饰词
            clarify_a_clean = clarify_a.replace("[澄清回答]", "").strip()
            context.raw_user_query = f"{orig_query} [澄清提问: {clarify_q} -> 澄清回答: {clarify_a_clean}]"
        else:
            context.raw_user_query = history[0].content
            
        return True


class DomainFilter(BaseFilter):
    """业务域提取器：读取 load_skill 或 tool metadata，定位所属业务技能域进行硬性隔离"""
    def execute(self, context: ExtractionContext) -> bool:
        from backend.app.config import settings
        if not settings.rule_extractor_domain_enabled:
            context.domain = "general"
            return True

        msg = context.target_message
        if not msg or not msg.tool_calls:
            context.domain = "general"
            return True
            
        try:
            calls = json.loads(msg.tool_calls)
        except Exception:
            context.domain = "general"
            return True
            
        domain = None

        # 1. 优先从当前消息的 SQL 调用中直接抓取 required_skill（最精准，直咬合 SQL）
        sql_calls = [c for c in calls if c.get("name") == "sql_db_query"]
        if sql_calls:
            args = sql_calls[0].get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            if isinstance(args, dict):
                domain = args.get("required_skill")

        # 2. 如果没有 SQL 调用（比如非 SQL 执行类消息），退而求其次找 load_skill
        if not domain:
            load_skill_calls = [c for c in calls if c.get("name") == "load_skill"]
            if load_skill_calls:
                args = load_skill_calls[0].get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                if isinstance(args, dict):
                    domain = args.get("skill_name") or args.get("skill")

        # 3. 最终确认与兜底保证不为空
        context.domain = domain or "general"
        return True


class PipelineManager:
    """管道调度管理器"""
    def __init__(self, filters: List[BaseFilter]):
        self.filters = filters
        
    def process(self, message_id: str, db) -> Optional[Dict[str, Any]]:
        context = ExtractionContext(message_id, db)
        
        # 从数据库拉取目标消息
        from backend.app.crud import get_message
        db_message = get_message(db, message_id)
        context.target_message = db_message
        
        for filter_instance in self.filters:
            if not filter_instance.execute(context):
                context.is_rejected = True
                logger.warning(
                    "规则过滤器拦截：消息 %s 未通过 %s 校验，原因: %s",
                    message_id,
                    filter_instance.__class__.__name__,
                    context.reject_reason
                )
                return None
                
        return {
            "message_id": context.message_id,
            "raw_user_query": context.raw_user_query,
            "extracted_sql": context.extracted_sql,
            "tool_result": context.tool_result,
            "domain": context.domain,
            "history_messages": context.history_messages
        }


# 默认的过滤器校验管道，按业务边界顺序链斯执行
DEFAULT_EXTRACTOR_PIPELINE = PipelineManager(filters=[
    SqlStepFilter(),           # 首先提取并填充 SQL 与执行结果
    SafetyWarningFilter(),     # 安全读取已填充的 context.tool_result 和 context.extracted_sql
    EmptyResultFilter(),       # 校验 context.tool_result
    TopologyBacktrackFilter(),
    DomainFilter()
])
