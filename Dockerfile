FROM python:3.7-alpine
RUN apk add --no-cache gcc jpeg-dev musl-dev zlib-dev linux-headers
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
ADD  * /pidi/
CMD ["python3", "-m", "pidi",\
	"--server", "pidi",\
        "--display","st7789",\
        "--blur-album-art",\
        "--rotation", "270"]

