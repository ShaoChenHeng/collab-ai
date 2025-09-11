import threading
import logging
from agent.tools.knowledge_base.kb_tool import get_model, DEFAULT_EMB_MODEL

logger = logging.getLogger(__name__)

def _prewarm_model():
    """
    在后台线程中加载嵌入模型。
    """
    try:
        get_model(DEFAULT_EMB_MODEL)  # 直接加载本地路径
        logger.debug("[kb] embedding model prewarmed.")
    except Exception as e:
        logger.warning(f"[kb] preload failed: {e}")

def start():
    """
    启动一个守护线程来执行模型预热。
    """
    thread = threading.Thread(target=_prewarm_model, daemon=True)
    thread.start()