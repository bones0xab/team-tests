import sys, os 
sys.path.insert(0, os.getcwd()) 
from dotenv import load_dotenv 
load_dotenv() 
from app.main import app 
routes = [r.path for r in app.routes] 
print('\n'.join(routes)) 
