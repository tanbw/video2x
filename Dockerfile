FROM ghcr.nju.edu.cn/k4yt3x/video2x:6.4.0

# 设置环境变量
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1
# 如果你希望 pip 也使用中科大的源，可以设置这个环境变量
ENV PIP_INDEX_URL=https://pypi.mirrors.ustc.edu.cn/simple/ 

# 更新系统并安装必要的软件包
# 确保安装了 python-venv (Arch 中通常是 python 包的一部分，但明确指定更安全)
# 安装 git, base-devel, curl, wget, unzip, vulkan-tools, nvidia-utils
RUN echo 'Server = https://mirrors.ustc.edu.cn/archlinux/$repo/os/$arch' > /etc/pacman.d/mirrorlist && \
    pacman -Syu --noconfirm --needed && \
    pacman -S --noconfirm --needed \
        git base-devel curl wget unzip \
        python python-pip which \ 
        vulkan-tools nvidia-utils && \
    # 清理缓存以减少镜像大小
    pacman -Scc --noconfirm

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt (如果有的话，推荐用来管理依赖)
# COPY ./requirements.txt /app/requirements.txt

# 创建虚拟环境
RUN python -m venv venv

# 激活虚拟环境并升级 pip，然后安装依赖
# 注意：在 RUN 指令中激活 venv 需要显式调用 venv/bin/pip 或在同一条 RUN 中 source
RUN /app/venv/bin/pip install --no-cache-dir --upgrade pip && \
    # 如果你有 requirements.txt 文件，使用下面这行
    # /app/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    # 如果没有 requirements.txt，直接安装需要的包
    /app/venv/bin/pip install --no-cache-dir fastapi uvicorn[standard] python-multipart

# 复制应用代码
COPY ./api.py /app/api.py

# 确保脚本有执行权限 (如果 api.py 本身需要执行权限)
# RUN chmod +x /app/api.py

# 暴露端口
EXPOSE 7863
ENTRYPOINT [ "" ]
# 启动命令：激活虚拟环境并运行应用
# 注意：在 CMD/ENTRYPOINT 中激活 venv 也需要显式路径或在 shell 中 source
# 使用 uvicorn 启动 FastAPI 应用 (推荐)
CMD ["/app/venv/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7863"]
# 或者，如果 api.py 是一个可直接运行的脚本
# CMD ["/app/venv/bin/python", "/app/api.py"]