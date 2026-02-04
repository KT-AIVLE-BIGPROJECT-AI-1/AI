import json, re
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _strip_code_fence(txt:str)->str:
    return re.sub(r"```json|```","",txt).strip()

def call_llm_json(prompt:str, model="gpt-4o-mini"):
    res = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":"JSON만 출력"},
                  {"role":"user","content":prompt}],
        temperature=0.2
    )
    txt=_strip_code_fence(res.choices[0].message.content)
    return json.loads(txt)
