# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import json
from typing import Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks, Response
from starlette.responses import StreamingResponse

from GridCalEngine.IO.gridcal.remote import RemoteInstruction, RemoteJob, run_job
from GridCalEngine.IO.gridcal.pack_unpack import parse_gridcal_data
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import SimulationTypes, JobStatus

router = APIRouter()

JOBS_LIST: Dict[str, RemoteJob] = dict()


def get_fs_folder() -> str:
    """
    Get the folder where to save files
    :return:
    """
    return "."


def generate_job_file_path(job_id: str):
    """

    :param job_id:
    :return:
    """
    return os.path.join(get_fs_folder(), f"{job_id}.zip")





async def process_json_data(json_data: Dict[str, Dict[str, Dict[str, str]]]):
    """
    Action called on the upload
    :param json_data: the grid info generated with 'gather_model_as_jsons_for_communication'
    """
    grid = parse_gridcal_data(data=json_data)
    print(f'Circuit loaded alright nbus{grid.get_bus_number()}, nbr{grid.get_branch_number()}')

    if 'instruction' in json_data:
        instruction = RemoteInstruction(data=json_data['instruction'])

        job = RemoteJob(grid=grid, instruction=instruction)

        # register the job
        JOBS_LIST[job.id_tag] = job

        # print("Job data\n", job.get_data())
        if job.instruction.operation != SimulationTypes.NoSim:
            driver = run_job(grid=grid, job=job)

            if driver is not None:
                print("Driver:", driver.name)
                if driver.results is not None:
                    return driver.results.get_dict()
                else:
                    return dict()
            else:
                return dict()

        else:
            print("No simulation")
            return dict()

    else:
        print('No Instruction found\n\n', json_data)
        return dict()


async def stream_load_json(json_data):
    """
    Async function to stream a json file
    :param json_data:
    :return:
    """

    async def generate():
        """
        generate
        """
        yield json.dumps(json_data).encode()

    return StreamingResponse(generate())


@router.post("/upload_job/")
async def upload_job(json_data: dict, background_tasks: BackgroundTasks):
    """
    Endpoint to upload a job into here
    :param json_data:
    :param background_tasks:
    :return:
    """
    background_tasks.add_task(stream_load_json, json_data)

    grid: MultiCircuit = parse_gridcal_data(data=json_data)

    print(f'Circuit loaded alright nbus{grid.get_bus_number()}, nbr{grid.get_branch_number()}')

    if 'instruction' in json_data:
        instruction = RemoteInstruction(data=json_data['instruction'])

        job = RemoteJob(grid=grid, instruction=instruction)

        # register the job
        JOBS_LIST[job.id_tag] = job
        job.status = JobStatus.Running

        # print("Job data\n", job.get_data())
        if job.instruction.operation != SimulationTypes.NoSim:

            try:
                driver = run_job(grid=grid, job=job)
            except Exception as e:
                return {"success": False, "results": None, "msg": f"{e}"}

            job.status = JobStatus.Done
            JOBS_LIST.pop(job.id_tag)

            if driver is not None:
                print("Driver:", driver.name)
                if driver.results is not None:
                    return {"success": True, "results": driver.results.get_dict(), "msg": "all good"}
                else:
                    return {"success": False, "results": None, "msg": "No results in the driver"}
            else:
                return {"success": False, "results": None, "msg": "The driver is None"}

        else:
            return {"success": False, "results": None, "msg": "No simulation"}

    else:
        return {"success": False, "results": None, "msg": "No Instruction found"}


@router.get("/jobs_list")
async def jobs_list():
    """
    Endpoint to return the list of jobs
    :return: string
    """
    return [job.get_data() for id_tag, job in JOBS_LIST.items()]


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a specific job by ID
    :param job_id: The ID of the job to delete
    :return: A message indicating the result
    """
    if job_id in JOBS_LIST:
        del JOBS_LIST[job_id]
        return {"message": f"Job {job_id} deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """
    Cancel a specific job by ID
    :param job_id: The ID of the job to cancel
    :return: A message indicating the result
    """
    job = JOBS_LIST.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.cancel()
    return {"message": f"Job {job_id} canceled successfully"}


@router.get("/download_results/{job_id}")
async def download_large_file(job_id: str):
    """
    Function to download a large file, ie the results of a simulation
    """

    job = JOBS_LIST.get(job_id, None)

    if job is None:
        return Response(status_code=404, content="Job not found")

    if job.status != JobStatus.Done:
        return Response(status_code=405, content="Job not finished yet :/")

    # Path to your large binary file
    file_path = generate_job_file_path(job_id=job_id)

    # Check if the file exists
    if not os.path.exists(file_path):
        return Response(status_code=406, content=f"File not found {file_path}")

    # Function to stream the file
    def iter_file(chunk_size=1024 * 1024):
        """

        :param chunk_size:
        :return:
        """
        with open(file_path, "rb") as file:
            sent = 0
            while chunk := file.read(chunk_size):  # Read in chunks of 1MB
                sent += chunk_size
                job.progress = f"{sent} MB"
                yield chunk

    print("Sending", job_id)

    # Return a streaming response
    return StreamingResponse(iter_file(), media_type="application/octet-stream")
