import pytest
pytest.skip('Requires Jira network access', allow_module_level=True)
import requests

url = "https://uname.emeal.nttdata.com/jiraito/rest/api/2/myself"

headers = {
    "Authorization": "Bearer GDdbybFCeSM6RsFHhD6Cs8Dp2yePB3kJaJq1mj",
    "Accept": "application/json"
}

r = requests.get(url, headers=headers)

print(r.status_code)
print(r.text)