from langchain.llms.base import LLM
from typing import Any, List, Optional
from langchain.callbacks.manager import CallbackManagerForLLMRun
from transformers import AutoTokenizer, AutoModelForCausalLM, GenerationConfig, LlamaTokenizerFast, BitsAndBytesConfig
import torch


class Qwen2_LLM(LLM):
    # 基于本地 Qwen2 自定义 LLM 类
    tokenizer: AutoTokenizer = None
    model: AutoModelForCausalLM = None

    def __init__(self, mode_name_or_path: str):
        super().__init__()
        print("正在从本地加载模型...")
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )
        self.tokenizer = AutoTokenizer.from_pretrained(mode_name_or_path, use_fast=False)
        self.model = AutoModelForCausalLM.from_pretrained(
            mode_name_or_path,
            quantization_config=quantization_config,
            device_map="auto"
        )

        self.model.generation_config = GenerationConfig.from_pretrained(mode_name_or_path)
        print("完成本地模型的加载")

    # prompt: 用户输入的文本提示词
    # stop: 可选的停止生成词列表
    # run_manager: 用于管理回调的对象
    # **kwargs: 其他可选参数
    def _call(self, prompt: str, stop: Optional[List[str]] = None,
              run_manager: Optional[CallbackManagerForLLMRun] = None,
              **kwargs: Any):
        # 将用户输入包装成对话格式
        messages = [{"role": "user", "content": prompt}]

        input_ids = self.tokenizer.apply_chat_template(messages,
                                                       tokenize=False,
                                                       add_generation_prompt=True)

        model_inputs = self.tokenizer([input_ids], return_tensors="pt").to('cuda')
        attention_mask = model_inputs.attention_mask if 'attention_mask' in model_inputs else None
        generated_ids = self.model.generate(
            model_inputs.input_ids,
            attention_mask=attention_mask,  # 添加attention_mask
            max_new_tokens=512
        )
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids) # 去除输入部分，保留纯生成内容
        ]
        # 解码为文本
        response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

        return response

    @property
    def _llm_type(self) -> str:
        return "Qwen2_LLM"
