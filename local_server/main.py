# This is a version of the main.py file found in ../../../server/main.py for testing the plugin locally.
# Use the command `poetry run dev` to run this.
import asyncio
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.responses import FileResponse

from datastore.factory import get_datastore
from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryResponse,
    UpsertRequest,
    UpsertResponse, CommandRequest, CommandResponse,
)
from models.models import CommandStatus

app = FastAPI()

PORT = 3333

origins = [
    f"http://localhost:{PORT}",
    "https://chat.openai.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.route("/.well-known/ai-plugin.json")
async def get_manifest(request):
    file_path = "./local_server/ai-plugin.json"
    simple_headers = {"Access-Control-Allow-Private-Network": "true"}
    return FileResponse(file_path, media_type="text/json", headers=simple_headers)


@app.route("/.well-known/logo.png")
async def get_logo(request):
    file_path = "./local_server/logo.png"
    return FileResponse(file_path, media_type="text/json")


@app.route("/.well-known/openapi.yaml")
async def get_openapi(request):
    file_path = "./local_server/openapi.yaml"
    return FileResponse(file_path, media_type="text/json")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert(
        request: UpsertRequest = Body(...),
):
    try:
        ids = await datastore.upsert(request.documents)
        return UpsertResponse(ids=ids)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/commands",
    response_model=CommandResponse,
)
async def create_command(
        request: CommandRequest = Body(...),
):
    logger.info("Received Command: " + str(request.command))
    try:
        id = await datastore.create_command(request.command)
        start_time = time.time()
        while True:
            logger.info("Polling for command status...")
            # Poll the database for the current status.
            command = await datastore.get_command(id)
            if command.status == CommandStatus.COMPLETED:
                return CommandResponse(id=id, errors=None)
            elif command.status == CommandStatus.ERROR:
                return CommandResponse(id=id, errors=command.errors)

            # Check if we've been polling for over a minute.
            if time.time() - start_time > 20:
                # Update the command status to 'ABANDONED'
                request.command.status = CommandStatus.ABANDONED
                await datastore.update_command(request.command)
                return CommandResponse(id=id, errors="Command was abandoned due to timeout. Check Obsidian connection")

            # Wait a few seconds before polling again.
            await asyncio.sleep(5)
    except Exception as e:
        logger.error(e)
        logger.error(e.__cause__)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post("/query", response_model=QueryResponse)
async def query_main(request: QueryRequest = Body(...)):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


# @app.delete(
#     "/delete",
#     response_model=DeleteResponse,
# )
# async def delete(
#         request: DeleteRequest = Body(...),
# ):
#     if not (request.ids or request.filter or request.delete_all):
#         raise HTTPException(
#             status_code=400,
#             detail="One of ids, filter, or delete_all is required",
#         )
#     try:
#         success = await datastore.delete(
#             ids=request.ids,
#             filter=request.filter,
#             delete_all=request.delete_all,
#         )
#         return DeleteResponse(success=success)
#     except Exception as e:
#         logger.error(e)
#         raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global datastore
    datastore = await get_datastore()


def start():
    uvicorn.run("local_server.main:app", host="localhost", port=PORT, reload=True)
