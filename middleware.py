from fastapi import FastAPI, Request, Response
import time


def my_middleware(app: FastAPI):
    @app.middleware("http")
    async def count_time_middleware(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        end_time = time.time()
        print(f"请求处理时间: {end_time - start_time}")
        return response

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        message = f"{request.client.host}:{request.client.port} - {request.method} {request.url} - {time.strftime('%Y-%m-%d %H:%M:%S')}"
        print(message)
        response = await call_next(request)
        return response
