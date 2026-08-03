FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt server_core.py mcp_server.py mcp_stdio.py ./

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["python", "mcp_server.py"]
