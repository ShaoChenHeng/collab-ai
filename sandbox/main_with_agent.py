from LLM import Qwen2_LLM
model_dir = "/home/scheng/llm/Qwen2-7B-Instruct"
llm = Qwen2_LLM(mode_name_or_path = model_dir)

def build_prompt(user_input: str, history: list) -> str:
    prompt = ""
    for user, bot in history:
        prompt += f"用户：{user}\n助手：{bot}\n"
    prompt += f"用户：{user_input}\n助手："
    return prompt

history = []
while True:
    user_input = input("你：")

    if user_input.strip().lower() in ["exit", "quit", "bye"]:
        break

    prompt = build_prompt(user_input, history)
    bot_reply = llm.invoke(prompt)
    print("助手：", bot_reply)
    history.append((user_input, bot_reply))
