from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv('MOONSHOT_API_KEY'),
    base_url="https://api.moonshot.cn/v1",
)

# 测试 API
try:
    completion = client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {"role": "user", "content": "Hello, how are you?"}
        ],
        temperature=0.3,
    )
    print("API 测试成功:", completion.choices[0].message.content)
except Exception as e:
    print("API 测试失败:", str(e))