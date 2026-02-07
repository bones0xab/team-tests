from langchain.tools import tool
from langchain.agents import create_agent
from langchain_ollama import OllamaLLM, ChatOllama
from services.Fetch import search_issues
from services.Normalisation import normalize_issue


def Get_Jira_data():
    jql = "created >= -30 AND status != Done"
    fields = ["summary", "status", "assignee", "updated"]
    issues = search_issues(jql, fields)
    normalized_data = [normalize_issue(i) for i in issues]
    return normalized_data



llm = ChatOllama(
    model="qwen2.5:7b-instruct",
    temperature=0.2
)



agent = create_agent(
    model = llm,
    system_prompt="Be concise. Answer in one sentence."
)
data = Get_Jira_data()

result = agent.invoke({"messages" : [{"role" : "user", "content" : "what weather casablanca has the most ?"}]})

print(result["messages"][-1].content)
