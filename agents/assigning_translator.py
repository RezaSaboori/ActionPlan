"""Assigning Translator Agent for correcting responsible parties in Persian translations."""

import logging
from typing import Dict, Any
from pathlib import Path
from utils.llm_client import LLMClient
from config.prompts import get_prompt

logger = logging.getLogger(__name__)


class AssigningTranslatorAgent:
    """
    Assigning Translator Agent that corrects responsible parties, jobs, 
    and departments in Persian translations to match the official reference document.
    """
    
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None):
        """
        Initialize Assigning Translator Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.reference_document = self._load_reference_document()
        self.system_prompt = get_prompt("assigning_translator")
        logger.info(f"Initialized AssigningTranslatorAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def _load_reference_document(self) -> str:
        """
        Load the reference document for organizational structure.
        
        Returns:
            Content of the reference document
        """
        try:
            # Get the reference document path
            ref_path = Path(__file__).parent.parent / "assigner_tools" / "Fa" / "Assigner refrence.md"
            
            if not ref_path.exists():
                logger.error(f"Reference document not found at: {ref_path}")
                return ""
            
            with open(ref_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"Loaded reference document: {len(content)} characters")
            return content
            
        except Exception as e:
            logger.error(f"Error loading reference document: {e}")
            return ""
    
    def execute(self, data: Dict[str, Any]) -> str:
        """
        Execute assigning translator logic.
        
        Args:
            data: Dictionary containing final_persian_plan
            
        Returns:
            Corrected Persian translation with accurate organizational assignments
        """
        logger.info("Assigning Translator correcting responsible parties in Persian translation")
        
        final_persian_plan = data.get("final_persian_plan", "")
        
        if not final_persian_plan:
            logger.warning("No Persian plan provided for assignment correction")
            return ""
        
        if not self.reference_document:
            logger.warning("Reference document not loaded, returning original plan")
            return final_persian_plan
        
        # Generate corrected Persian plan using LLM
        prompt = f"""شما یک کارشناس تصحیح ترجمه برای اسناد مدیریت بحران بهداشت و درمان هستید.

وظیفه شما:
۱. دریافت یک طرح عملیاتی/اجرایی به زبان فارسی که قبلاً از انگلیسی ترجمه شده است
۲. بررسی تمام مسئولین، پست‌های سازمانی، واحدها، معاونت‌ها، دفاتر، مراکز و سازمان‌های ذکر شده
۳. تطبیق آنها با ساختار رسمی وزارت بهداشت، درمان و آموزش پزشکی (از سند مرجع)
۴. تصحیح هرگونه عنوان، مسئولیت یا واحد سازمانی که به درستی ترجمه نشده است

اصول تصحیح:
- استفاده دقیق از اصطلاحات رسمی سازمانی (نه معادل تقریبی)
- حفظ سلسله مراتب سازمانی (وزارت > دانشگاه > مرکز)
- تطبیق کامل با سند مرجع
- حفظ تمام فرمت‌های markdown
- تصحیح فقط موارد اشتباه، نه تغییر کل متن
- اگر عنوانی در سند مرجع وجود ندارد، نزدیک‌ترین معادل رسمی را انتخاب کنید

سند مرجع ساختار سازمانی:
```
{self.reference_document}
```

طرح فارسی که باید تصحیح شود:
```
{final_persian_plan}
```

طرح تصحیح‌شده را بدون هیچ توضیح اضافی ارائه دهید.
فقط متن نهایی تصحیح‌شده را برگردانید."""
        
        try:
            corrected_plan = self.llm.generate(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.1
            )
            
            logger.info(f"Assignment correction completed: {len(corrected_plan)} characters")
            
            # Log changes if markdown logger available
            if self.markdown_logger:
                self.markdown_logger.log_agent_output("Assigning Translator", {
                    "input_length": len(final_persian_plan),
                    "output_length": len(corrected_plan),
                    "reference_doc_loaded": bool(self.reference_document),
                    "reference_doc_length": len(self.reference_document)
                })
            
            return corrected_plan
            
        except Exception as e:
            logger.error(f"Assignment correction error: {e}")
            # Return original plan if correction fails
            return final_persian_plan

