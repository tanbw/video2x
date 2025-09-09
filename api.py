import asyncio
import os
import uuid
import shutil
from typing import Dict, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
from pathlib import Path

app = FastAPI(title="Video2X Processing API")

# 配置
INPUT_DIR = "uploads"
OUTPUT_DIR = "outputs"
TASK_DB: Dict[str, dict] = {}  # 简单的内存数据库存储任务状态

# 确保目录存在
Path(INPUT_DIR).mkdir(exist_ok=True)
Path(OUTPUT_DIR).mkdir(exist_ok=True)

class ProcessingRequest(BaseModel):
    scale: int = 2

class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    message: Optional[str] = None

@app.post("/generate", response_model=TaskStatus, status_code=202)
async def create_processing_task(
    background_tasks: BackgroundTasks,
    scale: int = 2,
    file: UploadFile = File(...)
):
    """提交视频处理任务"""
    # 验证文件类型
    if not file.filename.endswith('.mp4'):
        raise HTTPException(status_code=400, detail="Only MP4 files are supported")
    
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    # 保存上传的文件
    input_path = os.path.join(INPUT_DIR, f"{task_id}_input.mp4")
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 初始化任务状态
    TASK_DB[task_id] = {
        "status": "pending",
        "input_path": input_path,
        "output_path": os.path.join(OUTPUT_DIR, f"{task_id}_output.mp4"),
        "scale": scale,
        "message": "Task created and waiting to be processed"
    }
    
    # 将任务添加到后台处理
    background_tasks.add_task(process_video, task_id)
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Task created and waiting to be processed"
    }

async def process_video(task_id: str):
    """后台处理视频的函数"""
    task = TASK_DB.get(task_id)
    if not task:
        return
    
    try:
        # 更新任务状态为处理中
        task["status"] = "processing"
        task["message"] = "Video processing started"
        
        # 构建命令video2x -i result.mp4 -o output.mp4 -p libplacebo 
        # --width 720 --height 1008 -c libx265  -e pix_fmt=yuv420p -e crf=28 -e preset=medium
        cmd = [
            "video2x",
            "-i", task["input_path"],
            "-o", task["output_path"],
            "-p", "libplacebo","--width", "720","--height", "1248",
            "-c", "libx265","-e", "crf=28","-e", "preset=medium",
            "--no-progress"
        ]
        
        # 打印命令
        print(f"执行命令: {' '.join(cmd)}")
        
        # 异步运行命令并实时输出
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 创建任务来实时读取输出
        stdout_task = asyncio.create_task(read_stream(process.stdout, "STDOUT"))
        stderr_task = asyncio.create_task(read_stream(process.stderr, "STDERR"))
        
        # 等待进程完成
        return_code = await process.wait()
        
        # 等待输出读取完成
        await asyncio.gather(stdout_task, stderr_task)
        
        # 检查输出文件是否存在且大小不为0
        output_file_ok = False
        if os.path.exists(task["output_path"]) and os.path.getsize(task["output_path"]) > 0:
            output_file_ok = True

        # 如果返回码是0，或者返回码是特定的崩溃码但文件已生成，都视为成功
        if return_code == 0 or (return_code == 3221226505 and output_file_ok):
            # 处理成功
            task["status"] = "completed"
            if return_code != 0:
                task["message"] = "Processing completed with a non-critical exit error. The output file should be usable."
                print(f"任务 {task_id} 处理完成，但退出时崩溃 (Code: {return_code})。输出文件已生成。")
            else:
                task["message"] = "Video processing completed successfully"
                print(f"任务 {task_id} 处理成功")
        else:
            # 处理失败
            task["status"] = "failed"
            error_msg = f"Processing failed with return code {return_code}"
            task["message"] = error_msg
            print(f"任务 {task_id} 处理失败: {error_msg}")
            
    except Exception as e:
        # 处理异常
        task["status"] = "failed"
        task["message"] = f"Error during processing: {str(e)}"
        print(f"任务 {task_id} 处理异常: {str(e)}")

async def read_stream(stream, label):
    """异步读取流并打印到控制台"""
    if stream:
        while True:
            line = await stream.readline()
            if not line:
                break
            print(f"[{label}] {line.decode().strip()}")

@app.get("/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """获取任务状态"""
    task = TASK_DB.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "message": task.get("message")
    }

@app.get("/download/{task_id}")
async def download_processed_video(task_id: str):
    """下载处理后的视频文件"""
    task = TASK_DB.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video processing is not completed yet")
    
    if not os.path.exists(task["output_path"]):
        raise HTTPException(status_code=404, detail="Processed video not found")
    
    # 返回文件
    return FileResponse(
        task["output_path"],
        media_type="video/mp4",
        filename=f"processed_{task_id}.mp4"
    )

@app.get("/")
async def root():
    return {"message": "Video2X Processing API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7863)
