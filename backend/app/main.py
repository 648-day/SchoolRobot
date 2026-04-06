from fastapi import FastAPI

app = FastAPI(title='Campus AI Assistant API')


@app.get('/')
def read_root():
    return {'message': 'Campus AI Assistant backend is running'}
