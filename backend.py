from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import yt_dlp
import requests
from typing import Dict
import asyncio

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Create and mount downloads directory
downloads_dir = os.path.join(current_dir, "downloads")
os.makedirs(downloads_dir, exist_ok=True)

# Mount the downloads directory
app.mount("/downloads", StaticFiles(directory=downloads_dir), name="downloads")

def sanitize_filename(filename: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename

# Common yt-dlp options
YDL_OPTIONS = {
    'format': 'best[height<=480]',  # Use lower quality to avoid throttling
    'quiet': False,
    'no_warnings': False,
    'ignoreerrors': True,
    'no_check_certificate': True,
    'noplaylist': True,  # Only download single video
    'extract_flat': False,
    'socket_timeout': 30,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    },
    'extractor_args': {
        'youtube': {
            'player_client': ['android'],  # Use android client to avoid some restrictions
            'skip': ['dash', 'hls']  # Skip DASH manifests and HLS to avoid some restrictions
        }
    }
}

@app.get("/", response_class=FileResponse)
async def root():
    frontend_path = os.path.join(current_dir, "frontend.html")
    if not os.path.exists(frontend_path):
        raise HTTPException(status_code=404, detail="Frontend file not found")
    return FileResponse(frontend_path)

@app.post("/video-info")
async def get_video_info(link: str = Form()):
    try:
        print(f"Fetching video info for: {link}")
        if not link:
            raise HTTPException(status_code=400, detail="Link is required")

        # Clean up the URL
        if "youtu.be" in link:
            video_id = link.split("/")[-1].split("?")[0]
        elif "youtube.com" in link:
            video_id = link.split("v=")[1].split("&")[0]
        else:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        print(f"Video ID: {video_id}")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
            
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(video_url, download=False)
                if not info:
                    raise HTTPException(status_code=400, detail="Could not fetch video info")
                
                # Return only necessary info to reduce response size
                return {
                    "title": info.get('title', 'Unknown Title'),
                    "duration": info.get('duration', 0),
                    "thumbnail": info.get('thumbnail', ''),
                    "description": info.get('description', '')
                }
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                print(f"YT-DLP error: {error_msg}")
                if "Sign in to confirm you're not a bot" in error_msg:
                    raise HTTPException(
                        status_code=400,
                        detail="Video is restricted. Try another video or update yt-dlp using: pip install -U yt-dlp"
                    )
                raise HTTPException(status_code=400, detail=f"Error fetching video info: {error_msg}")
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Error in video-info: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/download")
async def download_video(request: Request, link: str = Form()):
    try:
        print(f"Starting download for: {link}")
        if not link:
            raise HTTPException(status_code=400, detail="Link is required")

        # Clean up the URL
        if "youtu.be" in link:
            video_id = link.split("/")[-1].split("?")[0]
        elif "youtube.com" in link:
            video_id = link.split("v=")[1].split("&")[0]
        else:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        print(f"Video ID: {video_id}")
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # First get video info
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(video_url, download=False)
                if not info:
                    raise HTTPException(status_code=400, detail="Could not fetch video info")
                title = sanitize_filename(info.get('title', 'unknown'))
                print(f"Video title: {title}")
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                print(f"YT-DLP info error: {error_msg}")
                if "Sign in to confirm you're not a bot" in error_msg:
                    raise HTTPException(
                        status_code=400,
                        detail="Video is restricted. Try another video or update yt-dlp using: pip install -U yt-dlp"
                    )
                raise HTTPException(status_code=400, detail=f"Error fetching video info: {error_msg}")
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                print(f"Downloading: {d.get('_percent_str', '0%')}")
            elif d['status'] == 'finished':
                print(f"Download completed: {d['filename']}")

        # Download options
        download_opts = {
            **YDL_OPTIONS,
            'outtmpl': os.path.join(downloads_dir, f"{title}.%(ext)s"),
            'progress_hooks': [progress_hook],
            'format': 'best[height<=480]/worst',  # Fallback to worst quality if needed
            'verbose': True
        }

        print("Starting download process...")
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            try:
                error_code = ydl.download([video_url])
                if error_code != 0:
                    raise Exception("Download failed")
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                print(f"YT-DLP download error: {error_msg}")
                if "Sign in to confirm you're not a bot" in error_msg:
                    raise HTTPException(
                        status_code=400,
                        detail="Video is restricted. Try another video or update yt-dlp using: pip install -U yt-dlp"
                    )
                raise HTTPException(status_code=400, detail=f"Error downloading video: {error_msg}")
        
        # Get the downloaded file path
        downloaded_file = None
        for file in os.listdir(downloads_dir):
            if file.startswith(title):
                downloaded_file = file
                print(f"Found downloaded file: {downloaded_file}")
                break

        if not downloaded_file:
            raise HTTPException(status_code=400, detail="Download failed - file not found")

        return {
            "status": "success",
            "message": "Download completed successfully",
            "title": title,
            "filename": downloaded_file,
            "path": f"/downloads/{downloaded_file}"
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Error in download: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
