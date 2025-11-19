"""
LLM Service Module
==================
This module handles all LLM-related operations including:
- Intent classification using LLM
- Agentic RAG orchestration
- Answer generation with context
- Integration with Ollama service

وحدة خدمة LLM
==============
هذه الوحدة تتعامل مع جميع عمليات LLM بما في ذلك:
- تصنيف النية باستخدام LLM
- تنسيق Agentic RAG
- توليد الإجابات مع السياق
- التكامل مع خدمة Ollama
"""

import httpx
import os
from pydantic import BaseModel
from typing import Dict, Any

# ------------------------------------------------------------
# Service Connection Settings
# إعدادات الاتصال بالخدمات
# ------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = "llama3:8b"  # يمكن تغيير النموذج هنا / Model can be changed here

# ------------------------------------------------------------
# Data Models
# نماذج البيانات
# ------------------------------------------------------------
class Query(BaseModel):
    """
    Query model for LLM requests.
    / نموذج الاستعلام لطلبات LLM.
    
    Attributes:
        question: User's question / سؤال المستخدم
        user_id: User identifier / معرف المستخدم
    """
    question: str
    user_id: str

class LLMResponse(BaseModel):
    """
    LLM response model.
    / نموذج استجابة LLM.
    
    Attributes:
        answer: Generated answer / الإجابة المولدة
        source: Source of information / مصدر المعلومة
        intent: Detected intent / النية المكتشفة
    """
    answer: str
    source: str
    intent: str

# ------------------------------------------------------------
# قاعدة الأسئلة الشائعة (لأغراض التوجيه السريع)
# ------------------------------------------------------------
FAQ_DATABASE = {
    "متى آخر يوم للحذف والإضافة؟": "آخر يوم هو 20 فبراير 2025.",
    "ما هي درجة النجاح في مادة 101؟": "درجة C أو 60%.",
}

# ------------------------------------------------------------
# وظائف الخدمة
# ------------------------------------------------------------

async def generate_llm_response(prompt: str) -> str:
    """
    Generate LLM response by communicating with Ollama service.
    / توليد استجابة LLM من خلال التواصل مع خدمة Ollama.
    
    Args:
        prompt: The prompt/question to send to LLM
        / الموجه/السؤال لإرساله إلى LLM
        
    Returns:
        Generated answer from LLM
        / الإجابة المولدة من LLM
        
    Raises:
        httpx.TimeoutException: If request times out
        httpx.RequestError: If connection to Ollama fails
        
    Example:
        >>> answer = await generate_llm_response("What is AI?")
        >>> print(answer)
    """
    try:
        # زيادة timeout إلى 180 ثانية للنماذج الكبيرة
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": LLM_MODEL, 
                    "prompt": prompt, 
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 500  # تحديد عدد الكلمات القصوى
                    }
                }
            )
            response.raise_for_status()
            result = response.json()
            llm_answer = result.get("response", "لم أجد إجابة محددة.")
            return llm_answer.strip()
    except httpx.TimeoutException:
        return "انتهت مهلة الاتصال بالنموذج. يرجى المحاولة مرة أخرى أو تبسيط السؤال."
    except httpx.RequestError as e:
        return f"خطأ في الاتصال بـ Ollama: {e}. تأكد من أن Ollama يعمل وأن النموذج {LLM_MODEL} محمّل."
    except Exception as e:
        return f"حدث خطأ غير متوقع أثناء توليد الإجابة: {repr(e)}"

async def determine_intent(question: str) -> str:
    """
    Determine user intent using LLM-based classification.
    / تحديد نية المستخدم باستخدام تصنيف قائم على LLM.
    
    This function uses an LLM to classify the user's question into one of the
    following intents:
    - query_rag: Questions about regulations, study plans, course descriptions
    - analyze_progress: Questions about student records, GPA, remaining courses
    - simulate_gpa: Questions involving GPA simulation
    - graph_query: Questions about skills, specializations, course relationships
    - general_chat: General questions, greetings, or other queries
    
    تستخدم هذه الدالة LLM لتصنيف سؤال المستخدم إلى إحدى النوايا التالية:
    - query_rag: أسئلة حول اللوائح، الخطط الدراسية، توصيف المقررات
    - analyze_progress: أسئلة حول سجل الطالب، المعدل التراكمي، المقررات المتبقية
    - simulate_gpa: أسئلة تتضمن محاكاة المعدل التراكمي
    - graph_query: أسئلة حول المهارات، التخصصات، علاقات المقررات
    - general_chat: أسئلة عامة، تحيات، أو استفسارات أخرى
    
    Args:
        question: User's question / سؤال المستخدم
        
    Returns:
        Detected intent as string / النية المكتشفة كسلسلة نصية
        
    Example:
        >>> intent = await determine_intent("ما هو معدلي التراكمي؟")
        >>> print(intent)  # "analyze_progress"
    """
    
    # قائمة الأدوات المتاحة للـ Agent
    tools_description = """
    - query_rag: للأسئلة المتعلقة باللوائح، الخطط الدراسية، توصيف المقررات، أو أي معلومات موجودة في المستندات الرسمية.
    - analyze_progress: للأسئلة المتعلقة بسجل الطالب، المعدل التراكمي، المقررات المتبقية، أو المقررات القابلة للتسجيل.
    - simulate_gpa: للأسئلة التي تتضمن محاكاة المعدل التراكمي أو حساب المعدل المتوقع.
    - graph_query: للأسئلة المتعلقة بالمهارات، التخصصات، أو العلاقات بين المقررات (مثل: ما هي المهارات التي أكتسبها من مقرر X؟).
    - general_chat: للأسئلة العامة، التحية، أو أي سؤال لا يندرج تحت الفئات السابقة.
    """
    
    prompt = f"""
    أنت نظام توجيه ذكي. مهمتك هي تحليل سؤال المستخدم وتحديد الأداة الأنسب للإجابة عليه من القائمة التالية.
    
    الأدوات المتاحة:
    {tools_description}
    
    السؤال: "{question}"
    
    الرد يجب أن يكون اسم الأداة فقط، بدون أي شرح أو علامات ترقيم إضافية.
    مثال: analyze_progress
    """
    
    # استخدام نموذج LLM لتحديد النية
    intent = await generate_llm_response(prompt)
    
    # تنظيف وتصحيح النية
    intent = intent.strip().lower().replace('.', '').replace(' ', '_')
    
    # قائمة النوايا الصالحة
    valid_intents = ["query_rag", "analyze_progress", "simulate_gpa", "graph_query", "general_chat"]
    
    if intent in valid_intents:
        return intent
    else:
        # في حال فشل النموذج في تحديد نية صالحة، نعود إلى الدردشة العامة
        return "general_chat"

async def process_agentic_query(question: str, user_id: str, services: Dict[str, Any], is_demo: bool = False) -> LLMResponse:
    """
    Main Agentic RAG logic that routes questions to appropriate services.
    / المنطق الرئيسي لـ Agentic RAG الذي يوجه السؤال إلى الخدمة المناسبة.
    
    This function implements the core Agentic RAG pattern:
    1. Checks FAQ database for quick answers
    2. Determines user intent using LLM
    3. Routes to appropriate service based on intent
    4. Generates contextual answer with sources
    
    هذه الدالة تطبق نمط Agentic RAG الأساسي:
    1. التحقق من قاعدة الأسئلة الشائعة للإجابات السريعة
    2. تحديد نية المستخدم باستخدام LLM
    3. توجيه إلى الخدمة المناسبة بناءً على النية
    4. توليد إجابة سياقية مع المصادر
    
    Args:
        question: User's question / سؤال المستخدم
        user_id: User identifier (None for demo mode) / معرف المستخدم (None للوضع التجريبي)
        services: Dictionary of available services / قاموس الخدمات المتاحة
            - documents: Documents service for RAG
            - progress: Progress service for student analysis
            - graph: Graph service for skills queries
        is_demo: Whether running in demo mode / هل يعمل في الوضع التجريبي
        
    Returns:
        LLMResponse object with answer, source, and intent
        / كائن LLMResponse يحتوي على الإجابة والمصدر والنية
        
    Example:
        >>> services = {
        ...     "documents": documents_service,
        ...     "progress": progress_service,
        ...     "graph": graph_service
        ... }
        >>> response = await process_agentic_query(
        ...     "ما هي متطلبات التخرج؟",
        ...     "student_001",
        ...     services
        ... )
        >>> print(response.answer)
    """
    
    # 1. فحص الأسئلة الشائعة (FAQ)
    if question in FAQ_DATABASE:
        return LLMResponse(answer=FAQ_DATABASE[question], source="FAQ Database", intent="query_rag")
    
    # 2. تحديد النية
    intent = await determine_intent(question)
    
    # 3. توجيه السؤال بناءً على النية
    
    # 3.1. استعلام RAG (المستندات)
    if intent == "query_rag":
        context_str, source_info = services["documents"].retrieve_context(question)
        
        if context_str:
            rag_prompt = f"""
            أنت "مرشدي الأكاديمي الذكي".
            أجب على السؤال بدقة بناءً على المستندات التالية فقط.
            إذا لم تجد الجواب، قل "لا أعرف".

            المستندات:
            {context_str}

            السؤال:
            {question}
            """
            answer = await generate_llm_response(rag_prompt)
            return LLMResponse(answer=answer, source=source_info, intent=intent)
        else:
            # إذا لم يتم العثور على سياق RAG، ننتقل إلى الدردشة العامة
            intent = "general_chat"

    # 3.2. تحليل التقدم (Progress Analysis)
    elif intent == "analyze_progress":
        # إذا كان الوضع التجريبي، لا يمكن الوصول للبيانات الشخصية
        if is_demo or not user_id:
            return LLMResponse(
                answer="⚠️ الوضع التجريبي لا يدعم الوصول إلى بياناتك الشخصية. يرجى تسجيل الدخول بالبيانات الصحيحة للوصول إلى هذه الميزة.",
                source="Demo Mode",
                intent=intent
            )
        
        try:
            # استخدام analyze_progress بدلاً من analyze_student_plan
            progress_data = services["progress"].analyze_progress(
                services["progress_db"], 
                services.get("users_db"), 
                user_id
            )
            
            # صياغة السؤال لـ LLM ليقوم بتحليل البيانات
            analysis_prompt = f"""
            أنت مرشد أكاديمي. بناءً على بيانات تقدم الطالب التالية، أجب على سؤاله.
            
            بيانات الطالب:
            - المعدل التراكمي الحالي: {progress_data['current_gpa']}
            - الساعات المكتملة: {progress_data['completed_hours']}
            - المقررات المتبقية: {progress_data['remaining_courses_count']}
            - المقررات القابلة للتسجيل: {', '.join([c['code'] for c in progress_data['registerable_next_semester']])}
            - المقررات المكتملة: {progress_data['completed_courses']}
            
            السؤال:
            {question}
            """
            answer = await generate_llm_response(analysis_prompt)
            return LLMResponse(answer=answer, source="Student Progress Service", intent=intent)
        except Exception as e:
            return LLMResponse(answer=f"حدث خطأ أثناء تحليل تقدم الطالب: {repr(e)}", source="Error", intent=intent)

    # 3.3. استعلام الرسم البياني (Graph Query)
    elif intent == "graph_query":
        # هنا يمكن استخدام LLM لتوليد استعلام Cypher أو استدعاء وظائف محددة في graph_service
        # لتبسيط الأمر، سنطلب من LLM الإجابة بناءً على البيانات المتاحة في graph_service
        
        # مثال: إذا كان السؤال عن مهارات مقرر معين
        if "مهارات" in question and "مقرر" in question:
            # نحتاج إلى استخراج اسم المقرر من السؤال
            # (هذه خطوة متقدمة تتطلب LLM أكثر ذكاءً أو استخدام مكتبة مثل LangChain Tooling)
            # لتبسيط الأمر، سنفترض أن المستخدم يسأل عن مهارات مقرر CS101
            skills = services["graph"].get_skills_for_course("CS101")
            if skills:
                answer = f"المقرر CS101 يدرس المهارات التالية: {', '.join(skills)}"
                return LLMResponse(answer=answer, source="Graph DB (Neo4j)", intent=intent)
        
        # إذا لم يتمكن من معالجة السؤال كاستعلام رسم بياني محدد، ننتقل إلى الدردشة العامة
        intent = "general_chat"
        
    # 3.4. محاكاة المعدل (GPA Simulation) - هذه الوظيفة يجب أن تستدعى مباشرة من الواجهة الأمامية
    # لأنها تتطلب مدخلات منظمة (درجات متوقعة)، لذا لن يتم توجيهها عبر Agent هنا.
    
    # 3.5. الدردشة العامة (General Chat)
    if intent == "general_chat":
        general_prompt = f"""
        أنت "مرشدي الأكاديمي الذكي". أجب على السؤال التالي بأسلوب ودود ومفيد.
        السؤال:
        {question}
        """
        answer = await generate_llm_response(general_prompt)
        return LLMResponse(answer=answer, source="LLM (General)", intent=intent)
        
    # 4. حالة غير متوقعة
    return LLMResponse(answer="عذراً، لم أتمكن من فهم نيتك أو توجيه سؤالك إلى الخدمة المناسبة.", source="Agent Error", intent="unknown")

def process_chat_request(question: str, user_id: str, db_users, db_progress, db_notifications, is_demo: bool = False) -> Dict[str, Any]:
    """معالجة طلب الدردشة (وظيفة متزامنة للاستخدام في FastAPI)."""
    import asyncio
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from services import documents_service, progress_service, graph_service
    
    # إعداد الخدمات
    services = {
        "documents": documents_service,
        "progress": progress_service,
        "progress_db": db_progress,
        "users_db": db_users,
        "graph": graph_service
    }
    
    try:
        # تشغيل العملية غير المتزامنة
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # إذا كان الوضع التجريبي، نستخدم user_id مختلف لتجنب الوصول للبيانات الشخصية
            effective_user_id = user_id if not is_demo else None
            response = loop.run_until_complete(process_agentic_query(question, effective_user_id, services, is_demo))
            return {
                "answer": response.answer,
                "source": response.source,
                "intent": response.intent
            }
        finally:
            loop.close()
    except Exception as e:
        return {
            "answer": f"عذراً، حدث خطأ أثناء معالجة سؤالك: {str(e)}",
            "source": "Error",
            "intent": "error"
        }
