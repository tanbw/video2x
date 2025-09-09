FROM ghcr.io/k4yt3x/video2x:6.4.0

# 设置环境变量
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

# 更新系统并安装必要的软件包
RUN pacman -Syu --noconfirm --needed && \
    pacman -S --noconfirm --needed git base-devel curl wget unzip python python-pipx which vulkan-tools nvidia-utils && \
    # 清理缓存以减少镜像大小
    pacman -Scc --noconfirm
# 确保 pipx 的二进制目录在 PATH 中
RUN echo 'export PATH="/root/.local/bin:${PATH}"' >> /root/.bashrcs
# 使用 pipx 安装 Python 应用
RUN pipx install fastapi && \
    pipx install uvicorn[standard] && \
    pipx inject fastapi python-multipart
#RUN pipx ensurepath
WORKDIR /app
COPY ./api.py /app/api.py

# 确保脚本有执行权限
RUN chmod +x /app/api.py

EXPOSE 7863

# 使用 pipx 运行的 Python 应用
CMD ["python", "/app/api.py"]
