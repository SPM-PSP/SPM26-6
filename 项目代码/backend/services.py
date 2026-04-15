from collections import defaultdict
import csv
from datetime import datetime
import io
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional
from langchain_community.chat_models import ChatZhipuAI # For LLM interaction
from langchain_core.output_parsers import StrOutputParser # For LLM interaction
from langchain.prompts import ChatPromptTemplate
from typing import Literal

from backend_app.nlp_utils import parse_query_with_llm
from backend_app.security import get_password_hash

IntentType = Literal["INCREMENTAL_ADD", "REVISION", "DELETION", "REWRITE", "UNKNOWN"]
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from backend_app.models import (
    ActivityStat, AdminCreateUserInput, AdminResetPasswordInput, AdminResourceDetailView, AssessmentAnalysis, AssessmentAnalysisOutput, ConceptStat, DailyAccuracy, DashboardUsageResponse, PaginatedAdminResourcesResponse, PaginatedUsersResponse, PracticeChatInput, PracticeChatOutput, 
    FeedbackItem, PracticeQuestionDetailOutput, PracticeQuestionListItem, PracticeQuestionListOutput, PracticeQuestionNLInput, PublishedAssessmentInfo, StudentAssessmentSummary, StudentEffectivenessResponse, StudentQuestionInput, StudentQuestionOutput,
    RefineStudentQAInput, RefineTeachingPlanInput, RefineAssessmentInput, ChatMessage, SubjectPerformance, TeacherAssessmentListItem, TeacherAssessmentListOutput, TeacherEfficiencyStat, UsageStats  # Added new models
)
from backend_app.database_utils import admin_create_user, admin_delete_user, admin_update_user_password, get_activity_stats, get_aggregated_student_performance, get_all_assessment_for_student_view, get_all_practice_attempts_with_concepts, get_all_subjects,  get_assessment_details_by_id, get_assessment_question_stats, get_assessments_by_teacher_id, get_daily_accuracy_trend, get_low_performing_subjects, get_mysql_connection,get_practice_question_details_by_id, get_published_assessments_by_teacher, get_student_for_auth, get_teacher_content_creation_stats, get_teacher_for_auth, get_teacher_resource_detail, get_teaching_plan_by_id, get_unified_resources_by_subject, get_users_by_role, publish_assessment 
from backend_app.student_qa import (
    _rewrite_query_with_history,
    search_knowledge_base_for_answer, 
    construct_student_qa_prompt, 
    construct_student_qa_prompt_with_history, 
    get_llm_response_to_student
)
from backend_app.models import (
    AssessmentInput, 
    StudentAssessmentInput, StudentAssessmentEvaluationOutput,
    PracticeQuestionsInput, PracticeQuestionItem, PracticeQuestionsOutput,
    PracticeFeedbackInput, PracticeFeedbackOutput, StudentPerformanceDetail 
)

from fastapi import HTTPException 

from backend_app.assessment_generator import (
        perform_rag_search,
        construct_assessment_prompt,
        generate_assessment_with_llm,
        construct_assessment_prompt_with_history # Added import
    )
from backend_app.assessment_evaluation import (
        get_assessment_content_by_id, 
        construct_evaluation_prompt,
        get_llm_evaluation_for_answer, 
        parse_llm_evaluation
    )
from backend_app.practice_assistant import ( 
        search_knowledge_for_practice_topic,
        construct_practice_question_prompt,
        get_llm_practice_questions,
        construct_feedback_prompt as pa_construct_feedback_prompt, 
        get_llm_feedback_on_answer as pa_get_llm_feedback_on_answer,
        parse_feedback_and_correctness as pa_parse_feedback_and_correctness
    )

from backend_app.database_utils import (
        save_student_assessment_answer, 
        get_student_history_summary, 
        save_practice_question_to_catalog,
        save_practice_attempt, 
        log_activity
    )   


from langchain_community.embeddings import ZhipuAIEmbeddings
from langchain_chroma import Chroma

from langchain_community.chat_models import ChatZhipuAI

from langchain_core.messages import SystemMessage, HumanMessage,AIMessage

PracticeIntent = Literal["ADD_QUESTIONS", "REWRITE_QUESTIONS", "SUBMIT_ANSWER", "GENERATE_NEW", "UNKNOWN"]
CHROMA_PERSIST_DIR = 'chroma_db_zhipu' 

async def _rewrite_teaching_plan_query(chat_history: List[ChatMessage], new_query: str) -> str:
    """
    使用LLM根据教案对话历史，将用户最新的、可能不完整的后续问题，
    改写成一个独立的、包含完整上下文的、可以用于RAG检索的问题。
    """
    print("SERVICE (Teaching Plan Refine): Rewriting query with history for RAG...")
    
    history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in chat_history])
    
    rewrite_prompt_template = ChatPromptTemplate.from_template("""
        你是一个查询优化助手。你的任务是分析一段关于“教案生成”的对话历史，并将用户最新的、可能不完整的修改指令，改写成一个独立的、包含核心主题的、可以用于信息检索的查询。只输出改写后的查询，不要包含任何额外解释。

        **示例:**
        - **历史**: 对话是关于“一战历史”的教案。
        - **最新指令**: “增加一些关于萨拉热窝事件的细节”
        - **你的输出**: 一战历史中的萨拉热窝事件细节

        - **历史**: 对话是关于“Python列表推导式”的教案。
        - **最新指令**: “再加几个练习题”
        - **你的输出**: 关于Python列表推导式的练习题示例

        ---
        **对话历史:**
        {history}
        ---
        **用户的最新修改指令是:** "{query}"
        ---
        **改写后的独立检索查询:**
    """)
    
    try:
        # Note: Using a specific model for this task can be beneficial.
        # GLM-4 is generally good for instruction-following tasks like rewriting.
        llm = ChatZhipuAI(model="glm-4", temperature=0.0) 
        chain = rewrite_prompt_template | llm | StrOutputParser()
        rewritten_query = await chain.ainvoke({"history": history_str, "query": new_query})
        print(f"SERVICE (Teaching Plan Refine): Original query: '{new_query}', Rewritten query: '{rewritten_query}'")
        return rewritten_query.strip()
    except Exception as e:
        print(f"SERVICE ERROR (Teaching Plan Refine): Failed to rewrite query: {e}. Falling back to original query.")
        return new_query

async def _identify_user_intent(chat_history: List[ChatMessage], new_query: str) -> IntentType:
    print("SERVICE : Identifying user intent...")
    history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in chat_history])
    
    intent_prompt = f"""
你是一个执行严格指令的文本分类器，专注于分析【教案修改】相关的对话。你的唯一任务是将用户的最新指令分类为以下五种意图之一：INCREMENTAL_ADD, REVISION, DELETION, REWRITE, UNKNOWN。

**【核心分类规则 - 这是最重要的！】**
- **REVISION (修订)**: 当用户要求修改、替换、或重写【文档的某一个具体部分】时，意图是REVISION。**即使指令中包含“重写”这个词，只要它指向的是一个局部（例如“重写第二章”、“重写引言”），就必须分类为REVISION。**
- **REWRITE (重写)**: **只有当**用户的指令明确表示要【抛弃整个原文】，或者提出一个【全新的、与原文主题无关】的要求时，意图才是REWRITE。
- **INCREMENTAL_ADD (增补)**: 在原文基础上增加新内容。
- **DELETION (删除)**: 从原文中移除某个部分。
- **UNKNOWN (未知)**: 无法判断或闲聊。

---
**【示例学习】**
- 指令: "请重写课堂讨论环节。" -> **正确分类: REVISION**
- 指令: "把关于杜甫的部分改一下。" -> **正确分类: REVISION**
- 指令: "算了，我们重新开始，写一个关于宋词的教案。" -> **正确分类: REWRITE**
- 指令: "重写这份教案。" -> **正确分类: REWRITE**
---

对话历史:
{history_str}
---
用户最新指令: "{new_query}"
---

输出分类结果（一个单词）:
"""
    
    try:
        llm = ChatZhipuAI(model="glm-4", temperature=0.0)
        response = await llm.ainvoke(intent_prompt)
        intent = response.content.strip()
        
        valid_intents = ["INCREMENTAL_ADD", "REVISION", "DELETION", "REWRITE", "UNKNOWN"]
        if intent in valid_intents:
            print(f"SERVICE : Identified intent as: {intent}")
            return intent
        else:
            print(f"SERVICE WARNING : LLM returned an invalid intent '{intent}'. Defaulting to UNKNOWN.")
            return "UNKNOWN"
            
    except Exception as e:
        print(f"SERVICE ERROR : Failed to identify intent: {e}")
        return "UNKNOWN"

async def _identify_practice_intent(history: List[ChatMessage], new_query: str, active_question_text: Optional[str] = None) -> PracticeIntent:
    """使用LLM分析对话，判断用户更精确的意图。"""
    print("SERVICE: Identifying nuanced practice assistant intent...")
    history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in history])

    active_question_context = ""
    if active_question_text and active_question_text.strip():
        active_question_context = f"""
    **当前激活的题目 (如果学生正在作答):**
    ---
    {active_question_text}
    ---
    """
    else:
        active_question_context = "**当前没有激活的题目。**"



    intent_prompt = f"""
    你是一个文本分类器，任务是分析学生与AI练习助手的对话，判断学生最新输入的意图。
    意图只能是以下五种之一: ADD_QUESTIONS, REWRITE_QUESTIONS, SUBMIT_ANSWER, GENERATE_NEW, UNKNOWN。

    {active_question_context}

    **意图定义:**
    - ADD_QUESTIONS: 用户明确要求在上一轮题目基础上【增加】新的题目。
      (关键词: "再来几道", "加上", "多出点", "还想要2道")
    - REWRITE_QUESTIONS: 用户对上一轮的题目不满意，要求【替换】或【重写】。这包括改变难度、换内容、或完全换题型。
      (关键词: "太难了", "简单点", "换一批", "不要这个", "换成选择题")
    - SUBMIT_ANSWER: 用户正在提供问题的答案。**这是一个高优先级的判断**。如果【当前激活的题目】存在，并且用户的输入可以被合理解释为该题目的答案（**即使是很短的词或数字**），则意图应为 SUBMIT_ANSWER。例如，题目是填空题，用户的输入只是一个词。
    - GENERATE_NEW: 用户想开始一个【全新的练习主题】，与上一轮无关。
      (关键词: "我们来练习...", "换个主题", "我想学...", "出点关于...的题")
    - UNKNOWN: 无法判断或闲聊。

    **对话历史:**
    ---
    {history_str}
    ---
    **学生最新输入:** "{new_query}"
    ---

    **示例 (填空题作答):**
    - 当前激活的题目: "法国的首都是____。"
    - 学生最新输入: "巴黎"
    - 你的输出: SUBMIT_ANSWER

    你的输出【必须只包含一个单词】，即你选择的意图类型。
    """
    try:
        llm = ChatZhipuAI(model="glm-4", temperature=0.0)
        response = await llm.ainvoke(intent_prompt)
        intent = response.content.strip()
        
        valid_intents: List[PracticeIntent] = ["ADD_QUESTIONS", "REWRITE_QUESTIONS", "SUBMIT_ANSWER", "GENERATE_NEW", "UNKNOWN"]
        if intent in valid_intents:
            print(f"SERVICE: Identified intent as: {intent} (with active question context)")
            return intent
        print(f"SERVICE WARNING: LLM returned invalid intent '{intent}'. Defaulting to UNKNOWN.")
        return "UNKNOWN"
    except Exception as e:
        print(f"SERVICE ERROR: Failed to identify practice intent: {e}")
        return "UNKNOWN"

# In services.py, replace the existing process_practice_chat_service with this one

async def process_practice_chat_service(input_data: PracticeChatInput) -> PracticeChatOutput:
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    active_question_text = None
    practice_set_details = None

    try:
        if input_data.active_catalog_id and db_conn:
            print(f"SERVICE: Active catalog ID {input_data.active_catalog_id} found. Fetching question text for context.")
            practice_set_details = get_practice_question_details_by_id(db_conn, input_data.active_catalog_id)
            if practice_set_details:
                active_question_text = practice_set_details.get("question_text")

        intent = await _identify_practice_intent(input_data.history, input_data.new_query, active_question_text)

        # --- Branch 1: User is submitting an answer (No changes needed) ---
        if intent == "SUBMIT_ANSWER":
            if not input_data.active_catalog_id:
                return PracticeChatOutput(assistant_response_text="我好像不知道你在回答哪一套题，请先让我出题。", intent_detected=intent)
            
            if not practice_set_details:
                 return PracticeChatOutput(assistant_response_text=f"抱歉，我找不到ID为 {input_data.active_catalog_id} 的题目了，我们重新开始吧？", intent_detected=intent, error_message="Active practice set not found in DB.")

            try:
                feedback_input = PracticeFeedbackInput(student_id=input_data.student_id, catalog_id=input_data.active_catalog_id, student_answer=input_data.new_query)
                feedback_result = await get_practice_feedback_service(feedback_input)
                log_activity(
                        db_conn,
                        user_id=input_data.student_id,
                        user_role="student",
                        activity_type="PRACTICE_SUBMIT_ANSWER",
                        details={"catalog_id": input_data.active_catalog_id, "attempt_id": feedback_result.attempt_id}
                    )
                return PracticeChatOutput(assistant_response_text="这是你本次作答的反馈：", intent_detected=intent, feedback=feedback_result, catalog_id=0)
            except Exception as e:
                print(f"Error during feedback service call: {e}")
                return PracticeChatOutput(assistant_response_text="抱歉，在评价你的答案时出错了。", intent_detected=intent, error_message=str(e))

        # --- Branch 2: User wants to generate a completely new set of questions (No changes needed) ---
        elif intent == "GENERATE_NEW":
            nlp_prompt_new = """
            你是一个分析专家。请从以下文本中提取【核心练习主题】和【明确的题目偏好】。
            ---
            "{new_query}"
            ---
            你需要提取:
            1. "practice_topic" (字符串, 必填): 核心练习主题。
            2. "question_preferences" (对象, 必填): 一个只包含【题型:数量】的JSON对象。
            你的最终响应必须是且只能是一个JSON对象。
            """
            FULL_PROMPT = nlp_prompt_new.format(new_query=input_data.new_query)
            parsed_entities = await parse_query_with_llm(FULL_PROMPT)

            if "error" in parsed_entities or not parsed_entities.get("practice_topic"):
                return PracticeChatOutput(assistant_response_text="我不太明白你想要练习什么，可以再说清楚一点吗？", intent_detected=intent)

            practice_topic = parsed_entities.get("practice_topic")
            question_preferences = parsed_entities.get("question_preferences", {})
            
            service_input = PracticeQuestionsInput(student_id=input_data.student_id, practice_topic=practice_topic, question_preferences=question_preferences)
            new_questions_result, rag_snippets = await generate_practice_questions_service(service_input)

            if new_questions_result.error_message:
                return PracticeChatOutput(assistant_response_text=f"抱歉，生成题目时出错了: {new_questions_result.error_message}", intent_detected=intent)
            
            if rag_snippets and new_questions_result.generated_questions:
                source_attribution_text = "\n\n---\n**知识来源 (Knowledge Sources):**\n" + "".join([f"  • {' '.join(s.split())[:120]}...\n" for s in rag_snippets])
                new_questions_result.generated_questions.question_text += source_attribution_text
            
            log_activity(db_conn, user_id=input_data.student_id, user_role="student", activity_type="GENERATE_NEW_PRACTICE", details={"new_catalog_id": new_questions_result.catalog_id})
            
            return PracticeChatOutput(
                assistant_response_text="好的，这是为你准备的新题目：",
                intent_detected=intent,
                new_questions=new_questions_result,
                catalog_id=new_questions_result.catalog_id
            )

        # --- 【REFACTORED】Branch 3 & 4: ADD and REWRITE questions ---
        elif intent in ["ADD_QUESTIONS", "REWRITE_QUESTIONS"]:
            if not input_data.active_catalog_id:
                return PracticeChatOutput(assistant_response_text="我需要先为你出一套题，才能在它的基础上修改哦。", intent_detected=intent)
            if not practice_set_details:
                return PracticeChatOutput(assistant_response_text=f"抱歉，我找不到ID为 {input_data.active_catalog_id} 的题目了，我们重新开始吧？", intent_detected=intent, error_message="Active practice set not found in DB.")

            # --- 【核心修改 1: 内联查询重写逻辑】 ---
            print("SERVICE (Practice Refine): Inlining query rewrite with history...")
            history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in input_data.history])
            rewrite_prompt_template = ChatPromptTemplate.from_template("""
                你是一个查询优化专家，专注于处理“智能练习助手”的对话。
                你的任务是：分析对话历史，提取出【核心练习主题】和【所有历史约束】，然后将用户的【最新修改指令】智能地融入其中，生成一个全新的、独立的、完整的练习题生成指令。
                **核心原则：继承并覆盖。**
                **示例**: 历史是“关于《万历十五年》书中人物的选择题”，最新指令是“简单点的”，你的输出应为“生成一些关于《万历十五年》书中人物的、难度简单的选择题。”
                ---
                对话历史: {history}
                ---
                用户的最新修改指令是: "{query}"
                ---
                请生成全新的、独立的、完整的练习题生成指令:
            """)
            
            rewritten_full_instruction = ""
            try:
                llm_rewrite = ChatZhipuAI(model="glm-4", temperature=0.0) 
                chain_rewrite = rewrite_prompt_template | llm_rewrite | StrOutputParser()
                rewritten_full_instruction = await chain_rewrite.ainvoke({"history": history_str, "query": input_data.new_query})
            except Exception as e:
                print(f"SERVICE ERROR (Inline Rewrite): {e}. Falling back.")
                first_user_message = next((msg.content for msg in input_data.history if msg.role == 'user'), '')
                rewritten_full_instruction = f"{first_user_message} {input_data.new_query}"
            
            print(f"SERVICE (Practice Refine): Rewritten instruction: '{rewritten_full_instruction}'")
            # --- 查询重写结束 ---

            # 2. 从重写后的完整指令中提取结构化信息
            nlp_prompt_extract = f"""
            你是一个高度智能的指令分析专家。你的任务是从用户的【完整指令】中，提取【核心练习主题】和【题目偏好】，并输出一个严格的JSON对象。

            --- 用户的完整指令 ---
            {rewritten_full_instruction}
            ---

            **【你的提取任务和规则】**

            1.  **`practice_topic` (字符串, 必填)**: 提取用户想要练习的核心主题。
            2.  **`question_preferences` (JSON对象, 必填)**: 提取题型和数量。
                - **规则 A (数值提取)**: 如果指令中【明确提到了数字】（例如“5道选择题”），你必须提取那个【整数】。
                - **规则 B (默认值)**: 如果指令中【没有提到数字】，只是提到了题型或难度（例如“来点选择题”、“简单点的题”），你【必须】为该题型设定一个合理的【默认整数数量】，例如 `3` 或 `5`。
                - **【最重要】**: `question_preferences` 的值【必须永远是整数】，绝不能是 "一些"、"几个" 或 "简单" 这样的字符串。

            **【示例】**

            *   **输入指令**: "请生成5道关于《万历十五年》的选择题"
            *   **你的输出**:
                ```json
                {{
                  "practice_topic": "《万历十五年》",
                  "question_preferences": {{ "选择题": 5 }}
                }}
                ```

            *   **输入指令**: "请生成一些关于《万历十五年》书中人物的、难度调整为简单的选择题。"
            *   **你的输出 (应用规则 B)**:
                ```json
                {{
                  "practice_topic": "《万历十五年》书中人物",
                  "question_preferences": {{ "选择题": 5 }}
                }} ```

            你的最终响应必须是且只能是一个符合以上规则的JSON对象。
            """
            parsed_entities = await parse_query_with_llm(nlp_prompt_extract)
            if "error" in parsed_entities or not parsed_entities.get("practice_topic"):
                return PracticeChatOutput(assistant_response_text="抱歉，我没能完全理解你的修改要求，可以再说清楚一点吗？", intent_detected=intent)

            practice_topic = parsed_entities.get("practice_topic")
            question_preferences = parsed_entities.get("question_preferences", {})

            # 3. 使用重写后的指令进行RAG检索
            embeddings = ZhipuAIEmbeddings()
            rag_snippets = search_knowledge_for_practice_topic(rewritten_full_instruction, embeddings, CHROMA_PERSIST_DIR, top_k=5)

            # 4. 调用统一的生成器
            student_history_summary = get_student_history_summary(db_conn, input_data.student_id)
            prompt_components = construct_practice_question_prompt(
                practice_topic=practice_topic,
                question_preferences=question_preferences,
                student_history_summary=student_history_summary,
                retrieved_context_snippets=rag_snippets
            )
            raw_generated_questions = get_llm_practice_questions(
                prompt_components["system_message"],
                prompt_components["human_message"]
            )
            
            # 5. 【合并逻辑】如果意图是ADD，将新生成的内容与旧内容合并
            if intent == "ADD_QUESTIONS":
                original_questions = practice_set_details.get("question_text", "")
                original_answers = practice_set_details.get("model_answer", "")
                separator = "---参考答案与解析---"
                if separator in raw_generated_questions:
                    new_questions_part, new_answers_part = raw_generated_questions.split(separator, 1)
                    final_questions = f"{original_questions}\n\n{new_questions_part.strip()}".strip()
                    final_answers = f"{original_answers}\n\n{new_answers_part.strip()}".strip()
                    raw_generated_questions = f"{final_questions}\n\n{separator}\n\n{final_answers}"
                else:
                    raw_generated_questions = f"{original_questions}\n\n{separator}\n\n{original_answers}\n\n{raw_generated_questions}"

            # 6. 调用下游服务保存
            service_input = PracticeQuestionsInput(student_id=input_data.student_id, practice_topic=practice_topic, question_preferences=question_preferences)
            new_questions_result, _ = await generate_practice_questions_service(service_input, raw_generated_questions=raw_generated_questions)

            if new_questions_result.error_message:
                return PracticeChatOutput(assistant_response_text=f"抱歉，在处理你的题目时出错了: {new_questions_result.error_message}", intent_detected=intent)

            # 7. 附加知识来源并返回
            if rag_snippets and new_questions_result.generated_questions:
                source_attribution_text = "\n\n---\n**知识来源 (Knowledge Sources):**\n" + "".join([f"  • {' '.join(s.split())[:120]}...\n" for s in rag_snippets])
                new_questions_result.generated_questions.question_text += source_attribution_text
            
            log_activity(db_conn, user_id=input_data.student_id, user_role="student", activity_type=f"PRACTICE_{intent}", details={"new_catalog_id": new_questions_result.catalog_id, "based_on_id": input_data.active_catalog_id})
            
            response_text = "好的，已为你添加新题目。这是修改后的完整练习题：" if intent == "ADD_QUESTIONS" else "好的，这是根据你的要求修改后的完整练习题："
            return PracticeChatOutput(
                assistant_response_text=response_text,
                intent_detected=intent,
                new_questions=new_questions_result,
                catalog_id=new_questions_result.catalog_id
            )
        
        # --- Branch 5: Fallback ---
        else: # UNKNOWN
            return PracticeChatOutput(
                assistant_response_text="我不太确定该怎么做，你可以尝试让我“出题”、“修改题目”或者直接“提交你的答案”。",
                intent_detected="UNKNOWN"
            )
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()
    
async def _identify_assessment_intent(chat_history: List[ChatMessage], new_query: str) -> IntentType:
    print("SERVICE : Identifying user intent...")
    history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in chat_history])
    
    # Prompt 针对“试卷”场景进行微调
    intent_prompt = f"""
    你是一个用户意图分析专家，专注于分析【考核试卷】生成相关的对话。请分析对话历史和用户最新指令，将其核心意图分类为以下五种之一：

 - INCREMENTAL_ADD: 用户要求在原试卷基础上【增加】新的题目、题型或说明，而【不改变】已有内容。 (例如: "再加两道选择题", "在末尾加上评分标准")
 - REVISION: 用户要求【修改、替换或重写】原试卷中【已经存在】的某道题目或某个部分。 (例如: "把第一题改得更难一些", "选择题部分全部换成新的")
 - DELETION:用户要求杀掉什么题
 -REWRITE:全部重新生成
 -UNKNOWN:无法判断
    ---
    对话历史:
    {history_str}
    ---
    用户最新指令: "{new_query}"
    ---

    你的回答【必须只包含一个单词】，即你选择的意图类型。不要有任何解释。
    """
    

    try:
        llm = ChatZhipuAI(model="glm-4", temperature=0.0)
        # 这里可以加一个OutputParser来确保输出格式正确，但简单起见，我们先直接解析字符串
        response = await llm.ainvoke(intent_prompt)
        intent = response.content.strip()
        
        valid_intents = ["INCREMENTAL_ADD", "REVISION", "DELETION", "REWRITE", "UNKNOWN"]
        if intent in valid_intents:
            print(f"SERVICE : Identified intent as: {intent}")
            return intent
        else:
            print(f"SERVICE WARNING : LLM returned an invalid intent '{intent}'. Defaulting to UNKNOWN.")
            return "UNKNOWN"
    except:
        return "UNKNOWN"

def _get_zhipuai_api_key():
    api_key = os.environ.get("ZHIPUAI_API_KEY")
    print(api_key)
    if api_key is None:
        print("Warning: ZHIPUAI_API_KEY not found in environment. Using default key for service layer.")
        
    return api_key



async def process_student_question_service(input_data: StudentQuestionInput) -> StudentQuestionOutput:

    print(f"SERVICE: Processing student question: '{input_data.question}'")
    api_key = _get_zhipuai_api_key()
    rag_snippets = []
    llm_answer = "Could not determine an answer."
    error_message = None
    try:

        try:
            embeddings = ZhipuAIEmbeddings() 
        except Exception as e:
            print(f"SERVICE ERROR: Failed to initialize embeddings model: {e}")
            return StudentQuestionOutput(
                student_question=input_data.question,
                rag_context=None,
                llm_answer="Error: Could not initialize embeddings model.",
                error_message=f"Failed to initialize embeddings model: {e}"
            )

        rag_snippets = search_knowledge_base_for_answer(
            student_question=input_data.question,
            embeddings_model_instance=embeddings,
            vector_store_dir=CHROMA_PERSIST_DIR,
            top_k=5 
        )
        print(f"SERVICE: RAG search retrieved {len(rag_snippets)} snippets.")

        
        messages_for_llm = construct_student_qa_prompt(
            student_question=input_data.question,
            rag_snippets=rag_snippets
        )
        print("SERVICE: Prompt constructed.")

     
        llm_response = get_llm_response_to_student(
            messages=messages_for_llm
        )

        if llm_response:
            llm_answer = llm_response
            print("SERVICE: LLM response received.")
            db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
            log_activity(
                        db_conn,
                        user_id=input_data.student_id,
                        user_role="student",
                        activity_type="STUDENT_QA",
                        details={"question_length": len(input_data.question)}
                    )
            db_conn.close()
        else:
            llm_answer = "Failed to get a response from the LLM."
            error_message = "LLM did not provide an answer."
            print("SERVICE ERROR: LLM did not provide an answer.")
            
    except Exception as e:
        print(f"SERVICE ERROR: An unexpected error occurred: {e}")
        error_message = f"An unexpected error occurred: {str(e)}"
        # Ensure llm_answer reflects error if it happened before LLM call
        if llm_answer == "Could not determine an answer.": # Check if it's still the initial default
            llm_answer = "An error occurred while processing the question."

    return StudentQuestionOutput(
        student_question=input_data.question,
        rag_context=rag_snippets if rag_snippets else None,
        llm_answer=llm_answer,
        error_message=error_message
    )

async def generate_initial_teaching_plan_service(

    initial_outline: str,
    style_tone:str,
    output_structure:str
) -> tuple[str , List[str] ]:
    zhipuai_api_key = _get_zhipuai_api_key()
    if not style_tone or not style_tone.strip():
        final_style_tone = "清晰、专业且易于理解"
        print(f"SERVICE INFO: 'style_tone' was empty, using default: '{final_style_tone}'")
    else:
        final_style_tone = style_tone
    if not output_structure or not output_structure.strip():
        final_output_structure = "请为以下教学大纲生成一个完整的教案。内容应包括：1. 教学目标；2. 知识点详解；3. 课堂活动与互动环节建议；4. 简单的实训练习及其指导；5. 预估的时间分布。" # 这是一个非常全面和实用的默认结构
        print(f"SERVICE INFO: 'output_structure' was empty, using default: '{final_output_structure}'")
    else:
        final_output_structure = output_structure
    retrieved_rag_snippets = []
    try:
        print(f"SERVICE: Performing RAG search for query: '{initial_outline[:100]}...'")
        embeddings = ZhipuAIEmbeddings()
        retrieved_rag_snippets = perform_rag_search(
            keywords_list=[initial_outline],
            embeddings_model_instance=embeddings,
            vector_store_dir=CHROMA_PERSIST_DIR,
            top_k=10
        )
    except Exception as e:
        print(f"SERVICE ERROR during RAG search: {e}. Proceeding without RAG context.")

    system_message = (
    # 在系统消息里就埋下伏笔
    "你是一位经验丰富的教师和教案设计师，以其结构清晰、逻辑严谨的教案而闻名。你的任务是根据提供的大纲和要求，撰写一份详细的教案初稿。**你必须严格遵守用户指定的输出结构。**"
)
    human_message_parts = []
    human_message_parts.append(
    f"""
**【最高优先级指令：输出结构】**
你的最终输出【必须且只能】包含以下几个部分，并严格使用我提供的一级标题。不要增加、减少或修改任何一级标题。这是最重要的规则！

---
{final_output_structure}
---
"""
)

# --- 然后再提供其他上下文信息 ---
    human_message_parts.append(
    f"现在，请根据以下信息，为我生成一份完全符合上述结构要求的教案初稿。\n"
)
    human_message_parts.append(f"**1. 核心教学大纲:**\n{initial_outline}\n")

    if retrieved_rag_snippets:
        human_message_parts.append("**2. 补充参考材料 (用于丰富内容):**")
        for i, snippet in enumerate(retrieved_rag_snippets):
            human_message_parts.append(f"--- Snippet {i+1} ---\n{snippet}\n--- End Snippet {i+1} ---")
    else:
        human_message_parts.append("(无补充参考材料)")

    human_message_parts.append(f"\n**3. 输出语言风格要求:**\n{final_style_tone}\n")

    # --- 再次强调！---
    human_message_parts.append("\n**最后提醒：请务必、严格按照开头的【最高优先级指令：输出结构】来组织你的回答。如果你的最终输出不符合此模板的结构，你的任务就视为完全失败。**")
    

    human_message_content = "\n".join(human_message_parts)


    try:
        print("SERVICE: Initializing LLM for teaching plan generation (ChatZhipuAI)...")
        llm_for_plan = ChatZhipuAI(model="glm-4", temperature=0.7, api_key=zhipuai_api_key) 

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=human_message_content)
        ]
        
        print("SERVICE: Generating teaching plan via LLM...")
        ai_message = await llm_for_plan.ainvoke(messages) 
        generated_plan_content = ai_message.content

        if generated_plan_content and generated_plan_content.strip():
            print("SERVICE: Teaching plan generated successfully.")
            return generated_plan_content, retrieved_rag_snippets
        else:
            print("SERVICE ERROR: LLM returned empty content for teaching plan.")
            return None, retrieved_rag_snippets 
    except Exception as e:
        print(f"SERVICE ERROR during LLM call for teaching plan generation: {e}")
        return None, retrieved_rag_snippets

async def generate_assessment_service(
    input_data: AssessmentInput,
) -> tuple[str , str ]: 
    print(f"SERVICE: Initiating assessment generation for subject: {input_data.subject or 'General'}")

    final_question_prefs = input_data.question_preferences
    # --- 使用 subject 进行智能推荐 ---
    if not final_question_prefs:
        print("SERVICE INFO: No question preferences. Applying smart defaults based on subject.")
        subject_lower = (input_data.subject or "").lower()
        if "computer" in subject_lower or "编程" in subject_lower or "programming" in subject_lower:
            final_question_prefs = {"选择题": 2, "编程题": 2}
        else:
            final_question_prefs = {"选择题": 3, "简答题": 2}
        print(f"SERVICE INFO: Using defaults for '{input_data.subject}': {final_question_prefs}")
    
    retrieved_rag_snippets = []
    generated_assessment_content = None
    try:
        # 在调用construct_assessment_prompt之前，先执行RAG搜索
        print(f"SERVICE: Performing RAG search for assessment content: '{input_data.teaching_plan_content[:100]}...'")
        embeddings = ZhipuAIEmbeddings()
        retrieved_rag_snippets = perform_rag_search(
            keywords_list=[input_data.teaching_plan_content],
            embeddings_model_instance=embeddings,
            vector_store_dir=CHROMA_PERSIST_DIR,
            top_k=5  # 为试卷生成获取更精确的5个片段
        )
        assessment_prompt_components = construct_assessment_prompt(
            teaching_plan_content=input_data.teaching_plan_content,
            retrieved_rag_snippets=retrieved_rag_snippets,
            question_preferences=final_question_prefs,
            subject=input_data.subject
        )
        

        messages_for_llm = [
            SystemMessage(content=assessment_prompt_components["system_message"]),
            HumanMessage(content=assessment_prompt_components["human_message"])
        ]
        generated_assessment_content = generate_assessment_with_llm(messages_for_llm)

        if generated_assessment_content and generated_assessment_content.strip():
            print("SERVICE: Splitting generated content into questions and answers.")
            

            answer_separator = "参考答案与解析"
            parts = generated_assessment_content.split(answer_separator, 1)
            questions_part = parts[0].strip()
            answers_part = parts[1].strip() if len(parts) > 1 else "（无答案信息）"
            
            return questions_part, answers_part,retrieved_rag_snippets
        else:
            print("SERVICE ERROR: LLM returned empty content for assessment.")
            return None, None

    except Exception as e:
        print(f"SERVICE ERROR during assessment generation pipeline: {e}")
        return None, None

async def evaluate_student_assessment_answers_service(
    input_data: StudentAssessmentInput
) -> List[StudentAssessmentEvaluationOutput]:

    print(f"SERVICE: Initiating evaluation for student_id: {input_data.student_id or input_data.student_name} on assessment_id: {input_data.assessment_id}")
    zhipuai_api_key = _get_zhipuai_api_key() 
    results: List[StudentAssessmentEvaluationOutput] = []
    db_conn = None
    MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
    try:
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise Exception("Failed to connect to the database.")

        actual_student_id = input_data.student_id
        
        assessment_data = get_assessment_content_by_id(db_conn, input_data.assessment_id)
        if not assessment_data or not assessment_data.get("content"):
            raise ValueError(f"Could not retrieve content for assessment ID {input_data.assessment_id}.")
        assessment_content = assessment_data["content"]
        log_activity(
            db_conn,
            user_id=actual_student_id,
            user_role="student",
            activity_type="SUBMIT_ASSESSMENT",
            details={"assessment_id": input_data.assessment_id, "answer_count": len(input_data.answers)}
        )
        for answer_item in input_data.answers:
            question_id_str = answer_item.question_identifier
            student_ans_text = answer_item.student_answer_text
            
            print(f"SERVICE: Evaluating answer for Q: {question_id_str}, Student: {actual_student_id}")

            # Construct prompt
            eval_prompt_components = construct_evaluation_prompt(
                assessment_content, question_id_str, student_ans_text
            )
            

            raw_llm_evaluation = get_llm_evaluation_for_answer(
                eval_prompt_components["system_message"],
                eval_prompt_components["human_message"],
                zhipuai_api_key 
            )

            parsed_eval = parse_llm_evaluation(raw_llm_evaluation)
            
            # Save the evaluated answer
            answer_db_id = save_student_assessment_answer(
                db_conn,
                input_data.assessment_id,
                question_id_str,
                actual_student_id,
                student_ans_text,
                parsed_eval["llm_evaluation_feedback"],
                parsed_eval["llm_assessed_correctness"]
            )
            
            results.append(StudentAssessmentEvaluationOutput(
                answer_id=answer_db_id if answer_db_id else None,
                assessment_id=input_data.assessment_id,
                question_identifier=question_id_str,
                student_id=actual_student_id,
                student_answer_text=student_ans_text,
                llm_assessed_correctness=parsed_eval["llm_assessed_correctness"],
                llm_evaluation_feedback=parsed_eval["llm_evaluation_feedback"],
                error_message=None if answer_db_id else "Failed to save this answer."
            ))
            
    except Exception as e:
        print(f"SERVICE ERROR in evaluate_student_assessment_answers_service: {e}")

        if not results or results[-1].error_message != "Database not configured.":
             results.append(StudentAssessmentEvaluationOutput(
                assessment_id=input_data.assessment_id, 
                question_identifier="Overall Error", 
                student_id=input_data.student_id or 0,
                student_answer_text="N/A",
                llm_assessed_correctness="Error",
                llm_evaluation_feedback=str(e),
                error_message=str(e)
            ))
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()
            print("SERVICE: DB connection closed for evaluate_student_assessment_answers_service.")
            
    return results

async def generate_practice_questions_service(
    input_data: PracticeQuestionsInput,
    raw_generated_questions: Optional[str] = None
) -> tuple[PracticeQuestionsOutput, List[str]]:
    print(f"SERVICE: Generating/Saving practice questions for topic: {input_data.practice_topic}")
    rag_snippets = [] # <--- 初始化 rag_snippets 列表
    if raw_generated_questions is None:
        print("SERVICE: No raw content provided, generating from scratch...")
        history_summary = "No specific student performance history provided."
        db_conn_hist = None
        try:
            if input_data.student_id:
                db_conn_hist = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
                if db_conn_hist:
                    summary = get_student_history_summary(db_conn_hist, input_data.student_id)
                    if summary: history_summary = summary
        finally:
            if db_conn_hist and db_conn_hist.is_connected():
                db_conn_hist.close()

        from langchain_community.embeddings import ZhipuAIEmbeddings
        embeddings = ZhipuAIEmbeddings()
        rag_snippets = search_knowledge_for_practice_topic(input_data.practice_topic, embeddings, CHROMA_PERSIST_DIR)
        
        prompt_components = construct_practice_question_prompt(
            input_data.practice_topic,
            input_data.question_preferences,
            student_history_summary=history_summary,
            retrieved_context_snippets=rag_snippets
        )
        raw_generated_questions = get_llm_practice_questions(
            prompt_components["system_message"],
            prompt_components["human_message"]
        )
    
    db_conn_save = None
    try:
        if not (raw_generated_questions and raw_generated_questions.strip()):
            return PracticeQuestionsOutput(generated_questions=[], error_message="AI未能生成练习题内容。"),[]
        separator_pattern = re.compile(r'\s*---?\s*参考答案与解析\s*---?\s*', re.IGNORECASE)
        
        match = separator_pattern.search(raw_generated_questions)

        if match:
            # If a match is found, split the string at the match position
            all_questions_text = raw_generated_questions[:match.start()].strip()
            all_answers_text = raw_generated_questions[match.end():].strip()
            print("SERVICE INFO: Successfully split questions and answers using regex.")
        else:
            # Fallback if the separator is still not found
            all_questions_text = raw_generated_questions.strip()
            all_answers_text = "（答案解析未找到，AI可能未按指定格式输出）"
            print("SERVICE WARNING: Separator pattern not found. Could not split questions and answers.")

        # --- (分割逻辑修正结束) ---

        db_conn_save = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
        if not db_conn_save:
            raise Exception("Failed to connect to the database for saving.")

        concepts_list = [input_data.practice_topic] if input_data.practice_topic else []
        catalog_id = save_practice_question_to_catalog(
            db_conn_save, all_questions_text, all_answers_text, concepts_list=concepts_list
        )

        if catalog_id:
            generated_item = PracticeQuestionItem(question_text=all_questions_text, model_answer=all_answers_text)
            output = PracticeQuestionsOutput(generated_questions=generated_item, catalog_id=catalog_id)
            return output, rag_snippets
        else:
            output = PracticeQuestionsOutput(generated_questions=None, error_message="生成了练习题但保存至题库失败。")
            # --- 核心修改：返回 output 和空列表 ---
            return output, []
            
    except Exception as e:
        # It's helpful to log the full exception for debugging
        import traceback
        print(f"SERVICE ERROR in generate_practice_questions_service: {e}")
        traceback.print_exc()
        output = PracticeQuestionsOutput(generated_questions=None, error_message=f"An unexpected error occurred: {str(e)}")
        # --- 核心修改：返回 output 和空列表 ---
        return output, []
    finally:
        if db_conn_save and db_conn_save.is_connected():
            db_conn_save.close()




async def get_practice_feedback_service(
    input_data: PracticeFeedbackInput
) -> PracticeFeedbackOutput:
    print(f"SERVICE: Getting holistic feedback for student {input_data.student_id} on catalog_id {input_data.catalog_id}")

    db_conn = None
    questions_text = ""
    model_answers_text = ""
    try:
        MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        # ... (获取 questions_text 和 model_answers_text 的逻辑)
        practice_set_details = get_practice_question_details_by_id(db_conn, input_data.catalog_id)
        if not practice_set_details:
             raise HTTPException(status_code=404, detail=f"Practice set with catalog_id {input_data.catalog_id} not found.")
        questions_text = practice_set_details.get("question_text", "")
        model_answers_text = practice_set_details.get("model_answer", "")
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

    holistic_feedback_prompt = f"""
    你是一位顶级的AI辅导老师，善于对学生的一次性整体作答给出全面、细致、有条理的反馈。

    **【上下文信息】**

    1.  **试卷的全部题目:**
        ---
        {questions_text}
        ---

    2.  **所有题目的参考答案与解析:**
        ---
        {model_answers_text}
        ---

    3.  **学生提交的全部回答 (作为一个整体):**
        ---
        {input_data.student_answer}
        ---

    **【你的任务】**
    请一步到位，完成以下所有任务，并严格按照指定的JSON格式输出。

    1.  **总体评价 (Overall Comment)**: 首先，请对学生的整体作答情况给出一个简短、鼓励性的总体评价。
    2.  **逐题反馈 (Detailed Feedback)**: 接着，对学生回答的**每一个问题**，进行独立的分析和反馈。你需要：
        a.  从【学生提交的全部回答】中，**精确地抽取出**针对当前题目的那部分回答。
        b.  判断该回答的正确性 (`Correct`, `Partially Correct`, `Incorrect`, `Not Answered`)。
        c.  给出有建设性的、详细的反馈。
    
    **【输出格式 - 必须严格遵守！】**
    你的输出必须是且只能是一个单一的JSON对象，结构如下：
    ```json
    {{
      "overall_comment": "（这里是你的总体评价...）",
      "feedback_details": [
        {{
          "question_identifier": "（题目的原始标识符，如 '题目1'）",
          "student_answer": "（【必须】从学生回答中【原文复制】针对这个问题的具体内容。此字段【绝对不能】包含'见学生答案'、'如上'等任何占位符或缩写，必须是学生答案的原文。）",
          "correctness": "（'Correct', 'Partially Correct', 'Incorrect', 或 'Not Answered'）",
          "feedback": "（针对这个问题的详细反馈）"
        }},
        // ... 为其他所有题目生成类似的反馈对象 ...
      ]
    }}
    ```
    - **重要**: `feedback_details` 数组必须包含对**试卷中所有题目**的反馈，即使学生没有回答某个问题（此时 `student_answer` 应为空字符串 `""`，`correctness` 应为 `Not Answered`）。

    现在，请开始生成反馈JSON：
    """
    parsed_feedback_json = await parse_query_with_llm(holistic_feedback_prompt)

    if "error" in parsed_feedback_json or not parsed_feedback_json.get("feedback_details"):
        raise HTTPException(status_code=500, detail="Failed to get a valid holistic feedback from AI.")
        

    overall_comment = parsed_feedback_json.get("overall_comment", "No overall comment provided.")
    feedback_details_raw = parsed_feedback_json.get("feedback_details", [])
    total_questions = len(feedback_details_raw)
    score = 0.0
    if total_questions > 0:
        for item in feedback_details_raw:
            correctness = item.get("correctness")
            if correctness == "Correct":
                score += 1.0
            elif correctness == "Partially Correct":
                score += 0.5
    

        accuracy_percentage = (score / total_questions) * 100

        overall_correctness_for_db = f"{accuracy_percentage:.1f}%"
    else:
        overall_correctness_for_db = "N/A" # 没有题目，无法评估


    feedback_for_db = json.dumps(feedback_details_raw, ensure_ascii=False)

    db_conn = None
    attempt_id = None
    try:
        MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise Exception("Database connection failed for saving.")
        
        attempt_id = save_practice_attempt(
            db_conn,
            input_data.student_id,
            input_data.catalog_id,
            input_data.student_answer,
            overall_correctness_for_db,       
            feedback_for_db
    )
        if not attempt_id:
            raise Exception("Failed to save the practice attempt to the database.")
        
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

    # --- 5. 构造并返回API响应 ---
    # 使用 Pydantic 模型进行验证和序列化
    feedback_items = [FeedbackItem(**item) for item in feedback_details_raw]
    
    return PracticeFeedbackOutput(
        attempt_id=attempt_id,
        overall_comment=overall_comment,
        feedback_details=feedback_items,
        error_message=None
    )

# Helper function to convert Pydantic ChatMessage to Langchain messages
def convert_chat_messages_to_langchain_format(chat_history: List[ChatMessage], new_query: str) -> List:
    langchain_messages = []
    for msg in chat_history:
        if msg.role == "user":
            langchain_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            langchain_messages.append(AIMessage(content=msg.content))
        elif msg.role == "system": # If you expect system messages in history
            langchain_messages.append(SystemMessage(content=msg.content))
    langchain_messages.append(HumanMessage(content=new_query))
    return langchain_messages

async def refine_student_question_service(input_data: RefineStudentQAInput) -> StudentQuestionOutput:
    print(f"SERVICE: Refining student question for student_id: {input_data.student_id}")
    rag_snippets = []
    llm_answer = "Could not determine a refined answer."
    error_message = None

    try:
        standalone_query_for_rag = await _rewrite_query_with_history(input_data.history, input_data.new_query)
        
        try:
            embeddings = ZhipuAIEmbeddings() 
        except Exception as e:
            pass

        rag_snippets = search_knowledge_base_for_answer(
            student_question=standalone_query_for_rag, 
            embeddings_model_instance=embeddings,
            vector_store_dir=CHROMA_PERSIST_DIR,
            top_k=10 
        )
        print(f"SERVICE (Refine): RAG search retrieved {len(rag_snippets)} snippets for rewritten query.")

        history_langchain_messages = []
        for msg in input_data.history:
            if msg.role == "user" :
                history_langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history_langchain_messages.append(AIMessage(content=msg.content))

        final_messages_for_llm = construct_student_qa_prompt_with_history(
            history_messages=history_langchain_messages,
            new_query_content=input_data.new_query, 
            rag_snippets=rag_snippets
        )
        
        llm_response = get_llm_response_to_student(
             messages=final_messages_for_llm
        )

        if llm_response:
            llm_answer = llm_response
        else:

            pass

    except Exception as e:

        pass

    return StudentQuestionOutput(
        student_question=input_data.new_query,
        rag_context=rag_snippets if rag_snippets else None,
        llm_answer=llm_answer,
        error_message=error_message
    )



async def refine_teaching_plan_service(input_data: RefineTeachingPlanInput) -> tuple[str, str, List[str]]:
    print(f"SERVICE: Starting refine process for teaching plan ID: {input_data.base_teaching_plan_id}")

    # 1. 识别用户意图
    user_intent = await _identify_user_intent(input_data.history, input_data.new_query)
    
    db_conn = None
    original_plan_content = ""
    original_title = "未命名教案"
    MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
    zhipuai_api_key = _get_zhipuai_api_key()

    try:
        # 2. 连接数据库并获取原始教案内容
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if db_conn and input_data.base_teaching_plan_id:
            original_plan = get_teaching_plan_by_id(db_conn, input_data.base_teaching_plan_id)
            if original_plan:
                original_title = original_plan.get('title', '未命名教案')
                original_plan_content = original_plan.get('content', '').strip()

        # --- 【核心升级 1: 查询重写】 ---
        # 3. 在RAG搜索之前，先重写查询以包含历史上下文
        standalone_query_for_rag = await _rewrite_teaching_plan_query(input_data.history, input_data.new_query)

        # 4. 使用重写后的查询执行RAG搜索
        print(f"SERVICE: Performing RAG search for teaching plan refinement using rewritten query: '{standalone_query_for_rag[:100]}...'")
        embeddings = ZhipuAIEmbeddings()
        rag_snippets = perform_rag_search(
            keywords_list=[standalone_query_for_rag],
            embeddings_model_instance=embeddings,
            vector_store_dir=CHROMA_PERSIST_DIR,
            top_k=5  # Get 5 focused snippets for refinement
        )
        
        final_full_content = None
        rag_context_for_prompt = "\n".join([f"- {s}" for s in rag_snippets]) if rag_snippets else "无"

        # --- 【核心升级 2: Prompt 优化】 ---
        # 5. 根据意图构建不同的、优化后的Prompt并调用LLM
        if user_intent == "INCREMENTAL_ADD":
            print(f"SERVICE: Handling {user_intent} for teaching plan with smart-editing prompt.")
            system_message = "你是一位负责文本编辑和重组的AI专家，以输出完整、可直接使用的文档而闻名。"

            editing_prompt = f"""
            你是一位顶级的AI文本编辑专家和教学设计师。你的任务是根据用户的【增补指令】，对一份【原始教案】进行智能化的、无缝的修改。

            --- 原始教案 ---
            {original_plan_content}
            --- 原始教案结束 ---

            --- 用户的增补指令 ---
            "{input_data.new_query}"
            ---

            **【你的任务 - 必须严格遵守！】**

            1.  **分析与定位**: 请分析原始教案的结构，找到最适合整合用户新内容的**一个或多个位置**。
            2.  **智能整合**: 将新内容有机地、无缝地整合进原文中。如果新增一个知识点，你可能需要同步更新“教学目标”、“教学步骤”等相关部分，以确保教案的完整性和逻辑性。
            3.  **【最终输出规则 - 这是最高优先级的指令！】**:
                *   你的最终输出必须是**一份修改后的、全新的、完整的教案全文**。
                *   在你的回答中不可以使用任何形式的占位符，如 `（内容同原始教案）`、`(...)` 或 `[...略...]` 等。
                *   对于你认为不需要修改的原始部分，你必须将其**原文完整地复制**到最终的输出中。
                除了增加的内容其他不修改的内容原封不动的生成

            """
            llm_for_plan = ChatZhipuAI(model="glm-4-air", temperature=0.7, api_key=zhipuai_api_key)
            ai_message = await llm_for_plan.ainvoke([
                SystemMessage(content=system_message),
                HumanMessage(content=editing_prompt)
            ])
            final_full_content = ai_message.content

        elif user_intent in ["REVISION", "DELETION"]:
            print(f"SERVICE: Handling {user_intent} for teaching plan with smart-editing prompt.")
            system_message = "你是一位负责文本编辑和重组的AI专家。"
            
            # ========================= START OF CHANGE =========================
            # 旧的 prompt 虽然要求输出全文，但不够强硬，LLM 可能会偷懒。
            # 新的 prompt 使用了更明确、更强烈的措辞，并给出了反例，以杜绝占位符和多余的文本。
            editing_prompt = f"""
            你是一位顶级的AI文本编辑专家和教学设计师。你的核心任务是根据用户的【修改或删除指令】，对一份【原始教案】进行精准的、智能化的编辑，并输出一份【可以直接使用的、完整的最终文档】。
            你的关键能力是可以重复生成已有教案的内容，对于这些内容你要再次重复生成一边不得使用同原始教案相同的类似占位符，最终要生产一个和原始教案很类似的教案，你一定要生成和原教案差不多的内容而不是只生成需要被修改的那一部分
            --- 原始教案 ---
            {original_plan_content}
            --- 原始教案结束 ---

            --- 用户的修改/删除指令 ---
            "{input_data.new_query}"
            ---
            
            --- 补充参考材料 (用于丰富修改内容) ---
            {rag_context_for_prompt}
            ---

            **【你的任务和输出规则 - 这是最高优先级的指令，必须严格遵守！】**

            1.  **深度理解与执行**: 请仔细阅读【原始教案】的完整内容，并精确地执行用户的【修改/删除指令】。
            
            2.  **确保连贯性**: 在完成编辑后，请检查整个教案的上下文逻辑是否依然通顺，章节编号、标题层级是否依然正确。

            3.  **【最终输出格式 - 绝对规则】**:
                *   你的最终输出【必须是且只能是】一份【修改后的、全新的、完整的教案全文】，对于没有修改过的部分你也必须要原封不动的保留。
                *   在你的回答中不能使用任何形式的占位符，例如 `（内容同原始教案）`、`(...)`、`[...略...]` 或 `见上文` 等。如果你的输出包含任何此类占位符，任务就视为完全失败。
                *   对于你认为不需要修改的原始部分，你【必须将其原文完整地、一字不差地复制】到最终的输出中。
                *   你的回答【不能包含】任何“这是修改后的版本”、“根据您的要求...”之类的解释性前言或总结性后语。你的输出从第一个字符开始就必须是新教案的标题，到最后一个字符结束也必须是教案的结尾。

            """
            # ========================== END OF CHANGE ==========================

            llm_for_plan = ChatZhipuAI(model="glm-4-air", temperature=0.7, api_key=zhipuai_api_key)
            ai_message = await llm_for_plan.ainvoke([
                SystemMessage(content=system_message),
                HumanMessage(content=editing_prompt)
            ])
            final_full_content = ai_message.content

        else:  # REWRITE
            print(f"SERVICE: Handling {user_intent} for teaching plan with rewrite prompt.")
            system_message = "你是一位负责内容创作的AI专家。"
            rewrite_prompt = f"""
            你是一位顶级的教学设计师。现在，你将执行一项【完全重写】任务。

            **【指令 - 必须严格遵守！】**

            1.  **彻底忽略历史**: 下面会提供一份【原始教案】，但你的任务是**【完全忽略】**它的所有内容、结构和风格。它仅供你了解之前的主题，以便理解用户的转折。
            2.  **聚焦新指令**: 你的创作**唯一且全部的依据**是用户的【全新指令】。
            3.  **高质量输出**: 请根据用户的全新指令和补充参考材料，从零开始，创作一份全新的、高质量的、完整的教案。

            --- 原始教案 (仅供参考，必须忽略其内容) ---
            {original_plan_content}
            --- 原始教案结束 ---

            --- 用户的全新指令 (你的唯一创作依据) ---
            "{input_data.new_query}"
            ---
            
            --- 补充参考材料 ---
            {rag_context_for_prompt}
            ---

            现在，请彻底忘记原始教案，根据全新指令开始你的创作：
            """
            llm_for_plan = ChatZhipuAI(model="glm-4-air", temperature=0.7, api_key=zhipuai_api_key)
            ai_message = await llm_for_plan.ainvoke([
                SystemMessage(content=system_message),
                HumanMessage(content=rewrite_prompt)
            ])
            final_full_content = ai_message.content

        # 6. 生成新的语义化标题
        new_title = await _generate_semantic_title_for_refinement(original_title, input_data.new_query)
        if final_full_content is None or not final_full_content.strip():
            raise Exception("Failed to construct final content.")

        return new_title, final_full_content, rag_snippets
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"SERVICE ERROR in refine_teaching_plan_service: {e}")
        return None, None, []
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

def _apply_structured_edits(original_q_text, original_a_text, instructions, answer_separator):
    """
    Applies structured edits (delete, add) to original assessment text.
    This is a more robust version.
    """
    q_to_delete_identifiers = set(instructions.get("questions_to_delete", []))
    q_to_add = instructions.get("questions_to_add", [])

    def parse_content_robust(text_content, prefix_pattern=r'(题目\s*\d+|[一二三四五六七八九十、]+\s*[\w]+题)'):
        """
        Parses content by splitting it based on question identifiers or section titles.
        It handles both "题目X" and "一、选择题" style headers.
        """
        if not text_content:
            return {}, []
        
        # 找到所有的标题/题号
        identifiers = re.findall(f'^{prefix_pattern}', text_content, re.MULTILINE)
        
        # 如果找不到任何标识符，返回空
        if not identifiers:
            print(f"WARNING (_apply_structured_edits): No identifiers found in text starting with: {text_content[:100]}")
            return {}, []
            
        # 使用这些标识符作为分隔符来切分文本
        # 我们需要在每个标识符前加上一个特殊标记，以便后续处理
        # re.escape is important in case identifier contains special regex characters
        split_pattern = '|'.join(map(re.escape, identifiers))
        # Split and keep the delimiters
        parts = re.split(f'({split_pattern})', text_content)

        item_dict = {}
        ordered_keys = []
        
        # The first part is usually empty or whitespace before the first identifier
        # The list is [before_first, id_1, content_1, id_2, content_2, ...]
        i = 1
        while i < len(parts):
            key = parts[i].strip()
            content = parts[i+1].strip() if (i + 1) < len(parts) else ""
            
            # 组合题号和内容
            full_item_text = f"{key}\n{content}".strip()
            
            # 提取一个唯一的、标准化的key，比如 "题目1"
            match = re.match(r'(题目\s*\d+)', key)
            if match:
                normalized_key = re.sub(r'\s+', '', match.group(1)) # "题目 1" -> "题目1"
                item_dict[normalized_key] = full_item_text
                ordered_keys.append(normalized_key)

            i += 2
            
        return item_dict, ordered_keys

    # --- 1. 解析原始题目和答案 ---
    original_questions_dict, ordered_q_keys = parse_content_robust(original_q_text, r'(题目\s*\d+)')
    original_answers_dict, _ = parse_content_robust(original_a_text, r'(题目\s*\d+)')

    # --- 2. 执行删除操作 ---
    final_q_keys = [key for key in ordered_q_keys if key not in q_to_delete_identifiers]

    # --- 3. 执行添加操作 ---
    new_questions_section = []
    new_answers_section = []
    
    # 先把保留下来的旧题目和答案放进去
    for key in final_q_keys:
        if key in original_questions_dict:
            new_questions_section.append(original_questions_dict[key])
        if key in original_answers_dict:
            new_answers_section.append(original_answers_dict[key])
            
    # 再把要新增的题目和答案放进去
    for new_q_obj in q_to_add:
        q_text = new_q_obj.get("question_text", "").strip()
        a_text = new_q_obj.get("model_answer", "").strip()
        if q_text:
            new_questions_section.append(q_text)
        if a_text:
            new_answers_section.append(a_text)

    # --- 4. 重新组装试卷 ---
    final_questions_text = "\n\n".join(new_questions_section)
    final_answers_text = "\n\n".join(new_answers_section)

    return f"{final_questions_text}\n\n{answer_separator}\n\n{final_answers_text}"


async def refine_assessment_service(input_data: RefineAssessmentInput) -> tuple[str, str, list, str]:
    print(f"SERVICE: Starting refine process for assessment ID: {input_data.base_assessment_id}")

    user_intent = await _identify_assessment_intent(input_data.history, input_data.new_query)
    db_conn = None
    original_assessment_content = ""
    original_answers_text = ""
    original_subject = None
    original_title = "未命名考核"
    MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
    answer_separator = "---参考答案与解析---"

    try:
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if db_conn and input_data.base_assessment_id:
            original_assessment = get_assessment_details_by_id(db_conn, input_data.base_assessment_id)
            if original_assessment:
                original_title = original_assessment.get('title', '未命名考核')
                original_assessment_content = original_assessment.get('content', '').strip()
                original_answers_text = original_assessment.get('answers_text', '').strip()
                original_subject = original_assessment.get('subject')

        final_full_content = None
        # RAG Search based on the new query
        print(f"SERVICE: Performing RAG search for assessment refinement: '{input_data.new_query[:100]}...'")
        embeddings = ZhipuAIEmbeddings()
        rag_snippets = perform_rag_search(
            keywords_list=[input_data.new_query],
            embeddings_model_instance=embeddings,
            vector_store_dir=CHROMA_PERSIST_DIR,
            top_k=5
        )
        if user_intent == "INCREMENTAL_ADD":
            print(f"SERVICE: Handling {user_intent} with a dedicated creation-then-merge flow.")
            creation_prompt = f"""
            你是一位出题专家。你的任务是根据一个【核心主题】和用户的【具体要求】，创作出符合要求的【新增题目和答案】。
            核心主题: **{original_title}**
            用户的具体要求: **{input_data.new_query}**
            补充知识: **{rag_snippets}**
            你的输出【只应包含你新创作的题目和答案】，并使用 "{answer_separator}" 分隔。新题目要包含题型大标题，如“一、选择题”。
            """
            generated_new_content = generate_assessment_with_llm(messages=[
                SystemMessage(content="你是一个只负责内容创作的AI。"),
                HumanMessage(content=creation_prompt)
            ])
            if not generated_new_content or not generated_new_content.strip():
                raise Exception("LLM failed to generate new content for the ADD request.")
            final_full_content = f"{original_assessment_content}\n\n{original_answers_text}\n\n{generated_new_content}"
            # 我们将拼接逻辑简化，让前端或后续步骤处理合并，以确保所有内容都存在
            new_parts = generated_new_content.split(answer_separator, 1)
            new_questions_part = new_parts[0].strip()
            new_answers_part = new_parts[1].strip() if len(new_parts) > 1 else ""
            full_questions = f"{original_assessment_content}\n\n{new_questions_part}"
            full_answers = f"{original_answers_text}\n\n{new_answers_part}".strip()
            final_full_content = f"{full_questions}\n\n{answer_separator}\n\n{full_answers}"

        elif user_intent in ["REVISION", "DELETION"]:
            print(f"SERVICE: Handling {user_intent} with structured output approach.")
            structured_edit_prompt = f"""
            你是一个精准的文本编辑指令生成器。你的任务是分析一份【原始试卷】和用户的【修改要求】，然后生成一个描述如何修改的JSON指令。
            --- 原始试卷 ---
            {original_assessment_content}
            ---
            --- 用户的修改要求 ---
            {input_data.new_query}
            ---
            --- 补充知识 ---
            {rag_snippets}
            ---
            【你的任务】
            请生成一个JSON对象，该对象包含两个键：
            1. `questions_to_delete`: 一个包含【需要被删除的题目编号】的数组。编号必须是 "题目X" 的格式。例如 ["题目6"]。如果不需要删除任何题目，则为空数组 `[]`。
            2. `questions_to_add`: 一个包含【需要新增的题目】的数组，每个题目是一个包含 "question_text" 和 "model_answer" 的对象。如果不需要新增题目，则为空数组 `[]`。
            你的输出必须是且只能是一个JSON对象。
            如果用户的需求是修改重写一道题，那就是要删掉这一道题目同时增加这道题目，如果是删除则只是删除这一道题目
            """
            edit_instructions = await parse_query_with_llm(structured_edit_prompt)
            print("\n--- DEBUG: LLM Edit Instructions ---")
            import json
            print(json.dumps(edit_instructions, indent=2, ensure_ascii=False))
            print("--- END DEBUG ---\n")
            if "error" in edit_instructions:
                raise Exception(f"LLM failed to generate valid edit instructions: {edit_instructions['error']}")
            final_full_content = _apply_structured_edits(original_assessment_content, original_answers_text, edit_instructions, answer_separator)
            print("\n--- DEBUG: Content After Edits ---")
            print(f"Length: {len(final_full_content)}")
            print(f"Content Preview: {final_full_content[:500]}...")
            print("--- END DEBUG ---\n")

        else: # REWRITE
            print(f"SERVICE: Handling {user_intent} with direct generation approach.")
            system_prompt = "你是一位顶级的出题专家，请根据用户指令重写试卷。"
            human_prompt_parts = [
                "**【核心任务：重写试卷】**\n请【完全忽略】所有上下文，根据用户最新指令，从零开始生成一份【全新的、完整的】试卷。",
                f"用户的最新指令是：'{input_data.new_query}'",
                f"补充知识: {rag_snippets}",
                f"\n【输出格式规范】\n你的输出必须包含 {answer_separator} 分隔的题目和答案部分。"
            ]
            human_prompt_content = "\n".join(human_prompt_parts)
            messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt_content)]
            final_full_content = generate_assessment_with_llm(messages=messages)

        new_title = await _generate_semantic_title_for_refinement(original_title, input_data.new_query)
        if final_full_content is None:
            raise Exception("Failed to construct final content.")
        return new_title, final_full_content, rag_snippets, original_subject

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"SERVICE ERROR in refine_assessment_service: {e}")
        return None, None, [], None
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

async def get_student_assessment_performance_service(assessment_id: int) -> List[StudentAssessmentSummary]:

    print(f"SERVICE: Call received for aggregated performance on assessment_id: {assessment_id}")
    
    db_conn = None
    summary_list: List[StudentAssessmentSummary] = []
    
    MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
    if not MYSQL_DB_NAME:
        raise HTTPException(status_code=500, detail="Database configuration error.")

    try:
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise HTTPException(status_code=500, detail="Failed to connect to the database.")

        # Call the new aggregation function from database_utils
        aggregated_data = get_aggregated_student_performance(db_conn, assessment_id)

        if not aggregated_data:
            print(f"SERVICE: No performance data found for assessment_id: {assessment_id}. Returning empty list.")
            return []

        # Process each student's aggregated data
        for row in aggregated_data:
            total = row.get('total_answered', 0)
            if total > 0:
                correct = row.get('correct_count', 0)
                partial = row.get('partially_correct_count', 0)
                # Calculate accuracy: (Correct * 1 + Partial * 0.5) / Total * 100
                accuracy = ((correct + 0.5 * partial) / total) * 100
            else:
                accuracy = 0.0

            # Create the Pydantic model for the response
            summary_item = StudentAssessmentSummary(
                student_id=row['student_id'],
                student_name=row.get('student_name'),
                total_answered=total,
                correct_count=row.get('correct_count', 0),
                partially_correct_count=row.get('partially_correct_count', 0),
                incorrect_count=row.get('incorrect_count', 0),
                accuracy=round(accuracy, 2) # Round to 2 decimal places
            )
            summary_list.append(summary_item)
        
        print(f"SERVICE: Successfully aggregated performance for {len(summary_list)} students on assessment_id: {assessment_id}")
        return summary_list

    except Exception as e:
        print(f"SERVICE ERROR: An unexpected error occurred in get_student_assessment_performance_service: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while processing performance data.")
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()
            print(f"SERVICE: DB connection closed for get_student_assessment_performance_service (assessment_id: {assessment_id}).")



async def _rewrite_teaching_plan_query(chat_history: List[ChatMessage], new_query: str) -> str:
    print("SERVICE (Teaching Plan Refine): Rewriting query with history...")
    history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in chat_history])
    # (修改1) 使用模板变量而不是f-string
    rewrite_prompt_template = ChatPromptTemplate.from_template("""
        你是一个教学大纲优化助手。你的任务是分析一段关于“教案生成”的对话历史，并将用户最新的、可能不完整的修改指令，改写成一个独立的、包含核心主题的、可以用于信息检索的查询。只输出改写后的查询，不要包含任何额外解释。
        对话历史:
        ---
        {history}
        ---

        用户的最新修改指令是: "{query}"

        请根据以上对话历史，将这个指令改写成一个独立的、包含教案核心主题的检索查询。

        例如，如果历史是关于“一战历史”的教案，用户的指令是“增加一些关于萨拉热窝事件的细节”，你应该输出“一战历史中的萨拉热窝事件细节”。
        如果历史是关于“Python列表推导式”的教案，用户的指令是“再加几个练习题”，你应该输出“关于Python列表推导式的练习题示例”。

        现在，请开始改写：
        """)
    try:
        llm = ChatZhipuAI(model="glm-4", temperature=0.0) 
        chain = rewrite_prompt_template | llm | StrOutputParser()
        # (修改2) 将变量通过字典传递给ainvoke
        rewritten_query = await chain.ainvoke({"history": history_str, "query": new_query})
        print(f"SERVICE (Teaching Plan Refine): Original query: '{new_query}', Rewritten query: '{rewritten_query}'")
        return rewritten_query.strip()
    except Exception as e:
        print(f"SERVICE ERROR (Teaching Plan Refine): Failed to rewrite query: {e}. Falling back to original query.")
        return new_query


async def _rewrite_teaching_assessment_query(chat_history: List[ChatMessage], new_query: str) -> str:
    history_str = "\n".join([f"{msg.role}: {msg.content}" for msg in chat_history])
    
    # ## 修改点：优化Prompt，增加更复杂的示例和规则 ##
    rewrite_prompt_template = ChatPromptTemplate.from_template("""
    你是一个教学测试题优化助手。你的任务是分析一段关于“测试题生成”的对话历史，并将用户最新的、可能不完整的修改指令，改写成一个独立的、包含核心主题和【最新约束】的、可以用于信息检索的查询。

    **核心规则：**
    1.  **继承主题**：查询必须包含对话的核心主题（例如“一战历史”、“TensorFlow.js”）。
    2.  **覆盖约束**：如果用户的最新指令中包含了新的约束条件（如题型、难度、数量），这些新约束必须【覆盖】历史记录中的旧约束。
    3.  **保持简洁**：只输出改写后的查询，不要包含任何额外解释。

    ---
    **对话历史:**
    {history}
    ---
    **用户的最新修改指令是:** "{query}"
    ---

    **示例学习:**

    *   **示例1 (主题继承):**
        *   历史: 用户要求生成关于“一战历史”的习题。
        *   最新指令: “增加一些关于萨拉热窝事件的”
        *   改写后输出: `有关一战历史中的萨拉热窝事件的习题`

    *   **示例2 (题型覆盖 - 这非常重要!):**
        *   历史: 用户要求生成“5道关于Python基础知识的选择题”。
        *   最新指令: “再来2道填空题”
        *   改写后输出: `关于Python基础知识的填空题` (注意：题型从“选择题”变成了“填空题”)

    *   **示例3 (您的场景):**
        *   历史: 用户要求生成“关于TensorFlow.js编程的选择题”。
        *   最新指令: “再生成几道编程题”
        *   改写后输出: `关于TensorFlow.js的编程题` (注意：题型从“选择题”变成了“编程题”)

    现在，请根据以上规则和示例，对以下内容进行改写。

    **对话历史:**
    ---
    {history}
    ---
    **用户的最新修改指令是:** "{query}"

    **改写后的查询:**
    """)
    try:
        llm = ChatZhipuAI(model="glm-4", temperature=0.0) 
        chain = rewrite_prompt_template | llm | StrOutputParser()
        rewritten_query = await chain.ainvoke({"history": history_str, "query": new_query})
        print(f"DEBUG: Original Query: '{new_query}' | Rewritten Query: '{rewritten_query.strip()}'") # 添加这行来调试
        return rewritten_query.strip()
    except Exception as e:
        print(f"SERVICE ERROR (_rewrite_teaching_assessment_query): Failed to rewrite query. Error: {e}. Falling back to original query.")
        return new_query
    
async def get_assessment_list_service() -> PracticeQuestionListOutput:
    print("SERVICE: Call received for get_practice_question_list_service")
    db_conn = None
    MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
    if not MYSQL_DB_NAME:
        raise HTTPException(status_code=500, detail="Database not configured.")
        
    try:
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise HTTPException(status_code=500, detail="Failed to connect to the database.")


        raw_question_list = get_all_assessment_for_student_view(db_conn)
        

        question_list = [PracticeQuestionListItem(**item) for item in raw_question_list]

        return PracticeQuestionListOutput(questions=question_list)

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"SERVICE ERROR: An unexpected error occurred in get_practice_question_list_service: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching the practice list.")
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()


async def get_assessment_detail_service(assessment_id: int) -> PracticeQuestionDetailOutput:
    print(f"SERVICE: Call received for get_assessment_detail_service with id: {assessment_id}")
    db_conn = None
    MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
    if not MYSQL_DB_NAME:
        raise HTTPException(status_code=500, detail="Database not configured.")

    try:
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise HTTPException(status_code=500, detail="Failed to connect to the database.")
            
        assessment_details_dict = get_assessment_details_by_id(db_conn, assessment_id)
        
        if not assessment_details_dict:
            raise HTTPException(status_code=404, detail=f"Assessment with ID {assessment_id} not found.")
            
        return PracticeQuestionDetailOutput(**assessment_details_dict)

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"SERVICE ERROR: An unexpected error occurred in get_assessment_detail_service: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred while fetching assessment details.")
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

async def get_teacher_assessments_service(teacher_id: int) -> TeacherAssessmentListOutput:
    db_conn = None
    try:
        MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise HTTPException(status_code=500, detail="Database connection failed.")
        
        assessments_raw = get_assessments_by_teacher_id(db_conn, teacher_id)
        
        assessments_list = [TeacherAssessmentListItem(**item) for item in assessments_raw]
        return TeacherAssessmentListOutput(assessments=assessments_list)
        
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

async def publish_assessment_service(assessment_id: int, teacher_id: int):
    db_conn = None
    try:
        MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise HTTPException(status_code=500, detail="Database connection failed.")
        success = publish_assessment(db_conn, assessment_id, teacher_id)
        log_activity(
                    db_conn,
                    user_id=teacher_id,
                    user_role="teacher",
                    activity_type="PUBLISH_ASSESSMENT",
                    details={"assessment_id": assessment_id}
                )
        
        if not success:
            # 这可能是因为它已经被发布了
            raise HTTPException(status_code=409, detail="Assessment is already published or does not exist.")
            
        return {"message": f"Assessment {assessment_id} published successfully."}
        
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

async def list_users_service(role: str, page: int, page_size: int, search: Optional[str]) -> PaginatedUsersResponse:
    db_conn = get_mysql_connection(db_name="Aiagent")
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    try:
        result = get_users_by_role(db_conn, role, page, page_size, search)
        return PaginatedUsersResponse(**result)
    finally:
        if db_conn.is_connected():
            db_conn.close()

async def create_user_by_admin_service(user_data: AdminCreateUserInput) -> Dict[str, Any]:

    if user_data.role == 'student':
        existing_user = await get_student_for_auth(user_data.username)
    else:
        existing_user = await get_teacher_for_auth(user_data.username)

    if existing_user:
        raise HTTPException(status_code=409, detail=f"Username '{user_data.username}' already exists.")

    hashed_password = get_password_hash(user_data.password)
    
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    try:
        new_user_id = admin_create_user(db_conn, user_data.username, hashed_password, user_data.role)
        if not new_user_id:
            raise HTTPException(status_code=500, detail="Failed to create user in database.")
        return {"id": new_user_id, "username": user_data.username}
    finally:
        if db_conn.is_connected():
            db_conn.close()

async def reset_user_password_service(user_id: int, role: str, password: str):
    new_hashed_password = get_password_hash(password)
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    try:
        success = admin_update_user_password(db_conn, user_id, new_hashed_password, role)
        if not success:
            raise HTTPException(status_code=404, detail=f"User with role '{role}' and id {user_id} not found.")
        return {"message": "Password updated successfully."}
    finally:
        if db_conn.is_connected():
            db_conn.close()

async def delete_user_service(user_id: int, role: str):
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    try:
        success = admin_delete_user(db_conn, user_id, role)
        if not success:
            raise HTTPException(status_code=404, detail=f"User with role '{role}' and id {user_id} not found.")
        return {"message": "User deleted successfully."}
    finally:
        if db_conn.is_connected():
            db_conn.close()


async def get_teacher_resource_detail_service(resource_type: str, resource_id: int) -> AdminResourceDetailView:
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    try:
        details = get_teacher_resource_detail(db_conn, resource_type, resource_id)
        if not details:
            raise HTTPException(status_code=404, detail="Resource not found.")
        return AdminResourceDetailView(**details)
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()



async def list_all_subjects_service() -> List[str]:

    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    try:
        subjects = get_all_subjects(db_conn)
        return subjects
    finally:
        if db_conn.is_connected():
            db_conn.close()


async def list_resources_by_subject_service(
    subject: str, page: int, page_size: int, search: Optional[str]
) -> PaginatedAdminResourcesResponse:
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    try:
        data = get_unified_resources_by_subject(db_conn, subject, page, page_size, search)
        return PaginatedAdminResourcesResponse(**data)
    finally:
        if db_conn.is_connected():
            db_conn.close()

async def export_single_resource_service(resource_type: str, resource_id: int) -> Dict[str, str]:
    """
    获取单个资源的内容，并准备用于导出的数据。
    返回一个包含安全文件名和文件内容的字典。
    """
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    try:
        # 复用获取详情的函数
        details = get_teacher_resource_detail(db_conn, resource_type,resource_id)
        if not details:
            raise HTTPException(status_code=404, detail="Resource not found.")
        
        # --- 准备文件名和文件内容 ---
        
        # 清理标题，移除不适合做文件名的字符
        title = details.get('title', f'resource_{resource_id}')
        # 移除非法字符，并将空格替换为下划线
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title).replace(' ', '_')
        filename = f"{resource_type}_{safe_title}.txt"
        
        # 准备文件内容，格式化输出
        file_content = f"标题: {details.get('title', 'N/A')}\n"
        file_content += f"学科: {details.get('subject', 'N/A')}\n"
        file_content += f"资源ID: {details.get('id')}\n"
        file_content += f"========================================\n\n"
        file_content += details.get('full_content', '')
        
        return {"filename": filename, "content": file_content}
        
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

async def get_dashboard_usage_service() -> DashboardUsageResponse:
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    try:
        daily_raw = get_activity_stats(db_conn, 'daily')
        weekly_raw = get_activity_stats(db_conn, 'weekly')
        
        daily_stats = UsageStats(teacher=[], student=[])
        for row in daily_raw:
            stat = ActivityStat(activity_type=row['activity_type'], count=row['count'])
            if row['user_role'] == 'teacher':
                daily_stats.teacher.append(stat)
            elif row['user_role'] == 'student':
                daily_stats.student.append(stat)
        
        weekly_stats = UsageStats(teacher=[], student=[])
        for row in weekly_raw:
            stat = ActivityStat(activity_type=row['activity_type'], count=row['count'])
            if row['user_role'] == 'teacher':
                weekly_stats.teacher.append(stat)
            elif row['user_role'] == 'student':
                weekly_stats.student.append(stat)

        return DashboardUsageResponse(daily=daily_stats, weekly=weekly_stats)
        
    finally:
        if db_conn.is_connected():
            db_conn.close()

async def get_teaching_efficiency_service() -> List[TeacherEfficiencyStat]:
    """
    分析教师的备课和修正活动，计算教学效率指数。
    """
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    
    try:
        # 1. 从数据库获取原始统计数据
        raw_stats = get_teacher_content_creation_stats(db_conn)
        
        # 2. 在Python中处理和聚合数据
        # 使用一个字典来按 teacher_id 聚合数据
        teacher_data = {}

        for row in raw_stats:
            teacher_id = row['teacher_id']
            teacher_name = row['teacher_name']
            activity = row['activity_type']
            count = row['count']
            
            # 如果是第一次见到这位老师，为他初始化一个数据结构
            if teacher_id not in teacher_data:
                teacher_data[teacher_id] = {
                    "teacher_id": teacher_id,
                    "teacher_name": teacher_name,
                    "plans_created": 0,
                    "assessments_created": 0,
                    "plans_refined": 0,
                    "assessments_refined": 0
                }
            
            # 根据活动类型累加次数
            if activity == 'GENERATE_TEACHING_PLAN':
                teacher_data[teacher_id]['plans_created'] += count
            elif activity == 'REFINE_TEACHING_PLAN':
                teacher_data[teacher_id]['plans_refined'] += count
            elif activity == 'GENERATE_ASSESSMENT':
                teacher_data[teacher_id]['assessments_created'] += count
            elif activity == 'REFINE_ASSESSMENT':
                teacher_data[teacher_id]['assessments_refined'] += count
        
        # 3. 计算每个老师的效率指数并格式化为最终结果
        final_results = []
        for teacher_id, data in teacher_data.items():
            # 计算教案效率指数
            total_plan_actions = data['plans_created'] + data['plans_refined']
            if total_plan_actions > 0:
                plan_efficiency = (data['plans_created'] / total_plan_actions) * 100
            else:
                plan_efficiency = 0.0 # 或者 100.0，取决于如何定义无操作的效率

            # 计算考核效率指数
            total_assessment_actions = data['assessments_created'] + data['assessments_refined']
            if total_assessment_actions > 0:
                assessment_efficiency = (data['assessments_created'] / total_assessment_actions) * 100
            else:
                assessment_efficiency = 0.0

            # 创建 Pydantic 模型实例
            stat_entry = TeacherEfficiencyStat(
                teacher_id=data['teacher_id'],
                teacher_name=data['teacher_name'],
                plans_created=data['plans_created'],
                assessments_created=data['assessments_created'],
                plans_refined=data['plans_refined'],
                assessments_refined=data['assessments_refined'],
                plan_efficiency_index=round(plan_efficiency, 2),
                assessment_efficiency_index=round(assessment_efficiency, 2)
            )
            final_results.append(stat_entry)
            
        return final_results
        
    finally:
        if db_conn.is_connected():
            db_conn.close()

async def get_low_performing_subjects_service() -> List[SubjectPerformance]:
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
    try:
        raw_data = get_low_performing_subjects(db_conn, limit=5)
        return [SubjectPerformance(**item) for item in raw_data]
    finally:
        if db_conn.is_connected():
            db_conn.close()

async def get_student_effectiveness_service() -> StudentEffectivenessResponse:
    db_conn = None
    db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
    if not db_conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")
        
    try:
        # --- 添加的调试日志 ---
        print("\n--- [SERVICE] START: get_student_effectiveness_service ---")
        print(f"[SERVICE] 1. Before get_daily_accuracy_trend: Connection is connected? -> {db_conn.is_connected()}")

        # 1. 获取正确率趋势
        trend_data = get_daily_accuracy_trend(db_conn)

        print("[SERVICE] 1.1. SKIPPED get_daily_accuracy_trend call.")
        # --- 添加的调试日志 ---
        print(f"[SERVICE] 2. After get_daily_accuracy_trend: Connection is connected? -> {db_conn.is_connected()}")

        # 2. 获取知识点数据并分析
        attempts_with_concepts = get_all_practice_attempts_with_concepts(db_conn)
        
        print("[SERVICE] 3. After get_all_practice_attempts_with_concepts: All DB calls finished.")
        # --- 调试日志结束 ---
        
        concept_stats = defaultdict(lambda: {'total': 0, 'score': 0.0, 'incorrect': 0})
        
        for attempt in attempts_with_concepts:
            concepts_str = attempt.get('concepts_covered')
            correctness = attempt.get('correctness_assessment', '')
            
            if not concepts_str: continue

            try:
                concepts = json.loads(concepts_str)
                for concept in concepts:
                    concept_stats[concept]['total'] += 1
                    # '85.7%'
                    if '%' in correctness:
                        score_val = float(correctness.replace('%', '')) / 100.0
                        concept_stats[concept]['score'] += score_val
                        if score_val < 0.5: # 假设低于50%算错误
                            concept_stats[concept]['incorrect'] += 1
                    # 'Correct', 'Partially Correct'
                    elif correctness == 'Correct':
                        concept_stats[concept]['score'] += 1.0
                    elif correctness == 'Partially Correct':
                        concept_stats[concept]['score'] += 0.5
                    elif correctness == 'Incorrect':
                        concept_stats[concept]['incorrect'] += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        
        # 3. 计算结果
        concept_results = []
        for concept, stats in concept_stats.items():
            if stats['total'] > 0:
                mastery_rate = (stats['score'] / stats['total']) * 100
                concept_results.append(ConceptStat(
                    concept=concept,
                    mastery_rate=round(mastery_rate, 2),
                    total_attempts=stats['total'],
                    incorrect_attempts=stats['incorrect']
                ))
        
        # 按掌握率从低到高排序
        weakest_concepts = sorted(concept_results, key=lambda x: x.mastery_rate)[:10] # 只取最弱的10个

        return StudentEffectivenessResponse(
            accuracy_trend=[DailyAccuracy(**item) for item in trend_data],
            weakest_concepts=weakest_concepts
        )

    finally:
        if db_conn and db_conn.is_connected():
            print("[SERVICE] FINALLY: Closing connection.")
            db_conn.close()
        print("--- [SERVICE] END: get_student_effectiveness_service ---\n")

async def get_teacher_published_assessments_service(teacher_id: int) -> List[PublishedAssessmentInfo]:
    db_conn = None
    try:
        MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise HTTPException(status_code=500, detail="Database connection failed.")
        
        assessments_raw = get_published_assessments_by_teacher(db_conn, teacher_id)
        
        return [PublishedAssessmentInfo(**item) for item in assessments_raw]
        
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()

async def analyze_assessment_performance_service(assessment_id: int) -> AssessmentAnalysisOutput:
    db_conn = None
    try:
        MYSQL_DB_NAME = os.environ.get("MYSQL_DB")
        db_conn = get_mysql_connection(db_name=MYSQL_DB_NAME)
        if not db_conn:
            raise HTTPException(status_code=500, detail="Database connection failed.")

        stats_raw = get_assessment_question_stats(db_conn, assessment_id)
        if not stats_raw:
            raise HTTPException(status_code=404, detail="No student answer data found for this assessment.")

        assessment_data = get_assessment_content_by_id(db_conn, assessment_id)
        if not assessment_data:
            raise HTTPException(status_code=404, detail=f"Assessment with ID {assessment_id} not found.")
        
        assessment_title = assessment_data.get('title', 'Untitled Assessment')
        questions_text = assessment_data.get('content', '').split('---参考答案与解析---')[0].strip()

        # 3. 构造给LLM的提示 (Prompt Engineering)
        analysis_prompt = f"""
        你是一位顶级的教育数据分析专家。你的任务是分析一份考核的学情数据，并提供一份简洁、深刻、有洞察力的分析报告。

        **1. 考核基本信息:**
        - 考核标题: "{assessment_title}"

        **2. 考核题目内容:**
        ---
        {questions_text}
        ---

        **3. 各题作答情况统计:**
        以下是每个题目的作答情况统计：
        ```json
        {json.dumps(stats_raw, indent=2, ensure_ascii=False)}
        ```

        **你的任务 (必须严格遵守):**
        请根据以上所有信息，生成一份学情分析报告。你的输出必须是且只能是一个单一的、结构化的JSON对象，格式如下：

        ```json
        {{
          "assessment_title": "{assessment_title}",
          "overall_summary": "（这里是对班级整体表现的概括性总结，比如：整体掌握情况良好，但在...方面存在普遍困难。）",
          "question_analysis": [
            {{
              "question_identifier": "（错误率最高的题号，如 '题目3'）",
              "question_text": "（该题目的完整题干）",
              "correct_rate": "（该题的正确率，计算方式为 Correct / Total * 100）",
              "main_knowledge_point": "（根据题干，提炼出这道题考察的核心知识点或技能）",
              "common_errors": "（推测学生可能的常见错误或思维误区）"
            }},
            // ... (为其他错误率较高的2-3个题目生成类似对象) ...
          ],
          "teaching_suggestions": [
            "（基于以上分析，提出第一条具体的、可操作的教学建议）",
            "（提出第二条教学建议，例如：可以针对...知识点设计专项练习）",
            "（提出第三条教学建议，例如：下次授课时可以多举一些...的例子）"
          ]
        }}
        ```

        **分析要点:**
        - 在 `question_analysis` 中，请重点分析错误率最高或最值得关注的2-4个问题。
        - `teaching_suggestions` 必须具体、有针对性，能够直接帮助老师改进教学。

        现在，请开始生成你的JSON分析报告。
        """

        # 4. 调用LLM并解析 (LLM Call & Parsing)
        parsed_analysis = await parse_query_with_llm(analysis_prompt)
        
        if "error" in parsed_analysis or not parsed_analysis.get("question_analysis"):
            print(f"LLM parsing failed. Raw response: {parsed_analysis}")
            raise HTTPException(status_code=500, detail="Failed to get a valid analysis from the AI model.")

        # 使用Pydantic模型进行验证和返回
        return AssessmentAnalysisOutput(**parsed_analysis)

    except HTTPException as he:
        raise he # 直接重新抛出HTTP异常
    except Exception as e:
        print(f"SERVICE ERROR in analyze_assessment_performance_service: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred during analysis: {str(e)}")
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()


async def analyze_assessment_performance(assessment_id: int) -> AssessmentAnalysisOutput:
    db_conn = None
    try:
        db_conn = get_mysql_connection(db_name=os.environ.get("MYSQL_DB"))
        if not db_conn:
            raise HTTPException(status_code=500, detail="Database connection failed.")

        # --- 1. 数据聚合 (Data Aggregation) ---
        stats_raw = get_assessment_question_stats(db_conn, assessment_id)
        if not stats_raw:
            raise HTTPException(status_code=404, detail="该考核尚无学生作答数据，无法进行分析。")

        # --- 2. 获取上下文 (Get Context) ---
        assessment_data = get_assessment_content_by_id(db_conn, assessment_id)
        if not assessment_data:
            raise HTTPException(status_code=404, detail=f"ID为 {assessment_id} 的考核未找到。")
        
        assessment_title = assessment_data.get('title', '未命名考核')
        # 从 'content' 中分离出纯题目部分
        questions_text = assessment_data.get('content', '').split('---参考答案与解析---')[0].strip()

        # --- 3. 构造 Prompt (Prompt Engineering) ---
        analysis_prompt = f"""
        你是一位顶级的教育数据分析专家和教学顾问。你的任务是深入分析一份在线考核的学情统计数据，并为任课教师生成一份全面、深刻且极具操作性的学情分析报告。

        **【输入信息】**

        1.  **考核基本信息:**
            - 考核标题: "{assessment_title}"

        2.  **考核的全部题目:**
            ---
            {questions_text}
            ---

        3.  **各题作答情况的统计数据 (JSON格式):**
            ---
            {json.dumps(stats_raw, indent=2, ensure_ascii=False)}
            ---

        **【你的核心任务】**
        请基于以上所有信息，生成一份结构化的学情分析报告。你的输出必须是且只能是一个符合下面描述的、格式严谨的JSON对象。

        **【必需的输出JSON结构】**
        ```json
        {{
          "assessment_title": "{assessment_title}",
          "overall_summary": "（这里是对班级整体表现的高度概括性总结，必须简明扼要，点出核心问题。例如：本次考核显示，学生对基础概念掌握较为扎实，但在综合应用和解决复杂问题方面能力不足。）",
          "strength_points": [
            "（根据数据和题目，提炼出学生普遍掌握得最好的1-3个知识点或技能）",
            "（例如：学生对'Python基础语法'的记忆性知识掌握牢固）"
          ],
          "weakness_points": [
            "（根据数据和题目，提炼出学生普遍存在的、最关键的1-3个薄弱知识点或技能）",
            "（例如：学生在'递归思想的理解与应用'上存在普遍困难）"
          ],
          "problematic_questions": [
            {{
              "question_identifier": "（选择错误率最高或最能反映问题的题号，如 '题目3'）",
              "question_text": "（从上面提供的题目中，复制该题的完整题干）",
              "correct_rate": "（根据统计数据，计算并填入该题的正确率【纯数字，不要带百分号%】，例如 55.5）",
              "main_knowledge_point": "（精炼概括这道题考察的核心知识点或能力，例如：'链表的逆序操作'）",
              "common_error_analysis": "（深入分析学生为什么会在这道题上出错，是概念混淆、计算失误，还是审题不清？给出具体推测。）"
            }}
            // ... (为其他1-2个最值得关注的问题，生成同样结构的对象) ...
          ],
          "teaching_suggestions": [
            "（第一条教学建议：必须非常具体、可操作。例如：'建议在下节课用15分钟时间，通过画图和实例，重新讲解递归的执行过程，特别是回溯阶段。'）",
            "（第二条教学建议：例如：'可以设计一个关于链表操作的专项练习，包含头插法、尾插法和逆序，帮助学生巩固。'）",
            "（第三条教学建议：例如：'鼓励学生在编程题中多写注释，解释自己的思路，有助于暴露其思维误区。'）"
          ]
        }}
        ```
        **分析要求:**
        - **深刻洞察**: 不要只做表面描述，要深入分析数据背后的原因。
        - **聚焦重点**: `problematic_questions` 只需选择最关键的2-3个进行分析。
        - ** actionable**: `teaching_suggestions` 必须是老师看完就能直接用的具体方法，而不是空泛的口号。

        现在，请开始生成你的专业JSON分析报告。
        """

        # --- 4. 调用 LLM 并返回 ---
        parsed_analysis = await parse_query_with_llm(analysis_prompt)
        
        if "error" in parsed_analysis or not parsed_analysis.get("problematic_questions"):
            print(f"LLM parsing failed. Raw response: {parsed_analysis}")
            raise HTTPException(status_code=500, detail="AI模型未能生成有效的分析报告。")
        if 'problematic_questions' in parsed_analysis and isinstance(parsed_analysis['problematic_questions'], list):
            for question_data in parsed_analysis['problematic_questions']:
               if 'correct_rate' in question_data:
                    rate_val = question_data['correct_rate']
                    try:
                        # 如果是字符串, 移除 '%' 并转换为 float
                        if isinstance(rate_val, str):
                           cleaned_rate = float(rate_val.strip().replace('%', ''))
                        # 如果已经是数字, 确保是 float
                        else:
                            cleaned_rate = float(rate_val)
                        question_data['correct_rate'] = cleaned_rate
                    except (ValueError, TypeError):
                        # 如果转换失败, 打印警告并设置为默认值 0.0
                        print(f"Warning: Could not parse correct_rate '{rate_val}'. Defaulting to 0.0.")
                        question_data['correct_rate'] = 0.0
        return AssessmentAnalysis(**parsed_analysis)

    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分析过程中发生内部错误: {str(e)}")
    finally:
        if db_conn and db_conn.is_connected():
            db_conn.close()


async def _generate_semantic_title_for_refinement(original_title: str, user_query: str) -> str:
    """
    使用LLM根据原始标题和用户追问，生成一个描述性的新标题。
    """
    print(f"SERVICE: Generating semantic title. Original: '{original_title}', Query: '{user_query}'")
    
    title_generation_prompt = ChatPromptTemplate.from_template(
        """
        你是一位精通文件命名的专家。你的任务是根据一个【原始标题】和用户的【修改指令】，生成一个简洁、清晰、描述性的【新标题】。

        规则：
        1. 新标题必须保留【原始标题】的核心内容。
        2. 新标题应该简要地概括用户的【修改指令】。
        3. 新标题应该看起来专业，避免使用 "Refined", "ID" 等技术词汇。
        4. 新标题末尾可以加上一个版本标识，如 "(修订版)" 或 "(补充版)"。
        5. 你的回答【只能包含最终的标题字符串】，不要有任何额外的解释或引号。

        ---
        【示例 1】
        原始标题: "Python入门教案"
        修改指令: "再加两道编程练习题"
        你的输出: Python入门教案 - 补充编程练习

        【示例 2】
        原始标题: "一战历史考核"
        修改指令: "把选择题的难度提高一些"
        你的输出: 一战历史考核 (难度提升版)
        ---

        现在，请为以下输入生成新标题：
        原始标题: "{original_title}"
        修改指令: "{user_query}"
        """
    )
    
    try:
        # 使用一个快速、低成本的模型
        llm = ChatZhipuAI(model="glm-4", temperature=0.1)
        chain = title_generation_prompt | llm | StrOutputParser()
        new_title = await chain.ainvoke({"original_title": original_title, "user_query": user_query})
        return new_title.strip().replace('"', '') # 清理可能的引号
    except Exception as e:
        print(f"SERVICE WARNING: Failed to generate semantic title: {e}. Falling back to default.")
        # 如果LLM失败，提供一个仍然比之前好的后备标题
        return f"{original_title} (修订版 - {datetime.now().strftime('%H%M')})"