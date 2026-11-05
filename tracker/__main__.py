import uvicorn
from .app import app
from .config import *
uvicorn.run(app,host=os.getenv('TRACKER_HOST','127.0.0.1'),port=int(os.getenv('TRACKER_PORT','8766')))
