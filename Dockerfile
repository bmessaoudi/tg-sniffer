FROM python:3.10
ADD main.py .
ADD .env .
ADD requirements.txt . 
RUN pip install -r requirements.txt
CMD [“/usr/bin/python3”, “./main.py”] 