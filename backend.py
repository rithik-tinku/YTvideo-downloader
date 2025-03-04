from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins; you can restrict it by specifying the origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)
import os
import yt_dlp

cur_dir = os.getcwd()
@app.post("/download")
def download_video(link: str = Form( ... )):
    youtube_dl_options = {
    "format": "best", # Selects the best quality available
    "outtmpl": os.path. join(cur_dir, f"Video-{link[-11:]}.mp4")
    }
    with yt_dlp.YoutubeDL(youtube_dl_options) as ydl:
        ydl.download( [link] )
    return {"status": "Download started"}

    download_video('https://youtu.be/fA5Sby2hg?si=LFnS3T0s4yLfNQeX')
